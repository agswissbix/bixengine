import uuid
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.shortcuts import redirect
from datetime import datetime

from django.views.decorators.csrf import csrf_exempt
import json
from django.middleware.csrf import get_token
from django.conf import settings
from django.core.files.storage import default_storage
from django.contrib.auth.decorators import login_required
from functools import wraps

from commonapp.bixmodels import helper_db   
from .bixmodels.sys_table import *
from .bixmodels.user_record import *
from .bixmodels.user_table import *

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

import pandas as pd
import numpy as np
from pathlib import Path
from PIL import Image
from django.db import transaction, connection
from docxtpl import DocxTemplate




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
                "role": '',
                "chat": '',
                "telefono": ''
            })
    else:
        return JsonResponse({"isAuthenticated": False}, status=401)
        
        

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
    tables=SysTable.get_user_tables(1)
    workspaces_tables=dict()
    userid =Helper.get_userid(request)
    for table in tables:
        workspace = table["workspace"]
        
        if workspace not in workspaces_tables:
            workspaces_tables[workspace] = {}
            workspaces_tables[workspace]["id"]=table['workspace']
            workspaces_tables[workspace]["title"]=table['workspace']
            workspaces_tables[workspace]["icon"]='Home'
        subitem={}
        subitem['id']=table['id']
        subitem['title']=table['description']
        subitem['href']="#"
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


    response = {
        "menuItems": workspaces_tables,
        "otherItems": other_items,
        "favoriteTables": favorite_tables
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

        return JsonResponse({"success": True, "detail": "Record eliminato con successo"})
    
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "detail": "JSON non valido"}, status=400)
    
    except Exception as e:
        return JsonResponse({"success": False, "detail": f"Errore interno: {str(e)}"}, status=500)


def get_table_records(request):
    print('Function: get_table_records')
    data = json.loads(request.body)
    tableid = data.get("tableid")
    viewid= data.get("view")
    searchTerm= data.get("searchTerm")
    order=data.get("order")
    page=data.get("currentPage")
    master_tableid= data.get("masterTableid")
    master_recordid= data.get("masterRecordid")
    table=UserTable(tableid,Helper.get_userid(request))

    if viewid == '':
        viewid=table.get_default_viewid()

    records: List[UserRecord]
    conditions_list=list()
    records=table.get_table_records_obj(viewid=viewid,searchTerm=searchTerm,conditions_list=conditions_list,master_tableid=master_tableid,master_recordid=master_recordid)
    counter=table.get_total_records_count()
    table_columns=table.get_results_columns()
    rows=[]
    for record in records:
        row={}
        row['recordid']=record.recordid
        row['css']= "#"
        row['fields']=[]
        fields=record.get_record_results_fields()
        for field in fields:
                #TODO
                cssClass=''
                if tableid=='serviceandasset':
                    if field['fieldid'] == 'status' and field['value'] == 'Active':
                        cssClass='bg-emerald-50'
                    if field['fieldid'] == 'status' and field['value'] == 'Closed':
                        cssClass='bg-gray-50'
                    if field['fieldid'] == 'status' and field['value'] == 'Disabled':
                        cssClass='bg-yellow-50'
                    if field['fieldid'] == 'status' and field['value'] == 'CHECK':
                        cssClass='bg-red-100'
                    if field['fieldid'] == 'status' and field['value'] == 'CHECK - DNS':
                        cssClass='bg-yellow-100'
                    
                row['fields'].append({'recordid':'','css':cssClass,'type':field['type'],'value':field['value'],'fieldid':field['fieldid']})
        rows.append(row)
    
    columns=[]
    for table_column in table_columns:
        columns.append({'fieldtypeid':table_column['fieldtypeid'],'desc':table_column['description']})

    response_data = {
        "counter": counter,
        "rows": rows,
        "columns": columns
    }
        
    #time.sleep(4)

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
    table=UserTable(tableid)

    #TODO 
    #CUSTOM           

    #------ PITSERVICE - RENDICONTO LAVANDERIA --------------------------------
    if tableid == "rendicontolavanderia":
        # 1. Lettura (UNICA query) + filtro anno opzionale
        anno_filter = globals().get("anno_filter")       # es. "2025"
        sql = """
            SELECT *
            FROM user_rendicontolavanderia
            WHERE deleted_ = 'N'
        """
        if anno_filter:
            sql += f" AND anno = '{anno_filter}'"

        df = pd.DataFrame(HelpderDB.sql_query(sql))

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


