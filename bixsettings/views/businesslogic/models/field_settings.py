from django.contrib.sessions.models import Session
from commonapp.models import *
import os
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.core.mail import send_mail, BadHeaderError, EmailMessage
from django.http import HttpResponse
from django.template.loader import render_to_string
import requests
import json
import datetime
from django.contrib.auth.decorators import login_required
import time
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.db import connection, connections
from django.http import JsonResponse
from django.contrib.auth.models import Group, Permission, User, Group
from django_user_agents.utils import get_user_agent
#from bixdata_app.models import MyModel
from django import template
from bs4 import BeautifulSoup
from django.db.models import OuterRef, Subquery, Q
from ..logic_helper import *
from .database_helper import *

bixdata_server = os.environ.get('BIXDATA_SERVER')

class FieldSettings:
    settings = {
        'obbligatorio': {
            'type': 'select',
            'options': ['true', 'false'],
            'value': 'false'
        },
        'calcolato': {
            'type': 'select',
            'options': ['true', 'false'],
            'value': 'false'
        },
        'is_deadline_field': {
            'type': 'select',
            'options': ['date_deadline', 'date_start', 'frequency', 'frequency_months', 'assigned_to'],
            'value': ''
        },
        'default': {
            'type': 'parola',
            'value': ''
        },
        'label': {
            'type': 'parola',
            'value': ''
        },
        'total_sum': {
            'options': ['true', 'false'],
            'type': 'select',
            'value': 'false'
        },
        'total_avg': {
            'options': ['true', 'false'],
            'type': 'select',
            'value': 'false'
        },
        'span': {
            'type': 'select',
            'options': ['col-span-1', 'col-span-2', 'col-span-3', 'col-span-4'],
            'value': 'col-span-1'
        },
        'breakAfter': {
            'type': 'select',
            'options': ['true', 'false'],
            'value': 'false'
        },
        
    }

    def __init__(self, tableid, fieldid=None, userid=1):
        self.db_helper = DatabaseHelper('default')
        self.tableid = tableid
        self.fieldid = fieldid
        self.userid = userid
        self.settings = self.get_settings()

    def get_settings(self):
        settings_copy = {key: value.copy() for key, value in self.settings.items()}

        # Settings utente
        user_qs = SysUserFieldSettings.objects.filter(
            tableid=self.tableid,
            fieldid=self.fieldid,
            userid_id=self.userid
        ).values('settingid', 'value', 'conditions')

        # Settings admin
        admin_qs = SysUserFieldSettings.objects.filter(
            tableid=self.tableid,
            fieldid=self.fieldid,
            userid_id=1
        ).values('settingid', 'value', 'conditions')

        # Indicizza per settingid
        user_settings = {s['settingid']: s for s in user_qs}
        admin_settings = {s['settingid']: s for s in admin_qs}

        # Merge: user → admin
        merged_settings = []
        for settingid in set(admin_settings) | set(user_settings):
            if settingid in user_settings:
                merged_settings.append(user_settings[settingid])
            else:
                merged_settings.append(admin_settings[settingid])

        # Applica i valori recuperati alle impostazioni di base
        for setting in merged_settings:
            setting_id = setting['settingid']
            value = setting['value']
            if setting_id not in settings_copy:
                continue
            setting_info = settings_copy[setting_id]
            setting_info['value'] = value

            conditions = setting.get('conditions')
            if conditions:
                setting_info['conditions'] = conditions

                try:
                    valid_records, where_list = self._evaluate_conditions(conditions)
                except (json.JSONDecodeError, AttributeError):
                    valid_records = []
                    where_list = ""

                setting_info['valid_records'] = valid_records
                setting_info['where_list'] = where_list

        return settings_copy

    def _evaluate_conditions(self, conditions):
        """
        Valuta le condizioni JSON per il setting.
        Struttura JSON attesa:
        {
            "logic": "AND",
            "rules": [
                {"field": "status", "operator": "!=", "value": "vinta"},
                {"field": "userid", "operator": "=", "value": "$userid$"}
            ]
        }
        
        Ritorna:
        - lista di recordid validi per cui la condizione passa
        - le where conditions
        """
        table_name = f'user_{self.tableid}'
        logic = conditions.get("logic", "AND").upper()
        rules = conditions.get("rules", [])

        where_clauses = []

        for rule in rules:
            field = rule.get("field")
            operator = rule.get("operator")
            value = rule.get("value")

            # sostituzioni dinamiche
            if value == "$userid$":
                value = self.userid

            # Formatta correttamente il valore per SQL
            if isinstance(value, str):
                value = value.replace("'", "''")  # escape semplice
                value_str = f"'{value}'"
            else:
                value_str = str(value)

            if operator in ["=", "!=", ">", "<"]:
                where_clauses.append(f"{field} {operator} {value_str}")
            elif operator == "in":
                if isinstance(value, list):
                    value_list = ",".join([f"'{v}'" for v in value])
                    where_clauses.append(f"{field} IN ({value_list})")
            else:
                continue  # operatore non supportato

        if not where_clauses:
            return [], ""  # nessuna condizione -> nessun filtro

        # Combina con AND/OR
        sql_where = f" {logic} ".join(where_clauses)
        sql = f"SELECT recordid_ FROM {table_name} WHERE deleted_='N' AND {sql_where}"

        with connection.cursor() as cursor:
            cursor.execute(sql)
            records = [row[0] for row in cursor.fetchall()]

        return records, sql_where
    
    def get_all_settings(self):
        fields_by_table = SysField.objects.filter(
            tableid=self.tableid
        ).values_list('fieldid', flat=True)

        all_settings = {}

        for fieldid in fields_by_table:
            instance = FieldSettings(
                tableid=self.tableid,
                fieldid=fieldid,
                userid=self.userid
            )
            all_settings[fieldid] = instance.get_settings()

        return all_settings
    
    def has_permission_for_record(self, setting, recordid):
        value = setting.get("value") == "true"
        valid_records = setting.get("valid_records", [])
        has_conditions = bool(setting.get("conditions", None))

        # nessuna lista → si usa value direttamente
        if not has_conditions:
            return value

        match = str(recordid) in valid_records
        return value if match else not value

    def save(self):
        field_settings = self.settings
        success = True

        for setting, setting_data in field_settings.items():
            try:
                value = setting_data.get("value")
                conditions = setting_data.get("conditions")

                base_filters = Q(
                    tableid=self.tableid,
                    fieldid=self.fieldid,
                    settingid=setting,
                )

                cond_filter = Q()
                if conditions is None:
                    cond_filter = Q(conditions__isnull=True)
                else:
                    cond_filter = Q(conditions=conditions)

                exists_default = SysUserFieldSettings.objects.filter(
                    base_filters
                    & cond_filter
                    & Q(userid_id=1, value=value)
                ).exists()

                if exists_default:
                    if self.userid == 1:
                        continue
                    SysUserFieldSettings.objects.filter(
                        base_filters & Q(userid_id=self.userid)
                    ).delete()
                    continue

                SysUserFieldSettings.objects.update_or_create(
                    userid_id=self.userid,
                    tableid=self.tableid,
                    fieldid=self.fieldid,
                    settingid=setting,
                    defaults={
                        "value": value,
                        "conditions": conditions
                    }
                )
                print(f"Saved setting {setting}")

            except Exception as e:
                print(f"Error saving setting {setting}: {e}")
                success = False

        return success
   
    
        
        
    
 
   


