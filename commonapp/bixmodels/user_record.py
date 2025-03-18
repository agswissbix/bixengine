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
from commonapp.helper import *

bixdata_server = os.environ.get('BIXDATA_SERVER')

class UserRecord:

    context=""
    def __init__(self, tableid, recordid=None, userid=1):
        self.tableid=tableid
        self.recordid=recordid
        self.userid=userid
        self.master_tableid=""
        self.master_recordid=""
        self.values=dict()
        self.fields=dict()
        self.context='insert_fields'
        if tableid:
            fields=HelpderDB.sql_query(f"SELECT * FROM sys_field WHERE tableid='{self.tableid}'")
            for field in fields:
                self.fields[field['fieldid']]=field


        if recordid:
            self.values=HelpderDB.sql_query_row(f"SELECT * FROM user_{self.tableid} WHERE recordid_='{self.recordid}'")


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
        sql=f"SELECT sys_user_order.tableid,sys_table.description  FROM sys_user_order LEFT JOIN sys_table ON sys_user_order.fieldid=sys_table.id  WHERE sys_user_order.tableid='{self.tableid}' AND typepreference='keylabel' AND userid={self.userid} order by fieldorder asc"

        linked_tables=HelpderDB.sql_query(sql)
        for linked_table in linked_tables:
            linked_table['rowsCount']=5
    

        return linked_tables
    

    def get_badge_fields(self):
        sql=f"""
            SELECT f.*
            FROM sys_user_field_order AS fo LEFT JOIN sys_field AS f ON fo.tableid=f.tableid AND fo.fieldid=f.id

            WHERE fo.tableid='{self.tableid}' AND typepreference='badge_fields' AND fo.userid={self.userid} ORDER BY fieldorder
        """
        fields=HelpderDB.sql_query(sql)
        badge_fields=[]
        for field in fields:
            fieldid=field['fieldid']
            value=self.values[fieldid]
            badge_fields.append({"fieldid":fieldid,"value":value})
        return badge_fields
    
    def get_record_card_fields(self):
        sql=f"""
            SELECT f.*
            FROM sys_user_field_order AS fo LEFT JOIN sys_field AS f ON fo.tableid=f.tableid AND fo.fieldid=f.id

            WHERE fo.tableid='{self.tableid}' AND typepreference='insert_fields' AND fo.userid={self.userid} ORDER BY fieldorder
        """
        fields=HelpderDB.sql_query(sql)
        insert_fields=[]
        for field in fields:
            insert_field={}
            fieldid=field['fieldid']
            value=self.values[fieldid]
            if not value:
                value=""
            insert_field['tableid']="1"
            insert_field['fieldid']=fieldid
            insert_field['fieldorder']="1"
            insert_field['description']=field['description']
            insert_field['value']={"code": value, "value": value}
            insert_field['fieldtype']="Parola"
            insert_field['lookupitemsuser']=[
                            {"id": '1', "firstname": 'Mario', "lastname": 'Rossi', "link": 'user', "linkdefield": 'id', "linkedvalue": '1'},
                            {"id": '2', "firstname": 'Luca', "lastname": 'Bianchi', "link": 'user', "linkdefield": 'id', "linkedvalue": '2'}
                        ]
            insert_field["fieldtypewebid"]= "multiselect",
            insert_field['settings']={
                "calcolato": "false",
                "default": "",
                "nascosto": "false",
                "obbligatorio": "false"
            }
            
            insert_fields.append(insert_field)


        return insert_fields