@csrf_exempt
def save_record_fields(request):
    recordid = request.POST.get('recordid')
    tableid = request.POST.get('tableid')
    saved_fields = request.POST.get('fields')
    try:
        saved_fields_dict = json.loads(saved_fields)
    except json.JSONDecodeError:
        saved_fields_dict = {}
    record = UserRecord(tableid, recordid)
    for saved_fieldid, saved_value in saved_fields_dict.items():
        record.values[saved_fieldid] = saved_value

    record.save()
    recordid = record.recordid

    for file_key, uploaded_file in request.FILES.items():
        if file_key.startswith('files[') and file_key.endswith(']'):
            clean_key = file_key[6:-1]
        else:
            clean_key = file_key

        if tableid =='attachment':
            original_filename = uploaded_file.name
            record_path = f"{tableid}/{recordid}/{original_filename}"
            file_path = os.path.join(tableid, recordid, original_filename)

        else:
            _, ext = os.path.splitext(uploaded_file.name)
            record_path = f"{tableid}/{recordid}/{clean_key}{ext}"
            file_path = os.path.join(tableid, recordid, f"{clean_key}{ext}")


        # Salvataggio tramite default_storage (usa MEDIA_ROOT)
        if default_storage.exists(file_path):
            default_storage.delete(file_path)

        saved_path = default_storage.save(file_path, uploaded_file)

        # Salva il file anche in una path di backup che viene presa dal file env
        try:
            full_path = default_storage.path(saved_path)

            # Usa os.path.join per evitare errori di slash
            backup_base = env('BACKUP_DIR')
            #crea la cartella con tableid e dentro recordid e salva il file con il fieldid come nel salvataggio normale, ma nella cartella di backup, presa dall'env
            backup_path = os.path.join(backup_base, tableid, recordid, f"{clean_key}{ext}")

            # Crea la cartella di backup se non esiste
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            

            # Copia il file fisico nella cartella di backup
            if os.path.exists(full_path):
                shutil.copy2(full_path, backup_path)
                print(f"🧾 Backup file salvato in: {backup_path}")
            else:
                print(f"File non trovato per backup: {full_path}")

        except Exception as e:
            print(f"Errore nel salvataggio backup: {str(e)}")
            full_path = os.path.join(settings.MEDIA_ROOT, saved_path)

        print(f"🧾 File salvato fisicamente in: {full_path}")

        # Salva il percorso relativo nel record
        record.values[clean_key] = record_path

    record.save()

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
        
   

    return JsonResponse({"success": True, "detail": "Campi del record salvati con successo", "recordid": record.recordid})
    
def get_table_views(request):
    data = json.loads(request.body)
    tableid= data.get("tableid")
    table=UserTable(tableid)
    table_views=table.get_table_views()
    views=[ ]
    for table_view in table_views:
        views.append({'id':table_view['id'],'name':table_view['name']})
    response={ "views": views}

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

def get_record_card_fields(request):
    data = json.loads(request.body)
    tableid= data.get("tableid")
    recordid= data.get("recordid")
    master_tableid= data.get("mastertableid")
    master_recordid= data.get("masterrecordid")

    record=UserRecord(tableid,recordid,Helper.get_userid(request),master_tableid,master_recordid)
    card_fields=record.get_record_card_fields()
    response={ "fields": card_fields, "recordid": recordid}
    return JsonResponse(response)

