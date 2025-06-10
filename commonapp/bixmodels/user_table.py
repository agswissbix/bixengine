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

    def get_table_records(self,viewid='',searchTerm='', conditions_list=list(),fields=None,offset=0,limit=None,orderby='recordid_ desc'):
        columns = self.get_results_columns()
        fields=[]
        for column in columns:
            fields.append(column['fieldid'])
        records = self.get_records(viewid,searchTerm,conditions_list,fields,offset,limit,orderby,columns)
        return records
    
    def get_table_records_obj(self, viewid='', searchTerm='', conditions_list=list(), fields=None, offset=0, limit=None, orderby='recordid_ desc', master_tableid=None, master_recordid=None):
        """
        Recupera i record e le loro proprietà come lista di oggetti UserRecord ottimizzata.
        """
        if master_tableid and master_recordid:
            conditions_list.append(f"recordid{master_tableid}_='{master_recordid}'")

        # 1. Recupera le definizioni dei campi UNA SOLA VOLTA
        # Queste definizioni verranno passate a ciascuna istanza UserRecord
        field_definitions = self._get_fields_definitions()

        # 2. Recupera le colonne per la ricerca (se necessario)
        columns = self.get_results_columns() 

        # 3. Recupera TUTTI i dati grezzi dei record in UNA query
        raw_records_data = self.get_records(
            viewid=viewid,
            searchTerm=searchTerm,
            conditions_list=conditions_list,
            fields=fields,
            offset=offset,
            limit=limit,
            orderby=orderby,
            columns=columns
        )

        # 4. Crea istanze UserRecord usando i dati prefetched
        records_obj_list = []
        for raw_record in raw_records_data:
            record_id = raw_record.get('recordid_')
            if not record_id:
                continue

            # Prepara il dizionario dei dati prefetched per UserRecord.__init__
            prefetched_data_for_record = {
                'values': raw_record, # I dati grezzi completi del record
                'fields_definitions': field_definitions # Le definizioni comuni a tutti
            }

            # Crea l'istanza UserRecord passando i dati prefetched
            try:
                 record_instance = UserRecord(
                     tableid=self.tableid,
                     recordid=record_id, # Passa l'ID anche se è nei values, per chiarezza
                     userid=self.userid,
                     # master_tableid/master_recordid non servono qui, già gestiti nella query
                     _prefetched_data=prefetched_data_for_record # Il parametro speciale!
                 )
                 records_obj_list.append(record_instance)
            except Exception as e:
                 # Logga l'errore ma continua se possibile
                 print(f"Errore durante la creazione dell'istanza UserRecord per {record_id}: {e}")


        # Restituisce la lista di oggetti UserRecord popolati
        return records_obj_list
    
    def get_records(self,viewid='',searchTerm='', conditions_list=list(),fields=None,offset=0,limit=None,orderby='recordid_ desc',columns=None):
        """Ottieni elenco record in base ai parametri di ricerca

        Args:
            viewid (str, optional): vista applicata. Defaults to ''.
            searchTerm (str, optional): termine generico da cercare in tutti i campi. Defaults to ''.
            conditions_list (_type_, optional): condizioni specifiche sui campi. Defaults to list().

        Returns:
            _type_: lista di dict dei risultati
        """ 
        select_fields=f"user_{self.tableid}.*"
        fromsql=f"FROM user_{self.tableid}"

        if fields:
            select_fields='user_'+self.tableid+'.recordid_'
            for field in fields:
                select_fields=select_fields+',user_'+self.tableid+'.'+field

                
        conditions=f"user_{self.tableid}.deleted_='N'"
        #conditions=conditions+f" AND companyname like '%{searchTerm}%' " 
        for condition in conditions_list:
            conditions=conditions+f" AND {condition}"   

        #searchterm
        if searchTerm:
            searchTerm_conditions=''
            for column in columns:
                fieldid=column['fieldid']
                if searchTerm_conditions!='':
                    searchTerm_conditions=searchTerm_conditions + " OR "

                if fieldid.startswith("_recordid"):
                    linkedtableid = fieldid[len("_recordid"):]
                    fromsql=fromsql+f" LEFT JOIN user_{linkedtableid} ON user_{self.tableid}.recordid{linkedtableid}_=user_{linkedtableid}.recordid_ "
                    searchTerm_conditions=searchTerm_conditions+f"user_{linkedtableid+'.'+column['keyfieldlink']} like '%{searchTerm}%' " 
                else:
                    searchTerm_conditions=searchTerm_conditions+f"user_{self.tableid}.{fieldid} like '%{searchTerm}%' "

                
            if searchTerm_conditions!='':
                conditions=conditions+f" AND ({searchTerm_conditions}) "   
        orderby='user_'+self.tableid+'.'+orderby

        # → Calcola e salva il numero totale dei record
        count_sql = f"SELECT COUNT(*) as total_count {fromsql} WHERE {conditions}"
        count_result = HelpderDB.sql_query(count_sql)
        self._total_records_count = count_result[0]['total_count'] if count_result else 0

        sql=f"SELECT {select_fields} {fromsql} where {conditions}  ORDER BY {orderby} LIMIT 350 "
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
        sql=f"""
            SELECT *
            FROM sys_user_field_order
            LEFT JOIN sys_field ON sys_user_field_order.tableid=sys_field.tableid AND sys_user_field_order.fieldid=sys_field.id
            WHERE sys_user_field_order.typepreference = 'search_results_fields'
            AND sys_user_field_order.tableid = '{self.tableid}'
            AND sys_user_field_order.userid = {self.userid}
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
                                    