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

    # ============================
    #   COSTANTI DI CLASSE
    # ============================

    TEXT_CONDITIONS = {
        "Valore esatto": lambda self, field, val: field + " = '" + str(val).replace("'", "''") + "'",
        "Contiene": lambda self, field, val: field + " LIKE '%" + str(val).replace("'", "''") + "%'",
        "Diverso da": lambda self, field, val: field + " <> '" + str(val).replace("'", "''") + "'",
        "Nessun valore": lambda self, field, val: f"({field} IS NULL OR {field} = '')",
        "Almeno un valore": lambda self, field, val: f"({field} IS NOT NULL AND {field} <> '')"
    }

    LOOKUP_CONDITIONS = {
        "Valore esatto": lambda self, field, val: f"{field} = '{val}'",
        "Diverso da": lambda self, field, val: f"{field} <> '{val}'",
    }

    NUMBER_CONDITIONS = {
        "Tra": lambda self, field, r: f"({field} BETWEEN {r['min']} AND {r['max']})",
        "Maggiore di": lambda self, field, r: f"{field} > {r['min']}",
        "Minore di": lambda self, field, r: f"{field} < {r['max']}",
        "Diverso da": lambda self, field, r: f"{field} <> {r['min']}",
    }

    # ============================
    #   METODI STATICI UTILI
    # ============================

    @staticmethod
    def today():
        from datetime import datetime
        return datetime.today().strftime("%Y-%m-%d")

    @staticmethod
    def this_week():
        from datetime import datetime, timedelta
        now = datetime.today()
        start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
        end = (datetime.strptime(start, "%Y-%m-%d") + timedelta(days=6)).strftime("%Y-%m-%d")
        return start, end

    @staticmethod
    def this_month():
        from datetime import datetime, timedelta
        import dateutil.relativedelta as rd
        now = datetime.today()
        start = now.replace(day=1).strftime("%Y-%m-%d")
        end = (now.replace(day=1) + rd.relativedelta(months=1) - timedelta(days=1)).strftime("%Y-%m-%d")
        return start, end

    # ============================
    #   CONDIZIONI DATA (usa metodi)
    # ============================

    def get_date_conditions(self):
        return {
            "Oggi": lambda field: f"{field} = '{self.today()}'",
            "Questa settimana": lambda field: f"{field} BETWEEN '{self.this_week()[0]}' AND '{self.this_week()[1]}'",
            "Questo mese": lambda field: f"{field} BETWEEN '{self.this_month()[0]}' AND '{self.this_month()[1]}'",
            "Passato": lambda field: f"{field} < '{self.today()}'",
            "Futuro": lambda field: f"{field} > '{self.today()}'",
        }

    # ============================
    #   MAPPA GENERALE
    # ============================

    def get_condition_map(self):
        return {
            "Text": self.TEXT_CONDITIONS,
            "Parola": self.TEXT_CONDITIONS,
            "lookup": self.LOOKUP_CONDITIONS,
            "Utente": self.LOOKUP_CONDITIONS,
            "Numero": self.NUMBER_CONDITIONS,
            "Data": self.get_date_conditions()
        }
    
    @timing_decorator
    def build_condition(self, filter_type, field_id, filter_value, filter_condition):
        import json

        # --- NORMALIZZAZIONE DELLA CONDIZIONE ---
        if isinstance(filter_condition, list):
            cond_list = filter_condition[:]  # copia
        else:
            cond_list = [filter_condition]

        # --- DECODIFICA I VALUE ---
        try:
            parsed_value = json.loads(filter_value)
        except:
            parsed_value = filter_value

        # forza lista di set (se non lo è)
        if not isinstance(parsed_value, list):
            parsed_value = [parsed_value]

        # allinea lunghezze (default condition = "Valore esatto")
        max_len = max(len(cond_list), len(parsed_value))
        while len(cond_list) < max_len:
            cond_list.append("Valore esatto")
        while len(parsed_value) < max_len:
            parsed_value.append(None)

        cond_map = self.get_condition_map().get(filter_type)
        if not cond_map:
            return None

        date_specials = self.get_date_conditions()

        parts = []  # conterrà le espressioni per ciascuna coppia (cond_i, value_i)

        # --- PROCESSA 1:1 (cond_i, value_i) ---
        for cond_i, val_i in zip(cond_list, parsed_value):

            # normalizza cond_i (può essere None)
            if not cond_i:
                cond_i = "Valore esatto"

            # condizioni globali che ignorano il valore
            if cond_i == "Nessun valore":
                parts.append(f"({field_id} IS NULL)")
                continue

            if cond_i == "Almeno un valore":
                parts.append(f"({field_id} IS NOT NULL)")
                continue

            # date speciali (ignorano val_i)
            if filter_type == "Data" and cond_i in date_specials:
                parts.append("(" + date_specials[cond_i](field_id) + ")")
                continue

            # ---- ora gestiamo il caso standard per ciascun tipo ----

            # se val_i è None o vuoto, salta (nessun valore sensato da processare)
            if val_i is None or (isinstance(val_i, str) and val_i.strip() == ""):
                # se la condizione non è una di quelle che ignorano il valore, saltiamo
                # (oppure potremmo considerare Valore esatto su NULL, ma preferisco skip)
                continue

            # Per ogni coppia usiamo la mappatura cond_map; se mancante -> "Valore esatto"
            fun = cond_map.get(cond_i, cond_map.get("Valore esatto"))

            # --- TIPO Data con set dict {"from","to"} ---
            if filter_type == "Data" and isinstance(val_i, dict):
                from_d = val_i.get("from", "").strip()
                to_d = val_i.get("to", "").strip()

                if cond_i == "Valore esatto":
                    if from_d and to_d:
                        parts.append(f"({field_id} BETWEEN '{from_d}' AND '{to_d}')")
                    elif from_d:
                        parts.append(f"({field_id} = '{from_d}')")
                    elif to_d:
                        parts.append(f"({field_id} = '{to_d}')")
                elif cond_i == "Diverso da":
                    # NOT BETWEEN per range, o <> per valore singolo
                    if from_d and to_d:
                        parts.append(f"({field_id} NOT BETWEEN '{from_d}' AND '{to_d}')")
                    elif from_d:
                        parts.append(f"({field_id} <> '{from_d}')")
                    elif to_d:
                        parts.append(f"({field_id} <> '{to_d}')")
                else:
                    # fallback generico (usa funzione mappata se esiste)
                    # molti cond_map per Data possono definire fun(self, field, v)
                    try:
                        parts.append("(" + fun(self, field_id, val_i) + ")")
                    except Exception:
                        # se non è callable o fallisce, skip
                        continue

                continue

            # --- TIPO Numero con set dict {"min","max"} o singolo valore numerico---
            if filter_type == "Numero":
                # se è dict con min/max
                if isinstance(val_i, dict):
                    # la funzione della mappa si aspetta il dict
                    parts.append("(" + fun(self, field_id, val_i) + ")")
                else:
                    # valore singolo numerico
                    try:
                        # prova a convertire per sicurezza
                        num = float(val_i)
                        parts.append(f"({field_id} = {num})" if cond_i == "Valore esatto" else "(" + fun(self, field_id, val_i) + ")")
                    except Exception:
                        # valore non numerico -> skip
                        continue
                continue

            # --- TIPO lookup / Utente con lista o singolo valore ---
            if filter_type in ["lookup", "Utente"]:
                # se val_i è lista (es. ["A","B"]), allora per QUESTA coppia dobbiamo:
                # - se cond_i == "Diverso da" -> usare AND tra i sub-valori (esempio: field <> A AND field <> B)
                # - altrimenti -> usare OR tra i sub-valori (field = A OR field = B)
                if isinstance(val_i, list):
                    sub_fun = cond_map.get(cond_i, cond_map.get("Valore esatto"))
                    if cond_i == "Diverso da":
                        sub_join = " AND "
                    else:
                        sub_join = " OR "
                    subs = []
                    for sv in val_i:
                        subs.append(sub_fun(self, field_id, str(sv)))
                    if subs:
                        parts.append("(" + sub_join.join(subs) + ")")
                else:
                    parts.append("(" + fun(self, field_id, str(val_i)) + ")")
                continue

            # --- TIPO Text / Parola ---
            if filter_type in ["Text", "Parola"]:
                # se val_i è lista -> ogni elemento è un valore singolo (1:1 non list-vs-cond handled above)
                if isinstance(val_i, list):
                    # comportamento: per la singola coppia (cond_i, val_i_as_list) combiniamo i subvalori
                    # Diverso da -> AND, altrimenti OR
                    sub_fun = cond_map.get(cond_i, cond_map.get("Valore esatto"))
                    sub_join = " AND " if cond_i == "Diverso da" else " OR "
                    subs = [sub_fun(self, field_id, str(sv)) for sv in val_i if str(sv).strip()]
                    if subs:
                        parts.append("(" + sub_join.join(subs) + ")")
                elif isinstance(val_i, str) and "|" in val_i:
                    # stringa multivalore separata da |
                    sub_fun = cond_map.get(cond_i, cond_map.get("Valore esatto"))
                    sub_join = " AND " if cond_i == "Diverso da" else " OR "
                    subs = [sub_fun(self, field_id, p.strip()) for p in val_i.split("|") if p.strip()]
                    if subs:
                        parts.append("(" + sub_join.join(subs) + ")")
                else:
                    # singolo valore stringa
                    parts.append("(" + fun(self, field_id, str(val_i)) + ")")
                continue

            # --- DEFAULT: prova ad applicare la funzione mappata ---
            try:
                parts.append("(" + fun(self, field_id, val_i) + ")")
            except Exception:
                # skip se non è processabile
                continue

        # --- OR tra le diverse coppie (cond_i, val_i) come richiesto ---
        if parts:
            return "(" + " OR ".join(parts) + ")"
        return None

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
            filter_condition = filter_item.get('conditions', [])
            
            if not field_id or not filter_value:
                continue
            
            sql_condition = self.build_condition(filter_type, field_id, filter_value, filter_condition)

            if sql_condition:
                conditions_list.append(sql_condition)
        
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
                fieldtypeid = column.get('fieldtypeid')
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

                if fieldtypeid == 'Utente':
                    user_alias = f"user_{fieldid.replace('_', '')}" 
                    from_clauses.append(
                        f"LEFT JOIN sys_user AS {user_alias} ON user_{self.tableid}.{fieldid} = {user_alias}.id "
                    )
                    searchTerm_conditions.append(
                        f"({user_alias}.firstname LIKE '%{sanitized_term}%' OR {user_alias}.lastname LIKE '%{sanitized_term}%')"
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
                WHERE tableid='{self.tableid}' AND userid='{str(self.userid)}' AND fieldid IN ({field_ids_str}) AND fieldorder IS NOT NULL
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
            AND sys_user_field_order.fieldorder IS NOT NULL
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
                                    