import uuid
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.shortcuts import redirect
from datetime import datetime, date, timedelta, time

from django.views.decorators.csrf import csrf_exempt
import json
from django.middleware.csrf import get_token
from django.conf import settings
from django.core.files.storage import default_storage
from django.contrib.auth.decorators import login_required
from functools import wraps

import pytz
from rest_framework.response import Response
from rest_framework import status

from bixsettings.views.businesslogic.models.table_settings import TableSettings
from bixsettings.views.helpers.helperdb import Helperdb
from commonapp.bixmodels import helper_db   
from .bixmodels.user_record import *
from .bixmodels.user_table import *
from commonapp.models import SysCustomFunction, SysUser, SysUserSettings, SysTable
from django.db.models import F, OuterRef, Subquery, IntegerField
from commonapp.helper import *

import pyotp
import qrcode
import base64
from io import BytesIO
from collections import defaultdict
from commonapp.models import UserProfile
from commonapp import helper
import time
from typing import List
import re
import pandas as pd
import pdfkit
from django.http import HttpResponseForbidden
import os
import mimetypes
import shutil
from commonapp.utils.email_sender import EmailSender
from typing import Callable, Dict, List, Sequence, Union, Any
import whois
import dns.resolver
from docx import Document
import environ
import random
from faker import Faker
import xml.etree.ElementTree as ET
import importlib

import pandas as pd
import numpy as np
from pathlib import Path
from PIL import Image
from django.db import transaction, connection
from docxtpl import DocxTemplate
from collections import defaultdict
import json
from django.http import JsonResponse
import locale
from commonapp.bixmodels.helper_db import *

from . import graph_service
from dateutil import parser


env = environ.Env()
environ.Env.read_env()


@csrf_exempt
def test_connection(request):
    response = {
        "Stato": "Connessione riuscita",
    }
    return JsonResponse(response, safe=False)



@ensure_csrf_cookie
def test_connection_get_csrf(request):
    """
    Assicura che venga impostato un cookie CSRF in risposta.
    """
    token = get_token(request)
    print("CSRF Token impostato:", token)
    return JsonResponse({"detail": "CSRF cookie set",'csrftoken': token})

@login_required_api
def test_connection_post(request):
    print("Function: csrf_test_view")
    csrf_header = request.META.get('HTTP_X_CSRFTOKEN')
    print("Header X-CSRFToken:", csrf_header)
    print("Cookie csrftoken:", request.COOKIES.get('csrftoken'))
    print("Session ID:", request.COOKIES.get('sessionid'))
    if request.method == 'GET':
        # La GET serve a far impostare il cookie CSRF dal browser
        return JsonResponse({
            'message': 'CSRF cookie impostato. Usa questo endpoint per inviare la POST.',
            'csrftoken': get_token(request),
        })
    elif request.method == 'POST':
        # La POST è protetta dal middleware CSRF; se il token non è valido, la richiesta fallirà
        try:
            data = json.loads(request.body)
        except Exception:
            data = {}
        return JsonResponse({
            'message': 'POST ricevuta correttamente!',
            'data': data
        })
    else:
        return JsonResponse({'message': 'Metodo non consentito'}, status=405)


@ensure_csrf_cookie
@csrf_exempt
def get_csrf(request):
    """
    Assicura che venga impostato un cookie CSRF in risposta.
    """
    token = get_token(request)
    print("CSRF Token impostato:", token)
    return JsonResponse({"detail": "CSRF cookie set",'csrftoken': token})

@require_POST
def login_view(request):
    print("Function: login_view") 
    print("Header X-CSRFToken:", request.META.get('HTTP_X_CSRFTOKEN'))
    print("Cookie csrftoken:", request.COOKIES.get('csrftoken'))
    print("SessionID:", request.COOKIES.get('sessionid'))

    data = json.loads(request.body)
    username = data.get("username")
    password = data.get("password")

    user = authenticate(request, username=username, password=password)
    
    if user is not None:
        #Temp solution
        activeServer = HelpderDB.sql_query_row("SELECT value FROM sys_settings WHERE setting='cliente_id'")
        if activeServer['value'] == 'telefonoamico':
            recordid_utente=HelpderDB.sql_query_value(f"SELECT recordid_ FROM user_utenti WHERE nomeutente='{username}' AND deleted_='N'",'recordid_')
            record_utente=UserRecord('utenti',recordid_utente)
        #ruolo=record_utente.values['ruolo']
        ruolo = ''
        login(request, user)
        return JsonResponse({"success": True, "detail": "User logged in", "ruolo":ruolo})
    else:
        return JsonResponse({"success": False, "detail": "Invalid credentials"}, status=401)

@login_required_api  
def logout_view(request):
    logout(request)
    # Pulisci la sessione
    request.session.flush()
    
    return JsonResponse({"success": True, "detail": "User logged out"})

@login_required_api  
def user_info(request):
    print("Function: user_info")   
    data = json.loads(request.body) 
    page = data.get("page", "default")
    if request.user.is_authenticated:
        #Temp solution
        activeServer = HelpderDB.sql_query_row("SELECT value FROM sys_settings WHERE setting='cliente_id'")
        if activeServer['value'] == 'telefonoamico':
            sql=f"SELECT * FROM user_utenti WHERE nomeutente='{request.user.username}' AND deleted_='N'"
            record_utente=HelpderDB.sql_query_row(sql)
            nome=record_utente['nome']
            ruolo=record_utente['ruolo']
            
            if page=="/home" and ruolo != 'Amministratore':
                return JsonResponse({
                    "isAuthenticated": False,
                    "username": request.user.username,
                    "name": nome,
                    "role": record_utente['ruolo'],
                    "chat": record_utente['tabchat'],
                    "telefono": record_utente['tabtelefono']
                })
            else:
                return JsonResponse({
                    "isAuthenticated": True,
                    "username": request.user.username,
                    "name": nome,
                    "role": record_utente['ruolo'],
                    "chat": record_utente['tabchat'],
                    "telefono": record_utente['tabtelefono']
                })
        else:
            return JsonResponse({
                "isAuthenticated": True,
                "username": request.user.username,
                "name": '',
                "role": 'admin' if request.user.is_superuser else 'user',
                "chat": '',
                "telefono": ''
            })
    else:
        return JsonResponse({"isAuthenticated": False}, status=401)
        

@login_required_api
def get_user_id(request):
    cliente = Helper.get_cliente_id()
    print("Function: get_cliente_id: ", cliente)   
    return JsonResponse({"cliente": cliente})


@login_required_api  
def get_examplepost(request):  
    print("Function: get_examplepost")
    csrf_header = request.META.get('HTTP_X_CSRFTOKEN')
    print("Header X-CSRFToken:", csrf_header)
    print("Cookie csrftoken:", request.COOKIES.get('csrftoken'))
    if request.method == 'POST':
        try:
            # Decodifica il corpo della richiesta JSON
            data = json.loads(request.body)

            # Crea una risposta basata sui dati ricevuti
            response_data = {
                "responseExampleValue": "Risposta dal backend"
            }

            return JsonResponse(response_data)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=405)


@login_required_api  
def get_sidebarmenu_items(request):
    print("Function: get_sidebarmenu_items")
    tables= SysTable.get_user_tables(1)
    workspaces_tables=dict()
    userid =Helper.get_userid(request)
    for table in tables:
        workspace = table["workspace"]

        
        if workspace not in workspaces_tables:
            workspace_record = SysTableWorkspace.objects.filter(name=table['workspace']).first()
            workspaces_tables[workspace] = {}
            workspaces_tables[workspace]["id"]=table['workspace']
            workspaces_tables[workspace]["title"]=table['workspace']
            workspaces_tables[workspace]["icon"]=workspace_record.icon
            workspaces_tables[workspace]["order"]=table['workspace_order']
        subitem={}
        subitem['id']=table['id']
        subitem['title']=table['description']
        subitem['href']="#"
        subitem['order']=table['table_order']
        if "subItems" not in workspaces_tables[workspace]:
            workspaces_tables[workspace]['subItems']=[]
        workspaces_tables[workspace]["subItems"].append(subitem)

    favorite_tables = HelpderDB.sql_query(f"SELECT * FROM sys_user_favorite_tables WHERE sys_user_id = {userid}")

    username =Helper.get_username(request)
    other_items=[]
    active_server=Helper.get_activeserver(request)['value']
    if active_server == 'belotti':
        other_items.append({
                        "id": "LIFESTYLE",
                        "description": "INSERIMENTO RICHIESTA ACQUISTI"
                    })
        #gruppo=HelpderDB.sql_query_value(f"SELECT gruppo FROM user_sync_adiuto_utenti WHERE utentebixdata='{username}'","gruppo")
        #if gruppo:
         #   formularigruppo=HelpderDB.sql_query(f"SELECT formulari FROM user_sync_adiuto_formularigruppo WHERE gruppo='{gruppo}'")
          #  if formularigruppo:
           #     formulari=formularigruppo[0]['formulari']
            #    lista_formulari_list = formulari.split(",")
             #   for formulario in lista_formulari_list:
              #      other_items.append({
               #         "id": formulario,
                #        "description": formulario
                 #   })

    userid = Helper.get_userid(request)
    response = {
        "menuItems": workspaces_tables,
        "otherItems": other_items,
        "favoriteTables": favorite_tables,
        "userid": userid
    }
    return JsonResponse(response, safe=False)



def check_csrf(request):
    print("Header X-CSRFToken:", request.META.get('HTTP_X_CSRFTOKEN'))
    print("Cookie csrftoken:", request.COOKIES.get('csrftoken'))
    response = {
        "X-CSRFToken": "OK",
    }
    return JsonResponse(response, safe=False)



    

@csrf_exempt
@login_required
def enable_2fa(request):
    user = request.user
    user_profile = user.userprofile  # Ottieni il profilo dell'utente

    if request.method != "POST":
        return JsonResponse({"message": "Metodo non permesso"}, status=405)

    # Controlla se il 2FA è già attivo
    if user_profile.is_2fa_enabled:
        return JsonResponse({"message": "2FA già attivato"}, status=400)

    try:
        # Se 2FA non è attivo, generiamo un nuovo segreto OTP
        secret = pyotp.random_base32()
        user_profile.otp_secret = secret
        user_profile.is_2fa_enabled = True  # Attiva il 2FA
        user_profile.save()  # Salva il profilo con il nuovo segreto

        # Genera l'URL del QR Code
        totp = pyotp.TOTP(secret)
        otp_url = totp.provisioning_uri(name=user.username, issuer_name="Tabellone")

        # Genera il QR Code e convertilo in base64
        img = qrcode.make(otp_url)
        img_io = BytesIO()
        img.save(img_io, format="PNG")
        qr_base64 = base64.b64encode(img_io.getvalue()).decode('utf-8')

        return JsonResponse({"otp_url": otp_url, "qr_code": qr_base64})

    except Exception as e:
        return JsonResponse({"message": f"Errore nel generare il QR: {str(e)}"}, status=500)



@csrf_exempt
@login_required
def verify_2fa(request):
    if request.method != "POST":
        return JsonResponse({"message": "Metodo non permesso"}, status=405)

    # Ottieni i dati JSON
    data = json.loads(request.body)
    otp_token = data.get("otp")
    
    if not otp_token:
        return JsonResponse({"message": "Codice OTP mancante"}, status=400)

    # Ottieni il profilo utente e il segreto OTP
    user_profile = request.user.userprofile  # Ottieni il profilo dell'utente

    if not user_profile.is_2fa_enabled:
        return JsonResponse({"message": "2FA non attivato per questo utente"}, status=400)

    secret = user_profile.otp_secret  # Ottieni il segreto OTP salvato nel profilo

    # Verifica l'OTP
    totp = pyotp.TOTP(secret)
    if totp.verify(otp_token):
        return JsonResponse({"message": "2FA verificato con successo"})
    else:
        return JsonResponse({"message": "Codice OTP errato"}, status=400)
    

@csrf_exempt
@login_required
def disable_2fa(request):
    if request.method != "POST":
        return JsonResponse({"message": "Metodo non permesso"}, status=405)
    
    # Ottieni il profilo utente
    try:
        user_profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        return JsonResponse({"message": "Profilo utente non trovato"}, status=404)

    # Verifica se il 2FA è attivo
    if not user_profile.is_2fa_enabled:
        return JsonResponse({"message": "2FA non è attivo per questo utente"}, status=400)

    # Disabilita il 2FA nel database
    user_profile.is_2fa_enabled = False
    user_profile.save()  # Salva le modifiche al profilo utente

    # Pulisci il segreto dalla sessione, se presente
    if "otp_secret" in request.session:
        del request.session["otp_secret"]
        request.session.save()

    return JsonResponse({"message": "2FA disabilitato con successo"})
    
@csrf_exempt
@login_required
def change_password(request):
    try:
        data = json.loads(request.body)
        old_password = data.get('old_password')
        new_password = data.get('new_password')

        # Verifica che l'utente abbia fornito la password corretta
        if not request.user.check_password(old_password):
            return JsonResponse({'error': 'Password attuale non corretta'}, status=400)

        # Cambia la password
        request.user.set_password(new_password)
        request.user.save()
        
        # Importante: aggiorna la sessione per mantenere l'utente loggato
        update_session_auth_hash(request, request.user)
        
        return JsonResponse({'message': 'Password aggiornata con successo'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@csrf_exempt
def get_active_server(request):
    active_server = HelpderDB.sql_query_row("SELECT value FROM sys_settings WHERE setting='cliente_id'")
    return JsonResponse({"activeServer": active_server['value']})

@csrf_exempt
def delete_record(request):
    try:
        data = json.loads(request.body)
        recordid = data.get("recordid")
        tableid = data.get("tableid")

        if not recordid or not tableid:
            return JsonResponse({"success": False, "detail": "recordid o tableid mancante"}, status=400)

        # Esegui l'UPDATE marcando il record come cancellato
        sql = f"UPDATE user_{tableid} SET deleted_='Y' WHERE recordid_={recordid}"
        HelpderDB.sql_execute(sql)  # usa i parametri per evitare SQL injection

        custom_delete_record(tableid, recordid) 
        return JsonResponse({"success": True, "detail": "Record eliminato con successo"})
    
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "detail": "JSON non valido"}, status=400)
    
    except Exception as e:
        return JsonResponse({"success": False, "detail": f"Errore interno: {str(e)}"}, status=500)

def custom_delete_record(tableid,recordid):
    print("Function: custom_delete_record")
    if tableid=='chart':
        chart_record=UserRecord('chart',recordid)
        chartid=chart_record.values['report_id']
        chart = SysChart.objects.filter(id=chartid).first()
        if not chart:
            return

        dashboard_blocks = SysDashboardBlock.objects.filter(chartid=chart)
        # Per ogni blocco, elimina eventuali record figli
        for block in dashboard_blocks:
            SysUserDashboardBlock.objects.filter(dashboard_block_id=block.id).delete()

        dashboard_blocks.delete()
        chart.delete()
    

@timing_decorator
def get_table_filters(request):
    print('Function: get_table_filters')
    data = json.loads(request.body)
    tableid = data.get("tableid")

    # Utilizza la query SQL fornita
    query = f"""
        SELECT 
            T1.fieldid, 
            T1.fieldtypewebid, 
            T1.description,
            T1.lookuptableid 
        FROM 
            sys_field T1
        JOIN 
            sys_user_field_order T2 ON T1.id = T2.fieldid
        WHERE 
            T2.tableid = '{tableid}' 
        AND 
            T2.typepreference = 'search_fields'
        AND
            T2.fieldorder IS NOT NULL
    """
    
    # Esegui la query
    try:
        filters_data = HelpderDB.sql_query(query)
    except Exception as e:
        print(f"Errore nella query SQL per i filtri: {e}")
        return JsonResponse({"success": False, "error": "Database error"}, status=500)


    for f in filters_data:
        f['lookups'] = []
        lookuptableid = f['lookuptableid']
        if lookuptableid:
            sql = f'SELECT itemcode, itemdesc FROM sys_lookup_table_item WHERE lookuptableid="{lookuptableid}"'
            f['lookups'] = HelpderDB.sql_query(sql)

    response_filters = [
        {
            "fieldid": f['fieldid'],
            "type": f['fieldtypewebid'],
            "label": f['description'],
            'lookups': f['lookups']
        }
        for f in filters_data
    ]

    return JsonResponse({
        "success": True,
        "filters": response_filters
    })


def get_users(request):
    print('Function: get_users')
    data = json.loads(request.body)

    # Costruisci la query SQL
    sql = "SELECT id, firstname, lastname FROM sys_user WHERE disabled = 'N'"

    sql += " ORDER BY firstname LIMIT 50"

    try:
        users = HelpderDB.sql_query(sql)
    except Exception as e:
        print(f"Errore nella query SQL per gli utenti: {e}")
        return JsonResponse({"success": False, "error": "Database error"}, status=500)

    # Prepara la risposta nel formato desiderato dal frontend
    response_users = [
        {
            "userid": user['id'],
            "firstname": user['firstname'],
            "lastname": user['lastname'],
        }
        for user in users
    ]

    return JsonResponse({
        "success": True,
        "users": response_users
    })

@timing_decorator
def get_table_records(request):
    print('Function: get_table_records')
    data = json.loads(request.body)
    tableid = data.get("tableid")
    viewid = data.get("view")
    searchTerm = data.get("searchTerm", '')
    master_tableid = data.get("masterTableid")
    master_recordid = data.get("masterRecordid")
    filtersList = data.get("filtersList", []) # <-- Recupera la filtersList
    pagination= data.get("pagination", {"page": 1, "limit": 10})
    pagination_page= pagination.get("page", 1)
    pagination_limit= pagination.get("limit", 100)
    pagination_offset= (pagination_page-1)*pagination_limit
    order=data.get("order", {"fieldid": "recordid_", "direction": "desc"})
    order_fieldid= order.get("fieldid", "recordid_")
    order_direction= order.get("direction", "desc")

    table = UserTable(tableid, Helper.get_userid(request))

    # Costruisci la clausola WHERE dai filtri
    print(filtersList)
    # 1. Ottieni gli oggetti UserRecord GIA' PROCESSATI
    # Passa i filtri a get_table_records_obj
    if not order_fieldid:
        order_fieldid = 'recordid_'
    if not order_direction:
        order_direction = 'desc'

    record_objects = table.get_table_records_obj(
        viewid=viewid,
        searchTerm=searchTerm,
        master_tableid=master_tableid,
        master_recordid=master_recordid,
        filters_list=filtersList,
        offset=pagination_offset,
        limit=pagination_limit,
        orderby=f"{order_fieldid} {order_direction}"
    )
    
    counter = table.get_total_records_count()
    table_columns = table.get_results_columns()

    # --- BLOCCO ALERT (invariato) ---
    alerts = HelpderDB.sql_query(f"SELECT * FROM sys_alert WHERE tableid='{tableid}' AND alert_type='cssclass'")
    # ... la tua logica per `compiled_alerts` ...
    compiled_alerts = []
    for alert in alerts:
        try:
            cond_str = alert['alert_condition']  # <-- assicurati del nome colonna
            alert_param = json.loads(alert['alert_param'])

            cssclass = alert_param.get('cssclass', '')
            target = alert_param.get('target', 'record')  # 'record' | 'field'
            fieldid = alert_param.get('fieldid', '')

            conds = Helper.parse_sql_like_and(cond_str)  # <-- lista di (field, op, val)

            compiled_alerts.append({
                'conds': conds,
                'cssclass': cssclass,
                'target': target,
                'fieldid': fieldid
            })
        except json.JSONDecodeError:
            print(f"Errore nel decodificare il JSON per l'alert: {alert.get('id')}")
        except ValueError as e:
            print(f"Condizione non valida per alert {alert.get('id')}: {e}")

    # --- COSTRUZIONE RISPOSTA JSON (ORA MOLTO PIU' SEMPLICE) ---
    rows = []
    for record in record_objects:
        row = {
            "recordid": record.recordid,
            "css": "",
            "fields": []
        }

        # --- Logica per CSS (invariata) ---
        values_map = {str(k): v for k, v in record.values.items()}
        record_css = []
        field_css_map = defaultdict(list)
        for a in compiled_alerts:
            if Helper.evaluate_and_conditions(values_map, a["conds"]):
                css_class = a.get("cssclass", "")
                if a.get("target") == "record":
                    record_css.append(css_class)
                else:
                    field_id = str(a.get("fieldid", "")).strip()
                    if field_id:
                        field_css_map[field_id].append(css_class)
        row['css'] = ' '.join(record_css)

        # --- Popola i campi usando i dati pre-calcolati da UserRecord ---
        for column in table_columns:
            fieldid = column.get('fieldid')
            # Recupera la definizione completa del campo dall'oggetto record
            field_definition = record.fields.get(fieldid, {})

            # I valori sono già pronti!
            field_data = {
                "recordid": record.recordid,
                "css": ' '.join(field_css_map.get(str(fieldid), [])),
                "type": field_definition.get("fieldtypewebid", "standard"),
                "value": field_definition.get("convertedvalue", field_definition.get("value")), # Usa il valore convertito
                "fieldid": fieldid,
                
                # Aggiungi le chiavi extra se esistono (ora sono dentro field_definition)
                **{k: v for k, v in field_definition.items() if k in ['userid', 'linkedmaster_tableid', 'linkedmaster_recordid']}
            }
            row["fields"].append(field_data)
        
        rows.append(row)

    # --- Risposta Finale (invariata) ---
    final_columns = [{'fieldtypeid': c['fieldtypewebid'], 'desc': c['description'], 'fieldid': c['fieldid']} for c in table_columns]
    totalPages= (counter + pagination_limit - 1) // pagination_limit  
    response_data = {
        "counter": counter,
        "rows": rows,
        "columns": final_columns,
        "pagination": {
            "currentPage": pagination_page,
            "totalPages": totalPages
        },
        "order": {
            "fieldid": order_fieldid,
            "direction": order_direction
        }
    }
    return JsonResponse(response_data)


def get_sql_condition(field_type, values, condition, field_name):
    """
    Genera la stringa SQL per una singola condizione di filtro.
    """
    sql_parts = []
    
    if field_type in ("Parola", "text"):
        for value in values:
            value = value.replace("'", "''")  # Previene SQL injection
            if condition == "Valore esatto":
                sql_parts.append(f"`{field_name}` = '{value}'")
            elif condition == "Diverso da":
                sql_parts.append(f"`{field_name}` != '{value}'")
            elif condition == "Contiene":
                sql_parts.append(f"`{field_name}` LIKE '%{value}%'")
            elif condition == "Non contiene":
                sql_parts.append(f"`{field_name}` NOT LIKE '%{value}%'")
            # ... altre condizioni per le parole se necessarie
        return " OR ".join(sql_parts)

    elif field_type == "Numero":
        # I valori sono range, es. ["10-20", "30-40"]
        for value in values:
            if '-' in value:
                min_val, max_val = value.split('-')
                sql_parts.append(f"(`{field_name}` BETWEEN {min_val} AND {max_val})")
            else:
                # Tratta come valore singolo
                sql_parts.append(f"`{field_name}` = {value}")
        return " OR ".join(sql_parts)

    elif field_type == "Data":
        # I valori sono range, es. [{"from": "2023-01-01", "to": "2023-01-31"}]
        now = datetime.now()
        
        # Condizioni predefinite
        if condition == "Oggi":
            today_start = now.strftime('%Y-%m-%d 00:00:00')
            today_end = now.strftime('%Y-%m-%d 23:59:59')
            return f"(`{field_name}` BETWEEN '{today_start}' AND '{today_end}')"
        elif condition == "Passato":
            return f"(`{field_name}` < '{now.strftime('%Y-%m-%d %H:%M:%S')}')"
        elif condition == "Futuro":
            return f"(`{field_name}` > '{now.strftime('%Y-%m-%d %H:%M:%S')}')"
        # ... altre condizioni predefinite per le date
        
        # Condizioni su range
        for value in values:
            date_range = json.loads(value)
            from_date = date_range.get('from')
            to_date = date_range.get('to')
            
            if from_date and to_date:
                sql_parts.append(f"(`{field_name}` BETWEEN '{from_date}' AND '{to_date}')")
            elif from_date:
                sql_parts.append(f"`{field_name}` >= '{from_date}'")
            elif to_date:
                sql_parts.append(f"`{field_name}` <= '{to_date}'")
        return " OR ".join(sql_parts)
    
    # Gestione delle condizioni "Nessun valore" e "Almeno un valore"
    if condition == "Nessun valore":
        return f"(`{field_name}` IS NULL OR `{field_name}` = '')"
    elif condition == "Almeno un valore":
        return f"(`{field_name}` IS NOT NULL AND `{field_name}` != '')"

    return ""


@timing_decorator
def get_table_records_kanban(request):
    print('Function: get_table_records_kanban')
    data = json.loads(request.body)
    tableid = data.get("tableid")
    viewid = data.get("view")
    searchTerm = data.get("searchTerm")
    master_tableid = data.get("masterTableid")
    master_recordid = data.get("masterRecordid")

    table = UserTable(tableid, Helper.get_userid(request))

    

    record_objects = table.get_table_records_obj(
        viewid=viewid,
        searchTerm=searchTerm,
        master_tableid=master_tableid,
        master_recordid=master_recordid,
        limit=100000
    )

    #TODO rendere dinamico tramite i settings
    grouping_field = 'dealstage' 
    grouped_records = defaultdict(list)

    for record in record_objects:
        # Ottieni il valore del campo per il raggruppamento
        # Assumiamo che UserRecord abbia un metodo come get_value() o l'accesso tramite attributo
        grouping_key = record.values.get(grouping_field) 
        
        # Aggiungi il record alla lista corrispondente alla sua chiave
        grouped_records[grouping_key].append(record)

    column_definitions = [
        {"title": "Appuntamento", "id": "Appuntamento", "color": "bg-pink-100", "editable": True},
        {"title": "Offerta inviata", "id": "Offerta inviata", "color": "bg-pink-100", "editable": True},
        {"title": "Tech validation", "id": "Tech validation", "color": "bg-yellow-100", "editable": True},
        {"title": "Credit Check", "id": "Credit Check", "color": "bg-yellow-100", "editable": True},
        {"title": "Ordine materiale", "id": "Ordine materiale", "color": "bg-blue-100", "editable": True},
        {"title": "Progetto in corso", "id": "Progetto in corso", "color": "bg-blue-300", "editable": True},
        {"title": "Verifica saldo progetto", "id": "Verifica saldo progetto", "color": "bg-green-50", "editable": True},   
        {"title": "Progetto fatturato", "id": "Progetto fatturato", "color": "bg-green-200", "editable": True},
    ]     

    response_data = {
        "id": "1", # O un ID dinamico per la tua board
        "isDraggable": True,
        "columns": []
    }

    # Itera sulle definizioni per mantenere l'ordine corretto
    for index, col_def in enumerate(column_definitions):
        column_title = col_def['title']
        
        # Prendi la lista di record per questa colonna dai dati raggruppati
        records_in_group = grouped_records[column_title]
        
        # Prepara la lista di "tasks" per questa colonna
        tasks_list = []
        # NON SERVE PIÙ: locale.setlocale(locale.LC_ALL, 'it_IT.UTF-8')
        venduto = 0
        margine_effettivo = 0
        
        for record in records_in_group:
            # Trasforma ogni oggetto UserRecord nel formato "task" richiesto
            task_data = {
                "recordid": record.values.get("recordid_"),
                "css": "",
                "fields": {
                    record.fields['reference']['description']: record.fields['reference']['convertedvalue'],
                    record.fields['closedate']['description']: record.fields['closedate']['convertedvalue'],
                    record.fields['amount']['description']: record.fields['amount']['convertedvalue'],
                }
            }
            tasks_list.append(task_data)
            venduto += float(record.fields['amount']['value']) if record.fields['amount']['value'] else 0
            margine_effettivo += float(record.fields['effectivemargin']['value']) if record.fields['effectivemargin']['value'] else 0

        # NUOVO MODO DI FORMATTARE I NUMERI
        # Formatta con la virgola come separatore delle migliaia e il punto per i decimali (standard USA)
        # Esempio: 1234.56 -> "1,234.56"
        formatted_venduto_usa = f"{venduto:,.2f}"
        formatted_margine_usa = f"{margine_effettivo:,.2f}"

        # Sostituisci i separatori per ottenere il formato italiano
        # Esempio: "1,234.56" -> "1.234,56"
        formatted_venduto = formatted_venduto_usa.replace(",", "TEMP").replace(".", ",").replace("TEMP", ".")
        formatted_margine = formatted_margine_usa.replace(",", "TEMP").replace(".", ",").replace("TEMP", ".")

        aggregatefunctions = [
            {"title": "Venduto", "value": formatted_venduto},
            {"title": "Margine effettivo", "value": formatted_margine}
        ]
        
        # Costruisci l'oggetto completo della colonna
        column_data = {
            "id": col_def['id'],
            "title": column_title,
            "color": col_def['color'],
            "order": index,
            "editable": col_def['editable'],
            "tasks": tasks_list,
            "aggregatefunctions": aggregatefunctions
        }
        
        response_data["columns"].append(column_data)


    return JsonResponse(response_data)


def get_calendar_records(request):
    print('Function: get_calendar_records')
    data = json.loads(request.body)
    tableid = data.get("tableid")
    viewid = data.get("view")
    searchTerm = data.get("searchTerm")
    master_tableid = data.get("masterTableid")
    master_recordid = data.get("masterRecordid")

    table = UserTable(tableid, Helper.get_userid(request))

    if not viewid:
        viewid = table.get_default_viewid()

    # 1. Ottieni gli oggetti UserRecord con i dati grezzi
    # Questo metodo è già ottimizzato per caricare i dati base in una sola query.
    record_objects = table.get_table_records_obj(
        viewid=viewid,
        searchTerm=searchTerm,
        conditions_list=[], # La lista viene creata dentro il metodo
        master_tableid=master_tableid,
        master_recordid=master_recordid
    )

    response_data = {
        "counter": len(record_objects),
        "rows": [],
        "columns": [
            { "fieldtypeid": 'Testo', "desc": 'Event Title' },
            { "fieldtypeid": 'Data', "desc": 'Start Date' },
        ]
    }

    if tableid == 'assenze':
        # --- VARIABILI PER ORARI CONFIGURABILI ---
        # Qui puoi definire gli orari che preferisci
        orario_inizio = datetime.time(7, 0)  # Ore 07:00
        orario_fine = datetime.time(20, 0) # Ore 20:00
        # -----------------------------------------

        for record in record_objects:
            start_value = record.values.get('dal')
            end_value = record.values.get('al')

            if not isinstance(start_value, date) or not isinstance(end_value, date):
                continue

            giorno_corrente = start_value
            while giorno_corrente <= end_value:
                row = {}
                row['recordid'] = record.recordid
                tipo_assenza=record.fields['tipo_assenza']['convertedvalue']
                row['title'] = record.fields['recordiddipendente_']['convertedvalue'] + ' - ' + tipo_assenza  # Assicurati che questo campo esista
                
                # Combina la data corrente con gli orari definiti sopra
                row['startDate'] = datetime.datetime.combine(giorno_corrente, orario_inizio).isoformat()
                row['endDate'] = datetime.datetime.combine(giorno_corrente, orario_fine).isoformat()
                
                row['css'] = 'bg-green-100 border-l-4 border-red-500 text-red-800 dark:bg-red-900/50 dark:border-red-400 dark:text-red-200'
                if tipo_assenza=='Vacanza':
                    row['css'] = 'bg-green-100 border-l-4 border-green-500 text-green-800 dark:bg-green-900/50 dark:border-green-400 dark:text-green-200'
                if tipo_assenza=='Malattia':
                    row['css'] = 'bg-red-100 border-l-4 border-red-500 text-red-800 dark:bg-red-900/50 dark:border-red-400 dark:text-red-200'
                row['fields'] = []
                response_data['rows'].append(row)
                
                giorno_corrente += timedelta(days=1)

    if tableid == 'bollettini':
        # --- VARIABILI PER ORARI CONFIGURABILI ---
        # Qui puoi definire gli orari che preferisci
        orario_inizio = datetime.time(7, 0)  # Ore 07:00
        orario_fine = datetime.time(20, 0) # Ore 20:00
        # -----------------------------------------

        for record in record_objects:
            tipo_bollettino = record.values.get('tipo_bollettino')
            if tipo_bollettino=='Sostituzione':
                start_value = record.values.get('sostituzionedal')
                end_value = record.values.get('sostituzioneal')
            else:
                start_value = record.values.get('data')
                end_value = record.values.get('data')

            if not isinstance(start_value, date) or not isinstance(end_value, date):
                continue

            giorno_corrente = start_value
            while giorno_corrente <= end_value:
                row = {}
                row['recordid'] = record.recordid
                row['title'] = record.fields['recordidstabile_']['convertedvalue'] + ' - ' + record.fields['recordiddipendente_']['convertedvalue']  # Assicurati che questo campo esista
                
                # Combina la data corrente con gli orari definiti sopra
                row['startDate'] = datetime.datetime.combine(giorno_corrente, orario_inizio).isoformat()
                row['endDate'] = datetime.datetime.combine(giorno_corrente, orario_fine).isoformat()
                
                row['css'] = 'bg-gray-100 border-l-4 border-gray-500 text-gray-800 dark:bg-gray-900/50 dark:border-gray-400 dark:text-gray-200'
                if tipo_bollettino=='Sostituzione':
                    row['css'] = 'bg-blue-100 border-l-4 border-blue-500 text-blue-800 dark:bg-blue-900/50 dark:border-blue-400 dark:text-blue-200'
                if tipo_bollettino=='Generico':
                    row['css'] = 'bg-gray-100 border-l-4 border-gray-500 text-gray-800 dark:bg-gray-900/50 dark:border-gray-400 dark:text-gray-200'
                if tipo_bollettino=='Pulizia':
                    row['css'] = 'bg-blue-200 border-l-4 border-blue-500 text-blue-800 dark:bg-blue-900/50 dark:border-blue-400 dark:text-blue-200'
                if tipo_bollettino=='Giardino':
                    row['css'] = 'bg-green-200 border-l-4 border-green-500 text-green-800 dark:bg-green-900/50 dark:border-green-400 dark:text-green-200'
                row['fields'] = []
                response_data['rows'].append(row)
                
                giorno_corrente += timedelta(days=1)
                
    response_data['counter'] = len(response_data['rows'])
    return JsonResponse(response_data)

