from django.contrib.sessions.models import Session
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
from django.db.models import OuterRef, Subquery
from commonapp.bixmodels.helper_db import *
from commonapp.bixmodels.helper_sys import *
from commonapp.helper import *
from commonapp.bixmodels.sys_field import SysField  # Import SysField if it exists in this module
from datetime import date

bixdata_server = os.environ.get('BIXDATA_SERVER')

class UserRecord:

    context=""
    def __init__(self, tableid, recordid=None, userid=1, master_tableid="", master_recordid="", _prefetched_data=None):
        self.tableid = tableid
        self.recordid = recordid
        self.userid = userid
        self.master_tableid = master_tableid
        self.master_recordid = master_recordid
        self.values = {}
        self.fields = {} # Questo conterrà le definizioni dei campi arricchite con i valori
        self.context = 'insert_fields' # Mantenuto se serve

        if _prefetched_data:
            # --- Caso OTTIMIZZATO: Popola dai dati prefetched ---
            if 'values' not in _prefetched_data or 'fields_definitions' not in _prefetched_data:
                 raise ValueError("Dati prefetched incompleti per UserRecord.")

            self.values = _prefetched_data['values'] # Dati grezzi del record
            self.recordid = self.values.get('recordid_') # Assicurati che recordid sia corretto

            # Popola self.fields combinando definizioni e valori
            field_definitions = _prefetched_data['fields_definitions']
            for fieldid, definition_template in field_definitions.items():
                field_instance_definition = definition_template.copy()
                value = self.values.get(fieldid)
                if value is None:
                    value = ""

                field_instance_definition['value'] = value
                # Calcola 'convertedvalue' qui o lascialo ai metodi getter se preferisci
                field_instance_definition['convertedvalue'] = self._convert_display_value(field_instance_definition, value)

                self.fields[fieldid] = field_instance_definition

            # Non serve applicare master_recordid qui, dovrebbe essere già nei 'values'
            # se la query in UserTable è corretta.

        else:
            # --- Caso NON OTTIMIZZATO: Logica originale con query al DB ---
            # È buona norma refattorizzare le query in metodi privati
            self._fetch_field_definitions_from_db() # Metodo che contiene la logica originale per sys_field/settings
            if recordid:
                self._fetch_record_values_from_db() # Metodo che contiene la SELECT * FROM user_table WHERE recordid_ = ...
                self._populate_fields_with_values() # Metodo per popolare self.fields['value'] etc. dai self.values

            # Applica master_recordid SE è un nuovo record (recordid=None)
            # e stiamo usando la logica originale (non prefetched)
            if not recordid and master_tableid and master_recordid:
                 self._apply_master_record_defaults()

    # --- Metodi Helper per la logica originale (da popolare con il codice originale) ---

    def _fetch_field_definitions_from_db(self):
        """ Recupera definizioni e settings dei campi dal DB (logica originale) """
        # Metti qui la logica originale di __init__ per recuperare da sys_field e sys_user_field_settings
        if self.tableid:
            fields_db = HelpderDB.sql_query(f"SELECT * FROM sys_field WHERE tableid='{self.tableid}'")
            temp_fields = {}
            for field in fields_db:
                # Recupera settings e default (potrebbe essere ottimizzato anche qui)
                sql_settings = f"SELECT * FROM sys_user_field_settings WHERE fieldid='{field['fieldid']}' AND tableid='{self.tableid}' AND userid='{str(self.userid)}'" # Usa self.userid
                field['settings'] = HelpderDB.sql_query(sql_settings)
                sql_default = f"SELECT value FROM sys_user_field_settings WHERE settingid='default' AND fieldid='{field['fieldid']}' AND tableid='{self.tableid}' AND userid='{str(self.userid)}'" # Usa self.userid
                field['defaultvalue'] = HelpderDB.sql_query_value(sql_default, 'value')
                temp_fields[field['fieldid']] = field
            self.fields = temp_fields # Inizializza self.fields con le definizioni base

    def _fetch_record_values_from_db(self):
        """ Recupera i valori del record specifico dal DB (logica originale) """
        if self.recordid:
            self.values = HelpderDB.sql_query_row(f"SELECT * FROM user_{self.tableid} WHERE recordid_='{self.recordid}'")
            if not self.values:
                print(f"Attenzione: Record {self.recordid} non trovato nella tabella user_{self.tableid}")
                self.values = {} # Evita errori successivi

    def _populate_fields_with_values(self):
        """ Popola il campo 'value' e 'convertedvalue' in self.fields usando self.values """
        if not self.values: # Se il record non è stato trovato
             return

        for fieldid, field_def in self.fields.items():
            value = self.values.get(fieldid)
            if value is None:
                value = ""
            self.fields[fieldid]['value'] = value
            # Calcola convertedvalue anche qui per consistenza
            self.fields[fieldid]['convertedvalue'] = self._convert_display_value(field_def, value)

    def _apply_master_record_defaults(self):
        """ Applica i valori dal master record se è un nuovo record """
        # Aggiunta del controllo per master_tableid e master_recordid
        if not self.recordid and self.master_tableid and self.master_recordid:
            master_fieldid = f"recordid{self.master_tableid}_" # Convenzione da UserTable
            if master_fieldid in self.fields:
                # Imposta il valore di default nel dizionario 'fields'
                self.fields[master_fieldid]['value'] = self.master_recordid
                self.fields[master_fieldid]['convertedvalue'] = self.master_recordid # Assumendo che sia l'ID
                # Potresti voler aggiornare anche self.values per coerenza, anche se è vuoto
                # self.values[master_fieldid] = self.master_recordid

    # --- Metodo per la conversione (può stare qui) ---
    def _convert_display_value(self, field_definition, value):
        """ Converte il valore grezzo in valore display (logica da UserTable o originale) """
        fieldid = field_definition.get('fieldid')
        field_type = field_definition.get('fieldtypeid', 'standard')
        keyfieldlink = field_definition.get('keyfieldlink')
        tablelink = field_definition.get('tablelink')
        fieldtypewebid = field_definition.get('fieldtypewebid') # Aggiunto per file/html

        try:
            # NOTA: La logica originale in get_record_results_fields usava self.values
            # per i campi linkati (_recordid...). Qui usiamo il 'value' passato,
            # che dovrebbe essere l'ID del record collegato.

            # Caso Link (_recordid... convenzione)
            # Assumiamo che il fieldid nella definizione sia quello che inizia con '_'
            # e 'value' sia l'ID record collegato.
            if fieldid and fieldid.startswith('_') and not Helper.isempty(keyfieldlink) and not Helper.isempty(tablelink) and value:
                 linked_table_actual_name = tablelink # Usiamo tablelink direttamente
                 sql=f"SELECT {keyfieldlink} FROM user_{linked_table_actual_name} WHERE recordid_='{value}'"
                 fetched_value = HelpderDB.sql_query_value(sql, keyfieldlink)
                 return fetched_value if fetched_value is not None else value

            elif field_type == 'Utente' and value:
                 sql=f"SELECT firstname, lastname FROM sys_user WHERE id='{value}'"
                 user=HelpderDB.sql_query_row(sql)
                 return f"{user['firstname']} {user['lastname']}" if user else value

            elif field_type == 'Data' and value:
                 if isinstance(value, datetime.date): # Se è già un oggetto data/datetime
                     return value.strftime('%d/%m/%Y')
                 elif isinstance(value, str):
                     try:
                         # Prova a parsare formati comuni
                         if ' ' in value: # Probabile datetime YYYY-MM-DD HH:MM:SS
                              dt_obj = datetime.datetime.strptime(value.split()[0], '%Y-%m-%d')
                         else: # Probabile solo data YYYY-MM-DD
                              dt_obj = datetime.datetime.strptime(value, '%Y-%m-%d')
                         return dt_obj.strftime('%d/%m/%Y')
                     except ValueError:
                         return value # Restituisci stringa originale se parsing fallisce
                 else:
                     return value

            elif field_type == 'Memo' and fieldtypewebid == 'html':
                 # Nessuna conversione speciale necessaria qui per il valore grezzo,
                 # la gestione HTML avviene nel template.
                 return value

            elif fieldtypewebid == 'file':
                 # Probabilmente vuoi mostrare il nome del file o un link,
                 # ma il 'value' grezzo potrebbe essere solo l'ID o path.
                 # Qui restituiamo il valore grezzo, la logica display è altrove.
                 return value

            # Aggiungere logica per 'Categoria' (lookup) se necessario per display value
            elif not Helper.isempty(field_definition.get('lookuptableid')) and value:
                 #sql = f"SELECT itemvalue FROM sys_lookup_table_item WHERE lookuptableid='{field_definition['lookuptableid']}' AND itemcode='{value}'"
                 #item_value = HelpderDB.sql_query_value(sql, 'itemvalue')
                 item_value=value
                 return item_value if item_value is not None else value


            else: # Tipo standard o non gestito
                 return value
        except Exception as e:
            print(f"Error converting value for field {fieldid}: {e}")
            return value # Restituisci valore grezzo in caso di errore 


    def get_record_badge_fields(self):
        return_fields=[]
        sql = f"SELECT sys_field.* FROM sys_field join sys_user_order on sys_field.fieldid=sys_user_order.fieldid WHERE sys_field.tableid='{self.tableid}' AND sys_user_order.userid=1 AND sys_user_order.tableid='{self.tableid}' AND typePreference='campiFissi' ORDER BY fieldorder asc"
        fields = HelpderDB.sql_query(sql)
        for field in fields:
            fieldid = field['fieldid']
            return_field={}
            return_field['fieldid']=fieldid
            return_field['value']=self.values[fieldid]
            return_fields.append(return_field)
        return return_fields
    
    def get_record_results_fields(self):
        return_fields=[]
        sql = f"SELECT sys_field.* FROM sys_field join sys_user_field_order on sys_field.id=sys_user_field_order.fieldid WHERE sys_field.tableid='{self.tableid}' AND sys_user_field_order.userid=1 AND sys_user_field_order.tableid='{self.tableid}' AND typePreference='search_results_fields' ORDER BY fieldorder asc"
        fields = HelpderDB.sql_query(sql)
        for field in fields:
            fieldid = field['fieldid']
            value=self.values[fieldid]
            if fieldid.startswith('_') and not Helper.isempty(field['keyfieldlink']):
                value=self.values[fieldid.lstrip('_') + '_']
                field['fieldtypeid']='standard'
                sql=f"SELECT {field['keyfieldlink']} FROM user_{field['tablelink']} WHERE recordid_='{value}' "
                newvalue=HelpderDB.sql_query_value(sql,field['keyfieldlink'])
                value=newvalue
            
            if field['fieldtypeid']=='Utente':
                if value:
                    sql=f"SELECT firstname,lastname FROM sys_user WHERE id='{value}' "
                    user=HelpderDB.sql_query_row(sql)
                    newvalue=user['firstname']
                    value=newvalue

            if field['fieldtypeid']=='Data':
                if value:
                    if isinstance(value, str):
                        newvalue = datetime.datetime.strptime(value, '%Y-%m-%d').strftime('%d/%m/%Y')
                    else:
                        newvalue = value.strftime('%d/%m/%Y')
                    value=newvalue
            
            return_field={}
            return_field['type']='standard'
            return_field['fieldid']=fieldid
            return_field['value']=value
            return_fields.append(return_field) 
        return return_fields
        
    
    def get_fields_plain(self):
        fields_plain=self.fields
        return self.fields_plain
    
    def get_fields_detailed(self):
        fields_detailed=[]
        print(self.tableid)
        for fieldid, field in self.fields.items():
            print(fieldid)
            if(not Helper.isempty(field['tablelink']) and Helper.isempty(field['keyfieldlink'])):
                field['fieldtypeid']='Linked'
            if field['fieldtypeid']!='Linked':
                field_detailed={}
                field_detailed['tableid']="1"
                field_detailed['fieldid']="test1"+self.recordid
                field_detailed['fieldorder']="1"
                field_detailed['description']=field['description']  
                if self.recordid!="":
                    field_detailed['value']={"code": self.values[fieldid], "value": self.values[fieldid]}
                else:
                    field_detailed['value']={"code": "", "value": ""}
                
                field_detailed['fieldtype']="Parola"
                field_detailed['settings']={
                    "calcolato": "false",
                    "default": "",
                    "nascosto": "false",
                    "obbligatorio": "false"
                }
                fields_detailed.append(field_detailed)

        return fields_detailed
    
    def save(self):
        if self.recordid:
            counter=0
            sql=f"UPDATE user_{self.tableid} SET "
            for fieldid,value in self.values.items():
                if counter>0:
                    sql=sql+","
                if value!=None:  
                    if type(value)==str:
                        value = value.replace("'", "''")  
                    sql=sql+f" {fieldid}='{value}' "
                else:
                    sql=sql+f" {fieldid}=null "
                counter+=1
            sql=sql+f" WHERE recordid_='{self.recordid}'"  
            HelpderDB.sql_execute(sql) 
        else:
            sqlmax=f"SELECT MAX(recordid_) as max_recordid FROM user_{self.tableid}"
            result=HelpderDB.sql_query_row(sqlmax)
            max_recordid=result['max_recordid']
            if max_recordid is None:
                next_recordid = '00000000000000000000000000000001'
            else:
                next_recordid = str(int(max_recordid) + 1).zfill(32)
            
            sqlmax=f"SELECT MAX(id) as max_id FROM user_{self.tableid}"
            result=HelpderDB.sql_query_row(sqlmax)
            max_id=result['max_id']
            if max_id is None:
                next_id = 1
            else:
                next_id = max_id+1
            
            current_datetime=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sqlinsert=f"INSERT INTO user_{self.tableid} (recordid_,creatorid_,creation_,id) VALUES ('{next_recordid}',{self.userid},'{current_datetime}',{next_id}) "
            HelpderDB.sql_execute(sqlinsert)
            self.recordid=next_recordid
            self.save()

    def get_linked_tables(self):
        sql=f"SELECT sys_table.id as tableid,sys_table.description  FROM sys_user_order LEFT JOIN sys_table ON sys_user_order.fieldid=sys_table.id  WHERE sys_user_order.tableid='{self.tableid}' AND typepreference='keylabel' AND userid={self.userid} order by fieldorder asc"

        linked_tables=HelpderDB.sql_query(sql)
        for linked_table in linked_tables:
            linked_tableid=linked_table['tableid']
            sql=f"SELECT count(recordid_) as counter FROM user_{linked_tableid} WHERE recordid{self.tableid}_='{self.recordid}'"
            counter=HelpderDB.sql_query_value(sql,'counter')
            linked_table['rowsCount']=counter
    

        return linked_tables
    

    def get_badge_fields(self):
        badge_fields=[]
        if not self.recordid=='':
            sql=f"""
                SELECT f.*
                FROM sys_user_field_order AS fo LEFT JOIN sys_field AS f ON fo.tableid=f.tableid AND fo.fieldid=f.id

                WHERE fo.tableid='{self.tableid}' AND typepreference='badge_fields' AND fo.userid={self.userid} ORDER BY fieldorder
            """
            fields=HelpderDB.sql_query(sql)
            
            for field in fields:
                fieldid=field['fieldid']
                value=self.values[fieldid]
                badge_fields.append({"fieldid":fieldid,"value":value})
        return badge_fields
    
    def get_record_card_fields(self):

        #TODO
        if self.tableid=='pitticket' and self.master_tableid=='telefonate' and self.recordid=='':
            record_telefonate=UserRecord('telefonate',self.master_recordid)
            self.values['assegnatoda']=self.userid
            self.values['recordidstabile_']=(record_telefonate.values.get('recordidstabile_','') or '')
            self.values['titolorichiesta']="ticket da telefonata - "+ (record_telefonate.values.get('chi','') or '')
            self.values['personariferimento'] = (record_telefonate.values.get('chi') or '') + " " + (record_telefonate.values.get('telefono') or '')
            self.values['richiesta']=(record_telefonate.values.get('motivo_chiamata','') or '')
            
        sql=f"""
            SELECT f.*
            FROM sys_user_field_order AS fo LEFT JOIN sys_field AS f ON fo.tableid=f.tableid AND fo.fieldid=f.id

            WHERE fo.tableid='{self.tableid}' AND typepreference='insert_fields' AND fo.userid=1 ORDER BY fieldorder
        """
        fields=HelpderDB.sql_query(sql)
        insert_fields=[]
        for field in fields:
            defaultcode=''
            defaultvalue=''
            insert_field={}
            fieldid=field['fieldid']
            if fieldid.startswith("_"):
                fieldid= fieldid[1:] + "_"
            value=self.values.get(fieldid, '')
            
            #if self.recordid=='':
             #   value=""
            #else:
             #   value=self.values[fieldid]
              #  if not value:
               #     value=""
            insert_field['tableid']="1"
            insert_field['fieldid']=fieldid
            insert_field['fieldorder']="1"
            insert_field['description']=field['description']
            insert_field['value']={"code": value, "value": value}
            insert_field["fieldtypewebid"]= "",
            insert_field["lookuptableid"]= field['lookuptableid'],
            insert_field["tablelink"]= field['tablelink'],
            insert_field['linked_mastertable']=field['tablelink'],
            insert_field['settings']={
                "calcolato": "false",
                "default": "",
                "nascosto": "false",
                "obbligatorio": "false"
            }
            
            fieldtype='Parola'
            if not Helper.isempty(field['keyfieldlink']):
                fieldtype='linkedmaster'
                if(field['tablelink']==self.master_tableid):
                    sql=f"SELECT recordid_,{field['keyfieldlink']} FROM user_{field['tablelink']} where recordid_='{self.master_recordid}' "
                    linked_recordid=HelpderDB.sql_query_value(sql,'recordid_')
                    linked_key=HelpderDB.sql_query_value(sql,field['keyfieldlink'])
                    defaultcode=linked_recordid
                    defaultvalue=linked_key
                
                if(value!=""):
                    sql=f"SELECT recordid_,{field['keyfieldlink']} FROM user_{field['tablelink']} where recordid_='{value}' "
                    linked_recordid=HelpderDB.sql_query_value(sql,'recordid_')
                    linked_key=HelpderDB.sql_query_value(sql,field['keyfieldlink'])
                    insert_field['value']={"code": linked_recordid, "value": linked_key}

            if field['fieldtypeid'] == 'Data':
                fieldtype='Data'
                #defaultvalue=self.fields[fieldid]['defaultvalue']
                #if defaultvalue == '$today$':
                #TODO RENDERE DINAMICO CON I SETTINGS
                if self.tableid == 'telefonate' and fieldid == 'data': 
                    defaultcode=date.today().strftime('%Y-%m-%d')
                    defaultvalue=date.today().strftime('%Y-%m-%d')
                    
            #TODO RENDERE DINAMICO CON I SETTINGS
            if self.tableid == 'telefonate' and fieldid == 'ora_inizio':
                defaultcode = datetime.datetime.now().strftime("%H:%M")
                defaultvalue = datetime.datetime.now().strftime("%H:%M")

            if field['fieldtypeid'] == 'Utente':
                fieldtype='Utente'
                lookupitemsusers=[]
                users=HelperSys.get_users()
                for user in users:
                    lookupitemsuser={}
                    lookupitemsuser['id']=user['id']
                    lookupitemsuser['firstname']=user['firstname']
                    lookupitemsuser['lastname']=user['lastname']
                    lookupitemsuser['link']=''
                    lookupitemsuser['linkdefield']=''
                    lookupitemsuser['linkedvalue']=''
                    lookupitemsusers.append(lookupitemsuser)
                insert_field['lookupitemsuser']=lookupitemsusers
                defaultcode=self.userid
                defaultvalue=self.userid

            if field['fieldtypeid'] == 'Memo':
                fieldtype='Memo'
                if field['fieldtypewebid'] == 'html':
                    fieldtype='LongText'

            if field['fieldtypewebid'] == 'file':
                fieldtype='Attachment'

            if not Helper.isempty(field['lookuptableid']):
                fieldtype='Categoria' 
                items=HelpderDB.sql_query(f"SELECT * FROM sys_lookup_table_item WHERE lookuptableid='{field['lookuptableid']}'")
                insert_field['lookupitems']=items

            insert_field['fieldtype']=fieldtype

            if self.recordid=='' and value=='':
                insert_field['value']={"code": defaultcode, "value": defaultvalue}

            insert_fields.append(insert_field)


        return insert_fields


    def get_field(self,field_key):
        if field_key in self.fields:
            if (self.fields[field_key] is None  or self.fields[field_key]=='None'):
                return ''  
            else:
                return self.fields[field_key]      
        else:
            return ''