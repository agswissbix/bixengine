from django.contrib.sessions.models import Session
from bixsettings.models import *

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
from django.db.models import OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from .models.database_helper import *
from commonapp.models import *


class SettingsBusinessLogic:
    
    def __init__(self):
        self.test=None
    
    def get_user_tables(self, userid):
        workspaces = dict()

        def _user_order_subqueries(userid):
            """Restituisce subquery per order e id di SysUserTableOrder per un dato utente."""
            base_filter = {
                'tableid': OuterRef('id'),
                'userid': userid
            }
            order_sq = SysUserTableOrder.objects.filter(**base_filter).values('tableorder')[:1]
            id_sq = SysUserTableOrder.objects.filter(**base_filter).values('id')[:1]
            return order_sq, id_sq

        # Subquery utente corrente
        user_order_subquery, user_id_subquery = _user_order_subqueries(userid)

        # Subquery fallback
        fallback_order_subquery, fallback_id_subquery = _user_order_subqueries(1)

        workspace_rows = SysTableWorkspace.objects.all()

        for workspace_row in workspace_rows:
            workspaces[workspace_row.name] = dict()
            workspaces[workspace_row.name]['name'] = workspace_row.name
            workspaces[workspace_row.name]['groupOrder'] = workspace_row.order
            workspace_name = workspace_row.name

            # Annotazione per utente
            tablesdict = SysTable.objects.annotate(
                order=Subquery(user_order_subquery),
                user_order_id=Subquery(user_id_subquery)
            ).filter(
                workspace=workspace_name
            ).order_by(
                'workspace', 'order'
            ).values(
                'id', 'description', 'workspace', 'order', 'user_order_id'
            )

            tablesdict = list(tablesdict)

            # Filtra solo quelle con record valido (user_order_id e order non nulli)
            valid_tables = [t for t in tablesdict if t['user_order_id'] is not None]
            missing_tables_ids = [t['id'] for t in tablesdict if t['user_order_id'] is None]

            if missing_tables_ids:
                fallback_tables_qs = SysTable.objects.annotate(
                    order=Subquery(fallback_order_subquery),
                    fb_order_id=Subquery(fallback_id_subquery)
                ).filter(
                    workspace=workspace_name,
                    id__in=missing_tables_ids
                ).order_by(
                    'workspace', 'order'
                ).values(
                    'id', 'description', 'workspace', 'order', 'fb_order_id'
                )

                fallback_tables = [t for t in fallback_tables_qs if t['fb_order_id'] is not None]
            else:
                fallback_tables = []

            # Pulizia dei campi extra
            for t in valid_tables:
                t.pop('user_order_id', None)
            for t in fallback_tables:
                t.pop('fb_order_id', None)

            # Merge user + fallback e ordinamento finale
            all_tables = valid_tables + fallback_tables
            all_tables = sorted(all_tables, key=lambda x: x['order'] if x['order'] is not None else 99999)

            workspaces[workspace_row.name]['tables'] = all_tables

        return workspaces


    def get_search_column_results(self,userid,tableid, fields_type):
        dbh=DatabaseHelper()
        subquery = SysUserFieldOrder.objects.filter(fieldid=OuterRef('id')).filter(typepreference=fields_type).values('fieldorder')[:1]
        fields=SysField.objects.annotate(order=Subquery(subquery)).filter(tableid=tableid).order_by('order').values('id','fieldid','tableid','order','description')
        
        sql1=f"SELECT sys_field.id,sys_field.fieldid,sys_field.tableid,sys_user_field_order.fieldorder,description,sys_field.label FROM sys_field LEFT JOIN sys_user_field_order ON sys_field.id=sys_user_field_order.fieldid WHERE sys_field.tableid='{tableid}' AND  sys_user_field_order.userid={userid} AND sys_user_field_order.typepreference='{fields_type}' ORDER BY sys_user_field_order.fieldorder"
        fields1=dbh.sql_query(sql1)
        
        sql2=f"""
        SELECT sys_field.id,sys_field.fieldid,sys_field.tableid,NULL AS fieldorder,sys_field.description,sys_field.label
        FROM sys_field
        WHERE tableid='{tableid}' AND sys_field.id
        NOT IN
        (
        SELECT sys_user_field_order.fieldid
        FROM sys_user_field_order
        WHERE
        tableid='{tableid}' AND userid={userid} AND typepreference='{fields_type}'
        )
        ORDER BY sys_field.fieldid
        """
        fields2=dbh.sql_query(sql2)
        
        fields=fields1+fields2
        return fields
    
    def get_usersettings(self,bixid):
        userid=SysUser.objects.get(bixid=bixid).id
        us=UserSettings(userid)
        return us
    
    
class UserSettings:
    userid=0
    record_open_layout='rightcard'
    theme='default'
    active_panel='table'
    def __init__(self,user_id):
        userid=user_id
        
    def get_fieldsorder(tableid,typepreference):
        subquery = SysUserFieldOrder.objects.filter(fieldid=OuterRef('id')).filter(typepreference=typepreference).values('fieldorder')[:1]
        fields=SysField.objects.annotate(order=Subquery(subquery)).filter(tableid=tableid).order_by('order').values('id','fieldid','tableid','order')
        return fields

        