def get_graph_users():
    """
    Ottiene gli utenti Bixdata che hanno una corrispondenza su Graph.
    """
    graph_users = graph_service.get_all_users()
    
    if isinstance(graph_users, dict) and 'error' in graph_users:
        return {"error": graph_users['error']}
    
    # Enable sync just for valids Bixdata's users
    valid_users = []
    for user in graph_users:
        try:
            local_user = SysUser.objects.get(email=user.get('mail'))
            if (local_user):
                valid_users.append(user)
        except SysUser.DoesNotExist:
            continue

    return valid_users

def get_delta_link_from_db(event_owner):
    """
    Ottiene i delta link dell'utente dal DB locale.
    """
    event = UserEvents.objects.filter(owner=event_owner).exclude(calendar_delta_link__isnull=True).exclude(calendar_delta_link='').order_by('-id').first()
    return event.calendar_delta_link if event else None

def save_delta_link_to_db(event_owner, new_delta_link):
    """
    Aggiorna i delta link dell'utente nel DB locale.
    """
    UserEvents.objects.filter(owner=event_owner).update(calendar_delta_link=new_delta_link)

def _parse_graph_datetime(graph_datetime_data, target_timezone='Europe/Zurich'):
    """
    Esegue il parsing di un oggetto data/ora di Graph (UTC)
    e lo converte in un oggetto datetime 'naive' (senza fuso orario)
    rappresentante l'ora corretta nel fuso orario 'Europe/Zurich'.
    """
    if not graph_datetime_data:
        return None

    date_str = graph_datetime_data.get('dateTime') or graph_datetime_data.get('date')
    if not date_str:
        return None

    try:
        dt_object = parser.isoparse(date_str) 
    except ValueError as e:
        print(f"Errore di parsing ISO per data '{date_str}': {e}")
        return None

    if dt_object.tzinfo is None or dt_object.tzinfo.utcoffset(dt_object) is None:
        dt_object = pytz.utc.localize(dt_object)
    
    try:
        target_tz = pytz.timezone(target_timezone)
    except pytz.UnknownTimeZoneError:
        print(f"ATTENZIONE: Fuso orario '{target_timezone}' sconosciuto. Uso UTC per la conversione.")
        target_tz = pytz.utc 

    dt_object_converted = dt_object.astimezone(target_tz)

    return dt_object_converted.replace(tzinfo=None)

def _prepare_datetime_for_graph(naive_dt: datetime, tz_name: str = 'Europe/Zurich') -> str:
    """
    Rende un datetime naive (assunto essere in tz_name) aware e lo converte in UTC,
    restituendo la stringa ISO formattata.
    """
    if naive_dt is None:
        return None
        
    local_tz = pytz.timezone(tz_name)

    try:
        aware_dt = local_tz.localize(naive_dt, is_dst=None) 
    except pytz.exceptions.AmbiguousTimeError:
        aware_dt = local_tz.localize(naive_dt, is_dst=False)
    
    return aware_dt.isoformat(timespec='seconds')

def _map_and_save_event(event_data, user_email):
    """
    Mappa i dati dell'evento da Graph al modello UserEvents e li salva.
    """
    try:
        preferred_timezone = 'Europe/Zurich'
        
        body_content = event_data.get('body', {}).get('content', '')
        categories = event_data.get('categories', [])
        
        table_id = 'task'
        lower_categories = [cat.lower() for cat in categories]
        
        # TODO: da cambiare
        if 'task' in lower_categories:
            table_id = 'task'
        elif 'assenze' in lower_categories:
            table_id = 'assenze'

        calendar_id = event_data.get('calendar', {}).get('id')
        
        event = UserEvents.objects.filter(graph_event_id=event_data.get('id')).first()

        user_id = 0
        sys_user = None
        try:
            sys_user = SysUser.objects.get(email=user_email)
            if sys_user:
                user_id = sys_user.id
            elif event:
                user_id = event.user_id
        except SysUser.DoesNotExist:
            print(f"Utente Bixdata '{user_email}' non trovato nel DB locale.")
            if event:
                user_id = event.user_id
        
        graph_id = event_data.get('id')
        calendar_id = event_data.get('calendar', {}).get('id')
        subject = event_data.get('subject')
        body_content = event_data.get('body', {}).get('content', '')
        
        start_dt = _parse_graph_datetime(event_data.get('start'), preferred_timezone)
        end_dt = _parse_graph_datetime(event_data.get('end'), preferred_timezone)

        organizer_email = event_data.get('organizer', {}).get('emailAddress', {}).get('address')
        categories_str = ", ".join(event_data.get('categories', []))

        if event:
            saved_event = UserRecord('events', event.record_id) 
            
            saved_event.values['user_id'] = user_id
            saved_event.values['table_id'] = table_id
            saved_event.values['owner'] = user_email
            saved_event.values['subject'] = subject
            saved_event.values['body_content'] = body_content
            saved_event.values['start_date'] = start_dt
            saved_event.values['end_date'] = end_dt
            saved_event.values['timezone'] = preferred_timezone 
            saved_event.values['organizer_email'] = organizer_email
            saved_event.values['categories'] = categories_str
            saved_event.values['m365_calendar_id'] = calendar_id
            saved_event.values['graph_event_id'] = graph_id

            saved_event.save() 
            created = False
        else:
            saved_event = UserRecord('events')
            
            saved_event.values['user_id'] = user_id
            saved_event.values['table_id'] = table_id
            saved_event.values['owner'] = user_email
            saved_event.values['subject'] = subject
            saved_event.values['body_content'] = body_content
            saved_event.values['start_date'] = start_dt
            saved_event.values['end_date'] = end_dt
            saved_event.values['timezone'] = preferred_timezone 
            saved_event.values['organizer_email'] = organizer_email
            saved_event.values['categories'] = categories_str
            saved_event.values['m365_calendar_id'] = calendar_id
            saved_event.values['graph_event_id'] = graph_id

            saved_event.save()
            created = True

        return saved_event, created

    except Exception as e:
        print(f"Errore durante il salvataggio/aggiornamento dell'evento {event_data.get('id')}: {e}")
        return None, False
    
def initial_graph_calendar_sync(request):
    """
    Sincronizzazione iniziale degli eventi del calendario con il DB Bixdata.
    Da utilizzare solo quando il DB è vuoto.
    """
    print('Function: initial_graph_calendar_sync')

    graph_users = get_graph_users()
    
    if isinstance(graph_users, dict) and 'error' in graph_users:
        return JsonResponse({"success": False, "detail": f"Errore Graph: {graph_users['error']}"}, status=500)
    
    if not graph_users:
        return JsonResponse({"success": False, "detail": "Nessun utente trovato da Microsoft Graph"}, status=404)
    
    start_date = datetime.datetime.now().replace(day=1, hour=0, minute=0, second=0).isoformat()
    end_date = (datetime.datetime.now() + datetime.timedelta(days=365)).isoformat()
    
    total_events_merged = 0
    total_events_downloaded = 0
    users_synced_count = 0

    graph_users_map = {u.get('mail'): u for u in graph_users if u.get('mail')}

    # Sincronizzazione in uscita (da Bixdata a Microsoft 365)
    local_unsynced_events = UserEvents.objects.filter(graph_event_id__isnull=True).exclude(owner__isnull=True)
    
    events_by_owner = {}
    for event in local_unsynced_events:
        if event.owner not in events_by_owner:
            events_by_owner[event.owner] = []
        events_by_owner[event.owner].append(event)

    for owner_email, events_to_promote in events_by_owner.items():
        if owner_email not in graph_users_map:
            print(f"Utente '{owner_email}' non trovato su Graph, saltata promozione.")
            continue

        for local_event in events_to_promote:
            try:
                splitted_categories = local_event.categories.split(', ') if local_event.categories else []

                if not local_event.timezone:
                    local_event.timezone = 'Europe/Zurich'
                    local_event.save()

                if local_event.start_date and not local_event.end_date:
                    local_event.end_date = local_event.start_date
                    local_event.save()

                if local_event.end_date and not local_event.start_date:
                    local_event.start_date = local_event.end_date
                    local_event.save()

                if not local_event.start_date and not local_event.end_date:
                    continue

                result = graph_service.create_calendar_event(
                    user_email=owner_email,
                    subject=local_event.subject,
                    start_time=local_event.start_date.isoformat(),
                    end_time=local_event.end_date.isoformat(),
                    body_content=local_event.body_content,
                    timezone=local_event.timezone,
                    organizer_email=local_event.organizer_email,
                    categories=splitted_categories
                )
                
                if "error" not in result:
                    local_event.graph_event_id = result.get('id')
                    local_event.m365_calendar_id = result.get('calendar', {}).get('id')
                    local_event.save()
                    total_events_merged += 1
                else:
                    print(f"AVVISO: Creazione su Outlook fallita per '{local_event.subject}' ({owner_email}): {result['error']}")

            except Exception as e:
                 print(f"Errore grave durante la promozione di un evento: {e}")

    # Sincronizzazione in entrata (da MS 365/Graph a Bixdata)
    for graph_user in graph_users:
        user_email = graph_user.get('mail')
        
        if not user_email:
            continue

        events = graph_service.get_events_for_user(user_email, start_date, end_date)
        
        if isinstance(events, dict) and 'error' in events:
            continue

        if events:
            for event in events:
                _map_and_save_event(event, user_email)
                total_events_downloaded += 1
            
            users_synced_count += 1

    # TODO: gestire salvataggio in tabelle specifiche tramite categorizzazione
    # TODO: creazione iniziale eventi da tabelle specifiche (ed eventuale merge)

    return JsonResponse({
        "success": True, 
        "detail": f"Merge completato. {total_events_merged} locali promossi. Scaricati/Aggiornati {total_events_downloaded} eventi M365 ({users_synced_count} utenti)."
    })

def sync_graph_calendar(request):
    """
    Sincronizza gli eventi del calendario di un utente Outlook con il DB Bixdata
    usando i delta query.
    """
    print('Function: sync_graph_calendar')

    graph_users = get_graph_users()
    
    if isinstance(graph_users, dict) and 'error' in graph_users:
        return JsonResponse({"success": False, "detail": f"Errore Graph: {graph_users['error']}"}, status=500)
    
    if not graph_users:
        return JsonResponse({"success": False, "detail": "Nessun utente trovato da Microsoft Graph"}, status=404)
    
    start_date = datetime.datetime.now().replace(day=1, hour=0, minute=0, second=0).isoformat()
    end_date = (datetime.datetime.now() + datetime.timedelta(days=365)).isoformat()
    
    total_users_synced = 0
    
    for graph_user in graph_users:
        user_email = graph_user.get('mail')
        
        if not user_email:
            print(f"Utente senza email principale, saltato.")
            continue

        local_unsynced_events = UserEvents.objects.filter(owner=user_email, graph_event_id__isnull=True)
        promoted_count = 0
        
        if local_unsynced_events.exists():
            print(f"-> Trovati {local_unsynced_events.count()} eventi locali da sincronizzare per {user_email}.")
            
            for local_event in local_unsynced_events:
                try:

                    table=local_event.values['table_id']
                    subject=local_event.values['subject']
                    start_date=local_event.values['start_date']
                    end_date=local_event.values['end_date']
                    user=local_event.values['user_id']
                    owner=local_event.values['owner']
                    body_content=local_event.values['body_content']
                    timezone=local_event.values['timezone']
                    organizer_email=local_event.values['organizer_email']
                    categories=local_event.values['categories'].split(',')

                    if not timezone:
                        timezone = 'Europe/Zurich'

                    if not end_date and start_date:
                        end_date = start_date

                    if not start_date and end_date:
                        start_date = end_date

                    if not start_date and not end_date:
                        continue

                    event_data = {
                        'table': table,
                        'subject': subject,
                        'start_date': start_date,
                        'end_date': end_date,
                        'user': user,
                        'owner': owner,
                        'body_content': body_content,
                        'timezone': timezone,
                        'organizer_email': organizer_email,
                        'categories': categories,
                    }

                    result = create_event(event_data)
                    
                    if "error" not in result:
                        local_event.graph_event_id = result.get('id')
                        local_event.m365_calendar_id = result.get('calendar', {}).get('id')
                        local_event.save()
                        promoted_count += 1
                        print(f"   Sincronizzato: {local_event.subject}")
                    else:
                        print(f"   AVVISO: Sincronizzazione fallita per '{local_event.subject}'. Errore: {result['error']}")

                except Exception as e:
                     print(f"Errore grave durante la sincronizzazione di un evento: {e}")
        
        delta_link = get_delta_link_from_db(user_email)
        is_fully_synced = delta_link is None
        
        print(f"-> Sincronizzazione utente: {user_email}. Delta Link: {is_fully_synced and 'None (Full Sync)' or 'Exists'}")

        delta_result = graph_service.get_calendar_view_delta(user_email, start_date, end_date, delta_link)

        if isinstance(delta_result, dict) and 'error' in delta_result:
            print(f"   Errore per {user_email}: {delta_result.get('error')}.")
            continue

        events_from_graph = delta_result.get('value', [])

        if is_fully_synced:
            graph_event_ids = {e['id'] for e in events_from_graph if e.get('@removed') is None}
            UserEvents.objects.filter(owner=user_email).exclude(graph_event_id__in=graph_event_ids).delete()

        for event_data in events_from_graph:
            if event_data.get('@removed', {}).get('reason') == 'deleted':
                UserEvents.objects.filter(graph_event_id=event_data.get('id')).delete()
            else:
                _map_and_save_event(event_data, user_email)

        if '@odata.deltaLink' in delta_result:
            save_delta_link_to_db(user_email, delta_result['@odata.deltaLink'])
        
        total_users_synced += 1

    return JsonResponse({
        "success": True, 
        "detail": f"Sincronizzazione Delta Batch completata. {total_users_synced} utenti processati."
    })
    
def create_event(event_data):
    """
    Crea un nuovo evento su Microsoft Graph.
    """
    print('Function: create_event')

    user_id = event_data.get('user', None)
    table = event_data.get('table', None)
    owner = event_data.get('owner', None)
    subject = event_data.get('subject', None)
    body_content = event_data.get('body_content', None)
    start_date = event_data.get('start_date', None)
    end_date = event_data.get('end_date', None)
    categories = event_data.get('categories', [])
    timezone = event_data.get('timezone')
    organizer_email = event_data.get('organizer_email')

    if not timezone:
        timezone = 'Europe/Zurich'

    if user_id and not owner:
        user = SysUser.objects.get(id=user_id)
        if user:
            owner = user.email

    if not all([owner, subject, start_date, end_date]):
        return {"error": "Parametri mancanti per creare l'evento."}

    start_time_utc_str = _prepare_datetime_for_graph(start_date, timezone)
    end_time_utc_str = _prepare_datetime_for_graph(end_date, timezone)

    result = graph_service.create_calendar_event(
        user_email=owner,
        subject=subject,
        start_time=start_time_utc_str,
        end_time=end_time_utc_str,
        body_content=body_content,
        categories=categories,
        timezone=timezone,
        organizer_email=organizer_email
    )

    if "error" in result:
        print(f"Errore durante la creazione dell'evento su Graph: {result['details']}")
        return result

    return result

def update_event(event_data):
    """
    Aggiorna un evento esistente su Microsoft Graph.
    """
    print('Function: update_event')

    graph_event_id = event_data.get('graph_event_id')
    owner = event_data.get('owner')
    user_id = event_data.get('user')

    event = UserEvents.objects.filter(graph_event_id=graph_event_id).first()
    if not event:
        print(f"Evento con ID Graph {graph_event_id} non trovato nel DB locale.")
        return None

    if owner and (event.owner != owner):
        event = change_event_owner(graph_event_id, owner, user)
        graph_event_id = event.get('graph_event_id')
        if graph_event_id:
            owner = event.get('owner')

    if user_id and not owner:
        user = SysUser.objects.get(id=user_id)
        if user:
            owner = user.email

    if not graph_event_id or not owner:
        return {"error": "graph_event_id e owner sono obbligatori per l'aggiornamento."}

    subject = event_data.get('subject')
    body_content = event_data.get('body_content')
    start_date = event_data.get('start_date')
    end_date = event_data.get('end_date')
    categories = event_data.get('categories') 
    timezone = event_data.get('timezone', 'Europe/Zurich')
    organizer_email = event_data.get('organizer_email')


    if not timezone:
        timezone = 'Europe/Zurich'

    if not end_date and start_date:
        end_date = start_date

    if not start_date and end_date:
        start_date = end_date

    start_time_utc_str = _prepare_datetime_for_graph(start_date, timezone)
    end_time_utc_str = _prepare_datetime_for_graph(end_date, timezone)

    result = graph_service.update_calendar_event(
        user_email=owner,
        event_id=graph_event_id,
        subject=subject,
        start_time=start_time_utc_str,
        end_time=end_time_utc_str,
        body_content=body_content,
        categories=categories,
        timezone=timezone,
        organizer_email=organizer_email
    )

    if "error" in result:
        print(f"Errore durante l'aggiornamento dell'evento su Graph: {result.get('details')}")
        return result

    return result

def delete_event(owner, event_id):
    """
    Cancella un evento esistente su Microsoft Graph.
    """
    print('Function: delete_event')

    if not owner or not event_id:
        return Response(
            {"error": "Dati mancanti"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    result = graph_service.delete_event(owner, event_id)

    if "error" in result:
        if isinstance(result.get("details"), dict) and result["details"].get("error", {}).get("code") == "ErrorItemNotFound":
            return Response({"error": f"Evento con ID {event_id} non trovato."}, status=status.HTTP_404_NOT_FOUND)
        return Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response(status=status.HTTP_204_NO_CONTENT)

def change_event_owner(event_id, new_owner):
    """
    Cambia l'owner di un evento esistente su Microsoft Graph e nel DB locale.
    """
    # TODO: controllare che funzioni correttamente
    print('Function: change_event_owner')

    if not event_id or not new_owner:
        print("DAti mancanti per il cambio di utente")
        return None
    
    event = UserEvents.objects.filter(graph_event_id=event_id).first()
    if not event:
        print(f"Evento con ID Graph {event_id} non trovato nel DB locale.")
        return None
    
    old_owner = event.owner

    result = graph_service.delete_event(old_owner, event_id)
    if "error" in result:
        print(f"Errore durante la cancellazione dell'evento su Graph: {result.get('details')}")
        return result

    result = graph_service.create_calendar_event(
        user_email=new_owner,
        subject=event.subject,
        start_time=event.start_date.isoformat(),
        end_time=event.end_date.isoformat(),
        body_content=event.body_content,
        categories=event.categories,
        timezone=event.timezone
    )

    if "error" in result:
        print(f"Errore durante la creazione dell'evento su Graph: {result.get('details')}")
        event.graph_event_id = None
        event.save()

        return result
    
    event.graph_event_id = result.get('id')
    event.owner = new_owner

    user = SysUser.objects.get(email=new_owner).first()
    if user:
        event.user_id = user.id if user else None

    event.save()

    return event

def get_records_matrixcalendar(request):
    print('Function: get_records_matrixcalendar')
    data = json.loads(request.body)
    tableid = data.get("tableid")
    viewid = data.get("view")
    searchTerm = data.get("searchTerm")
    master_tableid = data.get("masterTableid")
    master_recordid = data.get("masterRecordid")

    userid = Helper.get_userid(request)

    table = UserTable(tableid, userid)

    if not viewid:
        viewid = table.get_default_viewid()

    # 1. Ottieni gli oggetti UserRecord con i dati grezzi
    # Questo metodo è già ottimizzato per caricare i dati base in una sola query.
    record_objects = table.get_table_records_obj(
        viewid=viewid,
        searchTerm=searchTerm,
        conditions_list=[], # La lista viene creata dentro il metodo
        master_tableid=master_tableid,
        master_recordid=master_recordid,
    )

    response_data_dev = {
        'resources': [],
        'events': [],
        'unplannedEvents': [],
        'viewMode': 'Settimanale',
        'counter': len(record_objects),
    }

    processed_resources = set()
    
    available_colors = [
        '#3b82f6',  # Blu
        '#ef4444',  # Rosso
        '#eab308',  # Giallo
        '#10b981',  # Verde
        '#8b5cf6',  # Viola
        '#f97316',  # Arancione
        '#ec4899',  # Rosa
        '#14b8a6',  # Turchese
    ]

    # Dizionario globale o definito prima del loop
    dynamic_colors = {}

    def get_color_for_title(title):
        if title not in dynamic_colors:
            if available_colors:
                # Se ci sono ancora colori disponibili, prendine uno
                color = available_colors.pop(0)
            else:
                # Se finiscono, genera un colore casuale (fallback)
                color = "#{:06x}".format(random.randint(0, 0xFFFFFF))
            dynamic_colors[title] = color
        return dynamic_colors[title]

    tablesettings_obj = TableSettings(tableid=tableid, userid=userid)
    tablesettings = tablesettings_obj.get_settings()

    response_data_dev['viewMode'] = tablesettings.get('table_planner_default_view', 'week').get('value')

    title_field = tablesettings.get('table_planner_title_field').get('value')
    color_field = tablesettings.get('table_planner_color_field').get('value')
    resource_field = tablesettings.get('table_planner_resource_field').get('value')
    date_from_field = tablesettings.get('table_planner_date_from_field').get('value')
    date_to_field = tablesettings.get('table_planner_date_to_field').get('value')
    time_from_field = tablesettings.get('table_planner_time_from_field').get('value')
    time_to_field = tablesettings.get('table_planner_time_to_field').get('value')
    if not date_from_field:
        return JsonResponse({"error": "Non è stato configurato alcun campo di tipo data."}, status=400)

    for record in record_objects:
        # Estrae il valore della risorsa dal record corrente
        resource_id = record.fields[resource_field]['value']
        resource_value = record.fields[resource_field]['convertedvalue']
                
        # Se il dipendente non è ancora stato processato, aggiungilo alla lista 'resources'.
        if resource_id not in processed_resources:
            response_data_dev['resources'].append({
                'id': resource_id,
                'name': resource_value
            })
            processed_resources.add(resource_id) # Aggiungi l'ID al set per non ripeterlo
            
        # 3. Creazione degli Eventi (Assenze)
        record_id = record.recordid
        event_id = record.fields['id']['convertedvalue']
        event_title = record.fields[title_field]['convertedvalue']
        event_color = record.fields[color_field]['convertedvalue']
        start_date = record.fields[date_from_field]['convertedvalue'] if date_from_field else None
        end_date = record.fields[date_to_field]['convertedvalue'] if date_to_field else start_date
        start_time = record.fields[time_from_field]['convertedvalue'] if time_from_field else datetime.time(8,0).strftime('%H:%M:%S')
        end_time = record.fields[time_to_field]['convertedvalue'] if time_to_field else datetime.time(12,0).strftime('%H:%M:%S')

        
        print(f"Processing event for {resource_value}: {event_title} from {start_date} to {end_date}")
        # Crea il dizionario per l'evento
        event_data = {
            'id': str(event_id),
            'resourceId': resource_id,
            'title': event_title,
            'description': f"Assenza per {event_title} di {resource_value}",
            'start': Helper.to_iso_datetime(start_date, start_time),
            'end': Helper.to_iso_datetime(end_date, end_time),
            'color': get_color_for_title(event_color),
            'recordid': str(record_id),
        }

        if event_data['start'] and event_data['end']:
            response_data_dev['events'].append(event_data)
        else:
            response_data_dev['unplannedEvents'].append(event_data)

    return JsonResponse(response_data_dev)


def matrixcalendar_save_record(request):
    """
    Salva l'aggiornamento di un evento del calendario in una tabella dinamica.
    Campi richiesti:
        - tableid (obbligatorio)
        - event.id (obbligatorio)
        - event.startdate (obbligatorio)
        - event.resourceid (obbligatorio)
    Campi opzionali:
        - event.enddate (usato se presente + campi planner associati configurati)
        - time fields, date_to_field (se configurati in TableSettings)
    """

    # --- Parsing input JSON ---
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "detail": "JSON non valido"}, status=400)

    tableid = data.get("tableid")
    event = data.get("event")

    if not tableid or not event:
        return JsonResponse({"success": False, "detail": "Parametri mancanti (tableid o event)"}, status=400)

    record_id = event.get('id')
    start_date_str = event.get('startdate')
    end_date_str = event.get('enddate')
    resource_id = event.get('resourceid')

    # --- Validazioni minime ---
    if not record_id:
        return JsonResponse({"success": False, "detail": "ID record mancante"}, status=400)
    # if not resource_id:
        # return JsonResponse({"success": False, "detail": "Resource ID mancante"}, status=400)

    # --- Recupero record dinamico ---
    record = UserRecord(tableid, record_id)
    if not record:
        return JsonResponse({"success": False, "detail": "Record non trovato"}, status=404)

    # --- Recupero impostazioni tabella ---
    userid = Helper.get_userid(request)
    tablesettings_obj = TableSettings(tableid=tableid, userid=userid)
    tablesettings = tablesettings_obj.get_settings()

    resource_field = tablesettings.get('table_planner_resource_field', {}).get('value')
    date_from_field = tablesettings.get('table_planner_date_from_field', {}).get('value')
    date_to_field = tablesettings.get('table_planner_date_to_field', {}).get('value')
    time_from_field = tablesettings.get('table_planner_time_from_field', {}).get('value')
    time_to_field = tablesettings.get('table_planner_time_to_field', {}).get('value')

    # --- Validazione campi obbligatori configurati ---
    if not resource_field or not date_from_field:
        return JsonResponse({
            "success": False,
            "detail": "Campi planner obbligatori non configurati (resource_field o date_from_field)"
        }, status=400)

    # --- Parsing date ---
    try:
        start_dt = None
        if start_date_str:
            start_dt = datetime.datetime.fromisoformat(start_date_str.replace("Z", "+00:00")).date()
        end_dt = None
        if end_date_str:
            end_dt = datetime.datetime.fromisoformat(end_date_str.replace("Z", "+00:00")).date()
    except ValueError:
        return JsonResponse({"success": False, "detail": "Formato data/ora non valido"}, status=400)

    # --- Aggiornamento valori record ---
    try:
        if date_from_field:
            record.values[date_from_field] = start_dt

        if date_to_field:
            record.values[date_to_field] = end_dt

        # Campi opzionali: orari
        if time_from_field:
            record.values[time_from_field] = start_dt.strftime('%H:%M:%S')
        if time_to_field and end_dt:
            record.values[time_to_field] = end_dt.strftime('%H:%M:%S')

        if resource_field and resource_id:
            record.values[resource_field] = resource_id

        record.save()

        return JsonResponse({"success": True, "detail": "Record aggiornato con successo"})

    except Exception as e:
        return JsonResponse({"success": False, "detail": f"Errore interno: {str(e)}"}, status=500)

@timing_decorator
def get_table_recordsBAK(request):
    print('Function: get_table_records')
    with CodeTimer("get_table_records BLOCCO 1"):
        data = json.loads(request.body)
        tableid = data.get("tableid")
        viewid = data.get("view")
        searchTerm = data.get("searchTerm")
        order = data.get("order")
        page = data.get("currentPage")
        master_tableid = data.get("masterTableid")
        master_recordid = data.get("masterRecordid")

        table = UserTable(tableid, Helper.get_userid(request))

        if viewid == '':
            viewid = table.get_default_viewid()

        records: List[UserRecord]
        conditions_list = []
        records = table.get_table_records_obj(
            viewid=viewid,
            searchTerm=searchTerm,
            conditions_list=conditions_list,
            master_tableid=master_tableid,
            master_recordid=master_recordid
        )
        counter = table.get_total_records_count()
        table_columns = table.get_results_columns()

    with CodeTimer("get_table_records BLOCCO 2"):
        # --- Leggi alert e parsea le condizioni UNA volta sola ---
        # NB: se il tuo helper supporta parametri, usa quelli (eviti injection)
        alerts = HelpderDB.sql_query(
                f"SELECT * FROM sys_alert WHERE tableid='{tableid}' AND alert_type='cssclass'"
            )

        compiled_alerts = []
        for alert in alerts:
            try:
                cond_str = alert['alert_condition']  # <-- assicurati del nome colonna
                alert_param = json.loads(alert['alert_param'])

                cssclass = alert_param.get('cssclass', '')
                target = alert_param.get('target', 'record')  # 'record' | 'field'
                fieldid = alert_param.get('fieldid', '')

                conds = Helper.parse_sql_like_and(cond_str)  # <-- lista di (field, op, val)

                compiled_alerts.append({
                    'conds': conds,
                    'cssclass': cssclass,
                    'target': target,
                    'fieldid': fieldid
                })
            except json.JSONDecodeError:
                print(f"Errore nel decodificare il JSON per l'alert: {alert.get('id')}")
            except ValueError as e:
                print(f"Condizione non valida per alert {alert.get('id')}: {e}")

        # --- Costruzione risposta ---
        rows = []

    with CodeTimer("get_table_records BLOCCO 3"):
        for record in records:
            # Adatta qui: se record non è dict, ricavane i campi:
            fields = record.get_record_results_fields()  # [{fieldid, value, type, ...}, ...]
            # Mappa: fieldid -> value (serve per i confronti)

            # 1) Normalizza la mappa valori: fieldid (string) -> value
            #    Se hai già record.values come dict, convertilo con chiavi stringa:
            if hasattr(record, "values") and isinstance(record.values, dict):
                values_map = {str(k): v for k, v in record.values.items()}
            else:
                # fallback: ricava dai fields
                values_map = {str(f["fieldid"]): f.get("value") for f in fields}



            # 2) Inizializza contenitori CSS
            record_css = []                      # classi da applicare all'intero record
            field_css_map = defaultdict(list)    # fieldid (string) -> [cssclass, ...]

            # 3) Applica gli alert che matchano
            for a in compiled_alerts:
                if Helper.evaluate_and_conditions(values_map, a["conds"]):
                    css = a.get("cssclass", "")
                    if not css:
                        continue

                    if a.get("target", "record") == "record":
                        record_css=css
                    else:  # target == 'field'
                        fid = str(a.get("fieldid", "")).strip()
                        if fid:
                            field_css_map[fid]=css

            row = {
            "recordid": record.recordid,
            "css": record_css,
                "fields": []
            }

            # 5) Popola i campi con css specifico (SOLO quelli destinati al campo)
            #    Se vuoi anche ereditare le classi del record sui campi, unisci le liste:
            #    fcss_list = record_css + field_css_map.get(fid, [])
            
            for f in fields:
                fcss=''
                fid = str(f["fieldid"])
                css = field_css_map.get(fid)
                if css:                     # True se fid è presente e il valore non è vuoto
                    fcss = (fcss + " " + css).strip()

                row["fields"].append({
                    "recordid": record.recordid,
                    "css": fcss,
                    "type": f.get("type"),
                    "value": f.get("value"),
                    "fieldid": f["fieldid"],
                })

            rows.append(row)

        

    # Colonne
    columns = [{'fieldtypeid': c['fieldtypeid'], 'desc': c['description']} for c in table_columns]

    response_data = {
        "counter": counter,
        "rows": rows,
        "columns": columns
    }
    return JsonResponse(response_data)


