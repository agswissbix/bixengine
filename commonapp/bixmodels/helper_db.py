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
from django.core.mail import send_mail, BadHeaderError, EmailMessage
import os


class HelpderDB:

    @classmethod     
    def insert():
        return True
    
    @classmethod 
    def update():
        return True
    
    @classmethod 
    def sql_query(cls,sql):
        with connections['default'].cursor() as cursor:
            cursor.execute(sql)
            rows = HelpderDB.dictfetchall(cursor)
        return rows
    
    @classmethod 
    def sql_query_row(cls,sql):
        rows=HelpderDB.sql_query(sql)
        if rows:
            return rows[0]
        else:
            return None
    
    @classmethod 
    def sql_query_value(cls,sql,column):
        row=HelpderDB.sql_query_row(sql)
        if row:
            return row[column]
        else:
            return None
        
    @classmethod 
    def sql_execute(cls,sql):
        with connections['default'].cursor() as cursor:
            cursor.execute(sql)
        return True
   
    @classmethod 
    def dictfetchall(cls,cursor):
        "Return all rows from a cursor as a dict"
        columns = [col[0] for col in cursor.description]
        return [
            dict(zip(columns, row))
            for row in cursor.fetchall()
        ]
    
    @classmethod
    def send_email(request=None, emails=None, subject=None, message=None, html_message=None, cc=None, bcc=None, recordid=None, attachment=None):
        # Inizializza CC e BCC solo se non sono forniti
        if cc is None:
            cc = []
        if bcc is None:
            bcc = []

        email_fields = dict()
        email_fields['subject'] = subject
        email_fields['mailbody'] = message
        email_fields['date'] = datetime.datetime.now().strftime('%Y-%m-%d-%H:%M:%S')
        email_fields['timestamp'] = datetime.datetime.now().strftime('%H:%M:%S')
        # Ensure emails is a list
        email_fields['recipients'] = emails if isinstance(emails, (list, tuple)) else emails.split(';')
        email_fields['cc'] = cc
        email_fields['bcc'] = bcc
        email_fields['attachment'] = attachment

        email = EmailMessage(
            subject,
            html_message,
            'bixdata@sender.swissbix.ch',
            email_fields['recipients'],  # Ensure this is a list or tuple
            bcc=bcc,
            cc=cc,
            attachments=attachment
        )
        email.content_subtype = "html"
        if attachment and os.path.exists(attachment):
            email.attach_file(attachment)
      
        send_return = email.send(fail_silently=False)

        with connections['default'].cursor() as cursor:
            cursor.execute("UPDATE user_email SET status = 'Inviata' WHERE recordid_ = %s", [recordid])

        return True
