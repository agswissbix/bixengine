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
from django import template
from bs4 import BeautifulSoup
from django.db.models import OuterRef, Subquery
from functools import wraps
from commonapp.bixmodels.user_record import *

def login_required_api(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        print("sessionid:", request.COOKIES.get("sessionid"))
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapped

class Helper:

    @classmethod     
    def isempty(cls, var):
        if var is None or var=='None' or var=='' or var=='null' or var==0:
            return True
        else:
            return False
        
    @classmethod
    def set_log(userid,action,tableid='',recordid='',informations=''):
        
        try:
            # Ottenere la data nel formato YYYY-MM-DD
            date_now = datetime.now().strftime("%Y-%m-%d")

            # Ottenere l'ora nel formato HH:MM
            time_now = datetime.now().strftime("%H:%M")

            record_log=UserRecord('log')
            record_log.values['date']=date_now
            record_log.values['date']=time_now
            return True

        except Exception as e:
            return False
    
    @classmethod
    def get_userid(cls,request):
        django_userid=request.user.id
        userid = 0
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM sys_user WHERE bixid = %s", [django_userid])
            row = cursor.fetchone()
            if row:
                userid = row[0]
        return userid
    