def get_pitservice_pivot_lavanderiaDEV(request):
    # response_data_dev.py  – dati di esempio
    response_data_dev = {
        "groups": [
            {   # Livello 0: Cliente A
                "groupKey": "ClienteA",
                "level": 0,
                "fields": [
                    {"value": "Marvel Gestioni e Immobili Sagl", "css": ""},
                    {"value": "Totale Cliente A", "css": "font-semibold"},
                    {"value": "", "css": ""},
                    {"value": "", "css": ""},
                    {"value": "5000", "css": "font-bold"},
                ],
                "subGroups": [
                    {   # Livello 1: Indirizzo 1
                        "groupKey": "ClienteA-Indirizzo1",
                        "level": 1,
                        "fields": [
                            {"value": "Progetto Casa Sirio", "css": ""},
                            {"value": "Totale Indirizzo 1", "css": "italic"},
                            {"value": "1000", "css": ""},
                            {"value": "1025", "css": ""},
                            {"value": "2025", "css": "font-semibold"},
                        ],
                        "rows": [
                            {
                                "recordid": "1",
                                "css": "",
                                "fields": [
                                    {"value": "Casa Sirio Via Giuseppe Stabile 3", "css": "text-xs"},
                                    {"value": "1000", "css": ""},
                                    {"value": "500", "css": ""},
                                    {"value": "525", "css": ""},
                                    {"value": "1025", "css": ""},
                                ],
                            },
                            {
                                "recordid": "1b",
                                "css": "",
                                "fields": [
                                    {"value": "Casa Sirio - Interno B", "css": "text-xs"},
                                    {"value": "1000", "css": ""},
                                    {"value": "500", "css": ""},
                                    {"value": "500", "css": ""},
                                    {"value": "1000", "css": ""},
                                ],
                            },
                        ],
                    },
                    {   # Livello 1: Indirizzo 2
                        "groupKey": "ClienteA-Indirizzo2",
                        "level": 1,
                        "fields": [
                            {"value": "Progetto San Giorgio", "css": ""},
                            {"value": "Totale Indirizzo 2", "css": "italic"},
                            {"value": "1500", "css": ""},
                            {"value": "1475", "css": ""},
                            {"value": "2975", "css": "font-semibold"},
                        ],
                        "rows": [
                            {
                                "recordid": "2",
                                "css": "",
                                "fields": [
                                    {"value": "Condominio San Giorgio", "css": "text-xs"},
                                    {"value": "1500", "css": ""},
                                    {"value": "700", "css": ""},
                                    {"value": "775", "css": ""},
                                    {"value": "1475", "css": ""},
                                ],
                            }
                        ],
                    },
                ],
            },
            {   # Livello 0: Cliente B
                "groupKey": "ClienteB",
                "level": 0,
                "fields": [
                    {"value": "Agenzia Immobiliare Ceresio SA", "css": ""},
                    {"value": "Totale Cliente B", "css": "font-semibold"},
                    {"value": "", "css": ""},
                    {"value": "", "css": ""},
                    {"value": "6075", "css": "font-bold"},
                ],
                "rows": [
                    {
                        "recordid": "3",
                        "css": "",
                        "fields": [
                            {"value": "Ufficio Agenzia Ceresio", "css": "text-xs"},
                            {"value": "2025", "css": ""},
                            {"value": "1000", "css": ""},
                            {"value": "1025", "css": ""},
                            {"value": "2025", "css": ""},
                        ],
                    },
                    {
                        "recordid": "4",
                        "css": "",
                        "fields": [
                            {"value": "Residenza Salice Via Frontini 8", "css": "text-xs"},
                            {"value": "4050", "css": ""},
                            {"value": "2000", "css": ""},
                            {"value": "2050", "css": ""},
                            {"value": "4050", "css": ""},
                        ],
                    },
                ],
            },
        ],
        "columns": [
            {"fieldtypeid": "Parola", "desc": "Nome / Descrizione"},
            {"fieldtypeid": "Numero", "desc": "Totale Riga/Gruppo"},
            {"fieldtypeid": "Numero", "desc": "Gennaio"},
            {"fieldtypeid": "Numero", "desc": "Febbraio"},
            {"fieldtypeid": "Numero", "desc": "Totale Complessivo"},
        ],
    }
    return JsonResponse(response_data_dev, safe=False)

def get_pitservice_pivot_lavanderia(request):
    # Costruisci la struttura di risposta
    response_data = {"groups": []}
    response_data["columns"] = []
    data = json.loads(request.body)
    tableid = data.get("tableid")
    view = data.get("view")
    searchterm = data.get("searchTerm")
    table=UserTable(tableid)

    #TODO 
    #CUSTOM           

    #------ PITSERVICE - RENDICONTO LAVANDERIA --------------------------------
    if tableid == "rendicontolavanderia":
        # 1. Lettura (UNICA query) + filtro anno opzionale
        anno_filter = globals().get("anno_filter")       # es. "2025"
        
        rows=table.get_pivot_records(viewid=view, searchTerm=searchterm, limit=10000)

        df = pd.DataFrame(rows)

        # 2. Elenco mesi nel formato presente nel DB (es. "04-Aprile")
        mesi = [
            f"{str(i).zfill(2)}-{nome}"
            for i, nome in enumerate(
                [
                    "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
                    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
                ],
                1,
            )
        ]

        # 3. Label-map per CLIENTE e STABILE (+ città per colonna extra)
        cli_ids = set(df["recordidcliente_"].dropna())
        sta_ids = set(df["recordidstabile_"].dropna())

        cliente_map = fetch_label_map("cliente", cli_ids,  "nome_cliente")

        # per lo stabile servono sia nome sia città
        stabili_rows = []
        if sta_ids:
            in_list = ",".join(f"'{x}'" for x in sta_ids)
            stabili_rows = HelpderDB.sql_query(f"""
                SELECT recordid_, titolo_stabile, citta
                FROM user_stabile
                WHERE recordid_ IN ({in_list})
            """)
        stabile_nome_map = {r["recordid_"]: r["titolo_stabile"] for r in stabili_rows}
        stabile_citta_map = {r["recordid_"]: r["citta"] for r in stabili_rows}

        # 4. Aggiunge la CITTÀ al dataframe (serve come 2ª colonna fissa)
        df["citta"] = df["recordidstabile_"].map(stabile_citta_map)

        # 5. Genera la risposta con la funzione genérica
        pivot_data = build_pivot_response(
            records            = df.to_dict("records"),             # no seconde query!
            group_fields       = ["recordidcliente_", "recordidstabile_", "citta"],
            num_group_levels   = 1,                                 # group ▶ cliente
            group_headers      = ["CLIENTE", "IMMOBILE", "CITTÀ"],
            column_field       = "mese",
            value_field        = "stato",                              # conteggio righe
            aggfunc            = "first",
            predefined_columns = mesi,                              # mesi in ordine fisso
            cell_format = lambda v, **_: (
                v or "",
                "bg-green-200  text-green-800  font-semibold"   # Inviato
                if v and "Inviato"          in str(v) else
                "bg-green-100  text-green-700  font-semibold"   # Nessuna ricarica
                if v and "Nessuna ricarica" in str(v) else
                "bg-yellow-200 text-yellow-800 font-semibold"   # Da preparare
                if v and "Da fare"     in str(v) else
                "bg-blue-200   text-blue-800 font-semibold"     # Preparato
                if v and "Preparato"        in str(v) else
                ""                                               # default: nessun colore
            ),
            label_maps         = {
                "recordidcliente_":  cliente_map,
                "recordidstabile_": stabile_nome_map,
            },
        )

        # 6. Ritocca le intestazioni dei mesi (da "04-Aprile" → "Aprile")
        for col in pivot_data["columns"][3:]:                       # prime 3 = gruppi
            col["desc"] = col["desc"].split("-", 1)[1]
        
    

               
            


    #------ PITSERVICE - LETTURA GASOLIO --------------------------------
    if tableid == "letturagasolio":
        # 1. Letture gasolio (UNICA query sul DB) ────────────────────────────────────
        df = pd.DataFrame(HelpderDB.sql_query("""
            SELECT *
            FROM user_letturagasolio
            WHERE anno      = '2025'      -- se diventa variabile basta parametrizzare
            AND deleted_  = 'N'
        """))

        # 2. Elenco mesi nel formato del DB ("04-Aprile") + coda per reorder
        mesi = [
            f"{str(i).zfill(2)}-{nome}"
            for i, nome in enumerate(
                [
                    "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
                    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
                ],
                1,
            )
        ]

        # 3. Batch-fetch anagrafiche (2 query) ──────────────────────────────────────
        cli_ids = set(df["recordidcliente_"].dropna())
        sta_ids = set(df["recordidstabile_"].dropna())
        cis_ids = set(df["recordidinformazionigasolio_"].dropna())

        cliente_map   = fetch_label_map("cliente",   cli_ids, "nome_cliente")
        stabile_nome  = fetch_label_map("stabile",   sta_ids, "riferimento")
        stabile_citta = fetch_label_map("stabile",   sta_ids, "citta")
        cis_nome      = fetch_label_map("informazionigasolio", cis_ids, "riferimento")
        cis_capienza  = fetch_label_map("informazionigasolio", cis_ids, "capienzacisterna")
        cis_minimo    = fetch_label_map("informazionigasolio", cis_ids, "livellominimo")

        # 4. Arricchisce il dataframe con la CITTÀ (serve come colonna indice fissa)
        df["citta"] = df["recordidstabile_"].map(stabile_citta)

        key_cols = ["recordidcliente_", "recordidstabile_", "citta",
                "recordidinformazionigasolio_", "mese"]

        stato_lookup: dict[tuple, set[str]] = (
            df.groupby(key_cols)["stato"]
            .agg(lambda s: set(s.dropna()))
            .to_dict()
        )

        # 5. Funzione di formattazione celle --------------------------------------
        def fmt_litri(val, *, col, idx, **_):
            """
            val → somma letturalitri   (value_field)
            col → mese (colonna pivot)
            idx → dict con le chiavi della riga (cliente, stabile, citta, cisterna)
            """
            key = (idx["recordidcliente_"],
                idx["recordidstabile_"],
                idx["citta"],
                idx["recordidinformazionigasolio_"],
                col)

            css = ""
            stati = stato_lookup.get(key, set())
            css = (
                "bg-green-200 text-green-800 font-semibold"
                if "Inviato" in stati else ""
            )
            return (val, css) 
            
        
        # 5. Pivot via funzione generica ───────────────────────────────────────────
        pivot_data = build_pivot_response(
            records            = df.to_dict("records"),
            group_fields       = [
                "recordidcliente_",              # livello 0  → CLIENTE
                "recordidstabile_",              # livello 1  → STABILE
                "citta",                         # ↓ righe
                "recordidinformazionigasolio_",  # ↓
            ],
            num_group_levels   = 2,              # 0=cliente, 1=stabile
            group_headers      = ["CLIENTE", "", "CITTÀ", "CISTERNA"],
            column_field       = "mese",
            value_field        = "letturalitri",
            aggfunc            = "sum",
            predefined_columns = mesi,
            cell_format        = fmt_litri,
            label_maps = {
                "recordidcliente_"            : cliente_map,
                "recordidstabile_"            : stabile_nome,
                "recordidinformazionigasolio_": cis_nome,
            },
        )

        # 6. Intestazioni mesi → solo nome breve ("Aprile") ------------------------
        for col in pivot_data["columns"][4:]:          # prime 4 = header gruppi
            col["desc"] = col["desc"].split("-", 1)[1]

        # 7. Aggiunge colonne Capienza e Livello minimo + riempie le righe ----------
        pivot_data["columns"].extend([
            {"fieldtypeid": "Parola", "desc": "Capienza"},
            {"fieldtypeid": "Parola", "desc": "Livello minimo"},
        ])

        def enrich(groups: list[dict]):
            """appende capienza / minimo alle righe di foglia (cisterna)"""
            for g in groups:
                if g.get("subGroups"):
                    enrich(g["subGroups"])
                for row in g.get("rows", []):
                    cid = row["recordid"]                     # id cisterna
                    row["fields"].extend([
                        {"value": cis_capienza.get(cid, ""), "css": ""},
                        {"value": cis_minimo.get(cid,   ""), "css": ""},
                    ])

        enrich(pivot_data["groups"])


    #------ PITSERVICE - DIPENDENTE --------------------------------
    if tableid == "dipendente":
        # 1. Query unica ----------------------------------------------------------
        df_raw = pd.DataFrame(HelpderDB.sql_query("""
            SELECT *
            FROM user_dipendente
            WHERE deleted_ = 'N'
            ORDER BY ruolo
        """))

        # 2. Trasforma i record in formato LONG  ----------------------------------
        #    (un record per singola colonna logica che vuoi poi ricompattare a pivot)
        long_rows   = []
        dip_map     = {}          # id dipendente  → cognome  (etichetta riga)
        COL_ORDER   = ["Cognome", "Nome", "Email", "Telefono"]

        for rec in df_raw.to_dict("records"):
            dip_id = rec["recordid_"]
            dip_map[dip_id] = rec["cognome"]         # servirà come label di riga

            long_rows.extend([
                {"ruolo": rec["ruolo"], "dip_id": dip_id, "campo": "Cognome",  "valore": rec["cognome"]},
                {"ruolo": rec["ruolo"], "dip_id": dip_id, "campo": "Nome",     "valore": rec["nome"]},
                {"ruolo": rec["ruolo"], "dip_id": dip_id, "campo": "Email",    "valore": rec["email"]},
                {"ruolo": rec["ruolo"], "dip_id": dip_id, "campo": "Telefono", "valore": rec["telefono"]},
            ])

        # 3. Pivot con funzione generica -----------------------------------------
        pivot_data = build_pivot_response(
            records            = long_rows,
            group_fields       = ["ruolo", "dip_id"],   # livello 0 = RUOLO  ; righe = dipendente
            num_group_levels   = 1,                     # solo RUOLO come gruppo
            group_headers      = ["RUOLO", "DIPENDENTE"],
            column_field       = "campo",
            value_field        = "valore",
            aggfunc            = "first",               # ciascuna coppia (dip, col) ha 1 valore
            predefined_columns = COL_ORDER,
            cell_format        = lambda v, **_: (v or "", ""),  # nessun colore speciale
            label_maps         = {"dip_id": dip_map},   # mostra il cognome al posto dell’ID
        )


    
    #------ SWISSBIX - SERVIZI --------------------------------
    if tableid == "serviceandasset":
        # 1. Estrazione dati (una sola query)
        df = pd.DataFrame(HelpderDB.sql_query("""
            SELECT *
            FROM user_serviceandasset
            WHERE deleted_ = 'N'
        """))

        # 2. Colonne pivot dinamiche ▶ tutti i valori distinti di `type`
        all_types: list[str] = sorted(df["type"].dropna().unique().tolist())

        # 3. Label-map per l’azienda (id ▶ nome)
        company_ids = set(df["recordidcompany_"].dropna())
        company_map = fetch_label_map("company", company_ids, "companyname")

        # 4. Costruzione della response con la funzione generica
        pivot_data = build_pivot_response(
            records           = df.to_dict("records"),    # evita una seconda query
            group_fields      = ["recordidcompany_", "description"],
            num_group_levels  = 1,                         # solo COMPANY come gruppo
            group_headers     = ["AZIENDA", "DOMINIO"],
            column_field      = "type",
            value_field       = "quantity",
            aggfunc           = "sum",
            predefined_columns= all_types,                # mantiene l’ordine alfabetico
            cell_format       = lambda v: v or "",        # cast valori None → stringa vuota
            label_maps        = {"recordidcompany_": company_map},
        )
        
    
    return JsonResponse(pivot_data) 




def fetch_label_map(table: str, ids: set[str], label_field: str) -> dict[str, str]:
    """
    Ritorna {recordid_: label_string} per il campo indicato.
    Se l'insieme è vuoto salta la query.
    """
    if not ids:
        return {}
    in_list = ",".join(f"'{x}'" for x in ids)
    rows = HelpderDB.sql_query(f"""
        SELECT recordid_, {label_field}
          FROM user_{table}
         WHERE recordid_ IN ({in_list})
    """)
    return {r["recordid_"]: r[label_field] for r in rows}

def build_pivot_response(
    records: List[Dict[str, Any]],
    *,
    group_fields: Sequence[str],
    column_field: str,
    value_field: str | None = None,
    aggfunc: Union[str, Callable] = "size",
    predefined_columns: Sequence[Any] | None = None,
    label_maps: Dict[str, Dict[Any, str]] | None = None,
    # ------------------------------------------------------------------------- #
    # NEW: la callback può accettare argomenti opzionali e restituire anche css
    cell_format: Callable[..., Any] | None = None,
    # ------------------------------------------------------------------------- #
    group_headers: Sequence[str] | None = None,
    num_group_levels: int | None = None,
) -> Dict[str, Any]:
    """
    Restituisce un dizionario già pronto per il front-end React.

    Parametri aggiuntivi:
    ─────────────────────
    cell_format : funzione opzionale che riceve il valore grezzo e (se lo vuole)
                  anche i parametri keyword:
                      • col  → nome colonna pivot
                      • idx  → dict {field: key} dell’indice riga
                  Può restituire:
                      • solo il valore                → css  = ""
                      • (valore, css)                 → tupla
                      • {"value": v, "css": cls}      → dict
    """

    # ---------------------------------------------------------------- record check
    if not records:
        return {"columns": [], "groups": []}

    if num_group_levels is None:
        num_group_levels = len(group_fields)
    if not (0 < num_group_levels <= len(group_fields)):
        raise ValueError("num_group_levels dev'essere compreso tra 1 e len(group_fields)")

    df = pd.DataFrame(records)

    # ---------------------------------------------------------------- pivot
    if value_field is None:
        pivot_df = pd.pivot_table(
            df,
            index=list(group_fields),
            columns=column_field,
            aggfunc="size",
            fill_value=0,
        )
    else:
        pivot_df = pd.pivot_table(
            df,
            index=list(group_fields),
            columns=column_field,
            values=value_field,
            aggfunc=aggfunc,
            fill_value=0 if aggfunc == "size" else "",
        )

    if predefined_columns is not None:
        pivot_df = pivot_df.reindex(columns=predefined_columns, fill_value=0)

    # ---------------------------------------------------------------- helpers
    def readable(field: str, key: Any) -> Any:
        """applica eventuale mapping id → label"""
        if label_maps and field in label_maps:
            mapped = label_maps[field].get(key, key)
            if isinstance(mapped, dict):              # se arriva un dict (caso raro)
                return next(iter(mapped.values())) if len(mapped) == 1 else str(mapped)
            return mapped
        return key

    def make_node(level: int, field: str, key: Any):
        return {
            "groupKey": key,
            "level": level,
            "fields": [
                {
                    "value": readable(field, key),
                    "css": "font-semibold" if level == 0 else "",
                }
            ],
            "subGroups": [],
            "rows": [],
        }

    root: Dict[Any, Any] = defaultdict(dict)

    # ---------------------------------------------------------------- build tree
    for row in pivot_df.reset_index().itertuples(index=False):
        idx_keys   = row[: len(group_fields)]
        pivot_vals = row[len(group_fields):]

        grp_parent: Dict[Any, Any] = root
        for lvl in range(num_group_levels):           # costruzione livelli gruppo
            key   = idx_keys[lvl]
            field = group_fields[lvl]
            if key not in grp_parent:
                grp_parent[key] = make_node(lvl, field, key)
            node = grp_parent[key]
            grp_parent = node.setdefault("subGroups_map", {})

        # --------------------------- riga foglia ------------------------------
        row_index_cells = [
            "" if i < num_group_levels else readable(group_fields[i], idx_keys[i])
            for i in range(len(group_fields))
        ]

        formatted_cells: List[Dict[str, Any]] = []
        for col_name, raw_val in zip(pivot_df.columns, pivot_vals):
            css   = ""
            value = raw_val

            if cell_format is not None:
                try:
                    formatted = cell_format(
                        raw_val,
                        col=col_name,
                        idx=dict(zip(group_fields, idx_keys)),
                    )
                except TypeError:                      # callback “vecchia firma”
                    formatted = cell_format(raw_val)

                if isinstance(formatted, tuple) and len(formatted) == 2:
                    value, css = formatted
                elif isinstance(formatted, dict):
                    value = formatted.get("value", "")
                    css   = formatted.get("css", "")
                else:                                   # valore puro
                    value = formatted

            formatted_cells.append({"value": value, "css": css})

        node["rows"].append(
            {
                "recordid": idx_keys[-1],
                "css": "",
                "fields": (
                    [{"value": c, "css": ""} for c in row_index_cells] +
                    formatted_cells
                ),
            }
        )

    # ---------------------------------------------------------------- collapse dict → list
    def collapse(node_dict):
        if isinstance(node_dict, dict) and "groupKey" in node_dict:
            node_dict["subGroups"] = [
                collapse(child)
                for child in node_dict.pop("subGroups_map", {}).values()
            ]
            return node_dict
        return [collapse(child) for child in node_dict.values()]

    groups = [collapse(n) for n in root.values()]

    # ---------------------------------------------------------------- header
    if group_headers is None:
        header_cols = [{"fieldtypeid": "Parola", "desc": ""} for _ in group_fields]
    else:
        if len(group_headers) != len(group_fields):
            raise ValueError("group_headers deve avere la stessa lunghezza di group_fields")
        header_cols = [{"fieldtypeid": "Parola", "desc": h} for h in group_headers]

    header_cols += [
        {"fieldtypeid": "Parola", "desc": str(col)} for col in pivot_df.columns
    ]

    return {"columns": header_cols, "groups": groups}


import csv

@csrf_exempt
def insert_domains(request):
    # Percorso del file CSV
    csv_path = "./commonapp/pleskn01.csv"

    def parse_domain(domain):
        domain_lower = domain.lower()
        if 'alias' in domain_lower:
            clean_name = domain_lower.split('alias')[0].strip().strip('.-')
            tipo = "Hosting - Alias"
        elif 'forward' in domain_lower:
            clean_name = domain_lower.split('forward')[0].strip().strip('.-')
            tipo = "Hosting - Forward"
        else:
            clean_name = domain_lower.strip()
            if ',' in clean_name:
                clean_name = clean_name.split(',')[0].strip()
            tipo = "Hosting"
        return clean_name, tipo

    inserted_count = 0
    skipped_count = 0
    results = []

    try:
        with open(csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            for row_num, row in enumerate(reader, 1):
                if not row:
                    continue

                domain = row[0].strip()
                try:
                    description, tipo = parse_domain(domain)
                    safe_description = description.replace("'", "''")
                    sql_check = f"SELECT 1 FROM user_serviceandasset WHERE description = '{safe_description}' LIMIT 1"
                    exists = HelpderDB.sql_query_value(sql_check, '1')

                    if not exists:
                        record = UserRecord('serviceandasset')
                        record.values['description'] = description
                        record.values['type'] = tipo
                        record.values['status'] = 'Active'
                        record.save()

                        inserted_count += 1
                        results.append({
                            'row': row_num,
                            'domain': domain,
                            'description': description,
                            'type': tipo,
                            'status': 'inserted'
                        })
                    else:
                        skipped_count += 1
                        results.append({
                            'row': row_num,
                            'domain': domain,
                            'description': description,
                            'type': tipo,
                            'status': 'skipped',
                            'reason': 'already_exists'
                        })

                except Exception as e:
                    results.append({
                        'row': row_num,
                        'domain': domain,
                        'status': 'error',
                        'error': str(e)
                    })
                    break  # Interrompe l'importazione se c'è un errore

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f"Errore nell'apertura del file: {str(e)}"
        }, status=500)

    return JsonResponse({
        'status': 'partial_success' if any(r['status'] == 'error' for r in results) else 'success',
        'summary': {
            'total_processed': len(results),
            'inserted': inserted_count,
            'skipped': skipped_count,
            'errors': len([r for r in results if r['status'] == 'error'])
        },
        'results': results,
        'message': (
            'IMPORTAZIONE INTERROTTA a causa di un errore.'
            if any(r['status'] == 'error' for r in results)
            else 'Tutti i domini sono stati inseriti correttamente o già esistevano.'
        )
    })


@csrf_exempt
def check_domains_presence(request):
    # Percorso del file CSV
    csv_path = "./commonapp/pleskn01.csv"

    def parse_domain(domain):
        domain_lower = domain.lower()
        if 'alias' in domain_lower:
            clean_name = domain_lower.split('alias')[0].strip().strip('.-')
            tipo = "Hosting - Alias"
        elif 'forward' in domain_lower:
            clean_name = domain_lower.split('forward')[0].strip().strip('.-')
            tipo = "Hosting - Forward"
        else:
            clean_name = domain_lower.strip()
            if ',' in clean_name:
                clean_name = clean_name.split(',')[0].strip()
            tipo = "Hosting"
        return clean_name, tipo

    found = []
    missing = []
    errors = []

    try:
        with open(csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            for row_num, row in enumerate(reader, 1):
                if not row:
                    continue

                domain = row[0].strip()

                try:
                    description, tipo = parse_domain(domain)
                    safe_description = description.replace("'", "''")
                    sql_check = f"SELECT 1 FROM user_serviceandasset WHERE description = '{safe_description}' LIMIT 1"
                    exists = HelpderDB.sql_query_value(sql_check, '1')

                    if exists:
                        found.append({
                            'row': row_num,
                            'domain': domain,
                            'description': description,
                            'type': tipo,
                            'status': 'found'
                        })
                    else:
                        missing.append({
                            'row': row_num,
                            'domain': domain,
                            'description': description,
                            'type': tipo,
                            'status': 'missing'
                        })

                except Exception as e:
                    errors.append({
                        'row': row_num,
                        'domain': domain,
                        'status': 'error',
                        'error': str(e)
                    })

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f"Errore nell'apertura del file: {str(e)}"
        }, status=500)

    return JsonResponse({
        'status': 'completed',
        'summary': {
            'total_checked': len(found) + len(missing),
            'found': len(found),
            'missing': len(missing),
            'errors': len(errors)
        },
        'results': {
            'found': found,
            'missing': missing,
            'errors': errors
        },
        'message': 'Controllo completato. Verifica la lista dei domini mancanti per eventuale reinserimento.'
    })




