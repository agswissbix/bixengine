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

    def get_table_records(self,viewid='',searchTerm='', conditions_list=list(),fields=None,offset=0,limit=None,orderby='recordid_ desc'):
        columns = self.get_results_columns()
        fields=[]
        for column in columns:
            fields.append(column['fieldid'])
        records = self.get_records(viewid,searchTerm,conditions_list,fields,offset,limit,orderby,columns)
        return records
    
    def get_table_records_obj(self,viewid='',searchTerm='', conditions_list=list(),fields=None,offset=0,limit=None,orderby='recordid_ desc',master_tableid=None,master_recordid=None):
        if master_tableid and master_recordid:
            conditions_list.append(f"recordid{master_tableid}_='{master_recordid}'")
        if self.tableid == 'contattostabile':
            print('get_table_records_obj')
        records=self.get_table_records(viewid,searchTerm,conditions_list,fields,offset,limit,orderby)
        records_obj=[]
        for record in records:
            record_obj=UserRecord(self.tableid,record['recordid_'],self.userid)
            records_obj.append(record_obj)
        return records_obj
    
    def get_records(self,viewid='',searchTerm='', conditions_list=list(),fields=None,offset=0,limit=None,orderby='recordid_ desc',columns=None):
        """Ottieni elenco record in base ai parametri di ricerca

        Args:
            viewid (str, optional): vista applicata. Defaults to ''.
            searchTerm (str, optional): termine generico da cercare in tutti i campi. Defaults to ''.
            conditions_list (_type_, optional): condizioni specifiche sui campi. Defaults to list().

        Returns:
            _type_: lista di dict dei risultati
        """ 
        select_fields='*'
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
        
        sql=f"SELECT {select_fields} {fromsql} where {conditions}  ORDER BY {orderby} LIMIT 50 "
        records = HelpderDB.sql_query(sql)
        return records
    
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
                                    