def get_record_linked_tables(request):
    data = json.loads(request.body)
    master_tableid= data.get("masterTableid")
    master_recordid= data.get("masterRecordid")

    record=UserRecord(master_tableid,master_recordid)
    linkedTables=record.get_linked_tables()
    response={ "linkedTables": linkedTables}
    return JsonResponse(response)

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
        row=HelpderDB.sql_query_row(sql)
        contatto_emai=''
        if row:
            contatto_recordid=row['recordidcontatti_']
            if contatto_recordid != 'None':
                contatto_record=UserRecord('contatti',contatto_recordid)
                if contatto_record:
                    contatto_emai=contatto_record.values['email']

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
                                    Via San Gottardo 26 <br/>
                                    6943 Vezia <br/>
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
                                Via San Gottardo 26 <br/>
                                6943 Vezia <br/>
                            </p>
                        </td>
                    </tr>
                </table>
            """

        email_fields = {
            "to": contatto_emai,
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
        meseLettura='2025-06'
        anno, mese = meseLettura.split('-')

        sql=f"SELECT * FROM user_contattostabile WHERE deleted_='N' AND recordidstabile_='{stabile_recordid}'"
        row=HelpderDB.sql_query_row(sql)
        contatto_email=''
        if row:
            contatto_recordid=row['recordidcontatti_']
            contatto_record=UserRecord('contatti',contatto_recordid)
            if contatto_record:
                contatto_email=contatto_record.values['email']

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
                                Via San Gottardo 26 <br/>
                                6943 Vezia <br/>
                            </p>
                        </td>
                    </tr>
                </table>
                """
        
        email_fields = {
            "to": contatto_email,
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
        #TODO sistemare dinamico
        meseLettura="2025 06-Giugno"
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
        if record_rendiconto.values['stato']=='Nessuna ricerica':
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
                sql=f"SELECT recordid_ as recordid, {kyefieldlink} as name FROM user_{linkedmaster_tableid} where {kyefieldlink} like '%{searchTerm}%' {additional_conditions} AND deleted_='N' LIMIT 20"
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
        
            table = UserTable(tableid)
            if viewid == '':
                viewid=table.get_default_viewid()

            records: List[UserRecord]
            conditions_list=list()
            records=table.get_table_records_obj(viewid=viewid,searchTerm=searchTerm, conditions_list=conditions_list)
            counter=table.get_total_records_count()
            table_columns=table.get_results_columns()
            rows=[]
            for record in records:
                row={}
                row['recordid']=record.recordid
                row['css']= "#"
                row['fields']=[]
                fields=record.get_record_results_fields()
                for field in fields:
                        #TODO
                        cssClass=''
                        if tableid=='serviceandasset':
                            if field['fieldid'] == 'status' and field['value'] == 'Active':
                                cssClass='bg-emerald-50'
                            if field['fieldid'] == 'status' and field['value'] == 'Closed':
                                cssClass='bg-gray-50'
                            if field['fieldid'] == 'status' and field['value'] == 'Disabled':
                                cssClass='bg-yellow-50'
                            if field['fieldid'] == 'status' and field['value'] == 'CHECK':
                                cssClass='bg-red-100'
                            if field['fieldid'] == 'status' and field['value'] == 'CHECK - DNS':
                                cssClass='bg-yellow-100'
                            
                        row['fields'].append({'recordid':'','css':cssClass,'type':field['type'],'value':field['value'],'fieldid':field['fieldid']})
                rows.append(row)
        
                columns=[]
                for table_column in table_columns:
                    columns.append({'fieldtypeid':table_column['fieldtypeid'],'desc':table_column['description']})







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

    if tableid == 'bollettinitrasporto' or tableid == 'stabile':
        attachments=HelpderDB.sql_query(f"SELECT * FROM user_attachment WHERE recordid{tableid}_='{recordid}' AND deleted_ = 'N'")
        attachment_list=[]
        for attachment in attachments:
            recordid=attachment['recordid_']
            file=attachment['file']
            type=attachment['type']
            note=attachment['note']
            attachment_list.append({'recordid':recordid,'file':file,'type':type, 'note':note})
            
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
        table_tabs = ['Tabella', 'Kanban', 'Pivot', 'Calendario', 'Gallery']
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
    userid = request.user.id
    dashboards = HelpderDB.sql_query(f"SELECT dashboardid AS id, name from v_user_dashboard_block WHERE bixid={userid}")

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

def extract_rows_xml(request):
    folder_path_xml = os.path.join(settings.XML_DIR)
    folder_path = os.path.join(settings.MEDIA_ROOT, 'printinginvoice')  # Cartella per i file PDF
    if not os.path.exists(folder_path_xml):
        os.makedirs(folder_path_xml)
    for filename in os.listdir(folder_path_xml):
        if filename.endswith('.xml'):
            file_path = os.path.join(folder_path_xml, filename)
            filename = filename.replace('.xml', '')

            xml_check = HelpderDB.sql_query_row(f"SELECT * FROM user_printinginvoice WHERE filename='{filename}'")

            try:
                if xml_check is None:
                    tree = ET.parse(file_path)
                    root = tree.getroot()

                    invoice_rows = []
                    # Cerca i nodi invoiceRow sotto invoiceRows
                    invoice_rows_container = root.find('InvoiceRows')
                    if invoice_rows_container is not None:
                        invoice_rows = invoice_rows_container.findall('InvoiceRow')
                    
                    company_name = root.find('RecipientDescription').text 
                    company = HelpderDB.sql_query_row(f"SELECT * FROM user_company WHERE companyname='{company_name}'")
                    if not company:
                        recordidcompany = '00000000000000000000000000000394'
                    else:
                        recordidcompany = company['recordid_']

                    printing_invoice = UserRecord('printinginvoice')
                    printing_invoice.values['recordidcompany_'] = recordidcompany
                    printing_invoice.values['title'] = company_name
                    printing_invoice.values['totalnet'] = root.find('Total').text
                    printing_invoice.values['date'] = root.find('IssueDate').text
                    printing_invoice.values['status'] = 'Creata'
                    printing_invoice.values['katunid'] = root.find('Id').text
                    printing_invoice.values['filename'] = filename


                    printing_invoice.save()

                    invoice_recordid = printing_invoice.recordid

                    for row in invoice_rows:
                        row_data = {
                            'Description': row.find('Description').text if row.find('Description') is not None else '',
                            'Quantity': row.find('Quantity').text if row.find('Quantity') is not None else '',
                            'UnitPrice': row.find('UnitPrice').text if row.find('UnitPrice') is not None else '',
                            'Price': row.find('Price').text if row.find('Price') is not None else '',
                            'Amount': row.find('Amount').text if row.find('Amount') is not None else ''
                        }

                        invoiceline = UserRecord('printinginvoiceline')
                        invoiceline.values['recordidprintinginvoice_'] = invoice_recordid
                        invoiceline.values['description'] = row_data['Description']
                        invoiceline.values['quantity'] = row_data['Quantity']
                        invoiceline.values['unitprice'] = row_data['UnitPrice']
                        invoiceline.values['price'] = row_data['Price']
                        invoiceline.values['amount'] = row_data['Amount']

                        invoiceline.save()

                else:
                    invoice_recordid = xml_check['recordid_']
                    printing_invoice = UserRecord('printinginvoice',invoice_recordid)


                folder_path_updated = os.path.join(folder_path, invoice_recordid)

                pdf_file = os.path.join(folder_path_xml, filename + '.pdf')

                if os.path.exists(pdf_file):

                    if not os.path.exists(folder_path_updated):
                        os.makedirs(folder_path_updated)

                    
                    shutil.copy(pdf_file, os.path.join(folder_path_updated, 'pdfkatun.pdf'))

                    printing_invoice_update = UserRecord('printinginvoice', invoice_recordid)
                
                    printing_invoice_update.values['pdfkatun'] = 'printinginvoice/' + invoice_recordid + '/pdfkatun.pdf'

                    printing_invoice_update.save()


                             
            except ET.ParseError as e:
                print("errore")
    return JsonResponse({'status': 'success', 'message': 'Rows extracted successfully.'})


def bexio_api_set_invoice(request, recordid=None):
    if not recordid:
        bixdata_invoices = HelpderDB.sql_query("SELECT * FROM user_printinginvoice WHERE status='Creata' LIMIT 1")
    else:
        bixdata_invoices = HelpderDB.sql_query(f"SELECT * FROM user_printinginvoice WHERE recordid_='{recordid}'")


    for invoice in bixdata_invoices:

        #invoice data
        recordid_company= invoice['recordidcompany_']
        record_company = UserRecord('company', recordid_company)
        bexio_contact_id= record_company.values.get('bexioid', None)
        invoice_title="Conteggio copie stampanti/Multifunzioni"
        if (bexio_contact_id is  None) or (bexio_contact_id == ''):
            bexio_contact_id = 297 #contact id di Swissbix SA
            invoice_title = "Conto copie stampanti/Multifunzioni Swissbix SA "+invoice['title']
        # 1. Ottieni la data e ora correnti come oggetto datetime
        now = datetime.datetime.now()

        # 2. Aggiungi 20 giorni utilizzando timedelta
        future_date = now + datetime.timedelta(days=30)

        # 3. Formatta la nuova data nel formato stringa desiderato
        invoice_dateto = future_date.strftime("%Y-%m-%d")

        # Se vuoi anche la data di partenza formattata
        invoice_datefrom = now.strftime("%Y-%m-%d")

        #invoice lines
        bixdata_invoicelines = HelpderDB.sql_query(f"SELECT * FROM user_printinginvoiceline WHERE recordidprintinginvoice_='{invoice['recordid_']}'")
        invoiceliness = []
        for invoiceline in bixdata_invoicelines:
            invoiceline_unitprice= invoiceline['unitprice']
            invoiceline_quantity= invoiceline['amount']
            bexio_invoiceline = {
                "tax_id": "39",
                "account_id": "353",
                "unit_id": 2,   
                "amount": invoiceline_quantity,
                "unit_price": invoiceline_unitprice,
                "type": "KbPositionCustom",
            }
            invoiceliness.append(bexio_invoiceline)

        bexio_invoice = {
            "title": "Conteggio copie stampanti/Multifunzioni",
            "contact_id": 297,
            "user_id": 1,
            "logopaper_id": 1,
            "language_id": 3,
            "currency_id": 1,
            "payment_type_id": 1,
            "header": "",
            "footer": "Vi ringraziamo per la vostra fiducia, in caso di disaccordo, vi preghiamo di notificarcelo entro 7 giorni. <br/>Rimaniamo a vostra disposizione per qualsiasi domanda,<br/><br/>Con i nostri più cordiali saluti, Swissbix SA",
            "mwst_type": 0,
            "mwst_is_net": True,
            "show_position_taxes": False,
            "is_valid_from": invoice_datefrom,
            "is_valid_to": invoice_dateto,
            #"postitions": invoiceliness,
        }

        payload  = r"""{"title":"ICT: Supporto Cliente","contact_id":"297","user_id":1,"logopaper_id":1,"language_id":3,"currency_id":1,"payment_type_id":1,"header":"","footer":"Vi ringraziamo per la vostra fiducia, in caso di disaccordo, vi preghiamo di notificarcelo entro 7 giorni. Rimaniamo a vostra disposizione per qualsiasi domanda,Con i nostri più cordiali saluti, Swissbix SA","mwst_type":0,"mwst_is_net":true,"show_position_taxes":false,"is_valid_from":"2025-06-25","is_valid_to":"2025-07-15","positions":[{"text":"Interventi</b>","type":"KbPositionText"},{"text":"TEST 25/06/2025 Galli Alessandro </b></span>","tax_id":"39","account_id":"155","unit_id":2,"amount":"1","unit_price":"140","type":"KbPositionCustom"}]}"""


        
        
        url = "https://api.bexio.com/2.0/kb_invoice"
        accesstoken=os.environ.get('BEXIO_ACCESSTOKEN')
        headers = {
            'Accept': "application/json",
            'Content-Type': "application/json",
            'Authorization': f"Bearer {accesstoken}",
        }

        response = requests.request("POST", url, data=payload, headers=headers)
        status_code = response.status_code
    return JsonResponse({'status': status_code, 'message': response.json()})



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

def sign_timesheet(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            recordid = data.get('recordid')
            img_base64 = data.get('image')
            if not img_base64:
                return JsonResponse({'error': 'No image data'}, status=400)

            header, img_base64 = img_base64.split(',', 1)
            img_data = base64.b64decode(img_base64)
            
            base_path = os.path.join(settings.STATIC_ROOT, 'pdf')
            filename_firma = 'firma_' + str(recordid) + '.png'

            # Salva firma come immagine
            firma_path = os.path.join(base_path, filename_firma)
            img_pil = Image.open(BytesIO(img_data))

            if img_pil.mode in ('RGBA', 'LA') or (img_pil.mode == 'P' and 'transparency' in img_pil.info):
                background = Image.new('RGB', img_pil.size, (255, 255, 255))
                background.paste(img_pil, mask=img_pil.split()[-1])
                img_pil = background
            else:
                img_pil = img_pil.convert('RGB')

            img_pil.save(firma_path, format='PNG')

            uid = uuid.uuid4().hex

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=10,
                border=0,
            )

            today = datetime.date.today()
            d1 = today.strftime("%d/%m/%Y")

            qrcontent = 'timesheet_' + str(recordid)


            data = qrcontent
            qr.add_data(data)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")

            qr_name = 'qrcode' + uid + '.png'

            qr_path = os.path.join(base_path, qr_name)

            img.save(qr_path)


            rows = HelpderDB.sql_query(f"SELECT t.*, c.companyname, c.address, c.city, c.email, c.phonenumber, u.firstname, u.lastname FROM user_timesheet AS t JOIN user_company AS c ON t.recordidcompany_=c.recordid_ JOIN sys_user AS u ON t.user = u.id WHERE t.recordid_='{recordid}'")

            server = os.environ.get('BIXENGINE_SERVER')
            firma_url = server + '/static/pdf/' + filename_firma
            qr_url = server + '/static/pdf/' + qr_name

            filename_with_path = os.path.join(base_path, 'firma_salvata_' + str(recordid) + '.pdf')


            row = rows[0]

            for value in row:
                if row[value] is None:
                    row[value] = ''

            row['recordid'] = recordid
            row['qrUrl'] = qr_url
            row['signatureUrl'] = firma_url


            timesheetlines = HelpderDB.sql_query(f"SELECT * FROM user_timesheetline WHERE recordidtimesheet_='{recordid}'")


            for line in timesheetlines:
                line['note'] = line['note'] or ''   
                line['expectedquantity'] = line['expectedquantity'] or ''
                line['actualquantity'] = line['actualquantity'] or ''

            row['timesheetlines'] = timesheetlines

            script_dir = os.path.dirname(os.path.abspath(__file__))
        
            wkhtmltopdf_path = script_dir + '\\wkhtmltopdf.exe'

            config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
            content = render_to_string('pdf/timesheet_signature.html', row)

            pdfkit.from_string(content, filename_with_path, configuration=config)


            try:
                with open(filename_with_path, 'rb') as f:
                    pdf_data = f.read()
  
                    response = HttpResponse(pdf_data, content_type='application/pdf')
                    response['Content-Disposition'] = 'attachment; filename="timesheet_signature.pdf"'

                    return response
            finally:
                if os.path.exists(firma_path):
                    os.remove(firma_path)
                if os.path.exists(filename_with_path):
                    os.remove(filename_with_path)
                if os.path.exists(qr_path):
                    os.remove(qr_path)

        except Exception as e:
            print(f"Error in sign_timesheet: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
        
@csrf_exempt
def update_user_profile_pic(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)
    
    try:
        # Remove this line - it causes the error
        # data = json.loads(request.body)
        
        # Get data from FormData instead
        user_id = request.POST.get('userid') 
        image_file = request.FILES.get('image')
        
        if not user_id or not image_file:
            return JsonResponse({'error': 'Missing user_id or image'}, status=400)
        
        print(f"User ID: {user_id}")
        print(f"Image file: {image_file.name}, size: {image_file.size}")
        
        # Process the image file here
        # Example: save to filesystem or convert to base64
        # image_content = image_file.read()
        # base64_image = base64.b64encode(image_content).decode('utf-8')
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        print(f"Error: {e}")
        return JsonResponse({'error': str(e)}, status=500)
    

@login_required(login_url='/login/')
def get_dashboard_blocks(request):

    data = json.loads(request.body)

    #dashboard_id = data.get('dashboardid')
    dashboard_id = data.get('dashboardid')  # Default to 1 if not provided
    
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
        selected = ''
        with connection.cursor() as cursor:

            context['userid'] = bixid

            size = 'full'
            context['size'] = size

            #datas = SysUserDashboardBlock.objects.filter(userid=bixid, size=size, dashboardid=dashboard_id).values()
            sql = "SELECT * FROM sys_user_dashboard_block WHERE userid = {userid} AND size = 'full' AND dashboardid = {dashboardid}".format(
                userid=bixid, dashboardid=dashboard_id
            )
            datas = dbh.sql_query(sql)

            # all_blocks = SysDashboardBlock.objects.all()
            sql = "SELECT * FROM sys_dashboard_block ORDER BY name asc"
            all_blocks = dbh.sql_query(sql)

            for block in all_blocks:
                context['block_list'].append(block)

            for data in datas:
                dashboard_block_id = data['dashboard_block_id']
                sql = "SELECT * FROM v_sys_dashboard_block WHERE id = {dashboard_block_id}".format(
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
                    block['gsh'] = 2

                width = results['width']
                if width == None or width == 0 or width == '':
                    width = 4

                height = results['height']
                if height == None or height == 0 or height == '':
                    height = '50%'
                
                if results['reportid'] is None or results['reportid'] == 0:

                    if results['widgetid'] is None:
                        tableid = results['tableid']
                        tableid = 'user_' + tableid
                        block['type'] = 'table'

                        block['html'] = 'table'
                        #block['html'] = get_records_table(request, results['tableid'], None, None, '', results['viewid'], 1, '', '')
                    else:
                        block['html'] = 'test'

                else:
    
                    selected = ''
                    if results['operation'] == 'somma':
                        fields = results['fieldid'].split(';')
                        for field in fields:
                            field = 'SUM(' + field + ')'
                            selected += field + ','
                        groupby = results['groupby']
                        if results['custom'] == 'group_by_day':
                            groupby = f"DATE_FORMAT({groupby}, '%Y-%m-%d')"
                        if results['custom'] == 'group_by_month':
                            groupby = f"DATE_FORMAT({groupby}, '%Y-%m')"

                    query_conditions = results['query_conditions']
                    #userid = get_userid(request.user.id)
                    userid = bixid
                    query_conditions = query_conditions.replace("$userid$", str(userid))
                    id = data['id']
                    tableid = results['tableid']
                    name = results['name']
                    layout = results['layout']
                    block['type'] = layout
                    fromtable = 'user_' + tableid

                    db = HelpderDB()
                    groupby_field_record = db.sql_query_row(
                        f"select * from sys_field where tableid='{tableid}' and fieldid='{results['groupby']}'")
                    if groupby_field_record['fieldtypeid'] == 'Utente':
                        fromtable = fromtable + f" LEFT JOIN sys_user ON {fromtable}.{results['groupby']}=sys_user.id "
                        selected += f"sys_user.firstname as {groupby}"
                    else:
                        selected += groupby

                    sql = "SELECT " + selected + " FROM " + fromtable + \
                          " WHERE " + query_conditions + " GROUP BY " + groupby
                    block['sql'] = sql
                    values = get_chart(request, sql, id, name, layout, fields)
                    block['value'] = values['value']
                    block['labels'] = values['labels']
                    block['id'] = id
                    block['name'] = name
                    block['fields'] = values['fields']

                block['width'] = width
                block['height'] = height

                context['userid'] = bixid
                context['blocks'].append(block) 

    return JsonResponse(context, safe=False)



def get_chart(request, sql, id, name, layout, fields):
    query = sql
    id_sql = id
    name_chart = name
    layout_chart = layout
    fields_chart = fields

    with connection.cursor() as cursor2:
        cursor2.execute(query)
        rows = cursor2.fetchall()
        formatted_rows = []
        for row in rows:
            formatted_row = [str(value) if not isinstance(value, (int, float)) else value for value in row]
            formatted_rows.append(formatted_row)

        rows = formatted_rows
        value = []
        for num in range(0, len(fields_chart)):
            value.append([row[num] for row in rows])

        labels = [row[-1] for row in rows]

        if None in labels:
            labels = ['Non assegnato' if v is None else v for v in labels]

        for i in range(len(value)):
            for j in range(len(value[i])):
                if value[i][j] is not None:
                    if value[i][j] == 'None':
                        value[i][j] = 0
                    value[i][j] = round(value[i][j], 2)

        context = {
            'value': value[0],
            'labels': labels,
            'id': id_sql,
            'name': name_chart,
            'fields': fields_chart,
        }

        return (context)



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


def add_dashboard_block(request):

    json_data = json.loads(request.body)

    blockid = json_data.get('blockid')
    size = json_data.get('size')
    dashboardid = json_data.get('dashboardid')

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

    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO sys_user_dashboard_block (userid, dashboard_block_id, dashboardid, size) VALUES (%s, %s, %s, %s)",
            [bixid, blockid, dashboardid, size]
        )
    return JsonResponse({'success': True})


def save_form_data(request):
    try:
        data = json.loads(request.body)  

        # Tutti i dati inviati
        payload = data.get("payload", {})
        print("[-PAYLOAD-]:", payload)

        # Esempio dei dati singoli
        tassa_annua = payload.get("tassa_annua")
        tassa_ammissione = payload.get("tassa_ammissione")
        nr_soci = payload.get("nr_soci")
        print(f"tassa_ammissione: {tassa_ammissione}, tassa_annua: {tassa_annua}, nr_soci: {nr_soci}")


        record=UserRecord('metrica_annuale', '00000000000000000000000000000023')
        record.values['tassa_annua'] = tassa_annua
        record.values['tassa_ammissione'] = tassa_ammissione
        record.values['nr_soci'] = nr_soci
        record.save()


        return JsonResponse({"success": True})
    except Exception as e:
        print("Errore nel parsing JSON:", e)
        return JsonResponse({"success": False, "error": str(e)}, status=400)


def get_form_fields(request):
    fields = {}

    record=UserRecord('metrica_annuale', '00000000000000000000000000000023')
    fields['tassa_annua'] = record.values.get('tassa_annua')
    fields['tassa_ammissione'] = record.values.get('tassa_ammissione')
    fields['nr_soci'] = record.values.get('nr_soci')
                                                   

    return JsonResponse({"success": True, "fields": fields})


#TODO
#TEMP
#CUSTOM TELEFONO AMICO

@transaction.atomic
def save_newuser(request):
    """
    Crea o aggiorna un utente Django e le relative tabelle ausiliarie.
    Utilizza l'ORM solo per il modello User e SQL crudo parametrizzato per le altre.
    La logica è resa robusta contro errori di duplicazione tramite UPSERT.
    """
    # --- 1. Raccolta e Validazione Dati ---
    username = (request.POST.get("username") or "").lower()
    firstname = request.POST.get("firstname")
    password = request.POST.get("password")
    lastname = request.POST.get("lastname", "")
    email = request.POST.get("email", "")

    if not all([username, firstname, password]):
        return JsonResponse(
            {
                "success": False,
                "error": "I campi username, firstname e password sono obbligatori",
            },
            status=400,
        )

    # --- 2. Verifica Esistenza Utente (usando l'ORM) ---
    user = User.objects.filter(username=username).first()

    if user:
        # --- CASO: L'UTENTE ESISTE GIÀ (AGGIORNAMENTO) ---
        user.first_name = firstname
        user.last_name = lastname
        user.email = email
        if password:
            user.set_password(password)
        user.save()

        with connection.cursor() as cur:
            # Aggiorna la tabella sys_user
            cur.execute(
                """
                UPDATE sys_user
                   SET firstname = %s, lastname = %s, email = %s
                 WHERE username = %s
                """,
                [firstname, lastname, email, username],
            )
            
            # **FIX**: Assicura che il profilo esista (UPSERT per MySQL).
            # Questo crea il profilo se manca (es. cancellato per errore)
            # e non fa nulla se esiste già, evitando errori.
            cur.execute(
                """
                INSERT INTO commonapp_userprofile (user_id, is_2fa_enabled)
                VALUES (%s, 0)
                ON DUPLICATE KEY UPDATE user_id = VALUES(user_id)
                """,
                [user.id]
            )
    else:
        # --- CASO: L'UTENTE NON ESISTE (CREAZIONE) ---
        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=firstname,
            last_name=lastname,
            email=email,
        )
        bixid = user.id  # FK verso auth_user

        with connection.cursor() as cur:
            # Calcola l'ID per sys_user (logica sconsigliata ma mantenuta)
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

            # **FIX**: Inserisce il profilo usando UPSERT.
            # Questo previene l'errore di chiave duplicata se un segnale `post_save`
            # ha già creato il record del profilo.
            cur.execute(
                """
                INSERT INTO commonapp_userprofile (user_id, is_2fa_enabled)
                VALUES (%s, 0)
                ON DUPLICATE KEY UPDATE user_id = VALUES(user_id)
                """,
                [bixid],
            )

    return JsonResponse({"success": True})

        
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