@csrf_exempt
def insert_domains_test(request):
    """
    Funzione per importare domini da un file CSV.
    MODALITÀ PROVA: Non effettua inserimenti reali, solo simulazione.
    Restituisce un report dettagliato di cosa verrebbe fatto.
    """
    
    # Percorso del file CSV (aggiustare secondo la propria struttura di cartelle)
    csv_path = "./commonapp/pleskn01.csv"

    def parse_domain(domain):
        """
        Analizza il dominio per estrarre nome pulito e tipo
        Gestisce i casi speciali 'alias' e 'forward'
        Applica pulizia della descrizione per i casi standard
        """
        domain_lower = domain.lower()
        if 'alias' in domain_lower:
            clean_name = domain_lower.split('alias')[0].strip().strip('.-')
            tipo = "Hosting - Alias"
        elif 'forward' in domain_lower:
            clean_name = domain_lower.split('forward')[0].strip().strip('.-')
            tipo = "Hosting - Forward"
        else:
            clean_name = domain_lower.strip()
            # Se c'è una virgola, si prende solo la prima parte come description
            if ',' in clean_name:
                clean_name = clean_name.split(',')[0].strip()
            tipo = "Hosting"
        return clean_name, tipo


    # Liste per tenere traccia dei risultati
    to_be_inserted = []
    already_existing = []
    errors = []

    try:
        with open(csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            for row_num, row in enumerate(reader, 1):
                if not row:
                    continue
                
                try:
                    domain = row[0].strip()
                    description, tipo = parse_domain(domain)

                    # Controlla se esiste già un record con questa description
                    safe_description = description.replace("'", "''")
                    sql_check = f"SELECT 1 FROM user_serviceandasset WHERE description = '{safe_description}' LIMIT 1"

                    exists = HelpderDB.sql_query_value(sql_check, '1')

                    if not exists:
                        # In modalità prova, solo simulazione
                        to_be_inserted.append({
                            'domain': domain,
                            'clean_description': description,
                            'type': tipo,
                            'status': 'Active',
                            'action': 'would_be_inserted'
                        })
                    else:
                        already_existing.append({
                            'domain': domain,
                            'clean_description': description,
                            'type': tipo,
                            'status': 'Active',
                            'action': 'already_exists'
                        })

                except Exception as e:
                    errors.append({
                        'row': row_num,
                        'domain': row[0] if row else 'empty_row',
                        'error': str(e)
                    })

    except Exception as e:
        errors.append({
            'file_error': f"Errore nell'apertura/lettura del file: {str(e)}"
        })

    return JsonResponse({
        'status': 'simulation_complete',
        'summary': {
            'total_processed': len(to_be_inserted) + len(already_existing),
            'would_be_inserted': len(to_be_inserted),
            'already_existing': len(already_existing),
            'errors': len(errors)
        },
        'details': {
            'to_be_inserted': to_be_inserted,
            'already_existing': already_existing,
            'errors': errors
        },
        'message': 'SIMULAZIONE COMPLETATA. Nessun dato è stato realmente inserito.'
    })




def _save_record_data(tableid, recordid=None, fields=None, files=None):
    """
    Funzione di utilità condivisa per creare o aggiornare un record.
    - tableid: stringa (obbligatoria)
    - recordid: id del record esistente o None per crearne uno nuovo
    - fields: dizionario dei campi {fieldid: value}
    - files: dict di file caricati (es. da request.FILES)
    """
    def normalize_value(value):
        if value == '' or value == 'null' or len(str(value).strip()) == 0:
            return None
        return value

    record = UserRecord(tableid, recordid)

    # 1️⃣ Assegna i campi
    if fields:
        for fieldid, value in fields.items():
            record.values[fieldid] = normalize_value(value)

    # 2️⃣ Salva i file (se presenti)
    if files:
        for file_key, uploaded_file in files.items():
            if file_key.startswith('files[') and file_key.endswith(']'):
                clean_key = file_key[6:-1]
            else:
                clean_key = file_key

            _, ext = os.path.splitext(uploaded_file.name)
            record_path = f"{tableid}/{record.recordid}/{clean_key}{ext}"
            file_path = os.path.join(tableid, record.recordid, f"{clean_key}{ext}")

            # Rimuovi file esistente se c’è
            if default_storage.exists(file_path):
                default_storage.delete(file_path)

            saved_path = default_storage.save(file_path, uploaded_file)

            # 🔁 Copia in backup
            try:
                full_path = default_storage.path(saved_path)
                backup_base = env('BACKUP_DIR')
                backup_path = os.path.join(backup_base, tableid, record.recordid, f"{clean_key}{ext}")
                os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                if os.path.exists(full_path):
                    shutil.copy2(full_path, backup_path)
            except Exception as e:
                print(f"Errore backup file {clean_key}: {e}")

            record.values[clean_key] = record_path

    record.save()
    return record

@csrf_exempt
def duplicate_record(request):
    data = json.loads(request.body)
    source_recordid = data.get('recordid')
    tableid = data.get('tableid')

    if not source_recordid or not tableid:
        return JsonResponse({'error': 'Missing recordid or tableid'}, status=400)

    # 1️⃣ Recupera il record sorgente
    source_record = UserRecord(tableid, source_recordid)
    if not source_record.recordid:
        return JsonResponse({'error': 'Record not found'}, status=404)

    excluded_fields = {
        'recordid_', 'creatorid_', 'creation_', 'lastupdaterid_', 'lastupdate_',
        'totpages_', 'firstpagefilename_', 'recordstatus_', 'deleted_',
    }

    if tableid == 'chart':
        excluded_fields.add('report_id')

    fields_copy = {
        k: v for k, v in source_record.values.items()
        if k not in excluded_fields
    }


    fields_copy.update({"id": None})

    # 3️⃣ Copia eventuali file fisici
    files_to_copy = {}
    for fieldid, value in source_record.values.items():
        if isinstance(value, str) and '/' in value:
            try:
                old_path = default_storage.path(value)
                if os.path.exists(old_path):
                    _, ext = os.path.splitext(old_path)
                    with open(old_path, 'rb') as f:
                        files_to_copy[fieldid] = ContentFile(f.read(), name=f"{fieldid}{ext}")
            except Exception as e:
                print(f"Errore copia file {fieldid}: {e}")

    # 4️⃣ Salva nuovo record usando la funzione condivisa
    new_record = _save_record_data(
        tableid=tableid,
        recordid='',          # nuovo record
        fields=fields_copy,
        files=files_to_copy
    )

    return JsonResponse({
        'success': True,
        'new_recordid': new_record.recordid
    })

@csrf_exempt
def save_record_fields(request):
    recordid = request.POST.get('recordid')
    tableid = request.POST.get('tableid')
    saved_fields = request.POST.get('fields')

    if not tableid or not saved_fields:
        try:
            data = json.loads(request.body)
            recordid = data.get('recordid', recordid)
            tableid = data.get('tableid', tableid)
            saved_fields = data.get('fields', saved_fields)
        except (json.JSONDecodeError, AttributeError):
            return JsonResponse({'error': 'Invalid or missing data'}, status=400)

    # 3. Parsing del campo fields
    try:
        if isinstance(saved_fields, dict):
            saved_fields_dict = saved_fields
        else:
            saved_fields_dict = json.loads(saved_fields)
    except json.JSONDecodeError:
        saved_fields_dict = {}

    if not tableid:
        return JsonResponse({'error': 'Missing tableid'}, status=400)

    uploaded_files = request.FILES if request.FILES else None

    # 4️⃣ Chiama la funzione comune
    record = _save_record_data(
        tableid=tableid,
        recordid=recordid,
        fields=saved_fields_dict,
        files=uploaded_files
    )
    recordid = record.recordid

    # for file_key, uploaded_file in request.FILES.items():
    #     if file_key.startswith('files[') and file_key.endswith(']'):
    #         clean_key = file_key[6:-1]
    #     else:
    #         clean_key = file_key

    #     _, ext = os.path.splitext(uploaded_file.name)
    #     record_path = f"{tableid}/{recordid}/{clean_key}{ext}"
    #     file_path = os.path.join(tableid, recordid, f"{clean_key}{ext}")

    #     if tableid =='attachment':
    #         original_filename = uploaded_file.name
    #         record.values['filename'] = original_filename
    #         record.save()
    #         #record_path = f"{tableid}/{recordid}/{original_filename}"
    #         #file_path = os.path.join(tableid, recordid, original_filename)

            


    #     # Salvataggio tramite default_storage (usa MEDIA_ROOT)
    #     if default_storage.exists(file_path):
    #         default_storage.delete(file_path)

    #     saved_path = default_storage.save(file_path, uploaded_file)

    #     # Salva il file anche in una path di backup che viene presa dal file env
    #     try:
    #         full_path = default_storage.path(saved_path)

    #         # Usa os.path.join per evitare errori di slash
    #         backup_base = env('BACKUP_DIR')
    #         #crea la cartella con tableid e dentro recordid e salva il file con il fieldid come nel salvataggio normale, ma nella cartella di backup, presa dall'env
    #         backup_path = os.path.join(backup_base, tableid, recordid, f"{clean_key}{ext}")

    #         # Crea la cartella di backup se non esiste
    #         os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            

    #         # Copia il file fisico nella cartella di backup
    #         if os.path.exists(full_path):
    #             shutil.copy2(full_path, backup_path)
    #             print(f"🧾 Backup file salvato in: {backup_path}")
    #         else:
    #             print(f"File non trovato per backup: {full_path}")

    #     except Exception as e:
    #         print(f"Errore nel salvataggio backup: {str(e)}")
    #         full_path = os.path.join(settings.MEDIA_ROOT, saved_path)

    #     print(f"🧾 File salvato fisicamente in: {full_path}")

    #     # Salva il percorso relativo nel record
    #     record.values[clean_key] = record_path

    # record.save()

    if tableid == 'task':
        event_exist = UserEvents.objects.filter(recordidtable=recordid, tableid='task').first()
        event_record = UserRecord('events', event_exist.record_id if event_exist else None)
        due_date = record.values['duedate']
        if due_date:
            end_str = record.values.get('end')
            start_str = record.values.get('start')
            planned_date = record.values.get('planneddate') or due_date
            duration = record.values.get('duration')

            # Default se non presenti
            if not start_str and not end_str:
                start_str = "08:00"
                end_str = "17:00"

            start_date = datetime.datetime.strptime(planned_date, "%Y-%m-%d").date()
            end_date = datetime.datetime.strptime(due_date, "%Y-%m-%d").date()

            start_time = None
            end_time = None

            if start_str:
                start_time = datetime.datetime.strptime(start_str, "%H:%M").time()
            if end_str:
                end_time = datetime.datetime.strptime(end_str, "%H:%M").time()

            start_datetime = datetime.datetime.combine(start_date, start_time or datetime.time(0, 0))
            end_datetime = datetime.datetime.combine(end_date, end_time or datetime.time(0, 0))

            duration_task = 1
            if duration and int(duration) > 0:
                duration_task = int(duration)

            if not end_str:
                end_datetime = start_datetime + datetime.timedelta(hours=duration_task)
            elif not start_str:
                start_datetime = end_datetime - datetime.timedelta(hours=duration_task)

            # Salvo nei valori dell’evento
            event_record.values['start_date'] = start_datetime
            event_record.values['end_date'] = end_datetime


        event_record.values['recordidtable'] = recordid
        event_record.values['tableid'] = 'task'
        event_record.values['subject'] = record.values['description']
        event_record.values['userid'] = record.values['user']
        event_record.values['timezone'] = 'Europe/Zurich'
        event_record.values['body_content'] = record.values['note']

        event_record.save()

    if tableid == 'stabile':
        stabile_record = UserRecord('stabile', recordid)
        if Helper.isempty(stabile_record.values['titolo_stabile']):
            stabile_record.values['titolo_stabile'] = ""
        if Helper.isempty(stabile_record.values['indirizzo']):
            stabile_record.values['indirizzo'] = ""
        riferimento = stabile_record.values['titolo_stabile'] + " " + stabile_record.values['indirizzo']
        stabile_record.values['riferimento'] = riferimento
        stabile_record.save()
        sql_riferimentocompleto = """
            UPDATE user_stabile AS stabile
            JOIN user_cliente AS cliente
            ON stabile.recordidcliente_ = cliente.recordid_
            SET stabile.riferimentocompleto = CONCAT(cliente.nome_cliente, ' ', stabile.riferimento);
        """
        HelpderDB.sql_execute(sql_riferimentocompleto)

    if tableid == 'dipendente':
        dipendente_record = UserRecord('dipendente', recordid)
        if Helper.isempty(dipendente_record.values['cognome']):
            dipendente_record.values['cognome'] = ""
        if Helper.isempty(dipendente_record.values['nome']):
            dipendente_record.values['nome'] = ""
        riferimento = dipendente_record.values['nome'] + " " + dipendente_record.values['cognome']
        dipendente_record.values['riferimento'] = riferimento
        dipendente_record.save()
        

    if tableid == 'contatti':
        contatto_record = UserRecord('contatti', recordid)
        if Helper.isempty(contatto_record.values['nome']):
            contatto_record.values['nome'] = ""
        if Helper.isempty(contatto_record.values['cognome']):
            contatto_record.values['cognome'] = ""
        riferimento = contatto_record.values['nome'] + " " + contatto_record.values['cognome']
        contatto_record.values['riferimento'] = riferimento
        contatto_record.save()

    if tableid == 'contattostabile':
        contattostabile_record = UserRecord('contattostabile', recordid)
        contatto_record = UserRecord('contatti', contattostabile_record.values['recordidcontatti_'])
        contattostabile_record.values['nome'] = contatto_record.values['nome']
        contattostabile_record.values['cognome'] = contatto_record.values['cognome']
        contattostabile_record.values['email'] = contatto_record.values['email']
        contattostabile_record.values['telefono'] = contatto_record.values['telefono']
        contattostabile_record.values['ruolo'] = contatto_record.values['ruolo']
        contattostabile_record.save()

    # ---LETTURE GASOLIO---
    if tableid == 'letturagasolio':
        letturagasolio_record = UserRecord('letturagasolio', recordid)
        stabile_record = UserRecord('stabile', letturagasolio_record.values['recordidstabile_'])
        informazionigasolio_record = UserRecord('informazionigasolio', letturagasolio_record.values['recordidinformazionigasolio_'])

        capienzacisterna = Helper.safe_float(informazionigasolio_record.values['capienzacisterna'])
        letturacm = Helper.safe_float(letturagasolio_record.values['letturacm'])

        if capienzacisterna:
            if capienzacisterna == 1500:
                if letturacm:
                    letturagasolio_record.values['letturalitri'] = letturacm * 10
            if capienzacisterna == 2000:
                if letturacm:
                    letturagasolio_record.values['letturalitri'] = letturacm * 13

        #TODO anno dinamico
        #letturagasolio_record.values['anno']='2025'
        letturagasolio_record.values['recordidcliente_'] = stabile_record.values['recordidcliente_']
        letturagasolio_record.values['capienzacisterna'] = capienzacisterna
        letturagasolio_record.values['livellominimo'] = informazionigasolio_record.values['livellominimo']
        letturagasolio_record.save()

    # ---BOLLETTINI---
    if tableid == 'bollettini':
        bollettino_record = UserRecord('bollettini', recordid)
        tipo_bollettino = bollettino_record.values['tipo_bollettino']
        nr = bollettino_record.values['nr']
        if not nr:
            if not tipo_bollettino:
                tipo_bollettino = ''
            sql = "SELECT * FROM user_bollettini WHERE tipo_bollettino='" + tipo_bollettino + "' AND deleted_='N' ORDER BY nr desc LIMIT 1"
            bollettino_recorddict = HelpderDB.sql_query_row(sql)
            if bollettino_recorddict['nr'] is None:
                nr = 1
            else:
                nr = int(bollettino_recorddict['nr']) + 1
            bollettino_record.values['nr'] = nr

        allegato = bollettino_record.values['allegato']
        if allegato:
            bollettino_record.values['allegatocaricato'] = 'Si'
        else:
            bollettino_record.values['allegatocaricato'] = 'No'

        stabile_record = UserRecord('stabile', bollettino_record.values['recordidstabile_'])
        cliente_recordid = stabile_record.values['recordidcliente_']
        bollettino_record.values['recordidcliente_'] = cliente_recordid
        bollettino_record.save()

    if tableid == 'rendicontolavanderia':
        rendiconto_record = UserRecord('rendicontolavanderia', recordid)
        if rendiconto_record.values['stato'] == 'Da fare' and rendiconto_record.values['allegato']:
            rendiconto_record.values['stato'] = 'Preparato'
        rendiconto_record.save()

    if tableid == 'richieste':
        richieste_record = UserRecord('richieste', recordid)
        richieste_record.values['stato'] = 'Merce spedita'
        richieste_record.save()

    # ---OFFERTE---
    if tableid == 'offerta':
        offerta_record = UserRecord('offerta', recordid)
        offerta_id = offerta_record.values['id']
        offerta_record.values['nrofferta'] = offerta_id
        offerta_record.save()

    

    # ---ATTACHMENT---
    if tableid == 'attachment':
        attachment_record = UserRecord('attachment', recordid)
        #TODO pitservice sistemare per pitservice
        #dipendente_record = UserRecord('dipendente', attachment_record.values['recordiddipendente_'])
        #allegati= HelpderDB.sql_query(f"SELECT * FROM user_attachment WHERE recordiddipendente_='{attachment_record.values['recordiddipendente_']}' AND deleted_='N'")
        #nrallegati=len(allegati) 
        #dipendente_record.values['nrallegati'] = nrallegati
        #dipendente_record.save()



    

    

    # ---RISCALDAMENTO---
    if tableid == 'riscaldamento':
        riscaldamento_record = UserRecord('riscaldamento', recordid)
        stabile_record = UserRecord('stabile', riscaldamento_record.values['recordidstabile_'])
        riscaldamento_record.values['recordidcliente_'] = stabile_record.values['recordidcliente_']
        riscaldamento_record.save()

    # ---PISCINA---
    if tableid == 'piscina':
        piscina_record = UserRecord('piscina', recordid)
        stabile_record = UserRecord('stabile', piscina_record.values['recordidstabile_'])
        piscina_record.values['recordidcliente_'] = stabile_record.values['recordidcliente_']
        piscina_record.save()

    #TODO
    #CUSTOM ---UTENTE---TELEFONO AMICO
    if tableid == 'utenti':
        utente_record = UserRecord('utenti', recordid)

        mutable_post = request.POST.copy()
        
        # Update the mutable copy
        mutable_post['username'] = utente_record.values['nomeutente']
        mutable_post['password'] = utente_record.values['password']
        mutable_post['firstname'] = utente_record.values['nome']
        #mutable_post['lastname'] = utente_record.fields['cognome']
        #mutable_post['email'] = utente_record.fields['email']
        
        request.POST = mutable_post
        
        # Call save_newuser
        result = save_newuser(request)

    #CUSTOM ---CHART---
    if tableid == 'chart':
        # =======================
        # LOAD CHART RECORD
        # =======================
        chart_record = UserRecord("chart", recordid)
        values = chart_record.values

        name = values.get("name")
        title = values.get("title")
        userid = 1
        layout = values.get("type")
        grouping = values.get("grouping")
        grouping_type = values.get("grouping_type")
        table_name = values.get("table_name")
        fields = values.get("fields")
        dynamic_field_1 = values.get("dynamic_field_1")
        dynamic_field_1_label = values.get("dynamic_field_1_label")
        operation = values.get("operation")
        fields_2 = values.get("fields_2")
        dynamic_field_2 = values.get("dynamic_field_2")
        dynamic_field_2_label = values.get("dynamic_field_2_label")
        operation2 = values.get("operation2")
        operation2_total = values.get("operation2_total")
        chartid = values.get("report_id")
        pivot_total_field = values.get("pivot_total_field")
        granularity = values.get("date_granularity", "day")
        func_button = values.get("function_button", None)
        colors = values.get("colors", None)
        category_dashboard = values.get("category_dashboard", None)


        # =======================
        # DASHBOARDS / VIEWS
        # =======================
        dashboards_str = values.get("dashboards", None)
        views_str = values.get("views", None)
        
        # Handle dashboards_str whether it's a string or already a list
        if isinstance(dashboards_str, str):
            dashboard_ids = [d.strip() for d in dashboards_str.split(",") if d.strip()]
        elif isinstance(dashboards_str, list):
            dashboard_ids = [str(d).strip() for d in dashboards_str if str(d).strip()]
        else:
            return JsonResponse({"error": "Dashboards value is missing."}, status=400)
        
        # Handle views_str whether it's a string or already a list
        if isinstance(views_str, str):
            view_ids = [v.strip() for v in views_str.split(",") if v.strip()]
        elif isinstance(views_str, list):
            view_ids = [str(v).strip() for v in views_str if str(v).strip()]
        else:
            return JsonResponse({"error": "Views value is missing."}, status=400)

        if category_dashboard:
            # category_dashboard può essere una stringa (es. "marketing,sales") o una lista
            if isinstance(category_dashboard, str):
                category_list = [c.strip() for c in category_dashboard.split(",") if c.strip()]
            elif isinstance(category_dashboard, list):
                category_list = [str(c).strip() for c in category_dashboard if str(c).strip()]
            else:
                category_list = []

            if category_list:
                # Recupera tutte le dashboard appartenenti a una delle categorie
                dashboards_by_category = SysDashboard.objects.filter(category__in=category_list)
                category_dashboard_ids = [str(d.id) for d in dashboards_by_category]

                # Unisci evitando duplicati
                dashboard_ids = list(set(dashboard_ids + category_dashboard_ids)) if dashboard_ids else list(set(category_dashboard_ids))

        # =======================
        # FIELD TYPE (ORM)
        # =======================
        field_type = (
            SysField.objects.filter(tableid=table_name, fieldid=grouping)
            .values_list("fieldtypewebid", flat=True)
            .first()
        )

        # =======================
        # FIELD DESCRIPTIONS
        # =======================
        field_descriptions = dict(
            SysField.objects.filter(tableid=table_name).values_list("fieldid", "description")
        )

        # =======================
        # PIVOT CONFIGURATION
        # =======================
        if grouping_type == "Pivot":
            if pivot_total_field:
                pivot_fields = [
                    {
                        "alias": pivot_total_field,
                        "field": pivot_total_field,
                        "label": field_descriptions.get(pivot_total_field, pivot_total_field),
                    }
                ]
                part_field_aliases = []

                if fields:
                    for field in fields.split(","):
                        field = field.strip()
                        if not field:
                            continue
                        part_field_aliases.append(field)
                        pivot_fields.append(
                            {
                                "alias": field,
                                "field": field,
                                "label": field_descriptions.get(field, field),
                            }
                        )

                config_python = {
                    "chart_type": "record_pivot",
                    "from_table": table_name,
                    "aggregation": {"function": "AVG"},
                    "pivot_fields": pivot_fields,
                    "dataset_label": name,
                    "total_breakdown": {
                        "total_field_alias": pivot_total_field,
                        "part_field_aliases": part_field_aliases,
                        "include_remainder": True,
                        "remainder_label": "Other",
                    },
                }

            else:
                datasets = [
                    {
                        "label": field_descriptions.get(field.strip(), field.strip()),
                        "alias": field.strip(),
                        "field": field.strip(),
                    }
                    for field in fields.split(",")
                    if field.strip()
                ]

                config_python = {
                    "chart_type": "record_pivot",
                    "from_table": table_name,
                    "aggregation": {"function": "AVG"},
                    "pivot_fields": datasets,
                    "dataset_label": f"Average {datasets[0]['label']}" if datasets else "Average Data",
                }

        # =======================
        # NON-PIVOT CONFIGURATION
        # =======================
        else:
            datasets = []
            for field in fields.split(","):
                field = field.strip()
                if not field:
                    continue
                dataset = {
                    "label": field_descriptions.get(field, field),
                    "alias": field,
                }
                if operation == "Somma":
                    dataset["expression"] = f"SUM({field})"
                else:
                    dataset["expression"] = f"COUNT({field})"
                datasets.append(dataset)

            # Dynamic Field 1
            if dynamic_field_1:
                datasets.append(
                    {
                        "label": dynamic_field_1_label,
                        "expression": dynamic_field_1,
                        "alias": dynamic_field_1_label,
                    }
                )

            # Secondary Datasets
            datasets2 = []
            if operation2_total == "Si":
                for field2 in (fields_2 or "").split(","):
                    field2 = field2.strip()
                    if not field2:
                        continue
                    if operation2 == "Media":
                        datasets2.append(
                            {
                                "alias": field2,
                                "label": "Average " + field_descriptions.get(field2, field2),
                                "post_calculation": {
                                    "function": "AVG",
                                    "source_dataset_alias": field2,
                                },
                            }
                        )
            else:
                for field2 in (fields_2 or "").split(","):
                    field2 = field2.strip()
                    if not field2:
                        continue
                    dataset2 = {
                        "label": field_descriptions.get(field2, field2),
                        "alias": field2,
                    }
                    dataset2["expression"] = (
                        f"SUM({field2})" if operation2 == "Somma" else f"COUNT({field2})"
                    )
                    datasets2.append(dataset2)

                if dynamic_field_2:
                    datasets2.append(
                        {
                            "label": dynamic_field_2_label,
                            "expression": dynamic_field_2,
                            "alias": dynamic_field_2_label,
                        }
                    )

            config_python = {
                "from_table": table_name,
                "group_by_field": {
                    "field": grouping,
                    "alias": grouping,
                },
                "datasets": datasets,
                "datasets2": datasets2,
                "order_by": f"{grouping} ASC",
            }

            #TODO custom wegolf gestiredinamico
            if grouping == 'recordidgolfclub_':
                config_python['group_by_field']["lookup"] = {
                    "on_key": "recordid_",
                    "from_table": "golfclub",
                    "display_field": "nome_club"
                }

            # Date granularity
            if field_type and field_type.lower() in ("date", "datetime", "data"):
                config_python["group_by_field"]["date_granularity"] = granularity

        # =======================
        # CHART SAVE (ORM)
        # =======================
        user = SysUser.objects.filter(id=userid).first()
        if chartid and chartid != "None":
            SysChart.objects.filter(id=chartid).update(
                name=title, layout=layout, config=config_python, userid=user,colors=colors, function_button_id=func_button
            )
            chart_obj = SysChart.objects.get(id=chartid)
        else:
            chart_obj = SysChart.objects.create(
                name=title, layout=layout, config=config_python, userid=user,colors=colors, function_button_id=func_button
            )
            chart_record.values["report_id"] = chart_obj.id
        chart_record.save()

        # =======================
        # DASHBOARD / VIEW LOGIC
        # =======================
        default_view = SysView.objects.filter(tableid=table_name, query_conditions="true").first()
        if not view_ids and default_view:
            view_ids = [str(default_view.id)]

        # Existing combinations
        existing_blocks = SysDashboardBlock.objects.filter(chartid=chart_obj)
        existing_combinations = set(
            (str(b.dashboardid_id) if b.dashboardid_id else None, str(b.viewid_id) if b.viewid_id else None)
            for b in existing_blocks
        )

        target_combinations = set()
        for dashboard_id in (dashboard_ids):
            for view_id in view_ids:
                target_combinations.add((dashboard_id, view_id))

        to_delete = existing_combinations - target_combinations
        to_create = target_combinations - existing_combinations
        to_update = target_combinations & existing_combinations

        # Delete old blocks
        for dashboard_id, view_id in to_delete:
            SysDashboardBlock.objects.filter(
                chartid=chart_obj, dashboardid_id=dashboard_id, viewid_id=view_id
            ).delete()

        # Create new blocks
        for dashboard_id, view_id in to_create:
            dashboard_obj = SysDashboard.objects.filter(id=dashboard_id).first() if dashboard_id else None
            view_obj = SysView.objects.filter(id=view_id).first() if view_id else None
            final_name = f"{title} {(view_obj.name if view_obj else '')} {(dashboard_obj.name if dashboard_obj else '')}".strip()

            SysDashboardBlock.objects.create(
                name=final_name,
                userid=user.id,
                viewid_id=view_id if view_obj else (default_view.id if default_view else None),
                chartid=chart_obj,
                dashboardid_id=dashboard_id if dashboard_obj else None,
                category="benchmark" if grouping == "recordidgolfclub_" else None,
            )

        # Update existing blocks
        for dashboard_id, view_id in to_update:
            dashboard_obj = SysDashboard.objects.filter(id=dashboard_id).first() if dashboard_id else None
            view_obj = SysView.objects.filter(id=view_id).first() if view_id else None
            final_name = f"{title} {(view_obj.name if view_obj else '')} {(dashboard_obj.name if dashboard_obj else '')}".strip()
            SysDashboardBlock.objects.filter(
                chartid=chart_obj, dashboardid_id=dashboard_id, viewid_id=view_id
            ).update(name=final_name)

    custom_save_record_fields(tableid, recordid)
    return JsonResponse({"success": True, "detail": "Campi del record salvati con successo", "recordid": record.recordid})



def custom_save_record_fields(tableid, recordid):
    idcliente = Helper.get_cliente_id()
    # Nome del modulo dinamico
    module_name = f"customapp_{idcliente}.customfunc"

    try:
        # Import dinamico
        customfunc = importlib.import_module(module_name)

        # Chiama la funzione se esiste
        if hasattr(customfunc, "save_record_fields"):
            return customfunc.save_record_fields(tableid, recordid)
        else:
            print(f"Funzione 'save_record_fields' non trovata in {module_name}")
    except ModuleNotFoundError:
        print(f"Modulo personalizzato {module_name} non trovato")
    except Exception as e:
        print(f"Errore durante l'importazione o l'esecuzione: {e}")

def get_table_views(request):
    data = json.loads(request.body)
    tableid= data.get("tableid")
    userid=Helper.get_userid(request)
    table=UserTable(tableid)
    table_default_viewid=table.get_default_viewid()
    table_views=table.get_table_views()

    views=[ ]
    for table_view in table_views:
        views.append({'id':table_view['id'],'name':table_view['name']})
    response={ "views": views, "defaultViewId": table_default_viewid}

    return JsonResponse(response)


def get_record_badge(request):
    data = json.loads(request.body)
    tableid= data.get("tableid")
    recordid= data.get("recordid")

    record=UserRecord(tableid,recordid)
    badgeItems=record.get_badge_fields()
    return_badgeItems={}
    for badgeItem in badgeItems:    
        return_badgeItems[badgeItem['fieldid']] = badgeItem['value']

    response={ "badgeItems": return_badgeItems}
    return JsonResponse(response)

def get_categories_dashboard(request):
    categories_dashboard = SysDashboard.objects.values_list('category', flat=True).distinct()
    categories_dashboard_lookup = [
        {"value": category, "label": category}
        for category in categories_dashboard if category
    ]

    return JsonResponse({"categories_dashboard": categories_dashboard_lookup})

def get_record_card_fields(request):
    data = json.loads(request.body)
    tableid= data.get("tableid")
    recordid= data.get("recordid")
    master_tableid= data.get("mastertableid")
    master_recordid= data.get("masterrecordid")

    userid = Helper.get_userid(request)

    record=UserRecord(tableid,recordid,userid,master_tableid,master_recordid)
    card_fields=record.get_record_card_fields()

    response={ "fields": card_fields, "recordid": recordid}
    if tableid == "chart":
        # Lookup per tabella sorgente
        tables_qs = SysTable.objects.all().values("id", "description")
        tables_lookup = [
            {"value": str(t["id"]), "label": t["description"]} for t in tables_qs
        ]

        # Lookup per campi (organizzati per tableid)
        fields_qs = SysField.objects.all().values("tableid", "fieldid", "description", "fieldtypewebid").order_by("tableid", "id")
        fields_lookup = {}
        for f in fields_qs:
            tid = str(f["tableid"])
            if tid not in fields_lookup:
                fields_lookup[tid] = []
            fields_lookup[tid].append({
                "value": f["fieldid"],
                "label": f["description"],
                "fieldtype": f["fieldtypewebid"]
            })

        dashboards_qs = SysDashboard.objects.all().values("id", "name").order_by("order_dashboard")

        dashboards_lookup = [
            {"value": str(d["id"]), "label": d["name"]}
            for d in dashboards_qs
        ]

        # Categories dashboard
        categories_dashboard = SysDashboard.objects.values_list('category', flat=True).distinct()
        categories_dashboard_lookup = [
            {"value": category, "label": category}
            for category in categories_dashboard if category
        ]

        # Views per tableid
        views_qs = SysView.objects.all().values("tableid", "name", "id")
        views_lookup = {}
        for v in views_qs:
            tid = str(v["tableid"])
            if tid not in views_lookup:
                views_lookup[tid] = []
            views_lookup[tid].append({
                "value": str(v["id"]),
                "label": v["name"]
            })

        customs_fn = SysCustomFunction.objects.all().order_by('order').values('id', 'title')
        functions_lookup = [
            {"value": str(fn["id"]), "label": fn["title"]}
            for fn in customs_fn
        ]

        colors = Helper.get_chart_colors()
        colors_lookup = [
            {"value": color, "label": color}
            for color in colors
        ]

        # Inseriamo i lookup nella response
        response["lookup"] = {
            "table": tables_lookup,
            "campi": fields_lookup,
            "views": views_lookup,
            "dashboards": dashboards_lookup,
            "functions": functions_lookup,
            "colors": colors_lookup,
            "categories_dashboard": categories_dashboard_lookup,
        }

    return JsonResponse(response)

def get_record_linked_tables(request):
    data = json.loads(request.body)
    master_tableid= data.get("masterTableid")
    master_recordid= data.get("masterRecordid")

    record=UserRecord(master_tableid,master_recordid)
    linkedTables=record.get_linked_tables()
    response={ "linkedTables": linkedTables}
    return JsonResponse(response)

#TODO da spostare nelle relative installazioni dei singoli clienti
@csrf_exempt
def prepara_email(request):
    data = json.loads(request.body)
    tableid= data.get("tableid")
    recordid= data.get("recordid")
    type= data.get("type")
    print(tableid,recordid)

    email_fields = {
            "to": "",
            "cc": "",
            "bcc": "",	
            "subject": "",
            "text": "",
            "attachment_fullpath": "",
            "attachment_relativepath": "",
            "attachment_name": "",
            }
    
    if type == 'emailLavanderia':
        rendiconto_recordid=recordid
        rendiconto_record=UserRecord('rendicontolavanderia',rendiconto_recordid)
        mese=rendiconto_record.values['mese'][3:]
        anno=rendiconto_record.values['anno']
        stato=rendiconto_record.values['stato']
        stabile_recordid=rendiconto_record.values['recordidstabile_']
        stabile_record=UserRecord('stabile',stabile_recordid)
        stabile_riferimento=stabile_record.values['riferimento']
        stabile_indirizzo=stabile_record.values['indirizzo']
        stabile_citta=stabile_record.values['citta']
        sql=f"SELECT * FROM user_contattostabile WHERE deleted_='N' AND recordidstabile_='{stabile_recordid}'"
        rows=HelpderDB.sql_query(sql)
        emailto=''
        for row in rows:
            contatto_email=None
            contatto_recordid=row['recordidcontatti_']
            if contatto_recordid != 'None':
                contatto_record=UserRecord('contatti',contatto_recordid)
                if contatto_record:
                    contatto_email=contatto_record.values['email']
            if contatto_email:
                if emailto=='':
                    emailto=contatto_email
                else:
                    emailto=emailto+','+contatto_email


        attachment_fullpath=HelpderDB.get_uploadedfile_fullpath('rendicontolavanderia',rendiconto_recordid,'allegato')
        attachment_relativepath=HelpderDB.get_uploadedfile_relativepath('rendicontolavanderia',rendiconto_recordid,'allegato')
        subject=f"Resoconto lavanderia - {stabile_riferimento} {stabile_citta} - {mese} {anno}"

        body = ""
        attachment_name=f"{stabile_riferimento} {stabile_citta} - Lavanderia - {mese} - {anno}.pdf"

        if stato=='Da fare':
            body = "Rendiconto da fare"

        if stato=='Inviato':
            body = "Rendiconto già inviato"

        if stato=='Preparato':
            
            body=f"""

                <p>
                    Egregi Signori,<br/>
                    Con la presente in allegato trasmettiamo il resoconto delle lavanderie dello stabile in {stabile_indirizzo} a {stabile_citta}.<br/>
                    Restiamo volentieri a disposizione e porgiamo cordiali saluti.
                </p>
                <br/>
                <table style="border: none; border-collapse: collapse; margin-top: 20px;">
                        <tr>
                            <td style="vertical-align: top; padding-right: 10px;">
                                <img src="https://pitservice.ch/wp-content/uploads/2025/04/miniminilogo.png" alt="Pit Service Logo">
                            </td>
                            <td style="font-family: Arial, sans-serif; font-size: 14px; line-height: 1.0">
                                <p>
                                    <b>Pit Service Sagl</b><br/>
                                    La cura del tuo immobile<br/>
                                    Phone: 091.993.03.92 <br/>
                                    Via Carvina 6 <br/>
                                    6807 Taverne <br/>
                                </p>
                            </td>
                        </tr>
                    </table>

                """
        
        if stato=='Nessuna ricarica':
            attachment_fullpath=''
            attachment_relativepath=''
            attachment_name=''
            body=f"""
<p>
Egregi Signori,<br/>

con la presente per informarvi che durante il mese corrente non abbiamo eseguito ricariche tessere lavanderia presso lo stabile in {stabile_indirizzo} a {stabile_citta}.<br/>

Cordiali saluti
</p>
<br/>
<table style="border: none; border-collapse: collapse; margin-top: 20px;">
                    <tr>
                        <td style="vertical-align: top; padding-right: 10px;">
                            <img src="https://pitservice.ch/wp-content/uploads/2025/04/miniminilogo.png" alt="Pit Service Logo">
                        </td>
                        <td style="font-family: Arial, sans-serif; font-size: 14px; line-height: 1.0">
                            <p>
                                <b>Pit Service Sagl</b><br/>
                                La cura del tuo immobile<br/>
                                Phone: 091.993.03.92 <br/>
                                Via Carvina 6 <br/>
                                6807 Taverne <br/>
                            </p>
                        </td>
                    </tr>
                </table>
            """

        email_fields = {
            "to": emailto,
            "cc": "contabilita@pitservice.ch,segreteria@pitservice.ch",
            "bcc": "",	
            "subject": subject,
            "text": body,
            "attachment_fullpath": attachment_fullpath,
            "attachment_relativepath": attachment_relativepath,
            "attachment_name": attachment_name,
            }
    
    if type == 'emailGasolio':
        stabile_recordid=recordid
        stabile_record=UserRecord('stabile',stabile_recordid)
        #TODO pitservice sistemare dinamico TODO GASOLI
        meseLettura='2025-10'
        anno, mese = meseLettura.split('-')

        sql=f"SELECT * FROM user_contattostabile WHERE deleted_='N' AND recordidstabile_='{stabile_recordid}'"
        row=HelpderDB.sql_query_row(sql)
        rows=HelpderDB.sql_query(sql)
        emailto=''
        for row in rows:
            contatto_email=None
            contatto_recordid=row['recordidcontatti_']
            if contatto_recordid != 'None':
                contatto_record=UserRecord('contatti',contatto_recordid)
                if contatto_record:
                    contatto_email=contatto_record.values['email']
            if contatto_email:
                if emailto=='':
                    emailto=contatto_email
                else:
                    emailto=emailto+','+contatto_email

        attachment_relativepath=stampa_gasoli(request)
        riferimento=stabile_record.values.get('riferimento', '')
        stabile_citta=stabile_record.values['citta']
        subject=f"Livello Gasolio - {mese} {anno} - {riferimento} {stabile_citta}"
        body=f"""
         <p>
                Egregi Signori,<br/>
                con la presente in allegato trasmettiamo la lettura gasolio dello stabile in {stabile_record.values['indirizzo']}<br/>
                Restiamo volentieri a disposizione e porgiamo cordiali saluti.<br/>
        </p>

                <table style="border: none; border-collapse: collapse; margin-top: 20px;">
                    <tr>
                        <td style="vertical-align: top; padding-right: 10px;">
                            <img src="https://pitservice.ch/wp-content/uploads/2025/04/miniminilogo.png"  alt="Pit Service Logo">
                        </td>
                        <td style="font-family: Arial, sans-serif; font-size: 14px; ">
                            <p>
                                <b>Pit Service Sagl</b><br/>
                                La cura del tuo immobile<br/>
                                Phone: 091.993.03.92 <br/>
                                Via Carvina 6 <br/>
                                6807 Taverne <br/>
                            </p>
                        </td>
                    </tr>
                </table>
                """
        
        email_fields = {
            "to": emailto,
            "cc": "contabilita@pitservice.ch,segreteria@pitservice.ch",
            "bcc": "",	
            "subject": subject,
            "text": body,
            "attachment_fullpath": "",
            "attachment_relativepath": attachment_relativepath,
            "attachment_name": f"Lettura_Gasolio_{mese}-{anno}-{riferimento}-{stabile_citta}.pdf",
            }

    return JsonResponse({"success": True, "emailFields": email_fields})

@csrf_exempt
def stampa_gasoli(request):
    data={}
    filename='report gasolio.pdf'
    recordid_stabile = ''
    data = json.loads(request.body)
    if request.method == 'POST':
        recordid_stabile = data.get('recordid')
        #meseLettura=data.get('date')
        #TODO pitservice sistemare dinamico TODO GASOLI
        meseLettura="2025 10-Ottobre"
        anno, mese = meseLettura.split(' ')
    script_dir = os.path.dirname(os.path.abspath(__file__))
    wkhtmltopdf_path = script_dir + '\\wkhtmltopdf.exe'
    config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
    
    record_stabile=UserRecord('stabile',recordid_stabile)
    data['stabile']=record_stabile.values
    sql=f"""
    SELECT t.recordid_,t.anno,t.mese,t.datalettura,t.letturacm,t.letturalitri, i.riferimento, i.livellominimo, i.capienzacisterna, i.note
    FROM user_letturagasolio t
    INNER JOIN (
        SELECT recordidinformazionigasolio_, MAX(datalettura) AS max_datalettura
        FROM user_letturagasolio
        WHERE anno='{anno}' AND mese like '%{mese}%' AND deleted_='N' AND recordidstabile_ = '{recordid_stabile}'
        GROUP BY recordidinformazionigasolio_
        
    ) subquery
    ON t.recordidinformazionigasolio_ = subquery.recordidinformazionigasolio_ 
    AND t.datalettura = subquery.max_datalettura
    INNER JOIN user_informazionigasolio i
    ON t.recordidinformazionigasolio_ = i.recordid_
    WHERE t.recordidstabile_ = '{recordid_stabile}' AND t.deleted_ = 'N' 
            """
    ultimeletturegasolio = HelpderDB.sql_query(sql)
    data['ultimeletturegasolio']=ultimeletturegasolio
    data["show_letturacm"] = any(l.get('letturacm') for l in ultimeletturegasolio)
    data["show_note"] = any(l.get('note') for l in ultimeletturegasolio)

    content = render_to_string('pdf/gasolio.html', data)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    wkhtmltopdf_path = script_dir + '\\wkhtmltopdf.exe'
    config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
    
    filename = f"Lettura Gasolio {mese} {anno}  {record_stabile.values['indirizzo']}.pdf"
    filename = re.sub(r'[\\/*?:"<>|]', "", filename)
    #filename='gasolio.pdf'

    filename_with_path = os.path.dirname(os.path.abspath(__file__))
    filename_with_path = filename_with_path.rsplit('views', 1)[0]
    filename_with_path = filename_with_path + '\\static\\pdf\\' + filename
    pdfkit.from_string(
        content,
        filename_with_path,
        configuration=config,
        options={
            "enable-local-file-access": "",
            # "quiet": ""  # <-- rimuovilo!
        }
    )

    if True:
        return 'commonapp/static/pdf/' + filename
    else:
        try:
            with open(filename_with_path, 'rb') as fh:
                response = HttpResponse(fh.read(), content_type="application/pdf")
                response['Content-Disposition'] = f'inline; filename={filename}'
                return response
            return response

        finally:
            os.remove(filename_with_path)
    


@csrf_exempt
def save_email(request):
    data = json.loads(request.body)
    email_data = data.get('emailData')
    tableid = data.get('tableid')
    recordid = data.get('recordid')
    #TODO 
    if tableid == 'rendicontolavanderia':
        record_rendiconto=UserRecord('rendicontolavanderia',recordid)
        if record_rendiconto.values['stato']=='Nessuna ricarica':
            record_rendiconto.values['stato']="Inviato - Nessuna ricarica"
        else:
            record_rendiconto.values['stato']="Inviato"
        record_rendiconto.save()
    record_email=UserRecord('email')
    record_email.values['recipients']=email_data['to']
    record_email.values['subject']=email_data['subject']  
    mail_body=email_data['text']
    if mail_body:
        mail_body=mail_body.replace('<p>','<p style="margin:0 0 4px 0;">')  
    record_email.values['mailbody']=mail_body
    record_email.values['cc']=email_data['cc']
    record_email.values['ccn']=email_data['bcc']
    
    record_email.values['status']="Da inviare"
    record_email.save()

    attachment_relativepath=email_data['attachment_relativepath']
    if attachment_relativepath != '':   
        record_email.values['attachment_name']=email_data['attachment_name'] 
        if attachment_relativepath.startswith("commonapp/static"):
            base_dir=settings.BASE_DIR
            file_path = os.path.join(settings.BASE_DIR, attachment_relativepath)
            #fullpath_originale = default_storage.path(file_path)
            fullpath_originale = Path(file_path)
            fullpath_originale=str(fullpath_originale)
        else:
                fullpath_originale=HelpderDB.get_uploadedfile_fullpath(tableid,recordid,'allegato')
        
        fullpath_email=HelpderDB.get_upload_fullpath('email',record_email.recordid,'attachment')
        #  Assicurati che la cartella di destinazione esista
        os.makedirs(os.path.dirname(fullpath_email), exist_ok=True)

        # ------------------ copia dell’allegato -------------
        if os.path.isfile(fullpath_originale):
            shutil.copy2(fullpath_originale, fullpath_email)
        
        record_email.values['attachment']=f"email/{record_email.recordid}/attachment.pdf"

    record_email.save()

    return JsonResponse({"success": True})

@csrf_exempt
def get_input_linked(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            searchTerm = data.get('searchTerm', '').lower()
            #linkedmaster_tableid_array = data.get('linkedmaster_tableid') # Puoi usare tableid se necessario
            #linkedmaster_tableid=linkedmaster_tableid_array[0]
            linkedmaster_tableid=data.get('linkedmaster_tableid')
            tableid=data.get('tableid')
            fieldid=data.get('fieldid')
            formValues=data.get('formValues')
            # Qui dovresti sostituire i dati di esempio con la tua logica di database
            # o qualsiasi altra fonte di dati.
            sql=f"SELECT keyfieldlink FROM sys_field WHERE tableid='{tableid}' AND fieldid='{fieldid}'"
            kyefieldlink=HelpderDB.sql_query_value(sql,'keyfieldlink')
            additional_conditions = ''
            #TODO temp
            if tableid == 'letturagasolio' and fieldid == 'recordidstabile_':
                recordid_cliente=formValues['recordidcliente_']
                if recordid_cliente:
                    additional_conditions = " AND recordidcliente_ = '"+recordid_cliente+"'"

            if tableid == 'letturagasolio' and fieldid == 'recordidinformazionigasolio_':
                recordid_stabile=formValues['recordidstabile_']
                if recordid_stabile:
                    additional_conditions = " AND recordidstabile_ = '"+recordid_stabile+"'"
            if searchTerm:
                sql=f"SELECT recordid_ as recordid, {kyefieldlink} as name FROM user_{linkedmaster_tableid} where {kyefieldlink} like '%{searchTerm}%' {additional_conditions} AND deleted_='N' ORDER BY recordid_ DESC LIMIT 20"
            else:
                sql=f"SELECT recordid_ as recordid, {kyefieldlink} as name FROM user_{linkedmaster_tableid} where deleted_='N' {additional_conditions} ORDER BY recordid_ desc LIMIT 20 "

            query_result=HelpderDB.sql_query(sql)
            items=query_result
            # Filtra gli elementi in base al searchTerm
            #filtered_items = [item for item in items if searchTerm in item['name'].lower()]

            return JsonResponse(items, safe=False)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
    else:
        return JsonResponse({'error': 'Method not allowed'}, status=405)




@csrf_exempt
def stampa_bollettini_test(request):
    data={}
    filename='bollettinotest.pdf'
    
    recordid_bollettino = ''
    data = json.loads(request.body)
    recordid_bollettino = data.get('recordid')
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    wkhtmltopdf_path = script_dir + '\\wkhtmltopdf.exe'
    config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
    
    content = render_to_string('pdf/bollettino_test.html', data)

    filename_with_path = os.path.dirname(os.path.abspath(__file__))
    filename_with_path = filename_with_path.rsplit('views', 1)[0]
    filename_with_path = filename_with_path + '\\static\\pdf\\' + filename
    pdfkit.from_string(
    content,
    filename_with_path,
    configuration=config,
    options={
        "enable-local-file-access": "",
        # "quiet": ""  # <-- rimuovilo!
    }
)


    #return HttpResponse(content)

    try:
        with open(filename_with_path, 'rb') as fh:
            response = HttpResponse(fh.read(), content_type="application/pdf")
            response['Content-Disposition'] = f'inline; filename={filename}'
            return response
        return response

    finally:
        os.remove(filename_with_path)

@csrf_exempt
def send_emails(request):
    data = {}
    
    if request.method == 'POST' and request.content_type == 'application/json':
        try:
            body_unicode = request.body.decode('utf-8')
            if body_unicode:  # controlla che non sia vuoto
                data = json.loads(body_unicode)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    recordid = data.get('recordid')

    if recordid:
        emails = HelpderDB.sql_query(f"SELECT * FROM user_email WHERE recordid_='{recordid}'")
    else:
        emails_to_send=[]
        emails = HelpderDB.sql_query("SELECT * FROM user_email WHERE status='Da inviare' LIMIT 5")
    
    for email in emails:
        full_path_attachment = None
        if email['attachment']:
            try:
                # Costruisci il percorso corretto del file
                file_path = os.path.join(settings.UPLOADS_ROOT, email['attachment'])
                
                # Verifica che il file esista
                if default_storage.exists(file_path):
                    full_path = default_storage.path(file_path)
                else:
                    full_path = os.path.join(settings.UPLOADS_ROOT, file_path)
                if os.path.exists(full_path):
                    full_path_attachment=full_path
                    
                else:
                    print(f"File non trovato: {file_path}")
                    full_path_attachment = None
            except Exception as e:
                print(f"Errore durante la lettura del file: {str(e)}")
                full_path_attachment = None

              
        try:
            result = EmailSender.send_email(
                emails=email['recipients'],
                subject=email['subject'],
                html_message=email['mailbody'],
                cc=email['cc'],
                bcc=email['ccn'],
                recordid=email['recordid_'],
                attachment=full_path_attachment,
                attachment_name=email['attachment_name']
            )
            email_record=UserRecord('email',email['recordid_'])
            email_record.values['status']='Inviata'
            email_record.values['date'] = datetime.datetime.now().strftime("%Y-%m-%d")  # formato aaaa-mm-gg
            email_record.values['sent_timestamp'] = datetime.datetime.now().strftime("%H:%M:%S")
            email_record.save()
        except Exception as e:
            print(str(e))
            return HttpResponse(f"Errore invio: {str(e)}")


    return HttpResponse("Email inviate con successo!")


@csrf_exempt
def get_form_data(request):
    data = json.loads(request.body)
    form_type = data.get('formType')
    formName = f"FORMULARIO ORDINE {form_type} 2025"
    raw_products  = HelpderDB.sql_query(f"SELECT * FROM user_sync_adiuto_prodotti WHERE deleted_='N' AND gruppo='{form_type}'")
        # Riorganizza per categoria
    categories_dict = defaultdict(list)
    for prod in raw_products:
        categoria = prod["categoria"] or "Senza Categoria"
        categories_dict[categoria].append({
            "id": prod["codice"],
            "name": prod["descrizione"]
        })

    # Convertilo in una lista nel formato atteso
    categories = [{"title": k, "products": v} for k, v in categories_dict.items()]

    categories2 = [
                {
                    "title": "Small Cases",
                    "products": [
                        {"id": "20.1069", "name": "Pink"},
                        {"id": "17.0070", "name": "Electro"},
                        {"id": "13.0469", "name": "Purple"},
                        {"id": "23.2442", "name": "Brown"},
                        {"id": "13.0467", "name": "Green"},
                    ],
                },
                {
                    "title": "Large Cases",
                    "products": [
                        {"id": "20.1070", "name": "Pink"},
                        {"id": "17.0071", "name": "Electro"},
                        {"id": "14.0067", "name": "Purple"},
                        {"id": "23.2443", "name": "Brown"},
                        {"id": "14.0065", "name": "Green"},
                    ],
                },
                {
                    "title": "Spray / Microfibers",
                    "products": [
                        {"id": "24.4657", "name": "Amsterdam"},
                        {"id": "24.4658", "name": "Cannes"},
                        {"id": "24.4659", "name": "Varenna"},
                    ],
                },
                {
                    "title": "Microfibers",
                    "products": [
                        {"id": "24.4653", "name": "Amsterdam"},
                        {"id": "24.4654", "name": "Cannes"},
                        {"id": "24.4655", "name": "Varenna"},
                    ],
                },
                {
                    "title": "Ambient",
                    "products": [
                        {"id": "23.3208", "name": "Ambient diffuser 200ml"},
                        {"id": "23.3209", "name": "Ambient spray 250ml"},
                        {"id": "21.1299", "name": "Belotti Candles"},
                    ],
                },
                {
                    "title": "Tatto",
                    "products": [
                        {"id": "19.0780", "name": "Asphalt clutch"},
                        {"id": "19.0778", "name": "Electro clutch"},
                        {"id": "19.0779", "name": "Nude clutch"},
                        {"id": "19.0783", "name": "Asphalt wallet"},
                        {"id": "19.0781", "name": "Electro wallet"},
                        {"id": "19.0782", "name": "Nude wallet"},
                        {"id": "15.0021", "name": "Black card holder"},
                        {"id": "15.0016", "name": "Black keychain"},
                    ],
                },
                {
                    "title": "Stationery",
                    "products": [
                        {"id": "23.2457", "name": "Transparent tape"},
                        {"id": "23.2456", "name": "Packing tape"},
                        {"id": "23.3599", "name": "Green highlighter"},
                        {"id": "23.2459", "name": "Yellow highlighter"},
                        {"id": "23.2460", "name": "Stapler refill"},
                        {"id": "15.557", "name": "Zeiss pen"},
                        {"id": "15.0528", "name": "Zeiss centering marker"},
                    ],
                },
            ]
        

    return JsonResponse({"success": True, "formName": formName, "categories": categories})



@csrf_exempt
def save_belotti_form_data(request):
    data = json.loads(request.body)
    print(data)
    return JsonResponse({"success": True})


import json
import pandas as pd
import io
import os
from django.http import JsonResponse, HttpResponse
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
import uuid


def remove_html_tags(input_string):
    soup = BeautifulSoup(input_string, "html.parser")
    cleaned_text = soup.get_text(separator=" ")
    splitted = cleaned_text.split("|:|")

    if splitted:  # Check if the list is not empty
        cleaned_text = splitted[0]

    return cleaned_text

@csrf_exempt
def export_excel(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            tableid = data.get('tableid', 'export')
            searchTerm = data.get('searchTerm')
            viewid = data.get('view')
            filters = data.get('filters', {})
        
            table = UserTable(tableid)
            if viewid == '':
                viewid=table.get_default_viewid()

            records: List[UserRecord]
            conditions_list=list()
            records=table.get_table_records_obj(viewid=viewid,searchTerm=searchTerm, conditions_list=conditions_list, filters_list=filters, limit=10000)
            counter=table.get_total_records_count()
            table_columns=table.get_results_columns()
            rows=[]
            for record in records:
                row = {
                    'recordid': record.recordid,
                    'css': '#',
                    'fields': []
                }

                # Dizionario dei campi effettivi nel record
                fields = record.fields or {}

                # Cicla su tutte le colonne previste dalla tabella
                for table_column in table_columns:
                    fieldid = table_column.get('fieldid')
                    field = fields.get(fieldid, {})  # Prendi il campo se esiste, altrimenti dict vuoto

                    value = field.get('convertedvalue', field.get('value', ''))
                    fieldtype = field.get('fieldtypewebid', 'standard')
                    cssClass = ''

                    # Crea la cella
                    field_data = {
                        'recordid': record.recordid,
                        'css': cssClass,
                        'type': fieldtype,
                        'value': value,
                        'fieldid': fieldid
                    }

                    row['fields'].append(field_data)

                rows.append(row)

            # (Opzionale) Costruisci anche la lista colonne
            columns = [
                {'fieldtypeid': col['fieldtypeid'], 'desc': col['description']}
                for col in table_columns
            ]

            # Prepara i dati ristrutturati per il DataFrame


            # Crea il DataFrame
            df = pd.DataFrame({
                'recordid': [row['recordid'] for row in rows],
                **{f"{col['desc']}": [row['fields'][i]['value'] for row in rows] for i, col in enumerate(columns)}
            }) 
            buffer = io.BytesIO()

            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Sheet1', index=False)
       
            buffer.seek(0)

            # Genera filename e path completo
            filename = f'{tableid}_{uuid.uuid4().hex}.xlsx'
            
            # Costruisci il path completo seguendo il pattern di stampa_bollettini
            script_dir = os.path.dirname(os.path.abspath(__file__))
            filename_with_path = script_dir.rsplit('views', 1)[0]
            filename_with_path = filename_with_path + '\\static\\excel\\' + filename
            print("filename_with_path:")
            print(filename_with_path)
            # Crea la directory se non esiste
            os.makedirs(os.path.dirname(filename_with_path), exist_ok=True)

            # Salva il file Excel
            with open(filename_with_path, 'wb') as f:
                f.write(buffer.getvalue())

            # Restituisci il file come response (usando lo stesso pattern di stampa_bollettini)
            try:
                with open(filename_with_path, 'rb') as fh:
                    response = HttpResponse(fh.read(), content_type="application/pdf")
                    response['Content-Disposition'] = f'inline; filename={filename}'
                    return response

            finally:
                # Rimuovi il file temporaneo dopo aver inviato la response
                if os.path.exists(filename_with_path):
                    os.remove(filename_with_path)

        except Exception as e:
            print(f"Errore durante l'esportazione: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Metodo non consentito'}, status=405)


@csrf_exempt
def get_record_attachments(request):
    data = json.loads(request.body)
    tableid = data.get('tableid')
    recordid = data.get('recordid')
    response={ "attachments": []}
    #TODO sistemare dinamico
    attachments=HelpderDB.sql_query(f"SELECT * FROM user_attachment WHERE recordid{tableid}_='{recordid}' AND deleted_ = 'N'")
    attachment_list=[]
    for attachment in attachments:
        recordid=attachment['recordid_']
        file=attachment['file']
        type=attachment['type']
        note=attachment['note']
        filename=note=attachment['filename']
        attachment_list.append({'recordid':recordid,'file':file,'type':type, 'note':note, 'filename':filename})
        
    response={ "attachments": attachment_list}
    print(response)
    return JsonResponse(response)
    
@csrf_exempt
def get_card_active_tab(request):
    data = json.loads(request.body)
    tableid = data.get('tableid')

    sql=f"SELECT * FROM sys_user_table_settings WHERE tableid='{tableid}' AND settingid='card_tabs'"
    query_result=HelpderDB.sql_query_row(sql)
    if not query_result:
        card_tabs = ['Campi','Collegati']
    else:
        card_tabs=query_result['value']
        card_tabs=card_tabs.split(',')


    

    sql=f"SELECT * FROM sys_user_table_settings WHERE tableid='{tableid}' AND settingid='scheda_active_tab'"
    query_result=HelpderDB.sql_query_row(sql)

    if not query_result:
        active_tab = ''
    else:
        active_tab=query_result['value']

    if active_tab not in card_tabs:
        active_tab=card_tabs[0]

    response = {
        "cardTabs": card_tabs,
        "activeTab": active_tab
    }
    return JsonResponse(response)


@csrf_exempt
def get_table_active_tab(request):
    data = json.loads(request.body)
    tableid = data.get('tableid')

    sql=f"SELECT * FROM sys_user_table_settings WHERE tableid='{tableid}' AND settingid='table_tabs'"
    query_result=HelpderDB.sql_query_row(sql)
    if not query_result:
        table_tabs = ['Tabella', 'Kanban', 'Pivot', 'Calendario', 'MatrixCalendar' , 'Planner' , 'Gallery']
    else:
        table_tabs=query_result['value']
        table_tabs=table_tabs.split(',')

    sql=f"SELECT * FROM sys_user_table_settings WHERE tableid='{tableid}' AND settingid='table_active_tab'"
    query_result=HelpderDB.sql_query_row(sql)

    if not query_result:
        active_tab = ''
    else:
        active_tab=query_result['value']

    if active_tab not in table_tabs:
        active_tab=table_tabs[0]

    response = {
        "tableTabs": table_tabs,
        "activeTab": active_tab
    }
    return JsonResponse(response)


def get_favorite_tables(request):
    data = json.loads(request.body)
    sys_user_id = Helper.get_userid(request)
    context = dict()
    
    query = "SELECT tableid FROM sys_user_table_order WHERE userid = '{}'".format(sys_user_id)
    with connection.cursor() as cursor: 
        cursor.execute(
            query
        )
        user_tables = HelpderDB.dictfetchall(cursor)

    if not user_tables:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT tableid FROM sys_user_table_order WHERE userid = 1"
            )
            user_tables = HelpderDB.dictfetchall(cursor)

    query = f"SELECT tableid FROM sys_user_favorite_tables WHERE sys_user_id = {sys_user_id}"
    with connection.cursor() as cursor:
        cursor.execute(
            query
        )
        favorite_tables = HelpderDB.dictfetchall(cursor)

    # Ottieni tutte le tabelle disponibili
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM sys_table")
        all_tables = HelpderDB.dictfetchall(cursor)

    # Crea un set degli ID delle tabelle favorite per un controllo più efficiente
    favorite_table_ids = {fav['tableid'] for fav in favorite_tables}

    # Usa tutte le tabelle invece di solo quelle in user_table_order
    tables = []
    for table in all_tables:
        table_entry = {
            'tableid': table['id'],
            'description': table['description'],
            'favorite': table['id'] in favorite_table_ids
        }
        tables.append(table_entry)

    context['tables'] = [
        {
            "itemcode": str(table["tableid"]),
            "itemdesc": table.get("description", ""),
            "favorite": table.get("favorite", False)
        }
        for table in tables
    ]

    return JsonResponse({"tables": context['tables']})

def save_favorite_tables(request):
    body = json.loads(request.body)
    fav_tables = body.get('tables', [])
    sys_user_id = Helper.get_userid(request)


    with connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM sys_user_favorite_tables where sys_user_id = %s",
            [sys_user_id]
        )

    with connection.cursor() as cursor:
        for table in fav_tables:
            cursor.execute(
                "INSERT INTO sys_user_favorite_tables(sys_user_id, tableid) VALUES (%s, %s)",
                [sys_user_id, table]
            )

    return JsonResponse({'success': True})


def script_test(request):
    domain = "off-horizon.ch"
    domain_info=get_domain_info(domain)

    return JsonResponse({'response': domain_info})

#TODO
#CUSTOM WINTELER
#TEMP
def script_winteler_load_t_wip(request):
    records= HelpderDB.sql_query("SELECT * FROM t_wipbarcode WHERE dataautomatica IS NULL LIMIT 500")
    for record in records:
        record_bixdata= UserRecord('wipbarcode')
        record_bixdata.values['wipbarcode'] = record['wipbarcode']
        record_bixdata.values['lottobarcode'] = record['lottobarcode']
        record_bixdata.values['datascansione'] = record['datascansione']
        record_bixdata.values['statowip']='Caricato'
        print('save:')
        print( record_bixdata.values['wipbarcode'])
        record_bixdata.save()
        sql="UPDATE t_wipbarcode SET dataautomatica='2025-07-03 00:00:00' WHERE wipbarcode='"+record['wipbarcode']+"'"
        HelpderDB.sql_execute(sql)

    return JsonResponse({'response': 'ok'})

def get_domain_info(domain):
    allowed_tlds = (".com", ".it", ".net", ".ch")

    result = {
        "domain": domain,
        "registrar": None,
        "nameservers": [],
        "a_records": []
    }

    if not domain.endswith(allowed_tlds):
        return {
            "registrar": "TLD non supportato",
            "nameservers": [],
            "a_records": []
        }

    # 1. DNS Lookup - A Record
    try:
        answers = dns.resolver.resolve(domain, 'A', lifetime=5)
        result["a_records"] = [rdata.address for rdata in answers]
    except Exception as e:
        result["a_records"] = []

    # 2. DNS Lookup - NS
    try:
        ns_answers = dns.resolver.resolve(domain, 'NS', lifetime=5)
        result["nameservers"] = [ns.to_text().strip().lower() for ns in ns_answers]
    except Exception as e:
        result["nameservers"] = []

    # 3. RDAP Lookup (registrar)
    try:
        rdap_url = f"https://rdap.org/domain/{domain}"
        rdap_resp = requests.get(rdap_url, timeout=5)
        if rdap_resp.status_code == 200:
            rdap_data = rdap_resp.json()
            registrar = rdap_data.get('registrar', {}).get('name')
            if registrar:
                result["registrar"] = registrar
    except Exception as e:
        result["registrar"] = None

    # 4. WHOIS fallback se mancano info
    if not result["registrar"] or not result["nameservers"]:
        try:
            time.sleep(1.2)  # throttle manuale
            info = whois.whois(domain)

            # Registrar
            registrar = info.registrar
            if isinstance(registrar, list):
                result["registrar"] = registrar[0]
            elif registrar:
                result["registrar"] = str(registrar)

            # Nameservers
            nameservers = info.name_servers
            if isinstance(nameservers, (list, set)):
                result["nameservers"] = sorted([ns.strip().lower() for ns in nameservers])
            elif isinstance(nameservers, str):
                result["nameservers"] = [nameservers.strip().lower()]
        except Exception as e:
            if not result["registrar"]:
                result["registrar"] = f"WHOIS Error: {str(e)}"
            if not result["nameservers"]:
                result["nameservers"] = [f"WHOIS Error: {str(e)}"]

    return result


def script_update_serviceandasset_domains_info(request, dominio=None):
    counter=0
    try:
        query = """
            SELECT * FROM user_serviceandasset 
            WHERE (type='Hosting' OR type='Hosting - Alias' OR type='Hosting - Forward')  AND deleted_='N' 
            AND description IS NOT NULL AND description != ''
        """

        # Se viene passato un dominio, aggiungilo come filtro
        if dominio:
            query += f" AND description = '{dominio}'"

        records = HelpderDB.sql_query(query)

        report_lines = []

        for record in records:
            counter=counter+1
            recordid=record['recordid_']
            domain = record['description'].strip()
            print(f"{counter} - {domain}")
            if not domain:
                continue

            domain_info = get_domain_info(domain)

            registrar = domain_info.get('registrar', 'N/A')
            nameservers = domain_info.get('nameservers', [])
            a_records = domain_info.get('a_records', [])

            record_update = UserRecord('serviceandasset', recordid)
            record_update.values['sector'] = 'Hosting'
            record_update.values['quantity'] = '1'

            # Inizializza status e provider
            status = ''
            provider = ''

            #TODO
            

            # Controlla quale IP è presente e assegna il provider corrispondente
            if '212.237.209.213' in a_records:
                record_update.values['provider'] = 'Pleskn01'
            elif '194.56.189.185' in a_records:
                record_update.values['provider'] = 'Plesk03'
            elif '82.220.34.22' in a_records:
                record_update.values['provider'] = 'Plesk 330'


            # IP da controllare
            known_ips = ['212.237.209.213', '194.56.189.185', '82.220.34.22']

            # Verifica se nessun nameserver contiene 'swissbix.com'
            ns_ok = any('swissbix.com' in ns for ns in nameservers)

            # Verifica se almeno uno degli IP è presente negli A record
            ip_found = any(ip in a_records for ip in known_ips)

            record_update.values['status'] = 'Active'
            # Imposta lo status se i nameserver non sono swissbix ma l'IP è uno dei noti
            if not ns_ok and ip_found:
                record_update.values['status'] = 'CHECK - DNS'

            # Controlla se nessuno dei tre IP è presente
            if not any(ip in a_records for ip in ['212.237.209.213', '194.56.189.185', '82.220.34.22']):
                record_update.values['status'] = 'CHECK'

            autonote = f"""
                <b>Registrar:</b> {registrar}<br>
                <b>DNS Nameserver:</b> {', '.join(nameservers) if nameservers else 'N/A'}<br>
                <b>Hosting (A Record):</b> {', '.join(a_records) if a_records else 'N/A'}<br>
            """

            
            # Pulizia
            autonote = autonote.replace("\n", "").replace("\t", "").strip()
            record_update.values['autonote'] = autonote
            record_update.values['note'] = 'updated'
            print(f"{counter} Save: {domain}")
            record_update.save()

            report_lines.append(f"<b>Dominio:</b> {domain}<br>"+autonote+" <br/><br/>")

        final_report = "<html><body><h2>Report domini</h2>" + "\n".join(report_lines) + "</body></html>"
        return HttpResponse(final_report)

    except Exception as e:
        return HttpResponse(f"Errore invio: {str(e)}")



def replace_text_in_paragraph(paragraph, key, value):
    """Sostituisce il testo mantenendo lo stile originale"""
    if key in paragraph.text:
        inline = paragraph.runs
        for item in inline:
            if key in item.text:
                item.text = item.text.replace(key, value)

def download_offerta(request):
    print('download_offerta')
    data = json.loads(request.body)
    recordid = data.get('recordid')

    record = UserRecord('offerta', recordid)
    templateofferta = record.values.get('tipoofferta', '')

    filename = f"Offerta_{record.values.get('id', '')}.docx"

    if templateofferta == 'Custodia':
        script_dir = os.path.dirname(os.path.abspath(__file__))
        print(script_dir)
        file_path = os.path.join(script_dir, 'static', 'template_offerte', 'servizio_custodia.docx')
        doc = Document(file_path)

        id_offerta = record.values.get('id', '')

        recordid_cliente = record.values.get('recordidcliente_', '')
        record_cliente = UserRecord('cliente', recordid_cliente)
        nome_cliente = record_cliente.values.get('nome_cliente', '')
        indirizzo_cliente = record_cliente.values.get('indirizzo', '')
        cap_cliente = record_cliente.values.get('cap', '')
        citta_cliente = record_cliente.values.get('citta', '')

        recordid_stabile = record.values.get('recordidstabile_', '')
        record_stabile = UserRecord('stabile', recordid_stabile)
        nome_stabile = record_stabile.values.get('titolo_stabile', '')
        indirizzo_stabile = record_stabile.values.get('indirizzo', '')
        citta_stabile = record_stabile.values.get('citta', '')

        data = datetime.datetime.now().strftime("%d.%m.%Y")

        replacements = {
            '{{nome_cliente}}': nome_cliente,
            '{{indirizzo_cliente}}': indirizzo_cliente,
            '{{cap_cliente}}': cap_cliente,
            '{{citta_cliente}}': citta_cliente,
            '{{data}}': data,
            '{{id_offerta}}': str(id_offerta),
            '{{nome_stabile}}': nome_stabile,
            '{{indirizzo_stabile}}': indirizzo_stabile,
            '{{citta_stabile}}': citta_stabile
        }

        for p in doc.paragraphs:
            for key, value in replacements.items():
                replace_text_in_paragraph(p, key, value)

    modified_file_path = os.path.join(script_dir, 'static', 'modified_template.docx')
    doc.save(modified_file_path)


    if os.path.exists(modified_file_path):
        with open(modified_file_path, 'rb') as fh:
            response = HttpResponse(fh.read(), content_type="application/pdf")
            response['Content-Disposition'] = f'inline; filename={filename}'
            #os.remove(modified_file_path)
            return response
    else:
        return JsonResponse({'error': 'File not found'}, status=404)



def get_dashboard_data(request):
    userid = Helper.get_userid(request)
    data = json.loads(request.body)
    dashboardCategory = data.get('dashboardCategory', '')   

    if dashboardCategory!='':
        dashboards = HelpderDB.sql_query(f"SELECT  id, name from sys_dashboard WHERE category='{dashboardCategory}'")
    else:
        dashboards_user = SysUserDashboard.objects.filter(userid=userid).values("dashboardid")
        dashboards_qs = SysDashboard.objects.filter(
            id__in=[d["dashboardid"] for d in dashboards_user]
        ).values("id", "name").order_by("order_dashboard")

        dashboards = [
            {"id": str(d["id"]), "name": d["name"]}
            for d in dashboards_qs
        ]

    return JsonResponse({
        'dashboards': dashboards
    })




def script_add_golfclub(request):
    """
    Genera dati casuali per 5 golf club e, per ognuno, le relative metriche 
    annuali per gli anni 2025, 2024, 2023 e 2022.
    """
    
    # Inizializza Faker per generare dati italiani
    fake = Faker('it_IT')
    
    # Lista degli anni per cui generare le metriche
    anni_da_generare = [2025, 2024, 2023, 2022]
    
    generated_data = []

    # Ciclo principale per creare 5 golf club
    for i in range(5):
        # --- 1. Creazione del Golf Club ---
        golfclub_record = UserRecord('golfclub')
        
        # Genera un nome di fantasia per il club
        nome_club = f"Golf Club {fake.last_name()} {random.choice(['Hills', 'Valley', 'Lake', 'Meadows'])}"
        
        golfclub_record.values['nome_club'] = nome_club
        golfclub_record.values['paese'] = fake.country()
        golfclub_record.values['indirizzo'] = fake.street_address()
        golfclub_record.values['email'] = f"info@{nome_club.lower().replace(' ', '').replace('-', '')}.com"
        
        golfclub_record.save()
        golfclub_recordid = golfclub_record.recordid

        club_info = {
            'golf_club': golfclub_record.values,
            'metriche_annuali': []
        }

        # Valori base per il primo anno (2022) che verranno poi variati
        nr_soci_base = random.randint(150, 700)
        cifra_affari_base = random.randint(400000, 2500000)

        # --- 2. Creazione delle Metriche per ogni Anno ---
        # Ciclo annidato per gli anni
        for anno in sorted(anni_da_generare): # Ordino per simulare una progressione
            metrica_annuale_record = UserRecord('metrica_annuale')
            
            # Applica una piccola variazione casuale rispetto ai valori base
            # per simulare la crescita/decrescita nel tempo
            variazione_soci = 1 + (anno - 2022) * random.uniform(-0.02, 0.05)
            variazione_cifra_affari = 1 + (anno - 2022) * random.uniform(-0.03, 0.08)

            nr_soci_attuali = int(nr_soci_base * variazione_soci)
            uomini = int(nr_soci_attuali * random.uniform(0.55, 0.75))
            donne = nr_soci_attuali - uomini
            
            metrica_annuale_record.values['recordidgolfclub_'] = golfclub_recordid
            metrica_annuale_record.values['anno'] = anno
            metrica_annuale_record.values['cifra_affari'] = int(cifra_affari_base * variazione_cifra_affari)
            metrica_annuale_record.values['nr_soci'] = nr_soci_attuali
            metrica_annuale_record.values['tassa_ammissione'] = random.randint(500, 2000)
            metrica_annuale_record.values['tassa_annua'] = random.randint(1500, 5000)
            metrica_annuale_record.values['uomini'] = uomini
            metrica_annuale_record.values['donne'] = donne
            metrica_annuale_record.values['prezzo_cart'] = random.randint(25, 60)
            metrica_annuale_record.values['nr_tornei_club'] = random.randint(10, 40)
            metrica_annuale_record.values['prezzo_ingresso_adulto'] = random.randint(50, 150)
            metrica_annuale_record.values['prezzo_ingresso_junior'] = random.randint(25, 75)
            metrica_annuale_record.values['prezzo_ingresso_lezione'] = random.randint(30, 80)
            
            metrica_annuale_record.save()
            
            club_info['metriche_annuali'].append(metrica_annuale_record.values)

        generated_data.append(club_info)

    return JsonResponse({
        'response': 'Generati 5 golf club, ciascuno con metriche per 4 anni (2022-2025).',
        'data': generated_data
    })






def script_test(request):
    companies = HelpderDB.sql_query("SELECT * FROM user_company")

    # Eventuale controllo per assenza di dati
    if not companies:
        return JsonResponse({'error': 'Nessun dato trovato'})
    
    df = pd.DataFrame(companies)

    # Nome e path del file
    file_name = 'Aziende.xlsx'
    static_dir = 'C:\\Users\\stagista\\Documents'
    file_path = os.path.join(static_dir, file_name)

    df_clean = df.replace([np.nan, np.inf, -np.inf], '', regex=True)

    # Salvataggio con formattazione
    with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Aziende')
        
        workbook = writer.book
        worksheet = writer.sheets['Aziende']
        
        # Formattazione intestazioni
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'align': 'center',
            'valign': 'vcenter',
            'fg_color': '#DCE6F1',
            'border': 1
        })

        # Formattazione celle centrato
        center_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter'
        })

        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)

        for row in range(1, len(df_clean) + 1):
            worksheet.set_row(row, None, center_format)

        # Larghezza colonne
        worksheet.set_column(0, 0, 35)  
        worksheet.set_column(1, 1, 15)  
        worksheet.set_column(2, 2, 18)  
        worksheet.set_column(3, 3, 15)  
        worksheet.set_column(4, 4, 18)  
        worksheet.set_column(5, 5, 15)  
        worksheet.set_column(6, 6, 20)  
        worksheet.set_column(7, 7, 15)  
        worksheet.set_column(8, 8, 10)  
        worksheet.set_column(9, 9, 10)  
        worksheet.set_column(10, 10, 85)  
        worksheet.set_column(11, 11, 10)  
        worksheet.set_column(12, 12, 25)  
        worksheet.set_column(13, 13, 50)  
        worksheet.set_column(14, 14, 20)  
        worksheet.set_column(15, 15, 40)  

    return JsonResponse({'success': True, 'path documento': file_path})


