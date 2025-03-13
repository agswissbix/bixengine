from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.shortcuts import redirect
from datetime import datetime

from django.views.decorators.csrf import csrf_exempt
import json
from django.middleware.csrf import get_token
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

    response = {
        "menuItems": workspaces_tables
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
    return JsonResponse({"success": True, "detail": "Record eliminato con successo"})


def get_table_records(request):
    data = json.loads(request.body)
    tableid = data.get("tableid")
    viewid= data.get("view")
    searchTerm= data.get("searchTerm")
    tableid='stabile'
    viewid=3 #temporaneo

    records = []
    table=UserTable(tableid)
    records=table.get_results_records()
    columns=table.get_results_columns()
    rows=[]
    for record in records:
        row={}
        row['recordid']=record['recordid_']
        row['css']= "#"
        row['fields']=[]
        for field in record:
            if field != 'recordid_':
                row['fields'].append({'recordid':record['recordid_'],'css':'','type':'standard','value':record[field]})
        

    response_data = {
        "rows": [
            {
                "recordid": "1",
                "css": "#",
                "fields": [
                    {
                        "recordid": "",
                        "css": "",
                        "type": "standard",
                        "value": "macbook"
                    },
                    {
                        "recordid": "",
                        "css": "",
                        "type": "standard",
                        "value": "nero"
                    },
                    {
                        "recordid": "",
                        "css": "",
                        "type": "standard",
                        "value": "Laptop"
                    },
                    {
                        "recordid": "",
                        "css": "",
                        "type": "standard",
                        "value": "2k"
                    },
                ]
            },
            {
                "recordid": "2",
                "css": "#",
                "fields": [
                    {
                        "recordid": "",
                        "css": "",
                        "type": "standard",
                        "value": "surface",
                    },
                    {
                        "recordid": "",
                        "css": "",
                        "type": "standard",
                        "value": "bianco",
                    },
                    {
                        "recordid": "",
                        "css": "",
                        "type": "standard",
                        "value": "Laptop",
                    },
                    {
                        "recordid": "",
                        "css": "",
                        "type": "standard",
                        "value": "1k",
                    },
                ]
            },
        ],
        "columns": [
            {
                "fieldtypeid": "Numero",
                "desc": "Product name"
            },
            {
                "fieldtypeid": "Numero",
                "desc": "Color"
            },
            {
                "fieldtypeid": "Numero",
                "desc": "Type"
            },
            {
                "fieldtypeid": "Numero",
                "desc": "Price"
            },
        ]
    }

    return JsonResponse(response_data)



def get_pitservice_pivot_lavanderia(request):
    table=UserTable('rendicontolavanderia')
    sql="SELECT * FROM user_rendicontolavanderia WHERE deleted_='N' ORDER BY recordidcliente_"
    query_result=HelpderDB.sql_query(sql)
    print(query_result[0])

    mesi = ['01.Gennaio', '02.Febbraio', '03.Marzo', '04.Aprile', '05.Maggio', '06.Giugno', '07.Luglio', '08.Agosto', '09.Settembre', '10.Ottobre', '11.Novembre', '12.Dicembre']
    
    # Raggruppa i record per cliente
    gruppi_per_cliente = defaultdict(list)
    for record in query_result:
        cliente = record.get('recordidcliente_')
        gruppi_per_cliente[cliente].append(record)
    
    # Costruisci la struttura di risposta
    response_data = {"groups": []}
    
    for recordid_cliente, records in gruppi_per_cliente.items():
        group = {}
        
        # Campi del gruppo: ad esempio potresti voler inserire il nome del cliente o altre info
        record_cliente=UserRecord('cliente',recordid_cliente)
        if record_cliente.values is not None:
            nome_cliente = record_cliente.values.get('nome_cliente', '')
        else:
            nome_cliente = ''
        group_fields = [{"fieldid": "cliente", "value": nome_cliente, "css": ""}]
        group["fields"] = group_fields
        group["rows"] = []
        # Costruiamo le righe: in questo esempio una sola riga per cliente
        # Per ogni mese verifichiamo se esiste un record per quel mese
        for record in records:
            row = {"recordid": record['recordid_'], "css": "#", "fields": []}
            recordid_stabile=record['recordidstabile_']
            record_stabile=UserRecord('stabile',recordid_stabile)
            if record_stabile.values is not None:
                titolo_stabile = record_cliente.values.get('titolo_stabile', '')
                citta = record_cliente.values.get('citta', '')
            else:
                titolo_stabile = ''
                citta=''
            row["fields"].append({"recordid": "", "css": "", "type": "standard", "value": titolo_stabile})
            row["fields"].append({"recordid": "", "css": "", "type": "standard", "value": citta})
            for mese in mesi:
                if any(r['mese'] == mese for r in records):
                    valore = "x"
                    css = ""
                else:
                    valore = ""
                    css = ""
            row["fields"].append({
                "recordid": "",
                "css": css,
                "type": "standard",
                "value": valore
            })
            group["rows"].append(row)
        
        
        response_data["groups"].append(group)


        response_data["columns"] = [
            {"fieldtypeid": "Parola", "desc": ""},
            {"fieldtypeid": "Parola", "desc": "Città"},
            {"fieldtypeid": "Parola", "desc": "Gennaio"},
            {"fieldtypeid": "Parola", "desc": "Febbraio"},
            {"fieldtypeid": "Parola", "desc": "Marzo"},
            {"fieldtypeid": "Parola", "desc": "Aprile"},
            {"fieldtypeid": "Parola", "desc": "Maggio"},
            {"fieldtypeid": "Parola", "desc": "Giugno"},
            {"fieldtypeid": "Parola", "desc": "Luglio"},
            {"fieldtypeid": "Parola", "desc": "Agosto"},
            {"fieldtypeid": "Parola", "desc": "Settembre"},
            {"fieldtypeid": "Parola", "desc": "Ottobre"},
            {"fieldtypeid": "Parola", "desc": "Novembre"},
            {"fieldtypeid": "Parola", "desc": "Dicembre"},

        ]

        
    response_dataDEV = {
        "groups": [
            {
                "rows": [
                    {
                        "recordid": "1",
                        "css": "#",
                        "fields": [
                            {"recordid": "", "css": "", "type": "standard", "value": "Reg.Sole"},
                            {"recordid": "", "css": "", "type": "standard", "value": "x"},
                            {"recordid": "", "css": "", "type": "standard", "value": "x"},
                            {"recordid": "", "css": "", "type": "standard", "value": ""}
                        ]
                    },
                    {
                        "recordid": "2",
                        "css": "#",
                        "fields": [
                            {"recordid": "", "css": "", "type": "standard", "value": "Via Rava 11"},
                            {"recordid": "", "css": "", "type": "standard", "value": "x"},
                            {"recordid": "", "css": "", "type": "standard", "value": "x"},
                            {"recordid": "", "css": "bg-green-500", "type": "standard", "value": "x"}
                        ]
                    }
                ],
                "fields": [
                    {"fieldid": "1", "value": "Cofis", "css": ""},
                    {"fieldid": "2", "value": "indirizzo 1", "css": ""}
                ]
            },
            {
                "rows": [
                    {
                        "recordid": "3",
                        "css": "#",
                        "fields": [
                            {"recordid": "", "css": "", "type": "standard", "value": "Via D.Fontana 6"}
                        ]
                    },
                    {
                        "recordid": "4",
                        "css": "#",
                        "fields": [
                            {"recordid": "", "css": "", "type": "standard", "value": "Residenza Salice Via Frontini 8"},
                            {"recordid": "", "css": "", "type": "standard", "value": "x"},
                            {"recordid": "", "css": "", "type": "standard", "value": "x"},
                            {"recordid": "", "css": "", "type": "standard", "value": ""}
                        ]
                    }
                ],
                "fields": [
                    {"fieldid": "1", "value": "Agogestilioni", "css": ""},
                    {"fieldid": "2", "value": "indirizzo2", "css": ""}
                ]
            },
            {
                "rows": [
                    {
                        "recordid": "5",
                        "css": "#",
                        "fields": [
                            {"recordid": "", "css": "", "type": "standard", "value": "Aggestioni Sagl"}
                        ]
                    },
                    {
                        "recordid": "6",
                        "css": "#",
                        "fields": [
                            {"recordid": "", "css": "", "type": "standard", "value": "Condominio Liberty Via Domenico Fontana 6"},
                            {"recordid": "", "css": "", "type": "standard", "value": "x"},
                            {"recordid": "", "css": "", "type": "standard", "value": "x"},
                            {"recordid": "", "css": "", "type": "standard", "value": ""}
                        ]
                    }
                ],
                "fields": [
                    {"fieldid": "1", "value": "Aggestioni Sagl", "css": ""},
                    {"fieldid": "2", "value": "indirizzo3", "css": ""}
                ]
            }
        ],
        "columns": [
            {"fieldtypeid": "Parola", "desc": ""},
            {"fieldtypeid": "Parola", "desc": "Città"},
            {"fieldtypeid": "Parola", "desc": "Gennaio"},
            {"fieldtypeid": "Parola", "desc": "Febbraio"},
            {"fieldtypeid": "Parola", "desc": "Marzo"},
            {"fieldtypeid": "Parola", "desc": "Aprile"},
            {"fieldtypeid": "Parola", "desc": "Maggio"},
            {"fieldtypeid": "Parola", "desc": "Giugno"},
            {"fieldtypeid": "Parola", "desc": "Luglio"},
            {"fieldtypeid": "Parola", "desc": "Agosto"},
            {"fieldtypeid": "Parola", "desc": "Settembre"},
            {"fieldtypeid": "Parola", "desc": "Ottobre"},
            {"fieldtypeid": "Parola", "desc": "Novembre"},
            {"fieldtypeid": "Parola", "desc": "Dicembre"},

        ]
    }

    return JsonResponse(response_data)

