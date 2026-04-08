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
        'is_editable': {
            'type': 'select',
            'options': ['true', 'false'],
            'value': 'true'
        },
        'calcolato': {
            'type': 'select',
            'options': ['true', 'false'],
            'value': 'false'
        },
        'has_dependencies': {
            'type': 'select',
            'options': ['true', 'false'],
            'value': 'false'
        },
        'is_deadline_field': {
            'type': 'select',
            'options': ['date_deadline', 'date_start', 'frequency', 'frequency_months', 'assigned_to', 'notice_days', 'label_reference'],
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

    def _get_merged_settings(self):
        # 1. Recupero dati Gruppi e Priorità
        group_user_qs = SysGroupUser.objects.filter(userid=self.userid).exclude(disabled='Y')
        group_ids = group_user_qs.values_list('groupid', flat=True)
        sys_groups = SysGroup.objects.filter(id__in=group_ids).exclude(disabled='Y')
        
        group_data = {}
        for sg in sys_groups:
            if sg.idmanager_id:
                priority = sg.priority if sg.priority is not None else 9999
                group_data[sg.idmanager_id] = priority
                
        group_user_ids = list(group_data.keys())

        # 2. Query impostazioni per i gruppi
        group_settings_qs = SysUserFieldSettings.objects.filter(
            tableid=self.tableid,
            fieldid=self.fieldid,
            userid__in=group_user_ids
        ).values('settingid', 'value', 'conditions', 'userid')

        # 3. Gestione Conflitti Gruppi
        best_group_settings = {}
        for s in group_settings_qs:
            sid = s['settingid']
            val_lower = str(s['value']).lower()
            current_priority = group_data.get(s['userid'], 9999)
            is_bool = val_lower in ['true', 'false', '1', '0']

            s_cond = s.get('conditions')
            if isinstance(s_cond, str):
                try:
                    s_cond = json.loads(s_cond)
                except:
                    s_cond = None
            s['conditions'] = s_cond

            if sid not in best_group_settings:
                s['priority'] = current_priority
                s['source'] = 'group'
                best_group_settings[sid] = dict(s)
            else:
                existing = best_group_settings[sid]
                if is_bool:
                    is_s_true = val_lower in ['true', '1']
                    is_e_true = str(existing['value']).lower() in ['true', '1']

                    if is_e_true and not is_s_true:
                        continue
                    elif is_s_true and not is_e_true:
                        existing['value'] = 'true'
                        existing['conditions'] = s['conditions']
                        existing['priority'] = current_priority
                    elif is_s_true and is_e_true:
                        e_cond = existing.get('conditions')
                        n_cond = s['conditions']

                        if not e_cond or not n_cond:
                            existing['conditions'] = None
                            existing['priority'] = min(existing['priority'], current_priority)
                        else:
                            merged = []
                            if isinstance(e_cond, dict) and e_cond.get('is_merged'):
                                merged.extend(e_cond['conditions_list'])
                            elif e_cond:
                                merged.append(e_cond)

                            if isinstance(n_cond, dict) and n_cond.get('is_merged'):
                                merged.extend(n_cond['conditions_list'])
                            elif n_cond:
                                merged.append(n_cond)

                            existing['conditions'] = {
                                'is_merged': True,
                                'conditions_list': merged
                            }
                            existing['priority'] = min(existing['priority'], current_priority)
                else:
                    if current_priority < existing['priority']:
                        existing['value'] = s['value']
                        existing['conditions'] = s['conditions']
                        existing['priority'] = current_priority
                        existing['userid'] = s['userid']

        # 4. Settings utente
        user_qs = SysUserFieldSettings.objects.filter(
            tableid=self.tableid,
            fieldid=self.fieldid,
            userid_id=self.userid
        ).values('settingid', 'value', 'conditions')

        # 5. Settings admin
        admin_qs = SysUserFieldSettings.objects.filter(
            tableid=self.tableid,
            fieldid=self.fieldid,
            userid_id=1
        ).values('settingid', 'value', 'conditions')

        user_settings = {s['settingid']: {**s, 'source': 'user'} for s in user_qs}
        admin_settings = {s['settingid']: {**s, 'source': 'default'} for s in admin_qs}

        # 6. Merge finale (Utente > Gruppi > Admin)
        merged_settings = []
        all_ids = set(admin_settings) | set(best_group_settings) | set(user_settings)

        try:
            current_uid = int(self.userid)
        except (ValueError, TypeError):
            current_uid = self.userid

        for sid in all_ids:
            if sid in user_settings and current_uid != 1:
                merged_settings.append(user_settings[sid])
            elif sid in best_group_settings:
                s = best_group_settings[sid]
                s.pop('priority', None)
                merged_settings.append(s)
            elif sid in admin_settings:
                merged_settings.append(admin_settings[sid])

        return merged_settings

    def get_settings(self):
        settings_copy = {key: value.copy() for key, value in self.settings.items()}

        # Initialize base source and original_default
        for key, value in settings_copy.items():
            value['source'] = 'hardcoded'
            value['original_default'] = value.get('value')

        merged_settings = self._get_merged_settings()

        # Applica i valori recuperati alle impostazioni di base
        for setting in merged_settings:
            setting_id = setting['settingid']
            value = setting['value']
            if setting_id not in settings_copy:
                continue
            setting_info = settings_copy[setting_id]
            setting_info['value'] = value

            if 'source' in setting:
                setting_info['source'] = setting['source']

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
            "rules": [ ... ]
        }
        Ritorna:
        - lista di recordid validi
        - stringa SQL WHERE
        """
        if isinstance(conditions, str):
            try:
                conditions = json.loads(conditions)
            except:
                return [], ""

        if not conditions:
            return [], ""

        if conditions.get('is_merged'):
            all_records = set()
            all_where_clauses = []
            for sub_cond in conditions.get('conditions_list', []):
                if sub_cond:
                    recs, wheres = self._evaluate_conditions(sub_cond)
                    all_records.update(recs)
                    if wheres:
                        all_where_clauses.append(f"({wheres})")
            
            sql_where = " OR ".join(all_where_clauses)
            return list(all_records), sql_where

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
        return self.get_bulk_field_settings(self.tableid, self.userid)
    
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
   
    
    @classmethod
    def get_bulk_field_settings(cls, tableid, userid):
        """
        Retrieves all merged field settings for an entire table efficiently.
        Returns: { fieldid: { 'settingid': {'value': '...'} } }
        """
        # 1. Recupero dati Gruppi e Priorità
        group_user_qs = SysGroupUser.objects.filter(userid=userid).exclude(disabled='Y')
        group_ids = group_user_qs.values_list('groupid', flat=True)
        sys_groups = SysGroup.objects.filter(id__in=group_ids).exclude(disabled='Y')
        
        group_data = {}
        for sg in sys_groups:
            if sg.idmanager_id:
                priority = sg.priority if sg.priority is not None else 9999
                group_data[sg.idmanager_id] = priority
                
        group_user_ids = list(group_data.keys())

        # 2. Query impostazioni per i gruppi
        group_settings_qs = SysUserFieldSettings.objects.filter(
            tableid=tableid,
            userid__in=group_user_ids
        ).values('fieldid', 'settingid', 'value', 'conditions', 'userid')

        # 3. Gestione Conflitti Gruppi
        best_group_settings = {}
        for s in group_settings_qs:
            fid = s['fieldid']
            sid = s['settingid']
            val_lower = str(s['value']).lower()
            current_priority = group_data.get(s['userid'], 9999)
            is_bool = val_lower in ['true', 'false', '1', '0']

            if fid not in best_group_settings:
                best_group_settings[fid] = {}

            s_cond = s.get('conditions')
            if isinstance(s_cond, str):
                try:
                    s_cond = json.loads(s_cond)
                except:
                    s_cond = None
            s['conditions'] = s_cond

            if sid not in best_group_settings[fid]:
                s['priority'] = current_priority
                s['source'] = 'group'
                best_group_settings[fid][sid] = dict(s)
            else:
                existing = best_group_settings[fid][sid]
                if is_bool:
                    is_s_true = val_lower in ['true', '1']
                    is_e_true = str(existing['value']).lower() in ['true', '1']

                    if is_e_true and not is_s_true:
                        continue
                    elif is_s_true and not is_e_true:
                        existing['value'] = 'true'
                        existing['conditions'] = s['conditions']
                        existing['priority'] = current_priority
                    elif is_s_true and is_e_true:
                        e_cond = existing.get('conditions')
                        n_cond = s['conditions']

                        if not e_cond or not n_cond:
                            existing['conditions'] = None
                            existing['priority'] = min(existing['priority'], current_priority)
                        else:
                            merged = []
                            if isinstance(e_cond, dict) and e_cond.get('is_merged'):
                                merged.extend(e_cond['conditions_list'])
                            elif e_cond:
                                merged.append(e_cond)

                            if isinstance(n_cond, dict) and n_cond.get('is_merged'):
                                merged.extend(n_cond['conditions_list'])
                            elif n_cond:
                                merged.append(n_cond)

                            existing['conditions'] = {
                                'is_merged': True,
                                'conditions_list': merged
                            }
                            existing['priority'] = min(existing['priority'], current_priority)
                else:
                    if current_priority < existing['priority']:
                        existing['value'] = s['value']
                        existing['conditions'] = s['conditions']
                        existing['priority'] = current_priority
                        existing['userid'] = s['userid']

        # 4. Settings utente
        user_qs = SysUserFieldSettings.objects.filter(
            tableid=tableid,
            userid_id=userid
        ).values('fieldid', 'settingid', 'value', 'conditions')

        # 5. Settings admin
        admin_qs = SysUserFieldSettings.objects.filter(
            tableid=tableid,
            userid_id=1
        ).values('fieldid', 'settingid', 'value', 'conditions')

        user_settings = {}
        for s in user_qs:
            fid = s['fieldid']
            if fid not in user_settings:
                user_settings[fid] = {}
            user_settings[fid][s['settingid']] = {**s, 'source': 'user'}

        admin_settings = {}
        for s in admin_qs:
            fid = s['fieldid']
            if fid not in admin_settings:
                admin_settings[fid] = {}
            admin_settings[fid][s['settingid']] = {**s, 'source': 'default'}

        fields_by_table = SysField.objects.filter(
            tableid=tableid
        ).values_list('fieldid', flat=True)

        try:
            current_uid = int(userid)
        except (ValueError, TypeError):
            current_uid = userid

        all_results = {}
        for fid in fields_by_table:
            t_user = user_settings.get(fid, {})
            t_admin = admin_settings.get(fid, {})
            t_group = best_group_settings.get(fid, {})

            all_ids = set(t_admin) | set(t_group) | set(t_user)

            defaults = {}
            for k, val in cls.settings.items():
                defaults[k] = val.copy()
                defaults[k]['source'] = 'hardcoded'
                defaults[k]['original_default'] = defaults[k].get('value')
            
            merged_settings = []
            for sid in all_ids:
                if sid in t_user and current_uid != 1:
                    merged_settings.append(t_user[sid])
                elif sid in t_group:
                    s = t_group[sid]
                    s.pop('priority', None)
                    merged_settings.append(s)
                elif sid in t_admin:
                    merged_settings.append(t_admin[sid])

            temp_instance = cls.__new__(cls)
            temp_instance.tableid = tableid
            temp_instance.userid = userid
            temp_instance.fieldid = fid
            
            for ms in merged_settings:
                sid = ms['settingid']
                if sid in defaults:
                    defaults[sid]['value'] = ms['value']
                    defaults[sid]['source'] = ms.get('source', 'unknown')
                    cond = ms.get('conditions')
                    if cond:
                        defaults[sid]['conditions'] = cond
                        try:
                            recs, wheres = temp_instance._evaluate_conditions(cond)
                            defaults[sid]['valid_records'] = recs
                            defaults[sid]['where_list'] = wheres
                        except (json.JSONDecodeError, AttributeError):
                            pass
            all_results[fid] = defaults

        return all_results        
        
    
 
   