def generate_timesheet_pdf(recordid, signature_path):
    """
    Genera il PDF del timesheet con la firma e restituisce il percorso del file PDF.
    """
    try:
        base_path = os.path.join(settings.STATIC_ROOT, 'pdf')
        os.makedirs(base_path, exist_ok=True)

        uid = uuid.uuid4().hex
        qr_name = f'qrcode_{uid}.png'
        qr_path = os.path.join(base_path, qr_name)

        # Genera QR
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=0,
        )
        qrcontent = f'timesheet_{recordid}'
        qr.add_data(qrcontent)
        qr.make(fit=True)
        img_qr = qr.make_image(fill_color="black", back_color="white")
        img_qr.save(qr_path)

        # Recupera dati dal DB
        rows = HelpderDB.sql_query(f"""
            SELECT t.*, c.companyname, c.address, c.city, c.email, c.phonenumber, 
                   u.firstname, u.lastname 
            FROM user_timesheet AS t 
            JOIN user_company AS c ON t.recordidcompany_=c.recordid_ 
            JOIN sys_user AS u ON t.user = u.id 
            WHERE t.recordid_='{recordid}'
        """)

        if not rows:
            raise Exception(f"Nessun timesheet trovato per recordid {recordid}")

        row = rows[0]
        for k in row:
            row[k] = row[k] or ''

        server = os.environ.get('BIXENGINE_SERVER')
        qr_url = f"{server}/static/pdf/{qr_name}"
        firma_url = f"{server}/{signature_path.replace(settings.STATIC_ROOT + '/', '')}"

        row['recordid'] = recordid
        row['qrUrl'] = qr_url
        row['signatureUrl'] = firma_url

        timesheetlines = HelpderDB.sql_query(
            f"SELECT * FROM user_timesheetline WHERE recordidtimesheet_='{recordid}'"
        )
        for line in timesheetlines:
            line['note'] = line.get('note') or ''
            line['expectedquantity'] = line.get('expectedquantity') or ''
            line['actualquantity'] = line.get('actualquantity') or ''
        row['timesheetlines'] = timesheetlines

        # Percorso PDF finale
        pdf_filename = f'timesheet_signature_{recordid}_{uuid.uuid4().hex}.pdf'
        pdf_path = os.path.join(base_path, pdf_filename)

        # Genera PDF
        script_dir = os.path.dirname(os.path.abspath(__file__))
        wkhtmltopdf_path = os.path.join(script_dir, 'wkhtmltopdf.exe')
        config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
        html_content = render_to_string('pdf/timesheet_signature.html', row)

        pdfkit.from_string(html_content, pdf_path, configuration=config)

        # Rimuove QR temporaneo
        if os.path.exists(signature_path):
            os.remove(signature_path)
        if os.path.exists(qr_path):
            os.remove(qr_path)

        return pdf_path, pdf_filename

    except Exception as e:
        print(f"Errore in generate_timesheet_pdf: {e}")
        raise

