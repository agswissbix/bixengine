from django.contrib.sessions.models import Session
from commonapp.models import *
import os
from bixsettings.views.beta import *
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
# from bixdata_app.models import MyModel
from django import template
from bs4 import BeautifulSoup
from django.db.models import OuterRef, Subquery, Q
from ..logic_helper import *
from .database_helper import *


bixdata_server = os.environ.get('BIXDATA_SERVER')


class TableSettings:
    settings = {
        'view': {
            'type': 'select',
            'options': ['true', 'false'],
            'value': 'true'
        },
        'edit': {
            'type': 'select',
            'options': ['true', 'false'],
            'value': 'true'
        },
        'risultati_edit': {
            'type': 'select',
            'options': ['true', 'false'],
            'value': 'false'
        },
        'autosave': {
            'type': 'select',
            'options': ['true', 'false'],
            'value': 'true'
        },
        'delete': {
            'type': 'select',
            'options': ['true', 'false'],
            'value': 'true'
        },
        'hidden': {
            'type': 'select',
            'options': ['true', 'false'],
            'value': 'false'
        },
        'menu': {
            'type': 'select',
            'options': ['true', 'false'],
            'value': 'false'
        },
        'icon_type': {
            'type': 'select',
            'options': ['fontawesome', 'material'],
            'value': 'fontawesome'
        },
        'icon': {
            'type': 'parola',
            'value': 'database'
        },
        'customview_list': {
            'type': 'select',
            'options': ['true', 'false'],
            'value': 'false'
        },
        'customview_card': {
            'type': 'select',
            'options': ['true', 'false'],
            'value': 'false'
        },
        'scheda_layout': {
            'type': 'select',
            'options': ['standard_dati', 'standard_allegati', 'allargata'],
            'value': 'standard_dati'
        },
        'scheda_mostratutti': {
            'type': 'select',
            'options': ['true', 'false'],
            'value': 'false'
        },
        'card_tabs': {
            'type': 'multiselect',
            #here options should be a list of name and selected = true or false
            'options': [
                {'name': 'Campi', 'selected': True},
                {'name': 'Collegati', 'selected': True},
                {'name': 'Allegati', 'selected': True},
                {'name': 'Analitica', 'selected': True},
                {'name': 'Storico', 'selected': True},
                {'name': 'Steps', 'selected': True},
                {'name': 'Checklist', 'selected': True},
            ],
            'value': 'Campi, Collegati'
        },
        "card_default_size": {
            "type": "select",
            "options": ["min", "max"],
            "value": "min"
        },
        "card_min_size": {
            "type": "parola",
            "value": "w-2/6"
        },
        'scheda_active_tab': {
            'type': 'select',
            'options': ['Campi', 'Collegati', 'Allegati', 'Analitica', 'Storico','Custom'],
            'value': 'fields'
        },
        'table_tabs': {
            'type': 'multiselect',
            #here options should be a list of name and selected = true or false
            'options': [
                {'name': 'Tabella', 'selected': True},
                {'name': 'Kanban', 'selected': True},
                {'name': 'Pivot', 'selected': True},
                {'name': 'Calendario', 'selected': True},
                {'name': 'MatrixCalendar', 'selected': True},
                {'name': 'Planner', 'selected': True},
                {'name': 'Gallery', 'selected': True},
            ],
            'value': 'Tabella'
        },
        'table_active_tab': {
            'type': 'select',
            'options': ['Tabella', 'Kanban', 'Pivot', 'Calendario','MatrixCalendar', 'Planner' , 'Gallery'],
            'value': 'Tabella'
        },
        'table_planner_resource_field': {
            'type': 'select',
            'options': [],
            'value': ''
        },
        'table_planner_color_field': {
            'type': 'select',
            'options': [],
            'value': ''
        },
        'table_planner_title_field': {
            'type': 'select',
            'options': [],
            'value': ''
        },
        'table_planner_date_from_field': {
            'type': 'select',
            'options': [],
            'value': ''
        },
        'table_planner_date_to_field': {
            'type': 'select',
            'options': [],
            'value': ''
        },
        'table_planner_time_from_field': {
            'type': 'select',
            'options': [],
            'value': ''
        },
        'table_planner_time_to_field': {
            'type': 'select',
            'options': [],
            'value': ''
        },
        'table_planner_default_view': {
            'type': 'select',
            'options': ['day', 'week', 'month'],
            'value': 'week'
        },
        'popup_layout': {
            'type': 'select',
            'options': ['standard_dati', 'standard_allegati', 'allargata'],
            'value': 'standard_dati'
        },
        'popup_width': {
            'type': 'select',
            'options': ['30', '60', '90'],
            'value': '60'
        },
        'scheda_record_width': {
            'type': 'select',
            'options': ['25', '42', '48', '57', '98'],
            'value': '25'
        },
        'allargata_dati_width': {
            'type': 'parola',
            'value': '50'
        },
        'scheda_ricerca_display': {
            'type': 'select',
            'options': ['true', 'false'],
            'value': 'true'
        },
        'scheda_ricerca_width': {
            'type': 'select',
            'options': ['20', '42', ''],
            'value': '20'
        },
        'scheda_ricerca_default': {
            'type': 'select',
            'options': ['filtri', 'ricerche_salvate'],
            'value': 'filtri'
        },
        'ricerca_lockedview': {
            'type': 'select',
            'options': ['true', 'false'],
            'value': 'false'
        },
        'risultati_limit': {
            'type': 'parola',
            'value': '50'
        },
        'risultati_layout': {
            'type': 'select',
            'options': ['righe', 'table', 'preview', 'badge', 'report', 'calendar'],
            'value': 'righe'
        },
        'risultati_width': {
            'type': 'select',
            'options': ['42', '48', '57', '98'],
            'value': '57'
        },
        'risultati_border': {
            'type': 'select',
            'options': ['1px solid transparent', '1px solid #dedede'],
            'value': '1px solid transparent'
        },
        'risultati_font_size': {
            'type': 'select',
            'options': ['6', '8', '10', '12', '14', '16', '18'],
            'value': '14'
        },
        'risultati_open': {
            'type': 'select',
            'options': ['right', 'down', 'popup'],
            'value': 'right'
        },
        'risultati_new': {
            'type': 'select',
            'options': ['right', 'down', 'popup'],
            'value': 'right'
        },
        'risultati_order': {
            'type': 'select',
            'options': ['asc', 'desc', ''],
            'value': 'desc'
        },
        'risultati_showreport': {
            'type': 'select',
            'options': ['true', 'false', ''],
            'value': 'false'
        },
        'risultati_showcalendar': {
            'type': 'select',
            'options': ['true', 'false', ''],
            'value': 'false'
        },
        'risultati_anteprima_aspectratio': {
            'type': 'select',
            'options': ['2:3', '3:2', '16:9'],
            'value': '2:3'
        },
        'risultati_stampa_elenco_orientamento': {
            'type': 'select',
            'options': ['portrait', 'landscape', ''],
            'value': 'portrait'
        },
        'linked_layout': {
            'type': 'select',
            'options': ['righe', 'preview', 'badge'],
            'value': 'righe'
        },
        'linked_open': {
            'type': 'select',
            'options': ['right', 'down', 'popup'],
            'value': 'down'
        },
        'linked_new': {
            'type': 'select',
            'options': ['right', 'down', 'popup'],
            'value': 'popup'
        },
        'linked_rows': {
            'type': 'select',
            'options': ['5', '10', '15', '20', '25', '30'],
            'value': '5'
        },
        'linked_label_opened': {
            'type': 'select',
            'options': ['true', 'false'],
            'value': 'false'
        },
        'pages_display': {
            'type': 'select',
            'options': ['true', 'false'],
            'value': 'true'
        },
        'pages_fileupload_display': {
            'type': 'select',
            'options': ['true', 'false'],
            'value': 'true'
        },
        'pages_view': {
            'type': 'select',
            'options': ['thumbnail', 'name', 'detail'],
            'value': 'thumbnail'
        },
        'pages_scheda_layout': {
            'type': 'select',
            'options': ['list', 'grid', 'hidden'],
            'value': 'list'
        },
        'pages_popup_layout': {
            'type': 'select',
            'options': ['list', 'grid', 'hidden'],
            'value': 'list'
        },
        'pages_thumbnail_show': {
            'type': 'select',
            'options': ['true', 'false', ''],
            'value': 'true'
        },
        'default_orderby': {
            'type': 'select',
            'options': [],
            'value': 'recordid'
        },
        'default_save': {
            'type': 'select',
            'options': ['salva', 'salva e chiudi', 'salva e nuovo', 'salva e nuovo-salva e chiudi',
                        'allega salva e nuovo', 'salva e ripeti'],
            'value': 'salva'
        },
        'default_viewid': {
            'type': 'select',
            'options': [],
            'value': 'true'
        },
        'default_recordstab': {
            'type': 'parola',
            'value': 'Tabella'
        },
        'default_recordtab': {
            'type': 'parola',
            'value': 'Fields'
        },
        'dem_mail_field': {
            'type': 'select',
            'options': ['address', 'bexio_contact_type_id', 'bexio_status', 'cap', 'city', 'companyname',
                        'customertype', 'email', 'ictpbx_price', 'id', 'id_bexio', 'id_vte', 'note', 'paymentstatus',
                        'phonenumber', 'recordidcontact_', 'recordiddealline_', 'recordiddeal_', 'recordidinvoiceline_',
                        'recordidinvoice_', 'recordidprojectmilestone_', 'recordidproject_', 'recordidsalesorderline_',
                        'recordidsalesorderplannedinvoice', 'recordidsalesorder_', 'recordidserviceandasset_',
                        'recordidservicecontract_', 'recordidtask_', 'recordidticket_', 'recordidtimesheet_',
                        'recordiduser_log_', 'recordid_jdoc', 'salesperson_text', 'salesuser', 'scn', 'sector',
                        'servizitxt', 'state', 'status', 'sw_price', 'tipo', 'travelkm_price', 'travel_price',
                        'vatnumber', 'website'],
            'value': 'address'
        },
        'fields_autoscroll': {
            'type': 'select',
            'options': ['true', 'false'],
            'value': 'false'
        },
        'col_s': {
            'type': 'parola',
            'value': '3'
        },
        'col_m': {
            'type': 'parola',
            'value': '3'
        },
        'col_l': {
            'type': 'parola',
            'value': '3'
        },
        'workspace': {
            'type': 'select',
            'options': [],
            'value': ''
        }
    }

    def __init__(self, tableid, userid=1):
        self.db_helper = DatabaseHelper('default')
        self.tableid = tableid
        self.userid = userid
        self.settings = self.get_settings()

    def get_settings(self):
        # Copia profonda delle impostazioni
        settings_copy = {key: value.copy() for key, value in self.settings.items()}

        self._populate_field_options(settings_copy)

        self._populate_workspace_options(settings_copy)

        user_settings_qs = SysUserTableSettings.objects.filter(
            tableid=self.tableid,
            userid=self.userid
        ).values('settingid', 'value', 'conditions')

        # Settings del defaultuser (admin)
        admin_settings_qs = SysUserTableSettings.objects.filter(
            tableid=self.tableid,
            userid=1
        ).values('settingid', 'value', 'conditions')

        # Indicizza per settingid
        user_settings = {
            s['settingid']: s for s in user_settings_qs
        }

        admin_settings = {
            s['settingid']: s for s in admin_settings_qs
        }

        # Merge: user → admin
        merged_settings = []
        for settingid in set(admin_settings) | set(user_settings):
            if settingid in user_settings:
                merged_settings.append(user_settings[settingid])
            else:
                merged_settings.append(admin_settings[settingid])

        self._apply_user_settings(settings_copy, merged_settings)

        return settings_copy

    def _populate_workspace_options(self, settings_copy):
        """Popola le opzioni del workspace nei settings."""
        workspaces = SysTableWorkspace.objects.all()
        if not workspaces:
            return

        workspace_options = [
            {'name': str(workspace.name)}
            for workspace in workspaces
        ]

        settings_copy['workspace']['options'] = workspace_options

        table_workspace = SysTable.objects.filter(id=self.tableid).values('workspace').first()
        settings_copy['workspace']['value'] = table_workspace['workspace'] if table_workspace else ''
        # Imposta il valore di default se non è già impostato
        if workspace_options and settings_copy['workspace']['value'] == '':
            settings_copy['workspace']['value'] = workspace_options[0]['name']


    def _populate_field_options(self, settings_copy):
        """Popola le opzioni dei campi planner e orderby nei settings."""
        fields = SysField.objects.filter(tableid=self.tableid).all()
        if not fields:
            return

        date_options = []
        time_options = []
        all_fields_options = []

        for field in fields:
            field_id_str = str(field.fieldid)
            all_fields_options.append(field_id_str)

            if field.fieldtypewebid == 'Data':
                date_options.append(field_id_str)
            elif field.fieldtypewebid == 'Ora':
                time_options.append(field_id_str)

        # Mapping delle opzioni ai settings
        field_option_mappings = {
            'all_fields': [
                'default_orderby',
                'table_planner_title_field',
                'table_planner_color_field',
                'table_planner_resource_field'
            ],
            'date_fields': [
                'table_planner_date_from_field',
                'table_planner_date_to_field'
            ],
            'time_fields': [
                'table_planner_time_from_field',
                'table_planner_time_to_field'
            ]
        }

        option_mapping = {
            'all_fields': all_fields_options,
            'date_fields': date_options,
            'time_fields': time_options
        }

        # Imposta le opzioni e i valori di default
        for field_type, setting_keys in field_option_mappings.items():
            options = option_mapping[field_type]
            for setting_key in setting_keys:
                settings_copy[setting_key]['options'] = options
                if options and settings_copy[setting_key]['value'] == '':
                    settings_copy[setting_key]['value'] = options[0]


    def _apply_user_settings(self, settings_copy, user_settings):
        """Applica i valori delle impostazioni utente ai settings."""
        for row in user_settings:
            setting_id = row['settingid']
            if setting_id not in settings_copy:
                continue

            setting_info = settings_copy[setting_id]

            if setting_info['type'] == 'multiselect':
                selected_values = row['value'].split(',') if row['value'] else []
                setting_info['value'] = selected_values
                for opt in setting_info['options']:
                    opt['selected'] = str(opt['name']) in selected_values
            else:
                setting_info['value'] = row['value']

            # Valuta condizioni
            conditions = row.get('conditions')
            if conditions:
                setting_info['conditions'] = conditions

                try:
                    valid_records, where_list = self._evaluate_conditions(conditions)
                except (json.JSONDecodeError, AttributeError):
                    valid_records = []
                    where_list = ""

                setting_info['valid_records'] = valid_records
                setting_info['where_list'] = where_list

            # Caso speciale per default_viewid
            if setting_id == 'default_viewid':
                self._populate_default_view_options(setting_info)

    def _populate_default_view_options(self, setting_info):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM sys_view WHERE tableid = %s",
                [self.tableid]
            )
            view_options = dictfetchall(cursor)

        setting_info['options'] = [
            {'name': str(opt['name']), 'id': str(opt['id'])}
            for opt in view_options
        ]

        if not view_options:
            setting_info['value'] = '0'

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
            return []  # nessuna condizione -> nessun filtro

        # Combina con AND/OR
        sql_where = f" {logic} ".join(where_clauses)
        sql = f"SELECT recordid_ FROM {table_name} WHERE deleted_='N' AND {sql_where}"

        with connection.cursor() as cursor:
            cursor.execute(sql)
            records = [row[0] for row in cursor.fetchall()]

        return records, sql_where

    def get_specific_settings(self, settingids):
        """
        Restituisce solo i settingids richiesti, caricando esclusivamente
        i valori necessari e applicando eventuali user overrides.
        
        settingids: int/str o lista di int/str
        """

        # Normalizza la lista
        if not isinstance(settingids, (list, tuple)):
            settingids = [settingids]

        # Filtra solo i setting richiesti dalla configurazione base
        base_settings = {
            key: value.copy()
            for key, value in self.settings.items()
            if key in settingids
        }

        if not base_settings:
            return {}

        # Applica solo le popolate necessarie
        # Evita le due chiamate globali se non servono
        if any("field_options" in v for v in base_settings.values()):
            self._populate_field_options(base_settings)

        if any("workspace_options" in v for v in base_settings.values()):
            self._populate_workspace_options(base_settings)

        # Carica SOLO gli user settings necessari (non tutti!)
        user_settings = SysUserTableSettings.objects.filter(
            tableid=self.tableid,
            userid=self.userid,
            settingid__in=settingids
        ).values('settingid', 'value')

        # Fallback su admin solo per quelli richiesti
        if not user_settings.exists():
            user_settings = SysUserTableSettings.objects.filter(
                tableid=self.tableid,
                userid=1,
                settingid__in=settingids
            ).values('settingid', 'value')

        # Applica solo le impostazioni richieste
        self._apply_user_settings(base_settings, user_settings)

        return base_settings
    
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
        table_settings = self.settings
        success = True

        for setting, setting_data in table_settings.items():

            if setting == 'workspace':
                SysTable.objects.filter(id=self.tableid).update(
                    workspace=table_settings[setting]['value']
                )
                continue

            try:
                value = setting_data.get("value")
                conditions = setting_data.get("conditions")

                base_filters = Q(
                    tableid_id=self.tableid,
                    settingid=setting,
                )

                cond_filter = Q()
                if conditions is None:
                    cond_filter = Q(conditions__isnull=True)
                else:
                    cond_filter = Q(conditions=conditions)

                is_equal_to_default = SysUserTableSettings.objects.filter(
                    base_filters 
                    & cond_filter
                    & Q(userid_id=1, value=value)
                ).exists()

                if is_equal_to_default:
                    if self.userid == 1:
                        continue
                    SysUserTableSettings.objects.filter(
                        base_filters & Q(userid_id=self.userid)
                    ).delete()
                else:
                    SysUserTableSettings.objects.update_or_create(
                        userid_id=self.userid,
                        tableid_id=self.tableid,
                        settingid=setting,
                        defaults={
                            "value": value,
                            "conditions": conditions
                        }
                    )
            except Exception as e:
                print(f"Error saving setting {setting}: {e}")
                success = False

        return success
