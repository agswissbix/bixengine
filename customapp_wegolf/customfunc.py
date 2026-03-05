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

    # DEFAULT DASHBOARD FOR NEW USER
    if tableid == 'golfclub':
        golfclub_record = UserRecord("golfclub", recordid)
        userid = golfclub_record.values.get('utente', None)

        default_userid = 22

        default_dashboards = SysUserDashboardBlock.objects.filter(
            userid_id=default_userid
        ).values_list('dashboardid', flat=True).distinct()

        for dashboard_id in default_dashboards:

            # Verifico se l'utente ha già blocchi per questa dashboard
            user_has_blocks = SysUserDashboardBlock.objects.filter(
                userid_id=userid,
                dashboardid_id=dashboard_id
            ).exists()

            if not user_has_blocks:
                blocks_to_clone = SysUserDashboardBlock.objects.filter(
                    userid_id=default_userid,
                    dashboardid_id=dashboard_id
                )

                for block in blocks_to_clone:
                    block.pk = None              # nuovo record
                    block.userid_id = userid     # assegno all'utente corretto
                    block.save()



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
    if sys_user.email:
        _send_email_reset_password(sys_user)
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
    

def _send_email_reset_password(sys_user: SysUser):
    from commonapp.utils.email_sender import EmailSender

    try:
        if not sys_user or not sys_user.email:
            return

        recipient = sys_user.email
        subject = "Creazione account WeGolf - Imposta la tua password"
        
        # Puoi impostare l'URL della piattaforma qui, o prenderlo dalle variabili di ambiente
        link_web = "https://" + env.str("BIXCUSTOM_DOMAIN")+ ":" + env.str("BIXCUSTOM_NGINX_PORT") + "/forgot-password"

        mailbody = f"""
        <p style="margin:0 0 6px 0;">Ciao {sys_user.firstname},</p>

        <p style="margin:0 0 10px 0;">
            Il tuo account è stato creato con successo. Clicca sul link sottostante per reimpostare la tua password, siccome per ora ne è stata impostata una di default.
        </p>

        <p style="margin:16px 0 0 0;">
            Modifica la tua password tramite il seguente link:
            <br>
            <a href="{link_web}">{link_web}</a>
        </p>

        <p style="margin:10px 0 0 0;">Cordiali saluti,</p>
        <p style="margin:0;">Il team</p>
        """

        email_data = {
            "to": recipient,
            "subject": subject,
            "text": mailbody,
            "cc": "",
            "bcc": "",
            "attachment_relativepath": "",
            "attachment_name": ""
        }

        EmailSender.save_email("user", sys_user.pk, email_data)

    except Exception as e:
        print(f"Error in _send_email_reset_password: {e}")