def print_timesheet(request):
    """
    Restituisce un PDF già generato, passato come file_path nel body.
    Serve per scaricare il PDF firmato precedentemente salvato.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)

    try:
        data = json.loads(request.body)
        recordid = data.get('recordid')

        if not recordid:
            return JsonResponse({'error': 'Missing recordid'}, status=400)


        record_timesheet = UserRecord('attachment', recordid)
        file_path = record_timesheet.values['file']

        # Percorso assoluto
        abs_path = os.path.join(settings.UPLOADS_ROOT, file_path)

        if not os.path.exists(abs_path):
            return JsonResponse({'error': f'File not found: {file_path}'}, status=404)

        # Legge il PDF e lo restituisce
        with open(abs_path, 'rb') as f:
            pdf_data = f.read()

        response = HttpResponse(pdf_data, content_type='application/pdf')
        filename = os.path.basename(file_path)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        print(f"Error in sign_timesheet (download): {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_exempt
def save_signature(request):
    """
    Riceve una firma in base64, genera il PDF del timesheet con la firma
    e salva il file come allegato nel DB (tabella attachment).
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)

    try:
        data = json.loads(request.body)
        recordid = data.get('recordid')
        img_base64 = data.get('image')

        if not recordid:
            return JsonResponse({'error': 'Missing recordid'}, status=400)
        if not img_base64:
            return JsonResponse({'error': 'No image data'}, status=400)

        # -------------------------
        # 1️⃣ Salva la firma come immagine PNG
        # -------------------------
        if ',' in img_base64:
            _, img_base64 = img_base64.split(',', 1)
        img_data = base64.b64decode(img_base64)

        base_path = os.path.join(settings.STATIC_ROOT, 'pdf')
        os.makedirs(base_path, exist_ok=True)

        filename_firma = f"firma_{recordid}_{uuid.uuid4().hex}.png"
        firma_path = os.path.join(base_path, filename_firma)

        img_pil = Image.open(BytesIO(img_data))
        if img_pil.mode in ('RGBA', 'LA') or (img_pil.mode == 'P' and 'transparency' in img_pil.info):
            background = Image.new('RGB', img_pil.size, (255, 255, 255))
            background.paste(img_pil, mask=img_pil.split()[-1])
            img_pil = background
        else:
            img_pil = img_pil.convert('RGB')
        img_pil.save(firma_path, format='PNG')

        # -------------------------
        # 2️⃣ Genera QR Code
        # -------------------------
        uid = uuid.uuid4().hex
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=0,
        )
        qrcontent = f"timesheet_{recordid}"
        qr.add_data(qrcontent)
        qr.make(fit=True)

        img_qr = qr.make_image(fill_color="black", back_color="white")
        qr_name = f"qrcode_{uid}.png"
        qr_path = os.path.join(base_path, qr_name)
        img_qr.save(qr_path)

        # -------------------------
        # 3️⃣ Recupera i dati del timesheet
        # -------------------------
        rows = HelpderDB.sql_query(f"""
            SELECT t.*, c.companyname, c.address, c.city, c.email, c.phonenumber, 
                   u.firstname, u.lastname 
            FROM user_timesheet AS t 
            JOIN user_company AS c ON t.recordidcompany_=c.recordid_ 
            JOIN sys_user AS u ON t.user = u.id 
            WHERE t.recordid_='{recordid}'
        """)

        if not rows:
            return JsonResponse({'error': f'Timesheet {recordid} non trovato'}, status=404)

        row = rows[0]
        for value in row:
            row[value] = row[value] or ''

        server = os.environ.get('BIXENGINE_SERVER')
        firma_url = f"{server}/static/pdf/{filename_firma}"
        qr_url = f"{server}/static/pdf/{qr_name}"

        # -------------------------
        # 4️⃣ Prepara i dati per il template
        # -------------------------
        row['recordid'] = recordid
        row['qrUrl'] = qr_url
        row['signatureUrl'] = firma_url

        timesheetlines = HelpderDB.sql_query(
            f"SELECT * FROM user_timesheetline WHERE recordidtimesheet_='{recordid}'"
        )
        for line in timesheetlines:
            line['note'] = line.get('note') or ''
            line['expectedquantity'] = line.get('expectedquantity') or ''
            line['actualquantity'] = line.get('actualquantity') or ''
        row['timesheetlines'] = timesheetlines

        # -------------------------
        # 5️⃣ Genera il PDF
        # -------------------------
        script_dir = os.path.dirname(os.path.abspath(__file__))
        wkhtmltopdf_path = os.path.join(script_dir, 'wkhtmltopdf.exe')
        config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
        content = render_to_string('pdf/timesheet_signature.html', row)

        pdf_filename = f"timesheet_signature_{recordid}_{uuid.uuid4().hex}.pdf"
        pdf_path = os.path.join(base_path, pdf_filename)
        pdfkit.from_string(content, pdf_path, configuration=config)

        # -------------------------
        # 6️⃣ Crea il record allegato
        # -------------------------
        attachment_record = UserRecord('attachment')
        attachment_record.values['type'] = "Signature"
        attachment_record.values['recordidtimesheet_'] = recordid
        attachment_record.save()

        uploads_dir = os.path.join(settings.UPLOADS_ROOT, f'attachments/{attachment_record.recordid}')
        os.makedirs(uploads_dir, exist_ok=True)

        final_pdf_path = os.path.join(uploads_dir, pdf_filename)
        shutil.copy(pdf_path, final_pdf_path)

        relative_path = f'attachments/{attachment_record.recordid}/{pdf_filename}'
        attachment_record.values['file'] = relative_path
        attachment_record.values['filename'] = pdf_filename
        attachment_record.save()

        # -------------------------
        # 7️⃣ Risposta finale
        # -------------------------
        return JsonResponse({
            'success': True,
            'message': 'PDF con firma salvato con successo',
            'recordid': recordid,
            'attachment_recordid': attachment_record.recordid,
            'pdf_filename': pdf_filename,
            'pdf_path': relative_path
        })

    except Exception as e:
        print(f"Error in save_signature: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
     
@csrf_exempt
def update_user_profile_pic(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)
            
    
    image_file = request.FILES.get('image')

    query = HelpderDB.sql_query_row(f"SELECT sys_user_id FROM v_users WHERE id = {request.user.id}")
    userid = query['sys_user_id'] 

    # Save the file
    from django.core.files.storage import default_storage
    file_path = f"userProfilePic/{userid}.png"
    #sostituisci l'immagine esistente se c'è
    if default_storage.exists(file_path):
        default_storage.delete(file_path)
    default_storage.save(file_path, image_file)

    return JsonResponse({'success': True})

    
    

@login_required(login_url='/login/')
def get_dashboard_blocks(request):
    userid=Helper.get_userid(request)
    request_data = json.loads(request.body)
    #TODO custom wegolf
    filters=request_data.get('filters', None)
    selected_clubs=None
    selected_years=None
    if filters:
        selected_clubs=filters.get('selectedClubs', [])
        selected_years=filters.get('selectedYears', [])
    cliente_id = Helper.get_cliente_id()
    #dashboard_id = data.get('dashboardid')
    dashboard_id = request_data.get('dashboardid')  # Default to 1 if not provided
    
    user_id = request.user.id


    dbh = HelpderDB()
    context = {}
    context['blocks'] = []  # Initialize the blocks list
    context['block_list'] = []  # Initialize the block_list list

    with connection.cursor() as cursor2:

        cursor2.execute(
            "SELECT sys_user_id FROM v_users WHERE id = %s", [user_id]
        )
        bixid = cursor2.fetchone()[0]
        
        cursor2.execute(
            "SELECT dashboardid FROM sys_user_dashboard WHERE userid = %s", [bixid]
        )

        righe = cursor2.fetchall()
        # dashboard_id = righe[0][0]
        context['dashboardid'] = dashboard_id

    if request.method == 'POST':
        if dashboard_id:
            selected = ''
            with connection.cursor() as cursor:

                context['userid'] = bixid

                size = 'full'
                context['size'] = size

                #datas = SysUserDashboardBlock.objects.filter(userid=bixid, size=size, dashboardid=dashboard_id).values()
                sql = "SELECT * FROM sys_user_dashboard_block WHERE userid = {userid} AND dashboardid = {dashboardid}".format(
                    userid=bixid, dashboardid=dashboard_id
                )
                datas = dbh.sql_query(sql)

                # all_blocks = SysDashboardBlock.objects.all()
                sql = "SELECT * FROM sys_dashboard_block WHERE dashboardid = {dashboard_id} ORDER BY id desc".format(
                    dashboard_id=dashboard_id
                )
                all_blocks = dbh.sql_query(sql)

                for block in all_blocks:
                    chart= HelpderDB.sql_query_row(f"SELECT name FROM sys_chart WHERE id='{block['chartid']}'")
                    block['description'] = chart['name'] if chart else 'N/A'
                    context['block_list'].append(block)

                for data in datas:
                    dashboard_block_id = data['dashboard_block_id']
                    sql = "SELECT * FROM sys_dashboard_block WHERE id = {dashboard_block_id}".format(
                        dashboard_block_id=dashboard_block_id
                    )
                    results = dbh.sql_query(sql)
                    results = results[0]
                    block = dict()
                    block['id'] = data['id']

                    block['gsx'] = data['gsx']
                    block['gsy'] = data['gsy']
                    block['gsw'] = data['gsw']
                    block['gsh'] = data['gsh']
                    block['viewid'] = results['viewid']
                    block['widgetid'] = results['widgetid']
                    # if they are null set default values
                    if block['gsw'] == None or block['gsw'] == '':
                        block['gsw'] = 3
                        block['gsh'] = 4

                    width = results['width']
                    if width == None or width == 0 or width == '':
                        width = 4

                    height = results['height']
                    if height == None or height == 0 or height == '':
                        height= '50%'
                    
                    if results['chartid'] is None or results['chartid'] == 0:

                        if results['widgetid'] is None:
                            if 'tableid' not in results:
                                continue
                            tableid = results['tableid'] if results['tableid'] is not None else ''
                            if tableid == '':
                                continue
                            tableid = 'user_' + tableid
                            block['type'] = 'table'

                            block['html'] = 'table'
                            #block['html'] = get_records_table(request, results['tableid'], None, None, '', results['viewid'], 1, '', '')
                        else:
                            block['html'] = 'test'

                    else:
                        chart_info = build_chart_data(
                            request,
                            results['chartid'],
                            results['viewid'],
                            filters,
                            block_category=results.get('category', '')
                        )
                        block['chart_data'] = chart_info['chart_data']
                        block['name'] = chart_info['name']
                        block['type'] = chart_info['type']

                    block['width'] = width
                    block['height'] = height

                    context['userid'] = bixid
                    context['blocks'].append(block) 

    return JsonResponse(context, safe=False)


@login_required(login_url='/login/')
def get_chart_data(request):
    try:
        request_data = json.loads(request.body)
        chart_id = request_data.get("chart_id")
        viewid = request_data.get("viewid", "")
        filters = request_data.get("filters", None)

        if not chart_id:
            return JsonResponse({"error": "chart_id is required"}, status=400)

        chart_info = build_chart_data(request, chart_id, viewid, filters)
        return JsonResponse(chart_info)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def build_chart_data(request, chart_id, viewid=None, filters=None, block_category=None):
    import re

    userid = Helper.get_userid(request)
    cliente_id = Helper.get_cliente_id()

    # ----------------------------------------------------------
    # 1) Lettura definizione chart
    # ----------------------------------------------------------
    chart = HelpderDB.sql_query_row(f"SELECT * FROM sys_chart WHERE id='{chart_id}'")
    if not chart:
        raise ValueError(f"Chart with id {chart_id} not found")

    chart_name = chart["name"]
    chart_layout = chart["layout"]
    chart_config = chart["config"]
    if isinstance(chart_config, str):
        chart_config = json.loads(chart_config)

    # ----------------------------------------------------------
    # 2) Ricavo categoria del blocco se non fornita
    # ----------------------------------------------------------
    if block_category is None:
        block_category = HelpderDB.sql_query_value(
            f"SELECT category FROM sys_dashboard_block WHERE chartid='{chart_id}' LIMIT 1",
            "category"
        ) or ""

    # ----------------------------------------------------------
    # 3) Query conditions della view
    # ----------------------------------------------------------
    query_conditions = ""
    if viewid:
        view = HelpderDB.sql_query_row(f"SELECT * FROM sys_view WHERE id='{viewid}'")
        if not view:
            raise ValueError(f"View with id {viewid} not found")
        query_conditions = (view.get("query_conditions") or "").replace("$userid$", str(userid))

    # ----------------------------------------------------------
    # 4) Pre-elaborazione filtri comuni (CLUB e ANNI)
    # ----------------------------------------------------------
    selected_years = (filters or {}).get("selectedYears", [])
    selected_clubs = (filters or {}).get("selectedClubs", [])
    dynamic_conditions = []  # <-- condizioni riusabili anche nella query per il placeholder

    # CLUB – logica unica
    user_club = HelpderDB.sql_query_value(
        f"SELECT recordid_ FROM user_golfclub WHERE utente='{userid}'",
        "recordid_"
    )

    if cliente_id == "wegolf":

        if block_category != "benchmark":
            # Non benchmark → club dell’utente
            if user_club:
                dynamic_conditions.append(f"recordidgolfclub_='{user_club}'")

        else:
            # benchmark → usa clubs selezionati
            if selected_clubs:
                club_list = "', '".join(selected_clubs)
                dynamic_conditions.append(f"recordidgolfclub_ IN ('{club_list}')")

        # ANNI
        if selected_years:
            year_list = "', '".join(selected_years)
            dynamic_conditions.append(f"anno IN ('{year_list}')")

    # Applica condizioni a query_conditions
    if dynamic_conditions:
        cond = " AND ".join(dynamic_conditions)
        if query_conditions:
            query_conditions += f" AND {cond}"
        else:
            query_conditions = cond

    # ----------------------------------------------------------
    # 5) Ottenimento dati dinamici del chart
    # ----------------------------------------------------------
    chart_data = get_dynamic_chart_data(request, chart_id, query_conditions or "1=1")
    if "datasets" in chart_data and chart_data["datasets"]:
        chart_data["datasets"][0]["view"] = viewid

    chart_data_json = json.dumps(chart_data, default=json_date_handler)

    # ----------------------------------------------------------
    # 6) Placeholder dinamico <colonna>
    # ----------------------------------------------------------
    placeholders = re.findall(r"<([^>]+)>", chart_name)

    if placeholders:

        # Condizioni già calcolate precedentemente
        where_clause = " AND ".join(dynamic_conditions) if dynamic_conditions else "1=1"

        # Recupero config del chart per sapere da quale tabella pescare
        chart_record = HelpderDB.sql_query_row(f"SELECT * FROM sys_chart WHERE id={chart_id}")
        if not chart_record:
            return {'error': 'Chart not found'}

        config = json.loads(chart_record['config'])
        from_table = config.get("from_table")
        if not from_table:
            return {'error': 'Missing from_table in chart config'}

        # Per ogni placeholder <colonna>
        for col in placeholders:

            dynamic_column = col.strip()

            dynamic_value = HelpderDB.sql_query_value(
                f"""
                    SELECT {dynamic_column}
                    FROM user_{from_table}
                    WHERE {where_clause}
                    ORDER BY anno DESC
                    LIMIT 1
                """,
                dynamic_column
            )

            # Sostituisci SOLO questo placeholder
            if dynamic_value is not None:
                chart_name = chart_name.replace(f"<{col}>", str(dynamic_value))

    # ----------------------------------------------------------
    # 7) Output finale
    # ----------------------------------------------------------
    return {
        "id": chart_id,
        "name": chart_name,
        "type": chart_layout.lower() if chart_layout else "value",
        "chart_data": chart_data_json,
        "config": chart_config,
    }



#TODO spostare in un helper e capire perchè è necessario reimportare qui il datetime o va in errore
def json_date_handler(obj):
    """
    Gestore personalizzato per json.dumps.
    Formatta gli oggetti date e datetime in 'gg.mm.aaaa'.
    """

    from datetime import datetime, date

    if isinstance(obj, (datetime, date)):
        # Formatta la data come 'giorno.mese.anno'
        return obj.strftime('%d.%m.%Y')
    
    # Se non è una data, solleva l'errore standard
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


from django.db import connection
# Assuming HelpderDB is a custom helper you have.
# from . import HelpderDB 

def get_chart(request, sql, id, name, layout, fields):
    """
    Fetches and processes data for a chart using a list of dictionaries.
    """
    # Parameters are assigned to local variables, which is redundant.
    # We can use the function arguments directly.
    query = sql
    fields_chart = fields

    dictrows = HelpderDB.sql_query(query)

    # It's good practice to handle cases with no data to prevent errors.
    if not dictrows:
        context = {
            'value': [],
            'labels': [],
            'id': id,
            'name': name,
            'fields': fields_chart,
        }
        return context

    labels = []
    value = []

    if layout == 'wqfef' :
        # This block was empty in the original code. 
        # You would need to implement the logic for these chart types here.
        # For now, it will return empty data as before.
        value = [0] # Original behavior
        labels = []

    elif layout == 'piechart_inline':
        # For a pie chart, we expect two fields: [value_field, label_field]
        value_key = fields_chart[0]
        label_key = fields_chart[1]
        
        # Extract values and labels using dictionary keys
        pie_values = [row_dict.get(value_key, 0) for row_dict in dictrows]
        labels = [row_dict.get(label_key) for row_dict in dictrows]
        
        # The value for a pie chart is a single list of numbers
        value = [pie_values] # Keep the nested list structure [[]] as per original logic

        # Clean up labels
        labels = ['Non assegnato' if v is None or v == 'None' or v == '' else v for v in labels]

    else: # Default logic for other charts like bar, line, etc.
        # The last key in the dictionary is assumed to be the label.
        # This mirrors the original logic of `row[-1]`.
        label_key = list(dictrows[0].keys())[-1]
        
        # Extract labels from the determined label key
        labels = [row_dict.get(label_key) for row_dict in dictrows]
        labels = ['Non assegnato' if v is None or v == 'None' or v == '' else v for v in labels]
        
        # `fields_chart` contains the keys for the data series
        for field_name in fields_chart:
            series = []
            for row_dict in dictrows:
                # Get value, default to 0 if it's None or the string 'None'
                item = row_dict.get(field_name)
                if item is None or item == 'None':
                    series.append(0)
                else:
                    # Round numeric values, otherwise append as is
                    try:
                        series.append(round(float(item), 2))
                    except (ValueError, TypeError):
                        series.append(item) # Append non-numeric if necessary
            value.append(series)

    # Final context preparation
    # The original code always returned `value[0]`, which is incorrect for multi-series charts.
    # We now return the appropriate structure based on the layout.
    final_value = value[0] if layout == 'piechart_inline' and value else value
    
    context = {
        'value': final_value,
        'labels': labels,
        'id': id,
        'name': name,
        'fields': fields_chart,
    }
    return context






def _format_datasets_from_rows(aliases, labels, dictrows):
    """
    Helper per formattare una lista di dataset a partire dal risultato di una query.
    """
    datasets = []
    for i, alias in enumerate(aliases):
        data = []
        for row in dictrows:
            value = row.get(alias)
            try:
                data.append(round(float(value), 2) if value is not None else 0)
            except (ValueError, TypeError):
                data.append(0)
        datasets.append({'label': labels[i], 'data': data})
    return datasets

def _perform_post_calculation(post_calc_def, all_db_datasets, labels):
    """
    Esegue calcoli post-query, come la media di un altro dataset.
    """
    calc_config = post_calc_def['post_calculation']
    source_alias = calc_config['source_dataset_alias']
    func = calc_config.get('function', 'AVG').upper()

    # Trova i dati del dataset di origine
    source_data = None
    for ds in all_db_datasets:
        if ds.get('original_alias') == source_alias:
            source_data = ds['data']
            break
    
    if source_data is None:
        return None # Dataset di origine non trovato

    # Esegui il calcolo
    result_value = 0
    if func == 'AVG':
        
        # --- INIZIO MODIFICA ---
        
        # 1. Ottieni l'anno corrente come STRINGA (es. "2024")
        current_year_str = str(datetime.date.today().year)
        
        # 2. Filtra i dati: escludi i valori il cui label (stringa) corrisponde all'anno corrente
        # Usiamo zip per accoppiare ogni label (anno come stringa) al suo valore
        filtered_data = [
            value for label_str, value in zip(labels, source_data) 
            if label_str != current_year_str
        ]
        
        # Nota: questo codice ora gestisce correttamente anche labels che 
        # non sono anni (es. "Gennaio"). "Gennaio" è diverso da "2024" (l'anno corrente),
        # quindi i suoi dati verranno correttamente inclusi nella media.
        
        # 3. Calcola la media sui dati filtrati
        if filtered_data:
            result_value = sum(filtered_data) / len(filtered_data)
        else:
            result_value = 0 # Evita divisione per zero (se source_data era vuoto o conteneva solo l'anno corrente)
            
        # --- FINE MODIFICA ---

    # Qui potrebbero essere aggiunte altre funzioni (SUM, etc.)
    
    # Crea il nuovo set di dati (es. una linea orizzontale per la media)
    num_labels = len(labels)
    calculated_data = [round(result_value, 2)] * num_labels
    
    return {'label': post_calc_def['label'], 'data': calculated_data}


# === COMMON HELPERS =========================================================

def _get_chart_colors(chart_record):
    """Ritorna i colori del grafico, default se mancano."""
    colors = chart_record.get('colors')
    if not colors:
        colors = Helper.get_chart_colors()
    return colors.split(',') if isinstance(colors, str) else colors


def _safe_get_value(record, key):
    """Converte in float in modo sicuro, restituendo 0 se fallisce."""
    try:
        return round(float(record.get(key, 0)), 2)
    except (ValueError, TypeError):
        return 0


def _build_chart_context_base(chart_id, chart_record, labels, datasets, datasets2=None):
    """Costruisce il contesto standard per un grafico."""
    context = {
        'id': chart_id,
        'name': chart_record['name'],
        'layout': chart_record['layout'],
        'labels': labels,
        'datasets': datasets
    }
    if datasets2:
        context['datasets2'] = datasets2

    context['colors'] = _get_chart_colors(chart_record)
    return context


# === SPECIFIC IMPLEMENTATIONS ==============================================

def _handle_record_pivot_chart(config, chart_id, chart_record, query_conditions):
    """Gestisce la generazione di dati per grafici 'record_pivot'."""
    pivot_fields_map = {item['alias']: item for item in config['pivot_fields']}
    aliases = list(pivot_fields_map.keys())

    # Costruzione query SELECT dinamica
    select_clauses = []
    agg_function = None
    if 'aggregation' in config:
        agg_function = config['aggregation'].get('function', 'SUM').upper()
        ALLOWED_FUNCTIONS = ['SUM', 'AVG', 'COUNT', 'MAX', 'MIN']
        if agg_function not in ALLOWED_FUNCTIONS:
            raise ValueError(f"Funzione di aggregazione non permessa: {agg_function}")

    for item in config['pivot_fields']:
        expr = item.get('field') or f"({item.get('expression')})"
        if agg_function:
            select_clauses.append(f"{agg_function}({expr}) AS {item['alias']}")
        else:
            select_clauses.append(f"{expr} AS {item['alias']}")

    from_table = f"user_{config['from_table']}"
    query = f"SELECT {', '.join(select_clauses)} FROM {from_table} WHERE {query_conditions} LIMIT 1"
    record_data = HelpderDB.sql_query_row(query)
    dataset_label = config.get('dataset_label', 'Dati')

    if not record_data:
        return {'id': chart_id, 'name': chart_record['name']}

    # --- Costruzione dataset finale ---
    final_labels, final_data = [], []

    # Calcolo breakdown (se presente)
    if 'total_breakdown' in config:
        pc_config = config['total_breakdown']
        total_alias = pc_config['total_field_alias']
        total_value = _safe_get_value(record_data, total_alias)
        if total_value == 0:
            final_labels = [pivot_fields_map[a]['label'] for a in pc_config['part_field_aliases']]
            if pc_config.get('include_remainder'):
                final_labels.append(pc_config['remainder_label'])
            final_data = [0] * len(final_labels)
        else:
            sum_parts = 0
            for alias in pc_config['part_field_aliases']:
                val = _safe_get_value(record_data, alias)
                final_labels.append(pivot_fields_map[alias]['label'])
                final_data.append(val)
                sum_parts += val

            if pc_config.get('include_remainder', False):
                remainder = total_value - sum_parts
                final_labels.append(pc_config['remainder_label'])
                final_data.append(round(remainder, 2))
    else:
        # Caso standard
        final_labels = [item['label'] for item in config['pivot_fields']]
        final_data = [_safe_get_value(record_data, a) for a in aliases]

    datasets = [{'label': dataset_label, 'data': final_data}]
    return _build_chart_context_base(chart_id, chart_record, final_labels, datasets)


def _handle_aggregate_chart(config, chart_id, chart_record, query_conditions):
    all_defs = config.get('datasets', []) + config.get('datasets2', [])
    db_defs = [ds for ds in all_defs if 'expression' in ds]
    post_calc_defs = [ds for ds in all_defs if 'post_calculation' in ds]

    db_aliases = [ds['alias'] for ds in db_defs]
    db_labels = [ds['label'] for ds in db_defs]
    select_clauses = [f"{ds['expression']} AS {ds['alias']}" for ds in db_defs]

    group_by_config = config['group_by_field']
    group_by_alias = group_by_config.get('alias', group_by_config['field'])

    main_table = f"user_{config['from_table']}"
    has_lookup = 'lookup' in group_by_config
    lookup_table = None

    # ---- Branch LOOKUP (ripristinato) ----
    if has_lookup:
        lookup_cfg = group_by_config['lookup']
        lookup_table = f"user_{lookup_cfg['from_table']}"
        main_alias, lookup_alias = 't1', 't2'
        # display_field è il campo "umano" da mostrare come label
        select_group_field = f"{lookup_alias}.{lookup_cfg['display_field']} AS {group_by_alias}"
        from_clause = (
            f"FROM {main_table} AS {main_alias} "
            f"JOIN {lookup_table} AS {lookup_alias} "
            f"ON {main_alias}.{group_by_config['field']} = {lookup_alias}.{lookup_cfg['on_key']}"
        )
        group_by_clause = f"GROUP BY {lookup_alias}.{lookup_cfg['display_field']}"
        # aliasing condizioni -> t1/t2
        qc = _aliasize_conditions(query_conditions, main_table, True, lookup_table)

    # ---- Branch NON-LOOKUP (come in origine, con tipi Data/Datetime ecc.) ---
    else:
        fieldid = group_by_config['field']
        try:
            field_record = SysField.objects.get(tableid=config['from_table'], fieldid=fieldid)
            field_type = field_record.fieldtypewebid
        except SysField.DoesNotExist:
            field_type = None

        select_group_field = f"t1.{fieldid} AS {group_by_alias}"
        from_clause = f"FROM {main_table} AS t1"
        group_by_clause = f"GROUP BY t1.{fieldid}"

        granularity = group_by_config.get('date_granularity')
        if field_type in ('Data', 'Datetime', 'Timestamp') and granularity:
            if granularity == 'day':
                expr = f"DATE(t1.{fieldid})"
            elif granularity == 'month':
                expr = f"DATE_FORMAT(t1.{fieldid}, '%Y-%m')"
            elif granularity == 'year':
                expr = f"YEAR(t1.{fieldid})"
            else:
                expr = f"t1.{fieldid}"
            select_group_field = f"{expr} AS {group_by_alias}"
            group_by_clause = f"GROUP BY {expr}"

        # aliasing condizioni -> t1
        qc = _aliasize_conditions(query_conditions, main_table, False, None)

    # composizione SELECT
    if select_clauses:
        query_select = f"{select_group_field}, {', '.join(select_clauses)}"
    else:
        query_select = select_group_field

    query = (
        f"SELECT {query_select} "
        f"{from_clause} "
        f"WHERE {qc} AND t1.deleted_='N' "
        f"{group_by_clause}"
    )
    if 'order_by' in config:
        query += f" ORDER BY {config['order_by']}"

    dictrows = HelpderDB.sql_query(query)
    if not dictrows:
        return {'id': chart_id, 'name': chart_record['name']}

    labels = [row[group_by_alias] for row in dictrows]
    all_db_datasets = _format_datasets_from_rows(db_aliases, db_labels, dictrows)
    for i, ds in enumerate(all_db_datasets):
        ds['original_alias'] = db_aliases[i]

    all_post_calc_datasets = []
    for pc_def in post_calc_defs:
        r = _perform_post_calculation(pc_def, all_db_datasets, labels)
        if r:
            all_post_calc_datasets.append(r)

    # Attenzione: NON poppare se la stessa alias serve a datasets e datasets2
    db_map = {ds['original_alias']: {k: v for k, v in ds.items() if k != 'original_alias'} for ds in all_db_datasets}
    pc_map = {ds['label']: ds for ds in all_post_calc_datasets}

    def _resolve(defs):
        out = []
        for d in defs or []:
            if 'expression' in d and d['alias'] in db_map:
                out.append(db_map[d['alias']])
            elif 'post_calculation' in d and d['label'] in pc_map:
                out.append(pc_map[d['label']])
        return out

    final_datasets1 = _resolve(config.get('datasets'))
    final_datasets2 = _resolve(config.get('datasets2'))

    # extra metadata invariati
    if chart_record['layout'] == 'value':
        icon = HelpderDB.sql_query_value(f"SELECT icon FROM user_chart WHERE report_id={chart_id} LIMIT 1", "icon")
        if icon and final_datasets1:
            final_datasets1[0]['image'] = icon

    if chart_record['layout'] in ('table', 'button') and final_datasets1:
        final_datasets1[0]['tableid'] = config['from_table']
        if chart_record['layout'] == 'table':
            final_datasets1[0]['view'] = chart_record.get('viewid', '')
        elif chart_record['layout'] == 'button':
            custom_func = SysCustomFunction.objects.filter(
                id=chart_record['function_button']
            ).values('tableid', 'context', 'title', 'function', 'conditions', 'params', 'css').first()
            if custom_func:
                for key in ['conditions', 'params']:
                    if custom_func.get(key):
                        try:
                            custom_func[key] = json.loads(custom_func[key])
                        except Exception:
                            pass
                final_datasets1[0]['fn'] = custom_func

    return _build_chart_context_base(chart_id, chart_record, labels, final_datasets1, final_datasets2 or None)

# --- NEW: aliasing robusto delle condizioni --------------------------------
import re

def _aliasize_conditions(query_conditions, main_table, has_lookup=False, lookup_table=None):
    """
    Rimpiazza i prefissi di tabella nelle condizioni con gli alias t1/t2.
    Gestisce sia `user_table`.`col` che user_table.col che `user_table` senza punti.
    Non tocca i nomi di colonna non qualificati.
    """
    qc = query_conditions or ""

    # pattern per main table
    # cattura: `user_table`.  |  user_table.  |  `user_table`
    patterns_main = [
        rf"`{re.escape(main_table)}`\.",  # `user_orders`.
        rf"\b{re.escape(main_table)}\.",  # user_orders.
        rf"`{re.escape(main_table)}`\b",  # `user_orders`
    ]
    for p in patterns_main:
        qc = re.sub(p, lambda m: "t1." if m.group(0).endswith(".") else "t1", qc)

    if has_lookup and lookup_table:
        patterns_lookup = [
            rf"`{re.escape(lookup_table)}`\.",
            rf"\b{re.escape(lookup_table)}\.",
            rf"`{re.escape(lookup_table)}`\b",
        ]
        for p in patterns_lookup:
            qc = re.sub(p, lambda m: "t2." if m.group(0).endswith(".") else "t2", qc)

    return qc


def get_dynamic_chart_data(request, chart_id, query_conditions='1=1'):
    """Genera dinamicamente i dati per un grafico leggendo la configurazione JSON dal database."""
    chart_record = HelpderDB.sql_query_row(f"SELECT * FROM sys_chart WHERE id={chart_id}")
    if not chart_record:
        return {'error': 'Chart not found'}

    config = json.loads(chart_record['config'])
    chart_type = config.get('chart_type', 'aggregate')

    handlers = {
        'record_pivot': _handle_record_pivot_chart,
        'aggregate': _handle_aggregate_chart,
    }

    handler = handlers.get(chart_type)
    if not handler:
        return {'error': f'Unknown chart type: {chart_type}'}

    return handler(config, chart_id, chart_record, query_conditions)



def save_dashboard_disposition(request):
    values = json.loads(request.body).get('values', [])

    print(values)
    for value in values:
        record_id = value.get('id')
        size = value.get('size')
        gsx = value.get('gsX')
        gsy = value.get('gsY')
        gsw = value.get('gsW')
        gsh = value.get('gsH')

        if record_id is not None:

            sql = f"UPDATE sys_user_dashboard_block SET gsx = {gsx}, gsy = {gsy}, gsw = {gsw}, gsh = {gsh} WHERE id = '{record_id}'"

            HelpderDB.sql_execute(sql)
    # Return a success response
    return JsonResponse({'success': True})


from collections import namedtuple
Block = namedtuple('Block', ['gsx', 'gsy', 'gsw', 'gsh'])

MAX_GRID_WIDTH = 12
NEW_GSW = 4
NEW_GSH = 4

def add_dashboard_block(request):
    json_data = json.loads(request.body)
    blockid = json_data.get('blockid')
    # Il campo 'size' viene comunque passato, ma ignorato per il calcolo gsw/gsh
    # size = json_data.get('size') 
    dashboardid = json_data.get('dashboardid')
    user_id = request.user.id
    
    # Coordinate e dimensioni di default del nuovo blocco
    new_gsx = 0
    new_gsy = 0
    new_gsw = NEW_GSW
    new_gsh = NEW_GSH
    
    # 1. Recupera l'ID utente di sistema
    # ... (Il codice per recuperare bixid rimane invariato)
    dbh = HelpderDB() # Mantenuto se necessario da HelpderDB()
    with connection.cursor() as cursor2:
        cursor2.execute(
            "SELECT sys_user_id FROM v_users WHERE id = %s", [user_id]
        )
        bixid = cursor2.fetchone()[0]

    # 2. Recupera i blocchi esistenti per questa dashboard
    existing_blocks = []
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT gsx, gsy, gsw, gsh FROM sys_user_dashboard_block WHERE userid = %s AND dashboardid = %s",
            [bixid, dashboardid]
        )
        # Converti i risultati in oggetti Block per un accesso pulito e gestione di NULL
        for row in cursor.fetchall():
            # Assicurati che tutti i valori siano interi (gestendo eventuali NULL come 0)
            gsx, gsy, gsw, gsh = (int(i) if i is not None else 0 for i in row)
            existing_blocks.append(Block(gsx, gsy, gsw, gsh))

    # 3. Calcola le coordinate (gsx, gsy)
    new_gsx, new_gsy = get_empty_position(existing_blocks, new_gsw, new_gsh, MAX_GRID_WIDTH)

    # 4. Inserisce il nuovo blocco con le coordinate calcolate (gsx, gsy) e le dimensioni (gsw, gsh)
    # NOTA: Ho modificato la query INSERT per includere i campi gsx, gsy, gsw, gsh.
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO sys_user_dashboard_block (userid, dashboard_block_id, dashboardid, size, gsx, gsy, gsw, gsh) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            [bixid, blockid, dashboardid, json_data.get('size'), new_gsx, new_gsy, new_gsw, new_gsh]
        )

    # Restituisce le nuove coordinate al frontend per l'aggiornamento immediato
    return JsonResponse({'success': True, 'gsx': new_gsx, 'gsy': new_gsy})

