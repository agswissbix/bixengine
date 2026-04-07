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
        'add': {
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
        'duplicate': {
            'type': 'select',
            'options': ['true', 'false'],
            'value': 'true'
        },
        'add_linked': {
            'type': 'select',
            'options': ['true', 'false'],
            'value': 'true'
        },
        'edit_linked': {
            'type': 'select',
            'options': ['true', 'false'],
            'value': 'true'
        },
        'duplicate_with_linked': {
            'type': 'multiselect',
            'options': [],
            'value': ''
        },
        'deadline_actions': {
            'type': 'parola',
            'value': ''
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
            'value': 'Campi,Collegati'
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
                {'name': 'Report', 'selected': True},
                {'name': 'Kanban', 'selected': True},
                {'name': 'Pivot', 'selected': True},
                {'name': 'Calendario', 'selected': True},
                {'name': 'Gallery', 'selected': True},
                {'name': 'TabellaRaggruppata', 'selected': True},
                {'name': 'Custom', 'selected': False},
            ],
            'value': 'Tabella'
        },
        'table_active_tab': {
            'type': 'select',
            'options': ['Tabella', 'Report', 'Kanban', 'Pivot', 'Calendario','MatrixCalendar', 'Planner' , 'Gallery', 'TabellaRaggruppata', 'Custom'],
            'value': 'Tabella'
        },
        "table_custom_tab_name": {
            "type": "parola",
            "value": "Custom"
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
        'table_planner_duration_field': {
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

    def _get_merged_settings(self, settingids=None):
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
        group_settings_qs = SysUserTableSettings.objects.filter(
            tableid=self.tableid,
            userid__in=group_user_ids
        )
        if settingids:
            group_settings_qs = group_settings_qs.filter(settingid__in=settingids)
        group_settings_qs = group_settings_qs.values('settingid', 'value', 'conditions', 'userid')

        # 3. Gestione Conflitti Gruppi
        best_group_settings = {}
        for s in group_settings_qs:
            sid = s['settingid']
            val_lower = str(s['value']).lower()
            current_priority = group_data.get(s['userid'], 9999)
            is_bool = val_lower in ['true', 'false', '1', '0']

            # Gestione parsing conditions per il mix
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
                        # Existing is true, new is false -> Ignore new
                        continue
                    elif is_s_true and not is_e_true:
                        # Existing is false, new is true -> Take new
                        existing['value'] = 'true'
                        existing['conditions'] = s['conditions']
                        existing['priority'] = current_priority
                    elif is_s_true and is_e_true:
                        # Both are true.
                        e_cond = existing.get('conditions')
                        n_cond = s['conditions']

                        if not e_cond or not n_cond:
                            # A true without conditions overrides everything and becomes absolute true
                            existing['conditions'] = None
                            existing['priority'] = min(existing['priority'], current_priority)
                        else:
                            # Both have conditions -> We must merge them with OR
                            merged = []
                            # Unpack existing merged conditions if it exists
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

        # 4. Query User e Admin
        user_settings_qs = SysUserTableSettings.objects.filter(
            tableid=self.tableid, 
            userid=self.userid
        )
        admin_settings_qs = SysUserTableSettings.objects.filter(
            tableid=self.tableid, 
            userid=1
        )
        
        if settingids:
            user_settings_qs = user_settings_qs.filter(settingid__in=settingids)
            admin_settings_qs = admin_settings_qs.filter(settingid__in=settingids)

        user_settings_qs = user_settings_qs.values('settingid', 'value', 'conditions', 'userid')
        admin_settings_qs = admin_settings_qs.values('settingid', 'value', 'conditions', 'userid')

        user_settings = {s['settingid']: {**s, 'source': 'user'} for s in user_settings_qs}
        admin_settings = {s['settingid']: {**s, 'source': 'default'} for s in admin_settings_qs}

        # 5. Merge finale (Utente > Gruppi > Admin)
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

    def get_settings(self, with_option=False):
        # Copia profonda delle impostazioni
        settings_copy = {key: value.copy() for key, value in self.settings.items()}

        if with_option:
            self._populate_field_options(settings_copy)
            self._populate_workspace_options(settings_copy)
            self._populate_linked_table_options(settings_copy)

        # Initialize base source and original_default
        for key, value in settings_copy.items():
            value['source'] = 'hardcoded'
            value['original_default'] = value.get('value')

        merged_settings = self._get_merged_settings()
        self._apply_user_settings(settings_copy, merged_settings)

        return settings_copy

    def _populate_linked_table_options(self, settings_copy):
        """Popola le opzioni delle tabelle collegate per il setting duplicate_with_linked."""
        from commonapp.bixmodels.user_record import UserRecord
        user_record = UserRecord(self.tableid, userid=self.userid)
        linked_tables = user_record.get_linked_tables()
        if not linked_tables:
            settings_copy['duplicate_with_linked']['options'] = []
            return

        options = [
            {'name': str(table['tableid']), 'label': str(table['description']), 'selected': False}
            for table in linked_tables
        ]
        settings_copy['duplicate_with_linked']['options'] = options

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
                'table_planner_resource_field',
                'table_planner_duration_field'
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

            if 'source' in row:
                setting_info['source'] = row['source']

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
        if any("field_options" in v for v in base_settings.values()):
            self._populate_field_options(base_settings)

        if any("workspace_options" in v for v in base_settings.values()):
            self._populate_workspace_options(base_settings)
            
        if "duplicate_with_linked" in base_settings:
            self._populate_linked_table_options(base_settings)

        # Merge usando il nuovo metodo globale
        merged_settings = self._get_merged_settings(settingids)

        # Applica
        self._apply_user_settings(base_settings, merged_settings)

        return base_settings
    
    def has_permission_for_record(self, setting, recordid=None):
        value = setting.get("value") == "true"
        valid_records = setting.get("valid_records", [])
        has_conditions = bool(setting.get("conditions", None))

        # nessuna lista → si usa value direttamente
        if not has_conditions or recordid is None:
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

    @classmethod
    def get_bulk_specific_settings(cls, tableids, userid, settingids=None):
        """
        Retrieves merged settings for multiple tables efficiently.
        Returns: { tableid: { settingid: {'value': '...'} } }
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
        group_settings_qs = SysUserTableSettings.objects.filter(
            tableid__in=tableids,
            userid__in=group_user_ids
        )
        if settingids:
            if isinstance(settingids, str):
                settingids = [settingids]
            group_settings_qs = group_settings_qs.filter(settingid__in=settingids)
        group_settings_qs = group_settings_qs.values('tableid', 'settingid', 'value', 'conditions', 'userid')

        # 3. Gestione Conflitti Gruppi
        best_group_settings = {}
        for s in group_settings_qs:
            tid = s['tableid']
            sid = s['settingid']
            val_lower = str(s['value']).lower()
            current_priority = group_data.get(s['userid'], 9999)
            is_bool = val_lower in ['true', 'false', '1', '0']

            if tid not in best_group_settings:
                best_group_settings[tid] = {}

            # Parsing conditions
            s_cond = s.get('conditions')
            if isinstance(s_cond, str):
                try:
                    s_cond = json.loads(s_cond)
                except:
                    s_cond = None
            s['conditions'] = s_cond

            if sid not in best_group_settings[tid]:
                s['priority'] = current_priority
                s['source'] = 'group'
                best_group_settings[tid][sid] = dict(s)
            else:
                existing = best_group_settings[tid][sid]
                
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

        # 4. Query User e Admin
        user_settings_qs = SysUserTableSettings.objects.filter(
            tableid__in=tableids, 
            userid=userid
        )
        admin_settings_qs = SysUserTableSettings.objects.filter(
            tableid__in=tableids, 
            userid=1
        )
        if settingids:
            user_settings_qs = user_settings_qs.filter(settingid__in=settingids)
            admin_settings_qs = admin_settings_qs.filter(settingid__in=settingids)

        user_settings_qs = user_settings_qs.values('tableid', 'settingid', 'value', 'conditions', 'userid')
        admin_settings_qs = admin_settings_qs.values('tableid', 'settingid', 'value', 'conditions', 'userid')

        user_settings = {}
        for s in user_settings_qs:
            tid = s['tableid']
            if tid not in user_settings:
                user_settings[tid] = {}
            user_settings[tid][s['settingid']] = {**s, 'source': 'user'}

        admin_settings = {}
        for s in admin_settings_qs:
            tid = s['tableid']
            if tid not in admin_settings:
                admin_settings[tid] = {}
            admin_settings[tid][s['settingid']] = {**s, 'source': 'default'}

        # 5. Merge finale per tutte le tabelle (Utente > Gruppi > Admin)
        try:
            current_uid = int(userid)
        except (ValueError, TypeError):
            current_uid = userid

        if settingids and isinstance(settingids, str):
            settingids = [settingids]

        result = {}
        for tid in tableids:
            result[tid] = {}
            
            t_user = user_settings.get(tid, {})
            t_admin = admin_settings.get(tid, {})
            t_group = best_group_settings.get(tid, {})

            all_ids = set(t_admin) | set(t_group) | set(t_user)

            if settingids:
                keys_to_process = settingids
            else:
                keys_to_process = cls.settings.keys()

            defaults = {}
            for k in keys_to_process:
                if k in cls.settings:
                    defaults[k] = cls.settings[k].copy()
                    defaults[k]['source'] = 'hardcoded'
                    defaults[k]['original_default'] = defaults[k].get('value')
                    result[tid][k] = defaults[k]

            merged_settings = []
            for sid in all_ids:
                if settingids and sid not in settingids:
                    continue
                if sid in t_user and current_uid != 1:
                    merged_settings.append(t_user[sid])
                elif sid in t_group:
                    s = t_group[sid]
                    s.pop('priority', None)
                    merged_settings.append(s)
                elif sid in t_admin:
                    merged_settings.append(t_admin[sid])

            for ms in merged_settings:
                sid = ms['settingid']
                if sid in result[tid]:
                    result[tid][sid]['value'] = ms['value']
                    result[tid][sid]['source'] = ms.get('source', 'unknown')
                    cond = ms.get('conditions')
                    if cond:
                        result[tid][sid]['conditions'] = cond

        return result