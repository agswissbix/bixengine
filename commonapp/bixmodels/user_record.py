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
        self.fields = {} # Conterrà le definizioni arricchite con 'value' e 'convertedvalue'
        
        if _prefetched_data:
            # --- Caso OTTIMIZZATO ---
            self.values = _prefetched_data['values']
            self.recordid = self.values.get('recordid_')
            field_definitions = _prefetched_data['fields_definitions']
            # NUOVO: estrai le mappe di dati pre-caricati
            eager_loaded_data = _prefetched_data.get('eager_loaded_data', {})

            for fieldid, definition_template in field_definitions.items():
                field_instance = definition_template.copy()
                if fieldid.startswith('_'):
                    # Se fieldid è '_esempio', la chiave per il valore diventa 'esempio_'
                    value_key = f"{fieldid[1:]}_"
                else:
                    # Altrimenti, usa il fieldid così com'è
                    value_key = fieldid

                # Recupera il valore usando la chiave determinata
                raw_value = self.values.get(value_key, "")

                field_instance['value'] = raw_value
                
                # MODIFICATO: Calcola il valore convertito usando i dati eager-loaded
                field_instance['convertedvalue'] = self._convert_display_value(
                    field_instance, eager_loaded_data
                )
                
                # NUOVO: Arricchiamo il field con dati utili al frontend
                if field_instance.get('fieldtypeid') == 'Utente' and raw_value:
                    try:
                        field_instance['userid'] = int(raw_value)
                    except (ValueError, TypeError):
                        pass
                elif field_instance.get('keyfieldlink') and (table_link := field_instance.get('tablelink')):
                    record_link_id = self.values.get(f"recordid{table_link}_")
                    if record_link_id:
                        field_instance['linkedmaster_tableid'] = table_link
                        field_instance['linkedmaster_recordid'] = record_link_id

                self.fields[fieldid] = field_instance
        else:
            # --- Caso NON OTTIMIZZATO (fallback alla logica originale) ---
            self._fetch_field_definitions_from_db()
            if recordid:
                self._fetch_record_values_from_db()
                self._populate_fields_with_values() # Questo ora chiamerà il _convert_display_value aggiornato

    def _populate_fields_with_values(self):
        """ Popola il campo 'value' e 'convertedvalue' in self.fields usando self.values (logica di fallback) """
        if not self.values: return
        for fieldid, field_def in self.fields.items():
            value = self.values.get(fieldid, "")
            self.fields[fieldid]['value'] = value
            # Passa un dizionario vuoto perché in questo branch non abbiamo dati eager
            self.fields[fieldid]['convertedvalue'] = self._convert_display_value(field_def, {})

    def _convert_display_value(self, field_definition, eager_data):
        """
        MODIFICATO: Converte il valore grezzo in valore display.
        Prioritizza l'uso di dati pre-caricati (eager_data).
        Esegue query al DB solo come fallback se eager_data non è disponibile.
        """
        raw_value = field_definition.get('value')
        if raw_value is None: return ""

        field_type = field_definition.get('fieldtypeid')
        table_link = field_definition.get('tablelink')
        
        try:
            # CASO: Utente
            if field_type == 'Utente' and raw_value:
                user_id = int(raw_value)
                # Prova a usare i dati pre-caricati
                if 'sys_user' in eager_data:
                    return eager_data['sys_user'].get(user_id, raw_value)
                # Fallback: query al DB
                sql = f"SELECT firstname, lastname FROM sys_user WHERE id='{user_id}'"
                user = HelpderDB.sql_query_row(sql)
                return f"{user['firstname']} {user['lastname']}" if user else raw_value

            # CASO: Campo collegato
            elif table_link and field_definition.get('keyfieldlink'):
                # L'ID del record collegato si trova in un'altra colonna di self.values
                linked_record_id = self.values.get(f"recordid{table_link}_")
                if not linked_record_id:
                    return raw_value # o ""
                
                # Prova a usare i dati pre-caricati
                if table_link in eager_data:
                    return eager_data[table_link].get(linked_record_id, linked_record_id)
                # Fallback: query al DB
                keyfield = field_definition['keyfieldlink']
                sql = f"SELECT {keyfield} FROM user_{table_link} WHERE recordid_='{linked_record_id}'"
                return HelpderDB.sql_query_value(sql, keyfield) or linked_record_id

            # CASO: Data
            elif field_type == 'Data' and raw_value:
                if isinstance(raw_value, datetime.date):
                    return raw_value.strftime('%d/%m/%Y')
                elif isinstance(raw_value, str):
                    try:
                        return datetime.datetime.strptime(raw_value.split(' ')[0], '%Y-%m-%d').strftime('%d/%m/%Y')
                    except (ValueError, TypeError):
                        return raw_value
                return raw_value

            # Altri casi non modificati
            else:
                return raw_value
                
        except Exception as e:
            print(f"Error converting value for field {field_definition.get('fieldid')}: {e}")
            return raw_value

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
    
    @timing_decorator
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
            #todo (controllo aggiunto perchè in alcune situazioni mi arrivava linked_tableid vuoto. in particolare nel caso di servicecontract)
            if linked_tableid:
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
                    lookupitemsuser['userid']=user['id']
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
                if field['fieldtypewebid'] == 'multiselect':
                    insert_field['fieldtypewebid']='multiselect'

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