def get_empty_position(existing_blocks, new_gsw, new_gsh, max_width):
    """
    Calcola le coordinate (gsx, gsy) più in alto a sinistra per il nuovo blocco,
    evitando la sovrapposizione con i blocchi esistenti.
    """
    
    # Inizia la ricerca in tutte le righe possibili. L'altezza massima attuale + 10
    # è un limite ragionevole per evitare loop infiniti in una griglia vuota.
    max_y_to_check = 0
    if existing_blocks:
         # Trova l'altezza massima (y + h) per definire l'area di ricerca iniziale
        max_y_to_check = max(b.gsy + b.gsh for b in existing_blocks)

    # Itera riga per riga (y), cercando la posizione a partire dalla riga 0.
    for y in range(max_y_to_check + new_gsh):
        # Itera colonna per colonna (x), assicurandosi di non superare la larghezza massima.
        x = 0
        while x <= max_width - new_gsw:
            
            is_overlap = False
            for block in existing_blocks:
                # Controlla l'intersezione (sovrapposizione) tra il nuovo blocco e un blocco esistente:
                # (A.gsx < B.gsx + B.gsw) AND (A.gsx + A.gsw > B.gsx) AND 
                # (A.gsy < B.gsy + B.gsh) AND (A.gsy + A.gsh > B.gsy)
                
                if (x < block.gsx + block.gsw) and \
                   (x + new_gsw > block.gsx) and \
                   (y < block.gsy + block.gsh) and \
                   (y + new_gsh > block.gsy):
                    
                    is_overlap = True
                    # C'è sovrapposizione. Sposta la ricerca X subito dopo il blocco che ha creato il conflitto.
                    # Questo evita di dover controllare inutilmente le coordinate intermedie.
                    x = block.gsx + block.gsw
                    break # Passa al blocco successivo
            
            if not is_overlap:
                # Trovata la posizione più in alto e più a sinistra che non si sovrappone.
                return x, y
            
            # Se c'è stata sovrapposizione, il ciclo interno ha aggiornato 'x'. 
            # Se non c'è stata, prova la colonna successiva.
            if not is_overlap:
                x += 1
                
    # Fallback, dovrebbe accadere solo se la logica della griglia è satura (improbabile con questo loop).
    return 0, max_y_to_check + new_gsh 


def save_form_data(request):
    """
    Salva o aggiorna dinamicamente i dati di un form per un utente e un anno specifici.
    """
    try:
        # --- 1. Autenticazione e Parsing Input ---
        # Esempio: DEVI implementare l'autenticazione per ottenere l'utente
        # user = get_user_from_request(request)
        # if not user:
        #     return JsonResponse({"error": "Autenticazione fallita"}, status=401)

        request_data = json.loads(request.body)
        year = request_data.get("year")
        payload = request_data.get("payload")
        
        if not year:
            return JsonResponse({"error": "Anno mancante"}, status=400)
        userid=Helper.get_userid(request)
        recordidgolfclub=HelpderDB.sql_query_value(f"SELECT recordid_ FROM user_golfclub WHERE utente={userid}","recordid_")

        # Controlla che i dati necessari siano presenti
        if not year or payload is None:
            return JsonResponse({"error": "Dati mancanti nella richiesta (year o payload)"}, status=400)

        # --- 2. Recupero del Record Esistente ---
        # Dovresti recuperare il record specifico per l'utente e l'anno.
        # Esempio: record, created = UserRecord.objects.get_or_create(user_id=user.id, anno=year)
        
        # Per ora, usiamo il tuo esempio
        #record = UserRecord('metrica_annuale', '00000000000000000000000000000023')

        table=UserTable('metrica_annuale')
        records=table.get_table_records_obj(conditions_list=[f"recordidgolfclub_='{recordidgolfclub}'",f"anno='{str(year)}'"])
        if records:
            record=records[0]
        else:
            record=UserRecord('metrica_annuale')
            record.values['anno']=year
            record.save()

        # --- 3. Aggiornamento Dinamico dei Valori ---
        # Il metodo .update() aggiorna il dizionario 'values' con tutte le coppie chiave-valore
        # presenti nel dizionario 'payload'. Se una chiave esiste già, il suo valore viene sovrascritto.
        # Se non esiste, viene creata.
        if hasattr(record, 'values') and isinstance(record.values, dict):
            record.values.update(payload)
        else:
            # Se 'record.values' non esiste, lo crea e lo popola con il payload.
            record.values = payload

        # --- 4. Salvataggio nel Database ---
        record.save()

        return JsonResponse({"success": True, "message": "Dati salvati con successo."})

    except json.JSONDecodeError:
        return JsonResponse({"error": "Request body non valido"}, status=400)
    except Exception as e:
        # Log dell'errore per il debug
        print(f"Errore in save_form_data: {e}")
        return JsonResponse({"error": "Errore interno del server"}, status=500)




#TODO spostare in customapp_wegolf
def get_form_fields(request):
    try:
        
        request_data = json.loads(request.body)
        userid=Helper.get_userid(request)
        year = request_data.get("year")
        if not year:
            return JsonResponse({"error": "Anno mancante"}, status=400)

        fields = {}
        recordidgolfclub=HelpderDB.sql_query_value(f"SELECT recordid_ FROM user_golfclub WHERE utente={userid}","recordid_")
        table=UserTable('metrica_annuale')
        records=table.get_table_records_obj(conditions_list=[f"recordidgolfclub_='{recordidgolfclub}'",f"anno='{str(year)}'"])
        if records:
            record=records[0]
        else:
            record=UserRecord('metrica_annuale')
            record.values['anno']=year
            record.values['recordidgolfclub_']=recordidgolfclub
            record.save()
        #record=UserRecord('metrica_annuale', '00000000000000000000000000000023')
        values=record.values
        sys_fields= HelpderDB.sql_query(f"SELECT * FROM sys_user_field_order AS fo JOIN sys_field f ON (fo.tableid=f.tableid AND fo.fieldid=f.id) WHERE fo.tableid='metrica_annuale' AND f.explanation is not null AND f.label != 'Dati' ORDER BY fo.fieldorder ASC")
        fields_settings_list = HelpderDB.sql_query(f"SELECT * FROM sys_user_field_settings WHERE tableid='metrica_annuale'")

        # --- Settings Pre-processing (New) ---
        # Create a dictionary for quick lookup: {fieldid: {settingid: value, ...}}
        processed_settings = {}
        for setting in fields_settings_list:
            field_id = setting.get("fieldid")
            setting_id = setting.get("settingid")
            setting_value = setting.get("value") # Assuming the column for the setting value is named 'value'
            
            if field_id and setting_id:
                # Initialize the dictionary for this field if it's the first time we see it
                if field_id not in processed_settings:
                    processed_settings[field_id] = {}
                processed_settings[field_id][setting_id] = setting_value

        # --- Form Building ---
                
        form_config = {}
        # Un set per tenere traccia delle intestazioni (sublabel) già aggiunte
        # per ogni gruppo, per evitare duplicati.
        added_headings = {}

        for field in sys_fields:
            # Estrai le informazioni dal campo corrente
            group_name = field.get("label")
            sub_group_name = field.get("sublabel")
            field_name = field.get("fieldid")
            field_label = field.get("description")
            field_type = field.get("explanation")

            # Se il gruppo principale non esiste in form_config, lo inizializzo
            if group_name not in form_config:
                form_config[group_name] = {
                    "title": group_name,
                    "icon": group_name,  # Icona di default
                    "fields": []
                }
                # Inizializzo anche il set per le intestazioni di questo gruppo
                added_headings[group_name] = set()

            # Se c'è un sottogruppo (sublabel) e non è ancora stato aggiunto come heading,
            # lo creo e lo aggiungo.
            if sub_group_name and sub_group_name not in added_headings[group_name]:
                heading = {
                    "type": "heading",
                    # Creo un nome univoco per l'heading per sicurezza
                    "name": f"heading_{sub_group_name.lower().replace(' ', '_')}",
                    "label": sub_group_name
                }
                form_config[group_name]["fields"].append(heading)
                # Marco questo heading come aggiunto per non ripeterlo
                added_headings[group_name].add(sub_group_name)

            field_specific_settings = processed_settings.get(field_name, {})
            required = False  # Default a True
            span="col-span-1"  # Default a col-span-1
            breakAfter = False  # Default a False
            if field_specific_settings:
                if field_specific_settings.get("obbligatorio") == 'true':
                    required = True
                if field_specific_settings.get("span"):
                    span = field_specific_settings.get("span")
                if field_specific_settings.get("breakAfter") == 'true':
                    breakAfter = True
            # Creo il dizionario del campo effettivo
            options=[]
            # Ipotizziamo che le opzioni siano in una lista di dizionari con chiavi 'value' e 'label'
            # Se la struttura è diversa, adatta questo ciclo di conseguenza
            source_options = [
                {
                    "value": "option1",
                    "label": "Opzione 1"
                },
                {
                    "value": "option2",
                    "label": "Opzione 2"
                }
                              ]

            lookuptableid=field.get("lookuptableid")
            if lookuptableid:
                field_options=HelpderDB.sql_query(f"SELECT * FROM sys_lookup_table_item WHERE lookuptableid='{lookuptableid}' ")
                for field_option in field_options:
                    itemcode=field_option.get("itemcode","")
                    itemdesc=field_option.get("itemdesc","")
                    options.append({"value":itemcode, "label":itemdesc})

            
            
            # Costruisci la lista di opzioni nel formato corretto per il frontend
            #options = [{"value": opt.get("value"), "label": opt.get("label")} for opt in source_options]

            showWhen={}
           
            form_field = {
                "name": field_name,
                "label": field_label,
                "type": field_type,
                "value": "",
                "span": span,
                "breakAfter": breakAfter,
                "required": required,
                "options": options,
                "showWhen": showWhen
            }

            # Aggiungo il campo alla lista dei campi del suo gruppo
            form_config[group_name]["fields"].append(form_field)
            
        saved_values = {}
        saved_values = record.values
        for section in form_config.values():
                    for field in section['fields']:
                        if field.get('name') in saved_values:
                            # Assegna il valore salvato, gestendo il caso di None
                            field['value'] = saved_values[field['name']] or ""
        final_response = {"config": form_config}
        return JsonResponse(final_response)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Request body non valido"}, status=400)
    except Exception as e:
        # Log dell'errore per il debug
        print(f"Errore in get_form_fields: {e}")
        return JsonResponse({"error": "Errore interno del server"}, status=500)


#TODO
#TEMP
#CUSTOM TELEFONO AMICO

def save_user_settings_api(request):
    """
    API per salvare la preferenza del tema di un utente.
    """
    try:
        data = json.loads(request.body)
        userid = data.get('userid')
        theme = data.get('theme')
        if not all([userid, theme]):
            return JsonResponse({"success": False, "error": "UserID o tema mancanti"}, status=400)
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({"success": False, "error": "Dati di richiesta non validi"}, status=400)

    try:
        # Check if the userid exists in sys_user
        if not SysUser.objects.filter(id=userid).exists():
            return JsonResponse({"success": False, "error": "UserID non trovato"}, status=400)
        
        user_instance = SysUser.objects.get(id=userid)

        SysUserSettings.objects.update_or_create(
            userid=user_instance,
            setting='theme',
            defaults={'value': theme}
        )

        return JsonResponse({"success": True, "message": "Tema salvato con successo."})
    except Exception as e:
        print(f"Errore nel salvataggio delle impostazioni utente: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)

def get_user_settings_api(request):
    """
    API per ottenere le impostazioni di un utente specifico.
    """
    try:
        data = json.loads(request.body)
        userid = data.get('userid')
        if not userid:
            return JsonResponse({"success": False, "error": "UserID mancante"}, status=400)
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({"success": False, "error": "Dati di richiesta non validi"}, status=400)

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT userid, value FROM sys_user_settings WHERE userid = %s AND setting = 'theme'",
                [userid]
            )
            user_theme = dictfetchall(cursor)
        
        # Gestisce il caso in cui il tema non esista
        theme_value = user_theme[0]['value'] if user_theme else 'default'
        
        return JsonResponse({
            "success": True,
            "userid": userid,
            "theme": theme_value
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@transaction.atomic
def save_newuser(request):
    """
    Gestisce la creazione di un nuovo utente tramite API JSON.
    """
    if request.method != 'POST':
        return JsonResponse({"success": False, "error": "Metodo non supportato"}, status=405)

    try:
        # 1. Parsing dei dati JSON
        data = json.loads(request.body)
        username = (data.get("username") or "").lower()
        firstname = data.get("firstname")
        password = data.get("password")
        lastname = data.get("lastname", "")
        email = data.get("email", "")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)

    # 2. Validazione Dati
    if not all([username, firstname, password]):
        return JsonResponse(
            {
                "success": False,
                "error": "I campi username, firstname e password sono obbligatori.",
            },
            status=400,
        )

    # 3. Verifica Esistenza Utente
    if User.objects.filter(username=username).exists():
        # L'utente esiste già, non è una creazione. Restituisci un errore.
        return JsonResponse(
            {
                "success": False,
                "error": "Esiste già un utente con questo username.",
            },
            status=409,  # Conflitto
        )

    # 4. Creazione Utente
    try:
        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=firstname,
            last_name=lastname,
            email=email,
        )
        bixid = user.id

        # 5. Esecuzione SQL aggiuntivo (se necessario)
        with connection.cursor() as cur:
            # Calcola l'ID per sys_user (logica da rivedere, ma mantenuta)
            cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM sys_user")
            userid = cur.fetchone()[0]

            # Inserisce in sys_user
            cur.execute(
                """
                INSERT INTO sys_user (id, firstname, lastname, username, disabled, superuser, bixid)
                VALUES (%s, %s, %s, %s, 'N', 'N', %s)
                """,
                [userid, firstname, lastname, username, bixid],
            )

            # Inserisce il profilo commonapp_userprofile con UPSERT
            cur.execute(
                """
                INSERT INTO commonapp_userprofile (user_id, is_2fa_enabled)
                VALUES (%s, 0)
                ON DUPLICATE KEY UPDATE user_id = VALUES(user_id)
                """,
                [bixid],
            )
    except Exception as e:
        # In caso di errore, la transazione viene annullata automaticamente
        # grazie a @transaction.atomic.
        return JsonResponse({"success": False, "error": f"Errore interno del server: {str(e)}"}, status=500)

    return JsonResponse({"success": True, "message": "Utente creato con successo."})


        
#TODO
#TEMP
def dictfetchall(cursor):
    "Return all rows from a cursor as a dict"
    columns = [col[0] for col in cursor.description]
    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]

def download_trattativa(request):
  
    # Percorso al template Word
    base_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(base_dir, 'templates', 'template.docx')

    if not os.path.exists(template_path):
        return HttpResponse("File non trovato", status=404)

    # Dati fissi
    dati_trattativa = {
        "indirizzo": "Via Industria 1A, Taverne",
        "azienda": "OpenAI Italia",
        "titolo": "Implementazione AI",
        "venditore": "Mario Rossi",
        "data_chiusura_vendita": "2025-07-17",
        "data_attuale": datetime.datetime.now().strftime("%d/%m/%Y"),
    }

    # Calcola il prezzo totale per ogni articolo

    # Carica il template e fai il rendering
    doc = DocxTemplate(template_path)
    doc.render(dati_trattativa)

    # Salva il documento in memoria
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )
    response['Content-Disposition'] = 'attachment; filename="documento_trattativa_generato.docx"'
    return response


