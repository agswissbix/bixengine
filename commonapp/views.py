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
import pandas as pd
import pdfkit
from django.http import HttpResponseForbidden
import os
import mimetypes
import shutil
from commonapp.utils.email_sender import EmailSender




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
    if request.user.is_authenticated:
        #Temp solution
        activeServer = HelpderDB.sql_query_row("SELECT value FROM sys_settings WHERE setting='cliente_id'")
        if activeServer['value'] == 'telefonoamico':
            sql=f"SELECT * FROM user_utenti WHERE nomeutente='{request.user.username}' AND deleted_='N'"
            record_utente=HelpderDB.sql_query_row(sql)
            nome=record_utente['nome']
            ruolo=record_utente['ruolo']
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
    
    username =Helper.get_username(request)
    other_items=[]

    if Helper.get_activeserver == 'belotti':
        gruppo=HelpderDB.sql_query_value(f"SELECT gruppo FROM user_sync_adiuto_utenti WHERE utentebixdata='{username}'","gruppo")
        if gruppo:
            formularigruppo=HelpderDB.sql_query(f"SELECT formulari FROM user_sync_adiuto_formularigruppo WHERE gruppo='{gruppo}'")
            if formularigruppo:
                formulari=formularigruppo[0]['formulari']
                lista_formulari_list = formulari.split(",")
                for formulario in lista_formulari_list:
                    other_items.append({
                        "id": formulario,
                        "description": formulario
                    })


    response = {
        "menuItems": workspaces_tables,
        "otherItems": other_items
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
    master_tableid= data.get("masterTableid")
    master_recordid= data.get("masterRecordid")
    table=UserTable(tableid)

    if viewid == '':
        viewid=table.get_default_viewid()

    records: List[UserRecord]
    conditions_list=list()
    records=table.get_table_records_obj(viewid=viewid,searchTerm=searchTerm,conditions_list=conditions_list,master_tableid=master_tableid,master_recordid=master_recordid)
    table_columns=table.get_results_columns()
    rows=[]
    for record in records:
        row={}
        row['recordid']=record.recordid
        row['css']= "#"
        row['fields']=[]
        fields=record.get_record_results_fields()
        for field in fields:
                row['fields'].append({'recordid':'','css':'','type':field['type'],'value':field['value'],'fieldid':field['fieldid']})
        rows.append(row)
    
    columns=[]
    for table_column in table_columns:
        columns.append({'fieldtypeid':table_column['fieldtypeid'],'desc':table_column['description']})

    response_data = {
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
    if tableid == "rendicontolavanderia":
        # 1. Lettura (1 sola query) + filtro anno opzionale ─────────────────────
        anno_filter = globals().get("anno_filter")  # es. "2025" se serve

        base_sql = """
                SELECT *
                FROM user_rendicontolavanderia
                WHERE deleted_ = 'N'
            """
        if anno_filter:
            base_sql += f" AND anno = '{anno_filter}'"

        df = pd.DataFrame(HelpderDB.sql_query(base_sql))

        # 2. Costruzione lista mesi nello stesso formato del DB (es. "04-Aprile")
        mesi = [
            f"{str(i).zfill(2)}-{m}"
            for i, m in enumerate(
                [
                    "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
                    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
                ],
                1,
            )
        ]

        # 3. Pivot: conta righe per (cliente, stabile, mese)  ───────────────────
        #   • senza colonna `values` (aggfunc='size') otteniamo direttamente il
        #     numero di record per cella
        #   • fill_value=0 sostituisce automaticamente i NaN assenti con 0
        pivot_df = pd.pivot_table(
            df,
            index=["recordidcliente_", "recordidstabile_"],
            columns="mese",
            aggfunc="size",
            fill_value=0,
        ).reindex(columns=mesi, fill_value=0)  # colonne mancanti completate a 0

        pivot_array = pivot_df.reset_index().values.tolist()

        # 4. Batch‑fetch anagrafiche (una query per tabella) ────────────────────
        cli_ids = {r[0] for r in pivot_array}
        sta_ids = {r[1] for r in pivot_array}

        cli_map = {}
        if cli_ids:
            in_list = ",".join(f"'{x}'" for x in cli_ids)
            rows = HelpderDB.sql_query(
                f"""
                    SELECT recordid_, nome_cliente
                    FROM user_cliente
                    WHERE recordid_ IN ({in_list})
                """
            )
            cli_map = {r["recordid_"]: r["nome_cliente"] for r in rows}

        sta_map = {}
        if sta_ids:
            in_list = ",".join(f"'{x}'" for x in sta_ids)
            rows = HelpderDB.sql_query(
                f"""
                    SELECT recordid_, titolo_stabile, citta
                    FROM user_stabile
                    WHERE recordid_ IN ({in_list})
                """
            )
            sta_map = {r["recordid_"]: (r["titolo_stabile"], r["citta"]) for r in rows}

        # 5. Riclassifica: cliente ▶ stabili (con valori mesi) ──────────────────
        data = defaultdict(list)  # {id_cli: [(id_sta, vals), ...]}
        for id_cli, id_sta, *val_mesi in pivot_array:
            data[id_cli].append((id_sta, val_mesi))

        # 6. Costruisci `response_data`  ─────────────────────────────────────────
        response_data = {
            "columns": [
                {"fieldtypeid": "Parola", "desc": ""},
                {"fieldtypeid": "Parola", "desc": "Città"},
                *[{"fieldtypeid": "Parola", "desc": m.split("-", 1)[1]} for m in mesi],
            ],
            "groups": [],
        }

        for id_cli, stabili in data.items():  # livello 0: cliente
            grp_cli = {
                "groupKey": id_cli,
                "level": 0,
                "fields": [
                    {"value": cli_map.get(id_cli, "Cliente non definito"), "css": "font-semibold"},
                    {"value": "", "css": ""},  # città non applicabile a livello cliente
                ],
                "rows": [],
            }

            for id_sta, vals in stabili:  # livello riga: stabile
                nome_sta, citta = sta_map.get(id_sta, ("Stabile non definito", ""))
                row_fields = [
                    {"value": nome_sta, "css": ""},
                    {"value": citta, "css": ""},
                ]

                # Valori mese → "X" se count ≥1, altrimenti "" (vuoto)
                for v in vals:
                    row_fields.append({"value": "X" if v >= 1 else "", "css": ""})

                grp_cli["rows"].append({"recordid": id_sta, "css": "", "fields": row_fields})

            response_data["groups"].append(grp_cli)

        
    

    if tableid=='letturagasolio':
        # 1. Recupero letture e pivot  ───────────────────────────────────────────────
        df = pd.DataFrame(HelpderDB.sql_query("""
            SELECT *
            FROM user_letturagasolio
            WHERE anno = '2025'
                AND deleted_ = 'N'
        """))

        mesi = [f"{str(i).zfill(2)}-{m}" for i, m in enumerate([
            "Gennaio","Febbraio","Marzo","Aprile","Maggio","Giugno",
            "Luglio","Agosto","Settembre","Ottobre","Novembre","Dicembre"
        ], 1)]

        pivot_df = (
            pd.pivot_table(
                df,
                index=["recordidcliente_", "recordidstabile_", "recordidinformazionigasolio_"],
                columns="mese",
                values="lettura",
                aggfunc="sum"
            ).reindex(columns=mesi)           # <- mantiene l’ordine
        ).fillna("")

        pivot_array = pivot_df.reset_index().values.tolist()

        # 2. Batch‑fetch anagrafiche  ────────────────────────────────────────────────
        cli_ids   = {r[0] for r in pivot_array}
        sta_ids   = {r[1] for r in pivot_array}
        cis_ids   = {r[2] for r in pivot_array}

        def fetch_map(table, id_set, fields):
            if not id_set:
                return {}
            in_list = ",".join(f"'{x}'" for x in id_set)
            cols    = ",".join(fields)
            rows    = HelpderDB.sql_query(f"""
                SELECT recordid_, {cols}
                FROM user_{table}
                WHERE recordid_ IN ({in_list})
            """)
            return {r["recordid_"]: {k: r[k] for k in fields} for r in rows}

        cli_map = fetch_map("cliente",            cli_ids, ["nome_cliente"])
        sta_map = fetch_map("stabile",            sta_ids, ["riferimento", "citta"])
        cis_map = fetch_map("informazionigasolio", cis_ids, ["riferimento", "capienzacisterna", "livellominimo"])

        # 3. Riclassifica: cliente ▶ stabile ▸ lista (cisterna, valori) ─────────────
        data = defaultdict(lambda: defaultdict(list))
        for id_cli, id_sta, id_cis, *val_mesi in pivot_array:
            data[id_cli][id_sta].append((id_cis, val_mesi))

        # 4. Costruisci response_data  (solo Python‑dict, 0 query extra) ────────────
        response_data = {
            "columns": (
                [{"fieldtypeid": "Parola", "desc": ""}, {"fieldtypeid": "Parola", "desc": "Città"}] +
                [{"fieldtypeid": "Parola", "desc": m.split("-", 1)[1]} for m in mesi] +
                [{"fieldtypeid": "Parola", "desc": "Capienza"},
                {"fieldtypeid": "Parola", "desc": "Livello minimo"}]
            ),
            "groups": []
        }

        for id_cli, stabili in data.items():                     # livello 0
            grp_cli = {
                "groupKey": id_cli,
                "level": 0,
                "fields": [
                    {"value": cli_map.get(id_cli, {}).get("nome_cliente", ""), "css": "font-semibold"},
                    {"value": "", "css": ""}
                ],
                "subGroups": []
            }

            for id_sta, cis_rows in stabili.items():             # livello 1
                sta_info = sta_map.get(id_sta, {})
                grp_sta = {
                    "groupKey": f"{id_cli}-{id_sta}",
                    "level": 1,
                    "fields": [
                        {"value": sta_info.get("riferimento", ""), "css": ""},
                        {"value": sta_info.get("citta", ""), "css": ""}
                    ],
                    "rows": []
                }

                for id_cis, vals in cis_rows:                    # riga (cisterna)
                    cis_info = cis_map.get(id_cis, {})
                    row_fields = [
                        {"value": cis_info.get("riferimento", ""), "css": "text-xs"},
                        {"value": "", "css": ""}
                    ] + [{"value": v, "css": ""} for v in vals] + [
                        {"value": cis_info.get("capienzacisterna", ""), "css": ""},
                        {"value": cis_info.get("livellominimo", ""),  "css": ""}
                    ]
                    grp_sta["rows"].append({"recordid": id_cis, "css": "", "fields": row_fields})

                grp_cli["subGroups"].append(grp_sta)

            response_data["groups"].append(grp_cli)            
            



    if tableid == 'dipendente':
        sql="SELECT * FROM user_dipendente  WHERE  deleted_='N' ORDER BY ruolo"
        query_result=HelpderDB.sql_query(sql)

        gruppi_per_ruolo = defaultdict(list)
        for record in query_result:
            ruolo = record['ruolo']
            gruppi_per_ruolo[ruolo].append(record)
        
        
        
        for ruolo, records in gruppi_per_ruolo.items():
            group = {}
            
           
            group['groupKey']=ruolo
            group['level']=ruolo
            group_fields = [{"fieldid": "ruolo", "value": ruolo, "css": ""}]
            group["fields"] = group_fields
            group['subGroups']=[]
            group["rows"] = []
            # Costruiamo le righe: in questo esempio una sola riga per cliente
            # Per ogni mese verifichiamo se esiste un record per quel mese
            for record in records:
                row = {"recordid": record['recordid_'], "css": "#", "fields": []}
                row["fields"].append({"recordid": "", "css": "", "type": "standard", "value": record['cognome']})
                row["fields"].append({"recordid": "", "css": "", "type": "standard", "value": record['nome']})
                row["fields"].append({"recordid": "", "css": "", "type": "standard", "value": record['email']})
                row["fields"].append({"recordid": "", "css": "", "type": "standard", "value": record['telefono']})
                group["rows"].append(row)
            
            
            response_data["groups"].append(group)


        response_data["columns"] = [
            {"fieldtypeid": "Parola", "desc": ""},
            {"fieldtypeid": "Parola", "desc": "Cognome"},
            {"fieldtypeid": "Parola", "desc": "Nome"},
            {"fieldtypeid": "Parola", "desc": "Email"},
            {"fieldtypeid": "Parola", "desc": "Telefono"}

        ]
    

    return JsonResponse(response_data)

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
        # Estrai il nome pulito dal campo
        if file_key.startswith('files[') and file_key.endswith(']'):
            clean_key = file_key[6:-1]
        else:
            clean_key = file_key

        _, ext = os.path.splitext(uploaded_file.name)

        file_path = f"uploads/{tableid}/{recordid}/{clean_key}{ext}"
        record_path = f"{tableid}/{recordid}/{clean_key}{ext}"

        # Salvataggio backup prima di salvare il file originale
        backup_folder = "C:/bixdata/backup/attachments"
        os.makedirs(backup_folder, exist_ok=True)
        backup_filename = f"{tableid}_{recordid}_{clean_key}{ext}"
        backup_path = os.path.join(backup_folder, backup_filename)

        # Backup prima del salvataggio
        with open(backup_path, 'wb+') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)

        # 🔁 Riavvolgi il file per riutilizzarlo
        uploaded_file.seek(0)

        # Ora salva nel percorso principale
        if default_storage.exists(file_path):
            default_storage.delete(file_path)

        saved_path = default_storage.save(file_path, uploaded_file)


        if default_storage.exists(saved_path):
            full_path = default_storage.path(saved_path)
        else:
            full_path = os.path.join(settings.MEDIA_ROOT, saved_path)

        record.values[clean_key] = record_path

    record.save()

    
    if tableid == 'stabile':
        stabile_record = UserRecord('stabile', recordid)
        if Helper.isempty(stabile_record.values['titolo_stabile']):
            stabile_record.values['titolo_stabile']=""
        riferimento=stabile_record.values['titolo_stabile']+" "+stabile_record.values['indirizzo']
        stabile_record.values['riferimento']=riferimento
        stabile_record.save()
        sql_riferimentocompleto=f"""
            UPDATE user_stabile AS stabile
            JOIN user_cliente AS cliente
            ON stabile.recordidcliente_ = cliente.recordid_
            SET stabile.riferimentocompleto = CONCAT(cliente.nome_cliente, ' ', stabile.riferimento);
        """
        HelpderDB.sql_execute(sql_riferimentocompleto)

    if tableid == 'contatti':
        contatto_record = UserRecord('contatti', recordid)
        if Helper.isempty(contatto_record.values['nome']):
            contatto_record.values['nome']=""
        if Helper.isempty(contatto_record.values['cognome']):
            contatto_record.values['cognome']=""
        riferimento=contatto_record.values['nome']+" "+contatto_record.values['cognome']
        contatto_record.values['riferimento']=riferimento
        contatto_record.save()

    if tableid == 'contattostabile':
        contattostabile_record = UserRecord('contattostabile', recordid)
        contatto_record=UserRecord('contatti',contattostabile_record.values['recordidcontatti_'])
        contattostabile_record.values['nome']=contatto_record.values['nome']   
        contattostabile_record.values['cognome']=contatto_record.values['cognome']
        contattostabile_record.values['email']=contatto_record.values['email']
        contattostabile_record.values['telefono']=contatto_record.values['telefono']
        contattostabile_record.values['ruolo']=contatto_record.values['ruolo']
        contattostabile_record.save()

    # ---LETTURE GASOLIO---
    if tableid == 'letturagasolio':
        letturagasolio_record = UserRecord('letturagasolio', recordid)
        stabile_record = UserRecord('stabile', letturagasolio_record.values['recordidstabile_'])
        informazionigasolio_record=UserRecord('informazionigasolio',letturagasolio_record.values['recordidinformazionigasolio_'])
        
        capienzacisterna=Helper.safe_float(informazionigasolio_record.values['capienzacisterna'])
        letturacm=Helper.safe_float(letturagasolio_record.values['letturacm'])

        if capienzacisterna:
            if capienzacisterna == 1500:
                if letturacm:
                    letturagasolio_record.values['letturalitri']=letturacm*10
            if capienzacisterna == 2000:
                if letturacm:
                    letturagasolio_record.values['letturalitri']=letturacm*13
        
        

        #TODO anno dinamico
        letturagasolio_record.values['anno']='2025'
        letturagasolio_record.values['recordidcliente_']=stabile_record.values['recordidcliente_']
        letturagasolio_record.values['capienzacisterna']=capienzacisterna
        letturagasolio_record.values['livellominimo']=informazionigasolio_record.values['livellominimo']
        letturagasolio_record.save()


    # ---BOLLETTINI---
    if tableid == 'bollettini':
        bollettino_record = UserRecord('bollettini', recordid)
        tipo_bollettino=bollettino_record.values['tipo_bollettino']
        nr=bollettino_record.values['nr']   
        if not nr:
            if not tipo_bollettino:
                tipo_bollettino=''
            sql="SELECT * FROM user_bollettini WHERE tipo_bollettino='"+tipo_bollettino+"' AND deleted_='N' ORDER BY nr desc LIMIT 1"
            bollettino_recorddict = HelpderDB.sql_query_row(sql)
            if bollettino_recorddict['nr'] is None:
                nr=1
            else:
                nr = int(bollettino_recorddict['nr']) + 1
            bollettino_record.values['nr']=nr
            
        allegato=bollettino_record.values['allegato']
        if allegato:
            bollettino_record.values['allegatocaricato']='Si'
        else:
            bollettino_record.values['allegatocaricato']='No'

        stabile_record = UserRecord('stabile', bollettino_record.values['recordidstabile_'])
        cliente_recordid=stabile_record.values['recordidcliente_']
        bollettino_record.values['recordidcliente_']=cliente_recordid
        bollettino_record.save()

    
    if tableid == 'rendicontolavanderia':
        rendiconto_record = UserRecord('rendicontolavanderia', recordid)
        if rendiconto_record.values['stato']=='Da fare' and rendiconto_record.values['allegato']:   
            rendiconto_record.values['stato']='Preparato'
        rendiconto_record.save()

    if tableid == 'richieste':
        richieste_record = UserRecord('richieste', recordid)
        richieste_record.values['stato']='Merce spedita'
        richieste_record.save()


    
   





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
            contatto_record=UserRecord('contatti',contatto_recordid)
            if contatto_record:
                contatto_emai=contatto_record.values['email']

        attachment_fullpath=HelpderDB.get_uploadedfile_fullpath('rendicontolavanderia',rendiconto_recordid,'allegato')
        attachment_relativepath=HelpderDB.get_uploadedfile_relativepath('rendicontolavanderia',rendiconto_recordid,'allegato')
        subject=f"Resoconto lavanderia - {stabile_riferimento} {stabile_citta} - {mese} {anno}"

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

        email_fields = {
            "to": contatto_emai,
            "cc": "contabilita@pitservice.ch,segreteria@pitservice.ch",
            "bcc": "",	
            "subject": subject,
            "text": body,
            "attachment_fullpath": attachment_fullpath,
            "attachment_relativepath": attachment_relativepath,
            "attachment_name": f"{stabile_riferimento} {stabile_citta} - Lavanderia - {mese} - {anno}.pdf",
            }
    
    if type == 'emailGasolio':
        stabile_recordid=recordid
        stabile_record=UserRecord('stabile',stabile_recordid)
        meseLettura='2025-04'
        anno, mese = meseLettura.split('-')

        sql=f"SELECT * FROM user_contattostabile WHERE deleted_='N' AND recordidstabile_='{stabile_recordid}'"
        row=HelpderDB.sql_query_row(sql)
        contatto_email=''
        if row:
            contatto_recordid=row['recordidcontatti_']
            contatto_record=UserRecord('contatti',contatto_recordid)
            if contatto_record:
                contatto_email=contatto_record.values['email']

        attachment_relativepath=stampa_gasoli(request,recordid_stabile=stabile_recordid,meseLettura=meseLettura)
        riferimento=stabile_record.values.get('riferimento', '')
        stabile_citta=stabile_record.values['citta']
        subject=f"Livello Gasolio - 05 {anno} - {riferimento} {stabile_citta}"
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
            "attachment_name": f"Lettura_Gasolio_05-{anno}-{riferimento}-{stabile_citta}.pdf",
            }

    return JsonResponse({"success": True, "emailFields": email_fields})

