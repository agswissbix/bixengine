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
import time
from typing import List
import pandas as pd




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

    table=UserTable(tableid)

    if viewid == '':
        viewid=table.get_default_viewid()

    records: List[UserRecord]
    
    records=table.get_table_records_obj(viewid=viewid,searchTerm=searchTerm)
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



def get_pitservice_pivot_lavanderia(request):
    # Costruisci la struttura di risposta
    response_data = {"groups": []}
    response_data["columns"] = []
    data = json.loads(request.body)
    tableid = data.get("tableid")
    table=UserTable(tableid)
    if tableid == 'rendicontolavanderia':
        sql="SELECT * FROM user_rendicontolavanderia  WHERE  deleted_='N' ORDER BY recordidcliente_"
        query_result=HelpderDB.sql_query(sql)
        df = pd.DataFrame(query_result)
        mesi = ['01.Gennaio', '02.Febbraio', '03.Marzo', '04.Aprile', '05.Maggio', '06.Giugno', '07.Luglio', '08.Agosto', '09.Settembre', '10.Ottobre', '11.Novembre', '12.Dicembre']
        
        pivot_df = pd.pivot_table(df,
                                index=['recordidcliente_', 'recordidstabile_'],
                                columns='mese',
                                values='anno',
                                aggfunc='sum')
        pivot_df = pivot_df.sort_index(axis=1)
        pivot_array = pivot_df.reset_index().values.tolist()
        for row in pivot_array:
            print(row)
        # Raggruppa i record per cliente
        gruppi_per_cliente = defaultdict(list)
        for record in pivot_array:
            recordid_cliente = record[0]
            gruppi_per_cliente[recordid_cliente].append(record)
        
        
        
        for recordid_cliente, records in gruppi_per_cliente.items():
            group = {}
            
            # Campi del gruppo: ad esempio potresti voler inserire il nome del cliente o altre info
            if recordid_cliente != 'None':
                record_cliente=UserRecord('cliente',recordid_cliente)
                nome_cliente = record_cliente.values.get('nome_cliente', '')
            else:
                nome_cliente = 'Cliente non definito'
            group_fields = [{"fieldid": "cliente", "value": nome_cliente, "css": ""}]
            group["fields"] = group_fields
            group["rows"] = []
            # Costruiamo le righe: in questo esempio una sola riga per cliente
            # Per ogni mese verifichiamo se esiste un record per quel mese
            for record in records:
                row = {"recordid": record[0], "css": "#", "fields": []}
                recordid_stabile=record[1]
                if recordid_stabile != 'None':
                    record_stabile=UserRecord('stabile',recordid_stabile)
                    titolo_stabile = record_stabile.values.get('titolo_stabile', '')
                    citta = record_stabile.values.get('citta', '')
                else:
                    titolo_stabile = 'Stabile non definito'
                    citta=''
                row["fields"].append({"recordid": "", "css": "", "type": "standard", "value": titolo_stabile})
                row["fields"].append({"recordid": "", "css": "", "type": "standard", "value": citta})

                for elemento in record[2:]:
                    if pd.isnull(elemento):
                        value = ''
                    else:
                        value = 'X'
                    row["fields"].append({
                        "recordid": "",
                        "css": '',
                        "type": "standard",
                        "value": value
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
    
    if tableid == 'letturagasolio':
        sql="SELECT * FROM user_letturagasolio  WHERE anno='2025' and  deleted_='N' ORDER BY recordidcliente_"
        query_result=HelpderDB.sql_query(sql)
        df = pd.DataFrame(query_result)
        mesi = ['01.Gennaio', '02.Febbraio', '03.Marzo', '04.Aprile', '05.Maggio', '06.Giugno', '07.Luglio', '08.Agosto', '09.Settembre', '10.Ottobre', '11.Novembre', '12.Dicembre']
        
        pivot_df = pd.pivot_table(df,
                                index=['recordidcliente_', 'recordidstabile_','recordidinformazionigasolio_'],
                                columns='mese',
                                values='lettura',
                                aggfunc='sum')
        pivot_df = pivot_df.sort_index(axis=1)
        pivot_array = pivot_df.reset_index().values.tolist()
        for row in pivot_array:
            print(row)
        # Raggruppa i record per cliente
        gruppi_per_cliente = defaultdict(list)
        for record in pivot_array:
            recordid_cliente = record[0]
            gruppi_per_cliente[recordid_cliente].append(record)
        
        
        
        for recordid_cliente, records in gruppi_per_cliente.items():
            group = {}
            
            # Campi del gruppo: ad esempio potresti voler inserire il nome del cliente o altre info
            if recordid_cliente != 'None':
                record_cliente=UserRecord('cliente',recordid_cliente)
                nome_cliente = record_cliente.values.get('nome_cliente', '')
            else:
                nome_cliente = 'Cliente non definito'
            group_fields = [{"fieldid": "cliente", "value": nome_cliente, "css": ""}]
            group["fields"] = group_fields
            group["rows"] = []
            # Costruiamo le righe: in questo esempio una sola riga per cliente
            # Per ogni mese verifichiamo se esiste un record per quel mese
            for record in records:
                row = {"recordid": record[0], "css": "#", "fields": []}
                recordid_stabile=record[1]
                if recordid_stabile != 'None':
                    record_stabile=UserRecord('stabile',recordid_stabile)
                    titolo_stabile = record_stabile.values.get('titolo_stabile', '')
                    citta = record_stabile.values.get('citta', '')
                else:
                    titolo_stabile = 'Stabile non definito'
                    citta=''
                
                
                row["fields"].append({"recordid": "", "css": "", "type": "standard", "value": titolo_stabile})
                row["fields"].append({"recordid": "", "css": "", "type": "standard", "value": citta})

                for elemento in record[3:]:
                    if pd.isnull(elemento):
                        value = ''
                    else:
                        value = elemento
                    row["fields"].append({
                        "recordid": "",
                        "css": '',
                        "type": "standard",
                        "value": value
                    })
                row["fields"].append({"recordid": "", "css": "", "type": "standard", "value": ''})
                row["fields"].append({"recordid": "", "css": "", "type": "standard", "value": ''})
                row["fields"].append({"recordid": "", "css": "", "type": "standard", "value": ''})
                row["fields"].append({"recordid": "", "css": "", "type": "standard", "value": ''})
                row["fields"].append({"recordid": "", "css": "", "type": "standard", "value": ''})
                row["fields"].append({"recordid": "", "css": "", "type": "standard", "value": ''})
                row["fields"].append({"recordid": "", "css": "", "type": "standard", "value": ''})
                row["fields"].append({"recordid": "", "css": "", "type": "standard", "value": ''})
                row["fields"].append({"recordid": "", "css": "", "type": "standard", "value": ''})

                recordid_cisterna=record[2]
                if recordid_cisterna != 'None':
                    record_cisterna=UserRecord('informazionigasolio',recordid_cisterna)
                    capienzacisterna = record_cisterna.values.get('capienzacisterna', '')
                    livellominimo = record_cisterna.values.get('livellominimo', '')
                else:
                    capienzacisterna = 'Cisterna non definita'
                    livellominimo='Cisterna non definita'
                row["fields"].append({"recordid": "", "css": "", "type": "standard", "value": capienzacisterna})
                row["fields"].append({"recordid": "", "css": "", "type": "standard", "value": livellominimo})
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
            {"fieldtypeid": "Parola", "desc": "Capienza"},
            {"fieldtypeid": "Parola", "desc": "Livello minimo"},

        ]

    

    return JsonResponse(response_data)

@csrf_exempt
def save_record_fields(request):
    data = json.loads(request.body)
    recordid = data.get("recordid")
    tableid = data.get("tableid")
    saved_fields = data.get("fields")
    record=UserRecord(tableid,recordid)
    for saved_fieldid, saved_value in saved_fields.items():
        record.values[saved_fieldid]=saved_value
    record.save()

    return JsonResponse({"success": True, "detail": "Campi del record salvati con successo"})

    
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
    response={ "badgeItems": badgeItems}
    return JsonResponse(response)

def get_record_card_fields(request):
    data = json.loads(request.body)
    tableid= data.get("tableid")
    recordid= data.get("recordid")

    record=UserRecord(tableid,recordid)
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
    email_fields = {
        "cc": "cc",
        "bcc": "bcc",	
        "subject": "subject",
        "text": "email text",
    }
    return JsonResponse({"success": True, "emailFields": email_fields})


@csrf_exempt
def save_email(request):
    print('save_email')
    return JsonResponse({"success": True})

@csrf_exempt
def get_input_linked(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            searchTerm = data.get('searchTerm', '').lower()
            tableid = data.get('tableid') # Puoi usare tableid se necessario

            # Qui dovresti sostituire i dati di esempio con la tua logica di database
            # o qualsiasi altra fonte di dati.
            items = [
                {'recordid': '1', 'name': 'Python'},
                {'recordid': '2', 'name': 'JavaScript'},
                {'recordid': '3', 'name': 'TypeScript'},
            ]

            # Filtra gli elementi in base al searchTerm
            filtered_items = [item for item in items if searchTerm in item['name'].lower()]

            return JsonResponse(filtered_items, safe=False)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
    else:
        return JsonResponse({'error': 'Method not allowed'}, status=405)
