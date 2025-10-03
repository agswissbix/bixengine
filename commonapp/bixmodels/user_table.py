from django.contrib.sessions.models import Session


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
import os
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.db import connection, connections
from django.http import JsonResponse
from django.contrib.auth.models import Group, Permission, User, Group
from django_user_agents.utils import get_user_agent
#from bixdata_app.models import MyModel
from django import template
from bs4 import BeautifulSoup
from django.db.models import OuterRef, Subquery
from commonapp.bixmodels.helper_db import *
from commonapp.bixmodels.user_record import *
from commonapp.helper import *
from collections import defaultdict


bixdata_server = os.environ.get('BIXDATA_SERVER')

class UserTable:
    
    def __init__(self,tableid,userid=1):
        self.tableid=tableid
        self.userid=userid
        self.context=''
        self._fields_definitions = None
        self._results_columns = None # Cache per le colonne dei risultati
        self._total_records_count = None

    def get_total_records_count(self):
        return self._total_records_count

    @timing_decorator
    def get_table_records(self,viewid='',searchTerm='', conditions_list=None,fields=None,offset=0,limit=None,orderby='recordid_ desc'):
        if conditions_list is None:
            conditions_list = []
        columns = self.get_results_columns()
        fields=[]
        for column in columns:
            fields.append(column['fieldid'])
        records = self.get_records(viewid,searchTerm,conditions_list,fields,offset,limit,orderby,columns)
        return records
    
    @timing_decorator
    def get_table_records_obj(self, viewid='', searchTerm='', conditions_list=None, fields=None, offset=0, limit=None, orderby='recordid_ desc', master_tableid=None, master_recordid=None, filters_list=None):
        """
        Recupera i record e le loro proprietà come lista di oggetti UserRecord ottimizzata.
        ORA gestisce anche l'eager loading dei dati collegati e i filtri da frontend.
        """
        print(f"filters_list: {filters_list}")
        if conditions_list is None:
            conditions_list = []
        if filters_list is None:
            filters_list = []
        
        # --- NUOVO: Processa la lista dei filtri dal frontend ---
        for filter_item in filters_list:
            field_id = filter_item.get('fieldid')
            filter_type = filter_item.get('type')
            filter_value = filter_item.get('value')
            
            if not field_id or not filter_value:
                continue
                
            if filter_type in ['lookup', 'Utente']:
                filter_values = json.loads(filter_value)
                
                if isinstance(filter_values, list) and filter_values:
                    conditions = []
                    for id in filter_values:
                        if str(id):
                            conditions.append(f"{field_id}='{id}'")
                    if conditions:
                        conditions_list.append(f"({' OR '.join(conditions)})")
            elif filter_type in ['Parola', 'Text']:
                # La stringa è già il valore da usare per la clausola LIKE.
                # NOTA: Usiamo LIKE per una ricerca più flessibile, ma possiamo anche usare '=' per "Valore esatto".
                # Per ora, come richiesto, ci concentriamo su 'Valore esatto'
                # Utilizziamo `LIKE` con i caratteri jolly `%` per una ricerca più ampia.
                # Se la condizione fosse 'Valore esatto', l'operatore sarebbe '='. Per ora, gestiamo solo il valore.
                
                values = filter_value.split('|')

                if len(values) > 0:
                    like_conditions = []
                    for val in values:
                        sanitized_val = val.replace("'", "''") 
                        like_conditions.append(f"{field_id} LIKE '%{sanitized_val}%'")
                    conditions_list.append(f"({' OR '.join(like_conditions)})")
                
            # Gestione del tipo 'Numero'
            elif filter_type == 'Numero':
                try:
                    # Il valore è un JSON che contiene i range. Es: '[{"min":"2","max":"3"},{"min":"4","max":"7"}]'
                    ranges = json.loads(filter_value)
                    range_conditions = []
                    for r in ranges:
                        min_val = r.get('min', '').strip()
                        max_val = r.get('max', '').strip()
                        if min_val and max_val:
                            range_conditions.append(f"({field_id} BETWEEN {min_val} AND {max_val})")
                        elif min_val:
                            range_conditions.append(f"({field_id} >= {min_val})")
                        elif max_val:
                            range_conditions.append(f"({field_id} <= {max_val})")
                    
                    if range_conditions:
                        conditions_list.append(f"({' OR '.join(range_conditions)})")

                except (json.JSONDecodeError, ValueError):
                    print(f"Errore di decodifica JSON o valore non valido per il filtro numerico {field_id}: {filter_value}")
                    continue

            # Gestione del tipo 'Data'
            elif filter_type == 'Data':
                try:
                    # Il valore è un JSON che contiene i range di date. Es: '[{"from":"2025-09-18","to":"2025-09-25"}]'
                    ranges = json.loads(filter_value)
                    range_conditions = []
                    for r in ranges:
                        from_date = r.get('from', '').strip()
                        to_date = r.get('to', '').strip()
                        if from_date and to_date:
                            range_conditions.append(f"({field_id} BETWEEN '{from_date}' AND '{to_date}')")
                        elif from_date:
                            range_conditions.append(f"({field_id} >= '{from_date}')")
                        elif to_date:
                            range_conditions.append(f"({field_id} <= '{to_date}')")
                    
                    if range_conditions:
                        conditions_list.append(f"({' OR '.join(range_conditions)})")

                except (json.JSONDecodeError, ValueError):
                    print(f"Errore di decodifica JSON o valore non valido per il filtro data {field_id}: {filter_value}")
                    continue
        
        # --- Fine del blocco di gestione filtri ---

        # Aggiunge le condizioni master-record se presenti
        if master_tableid and master_recordid:
            conditions_list.append(f"recordid{master_tableid}_='{master_recordid}'")

        field_definitions = self._get_fields_definitions()
        columns_for_search = self.get_results_columns() 

        raw_records_data = self.get_records(
            viewid=viewid, searchTerm=searchTerm, conditions_list=conditions_list,
            fields=fields, offset=offset, limit=limit, orderby=orderby,
            columns=columns_for_search
        )
        
        if not raw_records_data:
            return []

        # --- LOGICA DI EAGER LOADING SPOSTATA QUI DALLA VISTA (invariata) ---
        ids_to_fetch = defaultdict(set)
        all_field_defs = self._get_fields_definitions().values()

        for column in all_field_defs:
            fieldid = column.get('fieldid')
            
            if column.get('fieldtypeid') == 'Utente':
                for record_data in raw_records_data:
                    id = record_data.get(fieldid)
                    if id:
                        ids_to_fetch['sys_user'].add(id)

            elif column.get('keyfieldlink') and column.get('tablelink'):
                table_link = column.get('tablelink')
                linked_record_id_field = column.get('fieldid')
                for record_data in raw_records_data:
                    record_link_id = record_data.get(linked_record_id_field)
                    if record_link_id:
                        ids_to_fetch[table_link].add(record_link_id)

        fetched_data_maps = defaultdict(dict)
        
        if 'sys_user' in ids_to_fetch:
            user_ids_list = list(ids_to_fetch['sys_user'])
            users = HelpderDB.sql_query(f"SELECT id, firstname, lastname FROM sys_user WHERE id IN ({','.join(map(str, user_ids_list))})")
            fetched_data_maps['sys_user'] = {u['id']: f"{u.get('firstname', '')} {u.get('lastname', '')}".strip() for u in users}

        for table_link, record_ids_set in ids_to_fetch.items():
            if table_link == 'sys_user': continue
            record_ids_list = list(record_ids_set)
            keyfield = next((c['keyfieldlink'] for c in all_field_defs if c.get('tablelink') == table_link), None)
            
            if keyfield and record_ids_list:
                linked_records = HelpderDB.get_linked_records_by_ids(table_link, keyfield, record_ids_list)
                fetched_data_maps[table_link] = {r['recordid_']: r.get(keyfield) for r in linked_records}

        # --- Crea istanze UserRecord (invariato) ---
        records_obj_list = []
        for raw_record in raw_records_data:
            record_id = raw_record.get('recordid_')
            if not record_id:
                continue
            prefetched_data_for_record = {
                'values': raw_record,
                'fields_definitions': field_definitions,
                'eager_loaded_data': fetched_data_maps
            }
            try:
                record_instance = UserRecord(
                    tableid=self.tableid,
                    recordid=record_id,
                    userid=self.userid,
                    _prefetched_data=prefetched_data_for_record
                )
                records_obj_list.append(record_instance)
            except Exception as e:
                print(f"Errore durante la creazione dell'istanza UserRecord per {record_id}: {e}")

        return records_obj_list
    
    @timing_decorator
    def get_pivot_records(self,viewid='',searchTerm='', conditions_list=None,fields=None,offset=0,limit=None,orderby='recordid_ desc'):
        if conditions_list is None:
            conditions_list = []
        sql=f"""
            SELECT *
            FROM sys_field
            WHERE 
            tableid = '{self.tableid}'
            """
        columns=HelpderDB.sql_query(sql)

        fields=[]
        for column in columns:
            fields.append(column['fieldid'])
        records = self.get_records(viewid,searchTerm,conditions_list,fields,offset,limit,orderby,columns)
        return records
    
    @timing_decorator
    def get_records(self, viewid='', searchTerm='', conditions_list=None, fields=None, offset=0, limit=None, orderby='recordid_ desc', columns=None):
        """
        Ottieni elenco record in base ai parametri di ricerca.
        Versione migliorata per gestire filtri complessi e JOIN dinamiche.
        """
        if conditions_list is None:
            conditions_list = []
        
        # Inizializza le parti della query
        select_fields = [f"user_{self.tableid}.*"]
        from_clauses = [f"FROM user_{self.tableid}"]
        where_clauses = [f"user_{self.tableid}.deleted_='N'"]
        
        # 1. Gestione del termine di ricerca
        if searchTerm and columns:
            searchTerm_conditions = []
            for column in columns:
                fieldid = column.get('fieldid')
                if not fieldid:
                    continue
                
                # NOTA: Per unire le tabelle in base al recordid_ del campo collegato
                # l'approccio migliore è estrarre l'ID della tabella collegata
                # dal nome del campo (es. recordidclienti_)
                # o dalla definizione del campo.
                tablelink = column.get('tablelink')
                keyfieldlink = column.get('keyfieldlink')
                
                if tablelink and keyfieldlink:
                    # Aggiunge il JOIN alla lista di clausole
                    from_clauses.append(
                        f"LEFT JOIN user_{tablelink} ON user_{self.tableid}.recordid{tablelink}_ = user_{tablelink}.recordid_ "
                    )
                    # Aggiunge la condizione di ricerca
                    sanitized_term = searchTerm.replace("'", "''")
                    searchTerm_conditions.append(
                        f"user_{tablelink}.{keyfieldlink} LIKE '%{sanitized_term}%'"
                    )
                else:
                    sanitized_term = searchTerm.replace("'", "''")
                    searchTerm_conditions.append(
                        f"user_{self.tableid}.{fieldid} LIKE '%{sanitized_term}%'"
                    )
            
            if searchTerm_conditions:
                where_clauses.append(f"({' OR '.join(searchTerm_conditions)})")

        # 2. Aggiungi le condizioni della conditions_list
        if conditions_list:
            where_clauses.extend(conditions_list)

        # 3. Gestione della vista
        if viewid:
            view_query_conditions = HelpderDB.sql_query_value(
                sql=f"SELECT query_conditions FROM sys_view WHERE id='{viewid}' AND tableid='{self.tableid}'",
                column='query_conditions'
            )
            if view_query_conditions:
                view_query_conditions = str(view_query_conditions)
                view_query_conditions = view_query_conditions.replace('$userid$', str(self.userid))
                today = datetime.date.today().strftime("%Y-%m-%d")
                # view_query_conditions = view_query_conditions.replace('$today$', today) # Rimuovi se non usato
                where_clauses.append(view_query_conditions)

        # 4. Aggiungi i campi specifici se richiesti
        if fields:
            select_fields = [f"user_{self.tableid}.{field}" for field in fields]
            select_fields.insert(0, f"user_{self.tableid}.recordid_")
        
        # 5. Costruisci la query finale
        seen_elements = set()
        ordered_unique_clauses = []

        for clause in from_clauses:
            if clause not in seen_elements:
                ordered_unique_clauses.append(clause)
                seen_elements.add(clause)

        from_sql_string = " ".join(ordered_unique_clauses)
        where_sql_string = " AND ".join(where_clauses)
        select_sql_string = ", ".join(select_fields)
        
        # 6. Calcola e salva il numero totale dei record
        count_sql = f"SELECT COUNT(*) as total_count {from_sql_string} WHERE {where_sql_string}"
        count_result = HelpderDB.sql_query(count_sql)
        self._total_records_count = count_result[0]['total_count'] if count_result else 0
        
        # 7. Prepara la query per i record
        if not limit:
            limit = 100
            
        orderby_safe = f"user_{self.tableid}.{orderby}" # Previeni SQL Injection su orderby
        
        sql = (
            f"SELECT {select_sql_string} "
            f"{from_sql_string} "
            f"WHERE {where_sql_string} "
            f"ORDER BY {orderby_safe} "
            f"LIMIT {limit} OFFSET {offset}"
        )

        records = HelpderDB.sql_query(sql)
        return records
    
    def _get_fields_definitions(self):
        """
        Recupera e mette in cache le definizioni dei campi, incluse impostazioni
        e valori predefiniti, una sola volta per istanza UserTable.
        """
        if self._fields_definitions is None:
            self._fields_definitions = {}
            # Query per ottenere tutti i campi per la tabella
            sql_fields = f"SELECT * FROM sys_field WHERE tableid='{self.tableid}'"
            fields = HelpderDB.sql_query(sql_fields)

            if not fields: # Nessun campo trovato
                return self._fields_definitions

            field_ids_str = "'" + "','".join([f['fieldid'] for f in fields]) + "'"

            # Query per ottenere TUTTE le impostazioni utente per questi campi in una volta
            sql_settings = f"""
                SELECT fieldid, settingid, value
                FROM sys_user_field_settings
                WHERE tableid='{self.tableid}' AND userid='{str(self.userid)}' AND fieldid IN ({field_ids_str})
            """
            all_settings_list = HelpderDB.sql_query(sql_settings)
            # Organizza le impostazioni per fieldid per un accesso rapido
            all_settings = {}
            for setting in all_settings_list:
                fieldid = setting['fieldid']
                if fieldid not in all_settings:
                    all_settings[fieldid] = {}
                all_settings[fieldid][setting['settingid']] = setting['value']

            # Query per ottenere TUTTI gli ordinamenti per questi campi in una volta (se necessario)
            # Esempio per 'insert_fields', aggiungi altri typepreference se servono altrove
            sql_order = f"""
                SELECT fieldid, fieldorder, typepreference
                FROM sys_user_field_order
                WHERE tableid='{self.tableid}' AND userid='{str(self.userid)}' AND fieldid IN ({field_ids_str})
                ORDER BY typepreference, fieldorder
            """
            all_orders_list = HelpderDB.sql_query(sql_order)
            # Organizza gli ordinamenti
            all_orders = {}
            for order_info in all_orders_list:
                 fieldid = order_info['fieldid']
                 pref_type = order_info['typepreference']
                 if pref_type not in all_orders:
                     all_orders[pref_type] = {}
                 if fieldid not in all_orders[pref_type]:
                     all_orders[pref_type][fieldid] = order_info['fieldorder']


            for field in fields:
                fieldid = field['fieldid']
                # Assegna le impostazioni recuperate
                field['settings'] = all_settings.get(fieldid, {})
                # Assegna il valore predefinito (se presente nelle impostazioni)
                field['defaultvalue'] = all_settings.get(fieldid, {}).get('default', '')
                # Assegna l'ordine (se recuperato)
                field['order'] = {pref: orders.get(fieldid) for pref, orders in all_orders.items() if fieldid in orders}

                self._fields_definitions[fieldid] = field

        return self._fields_definitions
    
    def get_results_columns(self):
        #TODO abilitare per i singoli utenti e non solo con i parametri del superuser
        sql=f"""
            SELECT *
            FROM sys_user_field_order
            LEFT JOIN sys_field ON sys_user_field_order.tableid=sys_field.tableid AND sys_user_field_order.fieldid=sys_field.id
            WHERE sys_user_field_order.typepreference = 'search_results_fields'
            AND sys_user_field_order.tableid = '{self.tableid}'
            AND sys_user_field_order.userid = 1
            ORDER BY sys_user_field_order.fieldorder
            """
        columns=HelpderDB.sql_query(sql)
        return columns
    
    def get_table_views(self):
        sql=f"""
            SELECT *
            FROM sys_view
            WHERE tableid = '{self.tableid}'
            """
        views=HelpderDB.sql_query(sql)
        return views
    
    def get_default_viewid(self):
        sql="SELECT value FROM sys_user_table_settings WHERE tableid = '"+self.tableid+"' AND userid=1 AND settingid='default_viewid'"
        viewid=HelpderDB.sql_query_value(sql=sql,column='value')
        return viewid
                                    