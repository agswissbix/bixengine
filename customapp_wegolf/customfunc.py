from django.shortcuts import render
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
import pyodbc
import environ
from django.conf import settings
from commonapp.bixmodels.user_record import *
from commonapp.bixmodels.user_table import *
from commonapp.bixmodels.helper_db import *
from commonapp.helper import *
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from datetime import *
import qrcode
import base64
import pdfkit

from commonapp.helper import Helper
from commonapp.bixmodels.user_record import UserRecord
from commonapp.bixmodels.user_table import UserTable
from commonapp.bixmodels.helper_db import HelpderDB
from customapp_wegolf.script import *

from commonapp import views

# Initialize environment variables
env = environ.Env()
environ.Env.read_env()

def save_record_fields(tableid,recordid, old_record=""):

    # --- NOTIFICATIONS ---
    if tableid == 'notification':
        notification_record = UserRecord('notification', recordid)

        if not notification_record.values['date']:
            notification_record.values['date'] = datetime.datetime.now().strftime("%Y-%m-%d")

        if not notification_record.values['time']:
            notification_record.values['time'] = datetime.datetime.now().strftime("%H:%M")

        create_notification(recordid)

        notification_record.save()



def change_password(request):
    userid = Helper.get_userid(request)
    sys_user = SysUser.objects.filter(id=userid).first()
    if not sys_user:
        return JsonResponse({"success": False, "detail": "User not found"})
    if sys_user.disabled == 'N':
        return JsonResponse({"success": True, "detail": "User is already enabled"})
    sys_user.disabled = 'N'
    return sys_user.save()
    


def new_user(userid):
    sys_user = SysUser.objects.filter(id=userid).first()
    if not sys_user:
        return JsonResponse({"success": False, "detail": "User not found"})
    if sys_user.disabled == 'Y':
        return JsonResponse({"success": True, "detail": "User is already disabled"})
    sys_user.disabled = 'Y'
    return sys_user.save()

def get_user_info(request, page):
    userid = Helper.get_userid(request)
    user = SysUser.objects.filter(id=userid).first()
    return JsonResponse({
        "isAuthenticated": True,
        "username": request.user.username,
        "role": 'admin' if request.user.is_superuser else 'user',
        "chat": '',
        "telefono": '',
        "disabled": True if user.disabled == 'Y' else False
    })
    
