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
import mimetypes
import os
from django.conf import settings
from django.core.files.storage import default_storage


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
    def send_email(cls, emails=None, subject=None, message=None, html_message='Default', cc=None, bcc=None, recordid=None, attachment=None):
        # Inizializza CC e BCC solo se non sono forniti
        if cc is None:
            cc = []
        if bcc is None:
            bcc = []

        # Ensure emails is a list
        recipients = cls.ensure_list(emails)
        bcc = cls.ensure_list(bcc)
        cc = cls.ensure_list(cc)

        email = EmailMessage(
            subject,
            html_message,
            'bixdata@sender.swissbix.ch',
            recipients,  # Ensure this is a list or tuple
            bcc=bcc,
            cc=cc,
        )
        email.content_subtype = "html"
        if attachment and os.path.exists(attachment):
             # MIME type (fallback esplicito a application/pdf)
            mime, _ = mimetypes.guess_type(attachment)
            mime = mime or "application/pdf"
            email.attach_file(attachment, mimetype=mime)
      
        send_return = email.send(fail_silently=False)

        with connections['default'].cursor() as cursor:
            cursor.execute("UPDATE user_email SET status = 'Inviata' WHERE recordid_ = %s", [recordid])

        return True


    @classmethod 
    def get_upload_fullpath(cls,tableid,recordid,field):
        # Costruisci il percorso corretto del file
        #TODO gestire estensione del file dinamica
        file_path = os.path.join(settings.UPLOADS_ROOT, f"{tableid}/{recordid}/{field}.pdf")
        full_path = default_storage.path(file_path)
        
        return full_path    
        
    @classmethod 
    def get_uploadedfile_fullpath(cls,tableid,recordid,field):
        # Costruisci il percorso corretto del file
        #TODO gestire estensione del file dinamica
        file_path = os.path.join(settings.UPLOADS_ROOT, f"{tableid}/{recordid}/{field}.pdf")
        
        # Verifica che il file esista
        full_path=""
        if default_storage.exists(file_path):
            full_path = default_storage.path(file_path)
        if os.path.exists(full_path):
            return full_path
        else:
            print(f"File non trovato: {file_path}")
            return "File non trovato"
    
    
    @classmethod 
    def get_uploadedfile_relativepath(cls,tableid,recordid,field):
        # Costruisci il percorso corretto del file
        #TODO gestire estensione del file dinamica
        file_path = f"{tableid}/{recordid}/{field}.pdf"
        return file_path
    
    @classmethod
    def ensure_list(cls,value):
        """
        Restituisce sempre una lista di stringhe:
        • None  → []  
        • list/tuple → list(value)  
        • str (con o senza ';') → [..]  (split e strip)
        """
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return list(value)
        # qualunque altro oggetto (tipicamente str)
        return [v.strip() for v in str(value).split(';') if v.strip()]