@csrf_exempt
def trasferta_pdf(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)

            context = {
                "nome": data.get("nome", ""),
                "cognome": data.get("cognome", ""), 
                "reparto": data.get("reparto", ""),
                "data": data.get("data", ""),
                "motivo_trasferta": data.get("motivo", ""),
                "indirizzo_destinazione": data.get("indirizzo", ""),
                "chilometri_totali": 100,
                "altri_costi": data.get("altriCosti", ""),
                "durata": data.get("durata", ""),
            }
 
            base_dir = os.path.dirname(os.path.abspath(__file__))
            template_path = os.path.join(base_dir, 'templates', 'trasferta.docx')
            doc = DocxTemplate(template_path)
            doc.render(context)

            doc_io = BytesIO()
            doc.save(doc_io)
            doc_io.seek(0)

            response = HttpResponse(doc_io.read(), content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            response['Content-Disposition'] = 'attachment; filename="trasferta_generata.docx"'
            return response

        except Exception as e:
            return HttpResponse(f"Errore interno", status=500)

    return HttpResponse("Metodo non consentito", status=405)

def loading(request):

    return render(request, 'loading.html')

def new_dashboard(request):
    data = json.loads(request.body)
    dashboard_name = data.get('dashboard_name')
    category = data.get('category', None)

    user = request.user
    if not user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    # Recupera sys_user_id tramite query parametrizzata
    with connection.cursor() as cursor:
        cursor.execute("SELECT sys_user_id FROM v_users WHERE id = %s", [user.id])
        row = cursor.fetchone()
    if not row:
        return JsonResponse({'error': 'User not found in v_users'}, status=404)

    sys_user_id = row[0]

    # Crea la dashboard con l’ORM
    dashboard = SysDashboard.objects.create(
        userid=sys_user_id,
        name=dashboard_name,
        category=category
    )

    # Associa l’utente alla dashboard (usando l’ORM)
    SysUserDashboard.objects.create(
        userid_id=sys_user_id,
        dashboardid=dashboard
    )

    if category:
        # Recupera i grafici legati alla categoria (dalla tabella non-sys user_chart)
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT recordid_
                FROM user_chart
                WHERE category_dashboard = %s AND deleted_ = 'N'
            """, [category])
            chart_rows = cursor.fetchall()

        for row in chart_rows:
            recordid = row[0]
            chart_record = UserRecord("chart", recordid)
            values = chart_record.values

            # Estraggo i valori da user_chart
            chartid = values.get("report_id")
            title = values.get("title")
            table_name = values.get("table_name")
            grouping = values.get("grouping")
            views_str = values.get("views", None)

            # Se non c'è chartid valido, salta
            if not chartid or chartid == "None":
                continue

            # Recupero SysChart e la view di default
            chart_obj = SysChart.objects.filter(id=chartid).first()
            if not chart_obj:
                continue  # grafico non trovato, passo oltre

            if isinstance(views_str, str):
                view_ids = [v.strip() for v in views_str.split(",") if v.strip()]
            elif isinstance(views_str, list):
                view_ids = [str(v).strip() for v in views_str if str(v).strip()]
            else:
                return JsonResponse({"error": "Views value is missing."}, status=400)

            # View di default se non ne sono state fornite
            default_view = SysView.objects.filter(tableid=table_name, query_conditions="true").first()
            if not view_ids and default_view:
                view_ids = [str(default_view.id)]

            for view_id in view_ids:
                view_obj = SysView.objects.filter(id=view_id).first() if view_id else None

                # Nome del blocco
                final_name = f"{title or chart_obj.name} {(view_obj.name if view_obj else '')} {dashboard.name}".strip()

                # Evita duplicati (stesso chart, view e dashboard)
                exists = SysDashboardBlock.objects.filter(
                    userid=sys_user_id,
                    chartid=chart_obj,
                    dashboardid=dashboard,
                    viewid=view_obj
                ).exists()
                if exists:
                    continue

                # Crea il blocco
                SysDashboardBlock.objects.create(
                    name=final_name,
                    userid=sys_user_id,
                    chartid=chart_obj,
                    dashboardid=dashboard,
                    viewid=view_obj if view_obj else default_view,
                    category="benchmark" if grouping == "recordidgolfclub_" else None,
                )

    return JsonResponse({'success': True, 'message': 'New dashboard created successfully.'})


def delete_dashboard_block(request):
    data = json.loads(request.body)
    blockid = data.get('blockid')
    dashboardid = data.get('dashboardid')
    userid = request.user.id
    userid = HelpderDB.sql_query_row(f"SELECT sys_user_id FROM v_users WHERE id = {userid}")['sys_user_id']
    
    HelpderDB.sql_execute(
        f"DELETE FROM sys_user_dashboard_block WHERE id = '{blockid}' AND userid = '{userid}' AND dashboardid = '{dashboardid}'"
    )

    return JsonResponse({'success': True, 'message': 'Dashboard block deleted successfully.'})

def get_user_theme(request):
    userid = request.user.id
    if userid is None:
        return JsonResponse({'success': False, 'error': 'User not authenticated.'}, status=401)
    userid = HelpderDB.sql_query_row(f"SELECT sys_user_id FROM v_users WHERE id = {userid}")['sys_user_id']

    theme = HelpderDB.sql_query_row(f"SELECT value FROM sys_user_settings WHERE userid = '{userid}' AND setting = 'theme'")
    return JsonResponse({'success': True, 'theme': theme})

def set_user_theme(request):

    data = json.loads(request.body)
    theme = data.get("theme")

    userid = request.user.id

    userid = HelpderDB.sql_query_row(f"SELECT sys_user_id FROM v_users WHERE id = {userid}")['sys_user_id']

    #check if the record at the db exists before
    existing_record = HelpderDB.sql_query_row(f"SELECT * FROM sys_user_settings WHERE userid = '{userid}' AND setting = 'theme'")
    if not existing_record:
        HelpderDB.sql_execute(f"INSERT INTO sys_user_settings (userid, setting, value) VALUES ('{userid}', 'theme', '{theme}')")
    else:
        HelpderDB.sql_execute(f"UPDATE sys_user_settings SET value = '{theme}' WHERE userid = '{userid}' AND setting = 'theme'")

    return JsonResponse({'success': True, 'message': 'User theme updated successfully.'})


@csrf_exempt
def stampa_pdf_test(request):
    data={}
    filename='test.pdf'
    

    content = render_to_string('pdf/pdf_test.html', data)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    wkhtmltopdf_path = script_dir + '\\wkhtmltopdf.exe'
    config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
    filename_with_path = os.path.dirname(os.path.abspath(__file__))
    filename_with_path = filename_with_path.rsplit('views', 1)[0]
    filename_with_path = filename_with_path + '\\static\\pdf\\' + filename
    pdfkit.from_string(
        content,
        filename_with_path,
        configuration=config,
        options={
            "enable-local-file-access": "",
            # "quiet": ""  # <-- rimuovilo!
        }
    )

    try:
        with open(filename_with_path, 'rb') as fh:
            response = HttpResponse(fh.read(), content_type="application/pdf")
            response['Content-Disposition'] = f'inline; filename={filename}'
            return response
        return response

    finally:
        os.remove(filename_with_path)




def get_custom_functions(request):
    data = json.loads(request.body)
    tableid = data.get('tableid')

    customs_fn = SysCustomFunction.objects.filter(tableid=tableid).order_by('order').values()
    return JsonResponse({'fn': list(customs_fn)}, safe=False)


def calculate_dependent_fields(request):
    print("FUN:calculate_dependent_fields")
    idcliente = Helper.get_cliente_id()
    # Nome del modulo dinamico
    module_name = f"customapp_{idcliente}.customfunc"

    try:
        # Import dinamico
        customfunc = importlib.import_module(module_name)

        # Chiama la funzione se esiste
        if hasattr(customfunc, "calculate_dependent_fields"):
            return customfunc.calculate_dependent_fields(request)
        else:
            print(f"Funzione 'calculate_dependent_fields' non trovata in {module_name}")
    except ModuleNotFoundError:
        print(f"Modulo personalizzato {module_name} non trovato")
    except Exception as e:
        print(f"Errore durante l'importazione o l'esecuzione: {e}")




def get_filter_options(request):
    response = {
        'availableYears': ["2023", "2024", "2025"],
        'availableClubs': ["Ascona", "Lugano", "Locarno", "Bellinzona"],
        'filterOptions': [
            { 'field': "members", 'label': "Nr. Socii", 'options': [] },
            { 'field': "employees", 'label': "Nr. Dipendenti", 'options': [] },
        ],
    }

    return JsonResponse(response)


def get_calendar_data(request):
    # TODO: load from db

    responseDataDEV_python = {
        'resources': [
            {
                'recordid': 'antonijevictoplica',
                'name': 'Antonijevic Toplica'
            },
            {
                'recordid': 'BasarabaTomislav',
                'name': 'Basaraba Tomislav'
            },
            {
                'recordid': 'BerishaBekim',
                'name': 'Berisha Bekim'
            },
            {
                'recordid': 'DokovicDorde',
                'name': 'Dokovic Dorde'
            },
            {
                'recordid': 'FazziLuca',
                'name': 'Fazzi Luca'
            },
            {
                'recordid': 'RossiMario',
                'name': 'Rossi Mario'
            },
            {
                'recordid': 'BianchiGiulia',
                'name': 'Bianchi Giulia'
            },
            {
                'recordid': 'VerdiPaolo',
                'name': 'Verdi Paolo'
            },
            {
                'recordid': 'GalliAnna',
                'name': 'Galli Anna'
            },
            {
                'recordid': 'ContiMarco',
                'name': 'Conti Marco'
            }
        ],
        'events': [
            {
                'recordid': '1',
                'title': 'Pulizia completa Condominio Lucino',
                'start': datetime.datetime(2025, 1, 7, 10, 0).isoformat(),
                'end': datetime.datetime(2025, 1, 7, 11, 30),
                'description': 'Pulizia completa Condominio Lucino',
                'color': '#3b82f6',
                'resourceId': 'antonijevictoplica'
            },
            {
                'recordid': '2',
                'title': 'Pulizia entrata Residenza Nettuno',
                'start': datetime.datetime(2025, 1, 8, 14, 0),
                'end': datetime.datetime(2025, 1, 8, 15, 0),
                'description': 'Pulizia entrata Residenza Nettuno',
                'color': '#10b981',
                'resourceId': 'BasarabaTomislav'
            },
            {
                'recordid': '3',
                'title': 'Manutenzione giardino Villa Ada',
                'start': datetime.datetime(2025, 1, 22, 9, 0),
                'end': datetime.datetime(2025, 1, 22, 12, 0),
                'description': 'Taglio erba e siepi',
                'color': '#ef4444',
                'resourceId': 'RossiMario'
            }
        ],
        'unplannedEvents': [
            {
                'recordid': 'u1',
                'title': 'Pulizia finestre Stabile fortuna',
                'description': 'Note aggiuntive',
                'color': '#f97316'
            },
            {
                'recordid': 'u2',
                'title': 'Pulizie finestre Lisano 1 Massagno',
                'description': 'Note aggiuntive',
                'color': '#8b5cf6'
            }
        ]
    }

    return JsonResponse(responseDataDEV_python)

def save_calendar_event(request):
    data = json.loads(request.body)

    event = data.get('eventid')
    start = data.get('startdate')
    end = data.get('enddate')
    resource = data.get('resourceid')

    # TODO save data in db

    return JsonResponse(data)



#TODO spostare sotto customapp_wegolf
def get_benchmark_filters(request):
    golfclub_table=UserTable('golfclub')
    userid = Helper.get_userid(request)
    
    sql = f"""
        SELECT g.nome_club AS title,
               g.recordid_ AS recordid,
               g.Logo AS logo,
               g.paese AS paese
        FROM user_golfclub AS g
        JOIN user_metrica_annuale AS m
           ON g.recordid_ = m.recordidgolfclub_
        GROUP BY title, recordid
        ORDER BY title ASC
    """

    clubs = HelpderDB.sql_query(sql)

    sql_user_club = f"SELECT nome_club as title, recordid_ as recordid, logo, paese FROM user_golfclub WHERE utente = '{userid}'"
    logged_club = HelpderDB.sql_query(sql_user_club)

    if logged_club:
        logged_club = logged_club[0]

    already_present = any(c['recordid'] == logged_club['recordid'] for c in clubs)

    if already_present:
        clubs = [c for c in clubs if c['recordid'] != logged_club['recordid']]
    clubs.insert(0, logged_club)

    fields = SysField.objects.filter(tableid='metrica_annuale', fieldtypewebid='Numero').values('fieldid', 'description').order_by('description')
    
    fieldsClub = SysField.objects.filter(tableid='golfclub', fieldtypewebid='Numero').values('fieldid', 'description').order_by('description')
    response_data = {
            'filterOptionsNumbers': [
                {'field': field['fieldid'], 'label': field['description']}
                for field in fields
            ],
            'filterOptionsDemographic': [
                {'field': field['fieldid'], 'label': field['description']}
                for field in fieldsClub
            ],
            'availableClubs': clubs
        }
        
    # Restituisce il dizionario completo come risposta JSON
    # 'safe=True' (default) è corretto perché stiamo restituendo un dizionario
    return JsonResponse(response_data)

def get_filtered_clubs(request):
    data = json.loads(request.body)
    userid = Helper.get_userid(request)
    filters = data.get('filters', {})

    conditions = " TRUE"
    numeric_filters = filters.get('numericFilters', [])
    demographic_filters = filters.get('demographicFilters', [])

    # --------------------------------------------------------
    # 1. FILTRI NUMERICI → inclusi nella SQL
    # --------------------------------------------------------
    for nf in numeric_filters:
        field = nf.get('field')
        operator = nf.get('operator')
        value = nf.get('value')
        if value is not None:
            conditions += f" AND m.{field} {operator} {value}"

    # --------------------------------------------------------
    # 2. FILTRI DEMOGRAFICI (tranne distance) → inclusi nella SQL
    # --------------------------------------------------------
    # li tengo da parte per il filtro distanza
    distance_filter = None

    for df in demographic_filters:
        field = df.get('field')
        operator = df.get('operator')
        value = df.get('value')

        if field == "distance":
            distance_filter = df  # verrà gestito DOPO la query
            continue

        # campi booleani
        if field in ['colelgamenti_pubblici', 'infrastrutture_turistiche']:
            if isinstance(value, bool):
                value_db = 'Si' if value else 'No'
                conditions += f" AND g.{field} = '{value_db}'"
            continue

        # anno fondazione
        if field == "anno_fondazione":
            if value is not None:
                conditions += f" AND g.{field} {operator} {value}"
            continue

        # altri campi testuali
        if value:
            conditions += f" AND g.{field} = '{value}'"

    # --------------------------------------------------------
    # 3. ESECUZIONE QUERY senza distanza
    # --------------------------------------------------------
    sql = f"""
        SELECT g.nome_club AS title,
               g.recordid_ AS recordid,
               g.Logo AS logo,
               g.paese AS paese
        FROM user_golfclub AS g
        JOIN user_metrica_annuale AS m
           ON g.recordid_ = m.recordidgolfclub_
        WHERE {conditions}
        GROUP BY title, recordid
        ORDER BY title ASC
    """

    clubs = HelpderDB.sql_query(sql)

    sql_user_club = f"SELECT nome_club as title, recordid_ as recordid, logo, paese FROM user_golfclub WHERE utente = '{userid}'"
    logged_club = HelpderDB.sql_query(sql_user_club)

    if logged_club:
        logged_club = logged_club[0]

    # --------------------------------------------------------
    # 4. Filtro distanza applicato DOPO la query
    # --------------------------------------------------------
    if distance_filter:
        field = distance_filter.get('field')
        operator = distance_filter.get('operator')
        value = distance_filter.get('value')

        user_country = logged_club['paese']

        from geopy.distance import geodesic
        latitude, longitude = safe_geocode(user_country)
        user_coords = (latitude, longitude)

        filtered_clubs = []
        for club in clubs:
            country = club.get('paese')
            if not country:
                continue

            lat, lng = safe_geocode(country)
            if lat and lng:
                distance = geodesic(user_coords, (lat, lng)).km

                if operator == "<=" and distance <= value:
                    filtered_clubs.append(club)
                elif operator == ">=" and distance >= value:
                    filtered_clubs.append(club)

        clubs = filtered_clubs

    # --------------------------------------------------------

    already_present = any(c['recordid'] == logged_club['recordid'] for c in clubs)

    if already_present:
        clubs = [c for c in clubs if c['recordid'] != logged_club['recordid']]
    clubs.insert(0, logged_club)

    return JsonResponse({'availableClubs': clubs}, safe=False)

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import time

geolocator = Nominatim(user_agent="golf_app")

def safe_geocode(location_name, retries=2):
    """Tenta di geocodificare un nome paese, con retry e gestione errori."""
    if not location_name or not isinstance(location_name, str):
        return None
    
    for _ in range(retries):
        try:
            loc = geolocator.geocode(location_name, timeout=5)
            return (loc.latitude, loc.longitude) if loc else None
        except (GeocoderTimedOut, GeocoderServiceError):
            time.sleep(1)  # piccolo delay e retry
        except Exception:
            break
    return None

def get_wegolf_welcome_data(request):
    userid = Helper.get_userid(request)
    recordidgolfclub = HelpderDB.sql_query_value(
        f"SELECT recordid_ FROM user_golfclub WHERE utente = {userid}", 
        "recordid_"
    )
    sql = f"SELECT nome_club, logo FROM user_golfclub WHERE recordid_ = '{recordidgolfclub}'"
    golfclub_name = HelpderDB.sql_query_value(sql, "nome_club")
    golfclub_logo = HelpderDB.sql_query_value(sql, "logo")
    response_data = {
        'golfclubName': golfclub_name or '',
        'golfclubLogo': golfclub_logo or '',
        'recordidGolfclub': recordidgolfclub or ''
    }
    return JsonResponse(response_data)


def fieldsupdate(request):
    data = json.loads(request.body)
    params = data.get('params',{})
    tableid= params.get('tableid',None)
    recordid= params.get('recordid',None)
    for param, value in params.items():
        if param in ['tableid','recordid']:
            continue
        value=str(value).replace("'","''")
        HelpderDB.sql_execute(f"UPDATE user_{tableid} SET {param}='{value}' WHERE recordid_='{recordid}' ")
    fields= params
    return JsonResponse({'status': 'ok', 'message': 'Fields updated successfully.'})


def get_settings_data(request):
    try:
        userid = Helper.get_userid(request)

        recordidgolfclub = HelpderDB.sql_query_value(
            f"SELECT recordid_ FROM user_golfclub WHERE utente = {userid}", 
            "recordid_"
        )

        if not recordidgolfclub:
            return JsonResponse({"error": "Nessun golf club associato all'utente"}, status=404)

        club_data = HelpderDB.sql_query_row(
            f"SELECT * FROM user_golfclub WHERE recordid_ = '{recordidgolfclub}'"
        )

        if not club_data:
            return JsonResponse({"error": "Dati del golf club non trovati"}, status=404)

        settings = {
            "id": str(recordidgolfclub),
            "nome": club_data.get("nome_club", ""),
            "paese": club_data.get("paese", ""),
            "indirizzo": club_data.get("indirizzo", ""),
            "email": club_data.get("email", ""),
            "annoFondazione": club_data.get("anno_fondazione", ""),
            "collegamentiPubblici": club_data.get("colelgamenti_pubblici", ""),
            "direttore": club_data.get("direttore", ""),
            "infrastruttureTuristiche": club_data.get("infrastrutture_turistiche", ""),
            "pacchettiGolf": club_data.get("pacchetti_golf", ""),
            "struttureComplementari": club_data.get("strutture_complementari", ""),
            "territorioCircostante": club_data.get("territorio_circostante", ""),
            "tipoGestione": club_data.get("tipo_gestione", ""),
            "note": club_data.get("note", ""),
            "datiAnonimi": str(club_data.get("dati_anonimi")).lower() == 'true',
            "lingua": club_data.get("Lingua", ""),
            "valuta": club_data.get("valuta", ""),
            "formatoNumerico": club_data.get("formato_numerico", ""),
            "formatoData": club_data.get("formato_data", ""),
            "logo": club_data.get("Logo", "")
        }

        languages = []
        available_languages = get_available_languages()

        for lang in available_languages:
            languages.append(
                {
                    "code": lang.get("code"),
                    "value": lang.get("fieldid"),
                    "label": get_translation("translations", lang.get("fieldid"), userid= userid)
                }
            )

        response = {
            "settings": settings,
            "languages": languages
        }

        return JsonResponse(response, safe=False, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

def update_club_settings(request):
    try:
        if request.method != "POST":
            return JsonResponse({"error": "Metodo non consentito"}, status=405)

        # Recupera i dati inviati nel form
        data = request.POST
        logo_file = request.FILES.get("logo")

        userid = Helper.get_userid(request)

        recordidgolfclub = HelpderDB.sql_query_value(
            f"SELECT recordid_ FROM user_golfclub WHERE utente = {userid}", 
            "recordid_"
        )

        if not recordidgolfclub:
            return JsonResponse({"error": "Nessun golf club associato all'utente"}, status=404)

        club = UserRecord('golfclub', recordidgolfclub)

        # Aggiorna i campi testuali
        club.values['nome_club'] = data.get("nome", club.values.get('nome_club'))
        club.values['paese'] = data.get("paese", club.values.get('paese'))
        club.values['indirizzo'] = data.get("indirizzo", club.values.get('indirizzo'))
        club.values['email'] = data.get("email", club.values.get('email'))
        club.values['anno_fondazione'] = data.get("annoFondazione", club.values.get('anno_fondazione'))
        club.values['colelgamenti_pubblici'] = data.get("collegamentiPubblici", club.values.get('collegamenti_pubblici'))
        club.values['direttore'] = data.get("direttore", club.values.get('direttore'))
        club.values['infrastrutture_turistiche'] = data.get("infrastruttureTuristiche", club.values.get('infrastrutture_turistiche'))
        club.values['pacchetti_golf'] = data.get("pacchettiGolf", club.values.get('pacchetti_golf'))
        club.values['strutture_complementari'] = data.get("struttureComplementari", club.values.get('strutture_complementari'))
        club.values['territorio_circostante'] = data.get("territorioCircostante", club.values.get('territorio_circostante'))
        club.values['tipo_gestione'] = data.get("tipoGestione", club.values.get('tipo_gestione'))
        club.values['note'] = data.get("note", club.values.get('note'))
        club.values['dati_anonimi'] = data.get("datiAnonimi", club.values.get('dati_anonimi')) 
        club.values['Lingua'] = data.get("lingua", club.values.get('lingua'))
        club.values['valuta'] = data.get("valuta", club.values.get('valuta'))
        club.values['formato_numerico'] = data.get("formatoNumerico", club.values.get('formato_numerico'))
        club.values['formato_data'] = data.get("formatoData", club.values.get('formato_data'))

        # Elimino il file se in delete o update
        if (data.get("logo", None) == "$remove$" and club.values.get('Logo', None)) or (club.values.get('Logo', None) and logo_file):
            if default_storage.exists(club.values.get('Logo', '')):
                default_storage.delete(club.values['Logo'])
            club.values['Logo'] = None

        # Se è stato caricato un logo, salvalo sul server
        if logo_file:
            # Percorso completo: BACKUP_DIR/golfclub/<recordid>/logo/
            save_dir = os.path.join(settings.UPLOADS_ROOT, "golfclub", str(recordidgolfclub))
            os.makedirs(save_dir, exist_ok=True)

            # name, ext = logo_file

            # Nome del file e percorso finale
            file_path = os.path.join(save_dir, logo_file.name)

            # Salvataggio fisico del file
            with default_storage.open(file_path, "wb+") as destination:
                for chunk in logo_file.chunks():
                    destination.write(chunk)

            # Salva il path relativo nel DB (ad esempio per usarlo nel frontend)
            relative_path = f"golfclub/{recordidgolfclub}/{logo_file.name}"
            club.values['Logo'] = relative_path

        # Salva nel DB
        club.save()

        updated_settings = {
            "id": str(recordidgolfclub),
            "nome": club.values.get("nome_club", ""),
            "paese": club.values.get("paese", ""),
            "indirizzo": club.values.get("indirizzo", ""),
            "email": club.values.get("email", ""),
            "annoFondazione": club.values.get("anno_fondazione", ""),
            "collegamentiPubblici": club.values.get("colelgamenti_pubblici", ""),
            "direttore": club.values.get("direttore", ""),
            "infrastruttureTuristiche": club.values.get("infrastrutture_turistiche", ""),
            "pacchettiGolf": club.values.get("pacchetti_golf", ""),
            "struttureComplementari": club.values.get("strutture_complementari", ""),
            "territorioCircostante": club.values.get("territorio_circostante", ""),
            "tipoGestione": club.values.get("tipo_gestione", ""),
            "note": club.values.get("note", ""),
            "datiAnonimi": str(club.values.get("dati_anonimi")).lower() == 'true',
            "lingua": club.values.get("Lingua", ""),
            "valuta": club.values.get("valuta", ""),
            "formatoNumerico": club.values.get("formato_numerico", ""),
            "formatoData": club.values.get("formato_data", ""),
            "logo": club.values.get("Logo", "")
        }

        languages = []
        available_languages = get_available_languages()

        for lang in available_languages:
            languages.append(
                {
                    "code": lang.get("code"),
                    "value": lang.get("fieldid"),
                    "label": get_translation("translations", lang.get("fieldid"), userid= userid)
                }
            )


        return JsonResponse({
            "success": True,
            "message": "Impostazioni del club aggiornate correttamente.",
            "settings": updated_settings,
            "languages": languages
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

    
def get_documents(request):
    user_id = Helper.get_userid(request)
    documents_table=UserTable('documents', userid=user_id)
    documents=documents_table.get_records(conditions_list=[])

    data = []

    for document in documents:
        categories = []
        categories.append(document.get('categoria', ''))

        file = document.get('file', '')

        file_type = ""
        if file:
            file_type = file.split('.')[-1]

        date = document.get('data')
        if date:
            date = date.date().isoformat()

        data.append({
            'id': document.get('recordid_', ''),
            'title': document.get('titolo', ''),
            'description': document.get('descrizione', ''),
            'fileType': file_type,
            'categories': categories,
            'record_id': file,
            'data': date,
        })

    return JsonResponse({"documents": data}, safe=False)

def get_projects(request):
    userid = Helper.get_userid(request)
    project_table = UserTable('projects', userid)
    projects = project_table.get_records(conditions_list=[])

    data = []

    for project in projects:
        categories = []
        categories.append(project.get('categoria', ''))

        documents = project.get('documents', [])

        formatted_documents = []
        for document in documents:
            document_categories = []
            document_categories.append(document.get('categoria', ''))

            file = document.get('file', '')

            file_type = ""
            if file:
                file_type = file.split('.')[-1]

            document_date = document.get('data')
            if document_date:
                document_date = document_date.date().isoformat()

            formatted_documents.append({
                'id': document.get('recordid_', ''),
                'title': document.get('titolo', ''),
                'description': document.get('descrizione', ''),
                'fileType': file_type,
                'categories': document_categories,
                'record_id': file,
                'data': document_date,
            })

        project_date = project.get('data')
        if project_date:
            project_date = project_date.date().isoformat()

        projectid = project.get('recordid_', '')

        like = HelpderDB.sql_query_row(f"SELECT * FROM user_like WHERE recordidprojects_='{projectid}' AND utente='{userid}'")

        data.append({
            'id':projectid,
            'title': project.get('titolo', ''),
            'description': project.get('descrizione', ''),
            'categories': categories,
            'documents': formatted_documents,
            'data': project_date,
            'like': like is not None
        })
    
    
    return JsonResponse({"projects": data}, safe=False)

def like_project(request):
    try:
        data = json.loads(request.body)
        projectid = data.get("project", "")

        date = datetime.datetime.now().date() 

        userid = Helper.get_userid(request)
        if not userid:
             return JsonResponse({"error": "Autenticazione richiesta"}, status=401)

        project = UserTable('projects', userid=userid).get_records(conditions_list=[
            f"recordid_='{projectid}'"
        ])
        
        if not project:
            return JsonResponse({"error": "Project not found"}, status=404)
        
        like_record = HelpderDB.sql_query_row(f"SELECT * FROM user_like WHERE recordidprojects_='{projectid}' AND utente='{userid}'")

        if not like_record:
            like = UserRecord('like',)
            like.values['recordidprojects_'] = projectid
            like.values['utente'] = userid
            like.values['data'] = date
            like.save()
            return JsonResponse({"message": "Project liked successfully"}, status=200)
        else:
            return JsonResponse({"error": "Project already liked"}, status=400)
            
    except Exception as e:
        print(f"Error while liking project: {e}")
        return JsonResponse({"error": "Error while liking project", "detail": str(e)}, status=500)

def unlike_project(request):
    try:
        data = json.loads(request.body)
        project = data.get("project", "")
        user = Helper.get_userid(request)
        
        if not user:
             return JsonResponse({"error": "Autenticazione richiesta"}, status=401)

        like_record = HelpderDB.sql_query_row(f"SELECT * FROM user_like WHERE recordidprojects_='{project}' AND utente='{user}'")

        if not like_record:
            return JsonResponse({"error": "Project not liked"}, status=400)
        
        query = f"DELETE FROM user_like WHERE recordidprojects_='{project}' AND utente='{user}'"
        HelpderDB.sql_execute(query)

        return JsonResponse({"message": "Project unliked successfully"}, status=200)

    except Exception as e:
        print(f"Error while unliking project: {e}")
        return JsonResponse({"error": "Error while unliking project", "detail": str(e)}, status=500)
    
DEFAULT_LANG = "it"

def get_available_languages():
    """
    Recupera la lista delle lingue disponibili
    """
    try:
        languages_table = UserTable("languages")
        languages = languages_table.get_records(conditions_list=[])
        
        if not languages:
            languages = [{"language": "italiano", "code": "it"}]
        
        return languages

    except Exception as e:
        languages = [{"language": "italiano", "code": "it"}]

def get_languages(request):
    languages = get_available_languages()

    return JsonResponse({"languages": languages})

def get_user_language(userid):
    try:
        if not userid:
            return JsonResponse({"language": DEFAULT_LANG})
        
        golf_club = HelpderDB.sql_query_row(f"SELECT Lingua FROM user_golfclub WHERE utente = {userid}") 

        if not golf_club:
            return JsonResponse({"language": DEFAULT_LANG})
        
        language_string = golf_club.get("Lingua", "")

        if not language_string:
            return JsonResponse({"language": DEFAULT_LANG})

        languages = get_available_languages()
        language_code = DEFAULT_LANG

        for lang in languages:
            if lang.get("fieldid") == language_string:
                language_code = lang.get("code")

        return language_code
    except Exception as e:
        return DEFAULT_LANG

def get_language(request):
    userid = Helper.get_userid(request)
        
    language_code = get_user_language(userid)

    return JsonResponse({"language": language_code})

    
def sync_translation_fields(request):
    try :
        translations_table = UserTable('translations')

        fields = HelpderDB.sql_query("SELECT * from sys_field")

        for field in fields:
            table_id = field.get('tableid')
            field_id = field.get('fieldid')

            condition_list = [
                f"tableid='{table_id}'",
                f"identifier='{field_id}'"
            ]

            translation = translations_table.get_records(conditions_list=condition_list)

            if not translation:
                print("Adding translation")
                new_record = UserRecord('translations')
                new_record.values['type'] = "Field"
                new_record.values['tableid'] = table_id
                new_record.values['identifier'] = field_id

                # TODO: rendere poi dinamica questa parte con la selezione delle lingue dalla tabella delle lingue
                new_record.values['italian'] = field.get('description')
                new_record.values['english'] = ""
                new_record.values['french'] = ""
                new_record.values['german'] = ""

                new_record.save()
            else:
                print("Translation already exists")
         
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

def get_translation(tableid, fieldid, userid=None, code=None):
    language_code = "it"

    if code:
        language_code = code

    if userid:
        language_code = get_user_language(userid)

    languages = get_available_languages()
    
    language_field = None
    for lang in languages:
        if lang.get("code") == language_code:
            language_field = lang.get("fieldid")
            break
    
    if not language_field:
        language_field = fieldid

    translations_table = UserTable('translations')

    condition_list = [
        f"tableid='{tableid}'",
        f"identifier='{fieldid}'",
    ]

    translation = translations_table.get_records(conditions_list=condition_list)

    if not translation:
        return fieldid
    
    word =  translation[0].get(language_field)

    if not word:
        return fieldid

    return word