@csrf_exempt
def stampa_gasoli(request,recordid_stabile,meseLettura):
    data={}
    filename='gasolio.pdf'
    #TODO dinamico
    meseLettura="2025 05-Maggio"
    anno, mese = meseLettura.split(' ')
        
    script_dir = os.path.dirname(os.path.abspath(__file__))
    wkhtmltopdf_path = script_dir + '\\wkhtmltopdf.exe'
    config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
    
    record_stabile=UserRecord('stabile',recordid_stabile)
    data['stabile']=record_stabile.values
    sql=f"""
    SELECT t.recordid_,t.anno,t.mese,t.datalettura,t.lettura, i.riferimento, i.livellominimo, i.capienzacisterna
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
    
    content = render_to_string('pdf/gasolio.html', data)

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

    return 'commonapp/static/pdf/' + filename
    


@csrf_exempt
def save_email(request):
    data = json.loads(request.body)
    email_data = data.get('emailData')
    tableid = data.get('tableid')
    recordid = data.get('recordid')
    #TODO 
    if tableid == 'rendicontolavanderia':
        record_rendiconto=UserRecord('rendicontolavanderia',recordid)
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
    record_email.values['attachment_name']=email_data['attachment_name']
    record_email.values['status']="Da inviare"
    record_email.save()

    attachment_relativepath=email_data['attachment_relativepath']
    if attachment_relativepath.startswith("commonapp/static"):
        base_dir=settings.BASE_DIR
        file_path = os.path.join(settings.BASE_DIR, attachment_relativepath)
        fullpath_originale = default_storage.path(file_path)
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
            linkedmaster_tableid_array = data.get('linkedmaster_tableid') # Puoi usare tableid se necessario
            linkedmaster_tableid=linkedmaster_tableid_array[0]
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


def export_excel(request):
    if request.method == 'POST':
        tableid = request.POST.get('tableid')
        master_tableid = request.POST.get('master_tableid')
        master_recordid = request.POST.get('master_recordid')
        searchTerm = request.POST.get('searchTerm')
        viewid = request.POST.get('viewid')
        order_field = request.POST.get('order_field')
        order = request.POST.get('order')
        currentpage = 0
        table_type = request.POST.get('tableType')

       

        csv_file = f"{tableid}-{uuid.uuid4().hex}.csv"



        with open(csv_file, 'rb') as file:
            response = HttpResponse(file.read(), content_type='text/csv')
            response['Content-Disposition'] = 'attachment'
            response['filename'] = csv_file

        os.remove(csv_file)

        return response

@csrf_exempt
def get_record_attachments(request):
    data = json.loads(request.body)
    tableid = data.get('tableid')
    recordid = data.get('recordid')

    if tableid == 'bollettinitrasporto' or tableid == 'stabile':
        attachments=HelpderDB.sql_query(f"SELECT * FROM user_attachment WHERE recordid{tableid}_='{recordid}'")
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


def get_favorite_tables(request):
    data = json.loads(request.body)
    sys_user_id = Helper.get_userid(request)
    context = dict()
    
    query = "SELECT tableid FROM sys_user_table_order WHERE userid = '{}'".format(sys_user_id)
    with connection.cursor() as cursor:
        cursor.execute(
            query
        )
        tables = HelpderDB.dictfetchall(cursor)

    if not tables:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT tableid FROM sys_user_table_order WHERE userid = 1"
            )
            tables = HelpderDB.dictfetchall(cursor)

    query = f"SELECT tableid FROM sys_user_favorite_tables WHERE sys_user_id = {sys_user_id}"
    with connection.cursor() as cursor:
        cursor.execute(
            query
        )
        favorite_tables = HelpderDB.dictfetchall(cursor)

    i = 0
    for table in tables:
        if i < len(favorite_tables) and table['tableid'] == favorite_tables[i]['tableid']:
            table['favorite'] = True
            i += 1
        else:
            table['favorite'] = False

    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM sys_table")
        all_tables = HelpderDB.dictfetchall(cursor)

    for a, table in enumerate(all_tables):
        for b, t in enumerate(tables):
            if t['tableid'] == table['id']:
                tables[b]['description'] = table['description']

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
    fav_tables = request.POST.get('tables')
    fav_tables = json.loads(fav_tables)
    sys_user_id = Helper.get_userid(request.user.id)


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


def export_excel(request):
    data= json.loads(request.body)
    tableid = data.get('tableid')
    return JsonResponse({"success": True, "detail": "Excel esportato con successo"})





