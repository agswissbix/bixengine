import json
from django.shortcuts import render
from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from rest_framework import status
from commonapp.bixmodels.helper_db import *
from commonapp.bixmodels.user_record import *
from commonapp.bixmodels.user_table import *
from commonapp.helper import *
import pyodbc

from django.utils.dateparse import parse_datetime

# Create your views here.

@csrf_exempt
@api_view(['POST'])
def winteler_wip_barcode_scan(request):
    """
    Esempio di funzione che riceve un barcode lotto (barcodeLotto)
    e una lista di barcode wip (barcodeWipList).
    """
    # Estraggo i dati dal body della richiesta
    barcode_lotto = request.data.get('barcodeLotto', None)
    barcode_wip_list = request.data.get('barcodeWipList', [])

    # Verifico la presenza di barcodeLotto
    if not barcode_lotto:
        return Response(
            {"detail": "barcodeLotto è obbligatorio"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Verifico che barcodeWipList sia effettivamente una lista
    if not isinstance(barcode_wip_list, list):
        return Response(
            {"detail": "barcodeWipList deve essere una lista di barcode"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Da qui puoi inserire la logica che serve per salvare i dati nel database
    # o processarli come meglio credi. Ad esempio:
    # for wip in barcode_wip_list:
    #     # Salvataggio su DB o altra logica
    #     WipModel.objects.create(lotto=barcode_lotto, wip_code=wip)
    #
    # Oppure puoi semplicemente ritornare una conferma
    for barcode_wip in barcode_wip_list:
        print(barcode_wip)
        sql=f"INSERT INTO t_wipbarcode (wipbarcode,lottobarcode) VALUES ('{barcode_wip}','{barcode_lotto}')"
        HelpderDB.sql_execute(sql)
        wip_record=UserRecord('wipbarcode')
        wip_record.values['wipbarcode']=barcode_wip
        wip_record.values['lottobarcode']=barcode_lotto
        wip_record.save()
        

    return Response(
        {
            "message": "Dati ricevuti con successo!",
            "barcodeLotto": barcode_lotto,
            "barcodeWipList": barcode_wip_list
        },
        status=status.HTTP_200_OK
    )


import pyodbc
from django.http import JsonResponse

def sync_wipbarcode_bixdata_adiuto(request):
    conn_str = (
        'DRIVER={ODBC Driver 17 for SQL Server};'
        'SERVER=WIGBSRV17;'  # prova anche con: WIGBSRV17\\SQLEXPRESS
        'DATABASE=winteler_data;'
        'UID=sa;'
        'PWD=Winteler,.-21;'
        # oppure: 'Trusted_Connection=yes;' se sei su Windows
    )

    try:
        conn = pyodbc.connect(conn_str, timeout=5)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM t_wipbarcode")
        conn.commit()


        rows=HelpderDB.sql_query("SELECT * FROM user_wipbarcode where deleted_='N'")



        count = 0
        for row in rows:
            wipbarcode=row['wipbarcode']
            lottobarcode=row['lottobarcode']    
            datascansione=row['datascansione']    
            statowip=row['statowip']  
            id=row['id']
            insert_sql = f"""
            INSERT INTO t_wipbarcode (wipbarcode, lottobarcode, datascansione,id, statowip)
            VALUES ('{wipbarcode}', '{lottobarcode}', '{datascansione}', {id}, '{statowip}')
            """

            # Esegui il merge
            cursor.execute(insert_sql)
            count += 1

        cursor.commit()

        return JsonResponse({'status': 'success', 'rows': [list(row) for row in rows]})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass



def script_update_wip_status(request):
    conn_str = (
        'DRIVER={ODBC Driver 17 for SQL Server};'
        'SERVER=WIGBSRV17;'  # prova anche con: WIGBSRV17\\SQLEXPRESS
        'DATABASE=winteler_data;'
        'UID=sa;'
        'PWD=Winteler,.-21;'
        # oppure: 'Trusted_Connection=yes;' se sei su Windows
    )
    sql="SEleCT * FRom user_wipbarcode where deleted_='N' AND statowip='Barcodato'   "
    records_list=HelpderDB.sql_query(sql)

    results = []
    conn = pyodbc.connect(conn_str, timeout=5)
    cursor = conn.cursor()
    
    try:
        for record_dict in records_list:
            barcode = record_dict['wipbarcode']
            lottobarcode = record_dict['lottobarcode']
            recordid_wip = record_dict['recordid_']
            record_wip = UserRecord('wipbarcode', recordid_wip)

            try:
                cursor.execute("SELECT * FROM VA1014 WHERE F1028 = ? AND FENA <> 0", (barcode,))
                row = cursor.fetchone()

                if row:
                    column_names = [desc[0] for desc in cursor.description]
                    row_dict = dict(zip(column_names, row))
                    f_idd = row_dict.get("FIDD")
                    data_caricamento = row_dict.get("F2")

                    # Gestione data
                    if data_caricamento:
                        data_caricamento = datetime.datetime.strptime(data_caricamento, "%Y%m%d").strftime("%Y-%m-%d")
                    else:
                        data_caricamento = "Data non disponibile"

                    record_wip.values['datacaricamentoadiuto'] = data_caricamento
                    record_wip.values['statowip'] = "Caricato"
                    record_wip.save()

                    #update_sql = "UPDATE A1047 SET F1092='Caricato' WHERE F1028=?"
                    #cursor.execute(update_sql, (barcode,))
                    #conn.commit()

                    results.append(f"Barcode: {barcode}: FIDD trovato: {f_idd}, data caricamento: {data_caricamento}")

                else:
                    cursor.execute("SELECT * FROM VA1014 WHERE F1335 = ? AND FENA <> 0", (lottobarcode,))
                    row = cursor.fetchone()

                    if row:
                        record_wip.values['statowip'] = "Verificare"
                        record_wip.save()

                        #update_sql = "UPDATE A1047 SET F1092='Verificare' WHERE F1028=?"
                        #cursor.execute(update_sql, (barcode,))
                        #conn.commit()

                        results.append(f"Barcode: {barcode}: Nessuna riga trovata in VA1014 per quel barcode ma lotto già caricato. Da verificare")
                    else:
                        results.append(f"Barcode: {barcode}: Nessuna riga trovata in VA1014 per quel barcode")

            except Exception as e:
                results.append(f"Errore per barcode {barcode}: {str(e)}")

    finally:
        cursor.close()
        conn.close()

    return HttpResponse("<br>".join(results))


import pyodbc
import os
import requests
from django.http import HttpResponse

def sync_plesk_adiuto(request):
    # Connessione SQL Server
    conn_str = (
        'DRIVER={ODBC Driver 17 for SQL Server};'
        'SERVER=WIGBSRV17;'
        'DATABASE=winteler_data;'
        'UID=sa;'
        'PWD=Winteler,.-21;'
    )
    conn = pyodbc.connect(conn_str, timeout=5)
    cursor = conn.cursor()

    results = []

    # Richiesta a adiexp.php
    url = "https://adiwinteler.swissbix.com/adiexp.php"
    access_password = os.environ.get('WINTELER_ACCESS_PASSWORD')
    params = {'psw': access_password}

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        results.append(f"Risposta da adiwinteler plesk: {data}")

        if not isinstance(data, list):
            raise ValueError("La risposta non è una lista JSON")

        for record in data:
            adiwid = record.get('adiwid')
            timestamp = record.get('timestamp_confirmation')

            if not adiwid or not timestamp:
                results.append(f"Record incompleto: {record}")
                continue

            # Verifica se il record esiste già
            cursor.execute(
                "SELECT COUNT(*) FROM T_ADIWID_CONFIRMATION WHERE adiwid = ?",
                adiwid
            )
            exists = cursor.fetchone()[0]

            if exists:
                results.append(f"Già presente: adiwid={adiwid}")
                continue

            # Inserisce il nuovo record
            cursor.execute(
                "INSERT INTO T_ADIWID_CONFIRMATION (adiwid, timestamp_confirmation) VALUES (?, ?)",
                adiwid,
                timestamp
            )
            conn.commit()

            # Verifica inserimento
            cursor.execute(
                "SELECT COUNT(*) FROM T_ADIWID_CONFIRMATION WHERE adiwid = ?",
                adiwid
            )
            verify = cursor.fetchone()[0]

            if verify:
                results.append(f"Inserito correttamente: adiwid={adiwid}, timestamp={timestamp}")

                # Chiama adidl.php per eliminare il record dalla sorgente
                cleanup_url = "https://adiwinteler.swissbix.com/adidl.php"
                cleanup_params = {'psw': access_password, 'adiwid': adiwid}

                try:
                    cleanup_response = requests.get(cleanup_url, params=cleanup_params, timeout=5)
                    cleanup_response.raise_for_status()
                    results.append(f"Chiamata adidl.php per adiwid={adiwid}: {cleanup_response.text}")
                except requests.RequestException as e:
                    results.append(f"Errore chiamata adidl.php per adiwid={adiwid}: {str(e)}")
            else:
                results.append(f"Errore inserimento record adiwid={adiwid}")

    except requests.RequestException as e:
        results.append(f"Errore di richiesta HTTP: {str(e)}")
    except ValueError as e:
        results.append(f"Errore nel parsing JSON: {str(e)}")
    except pyodbc.Error as e:
        results.append(f"Errore SQL: {str(e)}")
    finally:
        cursor.close()
        conn.close()

    return HttpResponse("<br>".join(results))

def sql_safe(value):
    if value is None:
        return "NULL"

    if isinstance(value, (datetime, date)):
        return f"'{value.strftime('%Y%m%d')}'"

    if isinstance(value, (int, float)):
        return str(value)

    # qualunque altro tipo → cast a str, escape singoli apici
    cleaned = str(value).replace("'", "''")
    return f"'{cleaned}'"

def save_service_man(request):
    if request.method != 'POST':
        return HttpResponse({
            'success': False,
            'message': 'Metodo non permesso. Utilizza POST.'
        }, status=405)

    try:
        data=json.loads(request.body)

        tableid = "serviceman"

        new_record = UserRecord(tableid)
        new_record.values['nome'] = data.get('nome','')
        new_record.values['cognome'] = data.get('cognome','')
        new_record.values['telefono'] = data.get('telefono','')
        new_record.values['email'] = data.get('email','')
        new_record.values['targa'] = data.get('targa','')
        new_record.values['telaio'] = data.get('telaio','')
        new_record.values['modello'] = data.get('modello','')

        data_string_iso = data.get('data', None)

        dt_object = parse_datetime(data_string_iso)

        if dt_object: 
            new_record.values['data'] = dt_object.date()
            new_record.values['ora'] = dt_object.time().strftime("%H:%M:%S.%f")

        new_record.values['nomeutente'] = data.get('utente', '')

        new_record.save()

        return HttpResponse({
            'success': True,
            'message': 'Dati ricevuti e processati con successo.'
        }, status=200)

    except Exception as e:
        return HttpResponse({
            'success': False,
            'message': f'Si è verificato un errore inatteso: {str(e)}'
        }, status=500)
    
def get_service_man(request):
    results = []

    tableid = 'serviceman'
    table = UserTable(tableid)
    rows = table.get_records()

    # TODO: filtrare solo quelli in attesa di conferma

    for row in rows:

        cliente = f'{row["nome"]} {row["cognome"]}'

        results.append({
            "id": row["id"],
            "cliente": cliente,
            "data": row["data"],
            "highlight": False
        })

    return JsonResponse({"serviceMen": results}, safe=False)

def save_checklist(request):
    if request.method != 'POST':
        return HttpResponse({
            'success': False,
            'message': 'Metodo non permesso. Utilizza POST.'
        }, status=405)

    try:
        data = json.loads(request.body)
        checklist = data.get('checkList')

        tableid = "checklist"

        new_record = UserRecord(tableid)

        # Dati cliente
        daticliente = checklist.get('datiCliente')
        new_record.values['nomedetentore'] = daticliente.get('nomedetentore')
        new_record.values['via'] = daticliente.get('via')
        new_record.values['telefono'] = daticliente.get('telefono')
        new_record.values['email'] = daticliente.get('email')
        new_record.values['venditore'] = daticliente.get('venditore', '')

        # Dati vettura
        datiVettura = checklist.get('datiVettura')
        new_record.values['marca'] = datiVettura.get('marca')
        new_record.values['modello'] = datiVettura.get('modello')
        new_record.values['telaio'] = datiVettura.get('telaio')
        new_record.values['targa'] = datiVettura.get('targa')
        new_record.values['km'] = datiVettura.get('km')

        # Controllo Officina
        controlloOfficina = checklist.get('controlloOfficina')

        # Pneumatici
        pneumatici = controlloOfficina.get('pneumatici')

        new_record.values['pneumatici_antsx_mm'] = pneumatici.get('antSx').get('mm')
        new_record.values['pneumatici_antdx_mm'] = pneumatici.get('antDx').get('mm')

        pneumatici_antsx_data =  parse_datetime(pneumatici.get('antSx').get('data'))
        pneumatici_antdx_data = parse_datetime(pneumatici.get('antDx').get('data'))
        if pneumatici_antdx_data:
            new_record.values['pneumatici_antsx_data'] = pneumatici_antsx_data.date()
        if pneumatici_antdx_data:
            new_record.values['pneumatici_antdx_data'] = pneumatici_antdx_data.date()

        new_record.values['pneumatici_postsx_mm'] = pneumatici.get('postSx').get('mm')
        new_record.values['pneumatici_postdx_mm'] = pneumatici.get('postDx').get('mm')

        pneumatici_postsx_data =  parse_datetime(pneumatici.get('postSx').get('data'))
        pneumatici_postdx_data = parse_datetime(pneumatici.get('postDx').get('data'))
        if pneumatici_postsx_data:
            new_record.values['pneumatici_postsx_data'] = pneumatici_postsx_data.date()
        if pneumatici_postdx_data:
            new_record.values['pneumatici_postdx_data'] = pneumatici_postdx_data.date()

        # Cerchi
        cerchi = controlloOfficina.get('cerchi')
        new_record.values['cerchi_antsx_stato'] = cerchi.get('antSx', '')
        new_record.values['cerchi_antdx_stato'] = cerchi.get('antDx', '')
        new_record.values['cerchi_postsx_stato'] = cerchi.get('postSx', '')
        new_record.values['cerchi_postdx_stato'] = cerchi.get('postDx', '')

        # Freni
        freni = controlloOfficina.get('freni')
        new_record.values['freni_antsx_perc'] = freni.get('antSx').get('perc')
        new_record.values['freni_antdx_perc'] = freni.get('antDx').get('perc')
        new_record.values['freni_antsx_stato'] = freni.get('antSx').get('stato', '')
        new_record.values['freni_antdx_stato'] = freni.get('antDx').get('stato', '')
        new_record.values['freni_postsx_perc'] = freni.get('postSx').get('perc')
        new_record.values['freni_postdx_perc'] = freni.get('postDx').get('perc')
        new_record.values['freni_postsx_stato'] = freni.get('postSx').get('stato', '')
        new_record.values['freni_postdx_stato'] = freni.get('postDx').get('stato', '')

        # Motore
        motore = controlloOfficina.get('motore')
        new_record.values['perditeolio'] = motore.get('olio').get('perdite', '')
        new_record.values['perditeliquido'] = motore.get('liquido').get('perdite', '')
        new_record.values['perditeolio_dove'] = motore.get('olio').get('dove')
        new_record.values['perditeliquido_dove'] = motore.get('liquido').get('dove')

        # Assale
        assale = controlloOfficina.get('assale')
        new_record.values['assale_anteriore'] = assale.get('anteriore').get('presente', '')
        new_record.values['assale_posteriore'] = assale.get('posteriore').get('presente', '')
        new_record.values['assale_anteriore_dove'] = assale.get('anteriore').get('dove', '')
        new_record.values['assale_posteriore_dove'] = assale.get('posteriore').get('dove', '')

        # Parabrezza
        parabrezza = controlloOfficina.get('parabrezza')
        new_record.values['parabrezza_danni'] = parabrezza.get('danni', '')
        new_record.values['parabrezza_sostituzione'] = parabrezza.get('sostituzione', '')

        # Batteria
        batteria = controlloOfficina.get('batteria')
        new_record.values['batteria_avviamento_stato'] = batteria.get('avviamento', '')
        new_record.values['batteria_secondaria_stato'] = batteria.get('secondaria', '')

        # Test Breve
        new_record.values['test_breve'] = controlloOfficina.get('testBreve', '')

        # MSI Plus
        msiplus = controlloOfficina.get('msiPlus')
        new_record.values['msi_plus'] = msiplus.get('presente', '')
        new_record.values['msiplus_scadenza'] = msiplus.get('scadenza', '')

        # Starclass
        starclass = controlloOfficina.get('starclass')
        new_record.values['starclass'] = starclass.get('presente', '')
        new_record.values['starckass_scadenza'] = starclass.get('scadenza', '')

        # Osservazioni officina
        new_record.values['osservazioni_officina'] = controlloOfficina.get('osservazioni')
        new_record.values['stimacosti_officina'] = controlloOfficina.get('stimaCosti')

        # Controllo carrozzeria
        controlloCarrozzeria = checklist.get('controlloCarrozzeria')
        new_record.values['grandinata'] = controlloCarrozzeria.get('grandinata', '')
        new_record.values['osservazioni_carrozzeria'] = controlloCarrozzeria.get('osservazioni')
        new_record.values['stimacosti_carrozzeria'] = controlloCarrozzeria.get('stimaCosti')

        new_record.save()

        return HttpResponse({
            'success': True,
            'message': 'Dati ricevuti e processati con successo.'
        }, status=200)

    except Exception as e:
        return HttpResponse({
            'success': False,
            'message': f'Si è verificato un errore inatteso: {str(e)}'
        }, status=500)
    
def save_nota_spesa(request):
    if request.method != 'POST':
        return HttpResponse({
            'success': False,
            'message': 'Metodo non permesso. Utilizza POST.'
        }, status=405)

    try:
        data=json.loads(request.body)

        tableid = 'notespese'

        new_record = UserRecord(tableid)

        new_record.values['tipo'] = data.get('tipo', '')
        new_record.values['importo'] = data.get('importo')
        new_record.values['pagamento'] = data.get('pagamento', '')
        new_record.values['note'] = data.get('note')

        new_record.save()

        return HttpResponse({
            'success': True,
            'message': 'Dati ricevuti e processati con successo.'
        }, status=200)
    except Exception as e:
        return HttpResponse({
            'success': False,
            'message': f'Si è verificato un errore inatteso: {str(e)}'
        }, status=500)
    
def save_preventivo_carrozzeria(request):
    if request.method != 'POST':
        return HttpResponse({
            'success': False,
            'message': 'Metodo non permesso. Utilizza POST.'
        }, status=405)

    try:
        data=json.loads(request.body)

        tableid = "preventivocarrozzeria"

        new_record = UserRecord(tableid)
        new_record.values['modello'] = data.get('modello','')
        new_record.values['telaio'] = data.get('telaio','')
        new_record.values['targa'] = data.get('targa','')
        new_record.values['nomeutente'] = data.get('utente','')
        new_record.values['nome'] = data.get('nome')
        new_record.values['cognome'] = data.get('cognome')

        new_record.save()

        return HttpResponse({
            'success': True,
            'message': 'Dati ricevuti e processati con successo.'
        }, status=200)
    except Exception as e:
        return HttpResponse({
            'success': False,
            'message': f'Si è verificato un errore inatteso: {str(e)}'
        }, status=500)
    
def save_nuova_auto(request):
    if request.method != 'POST':
        return HttpResponse({
            'success': False,
            'message': 'Metodo non permesso. Utilizza POST.'
        }, status=405)

    try:
        data=json.loads(request.body)

        tableid = "formautonuove"

        new_record = UserRecord(tableid)
        new_record.values['modello'] = data.get('modello', '')
        new_record.values['telaio'] = data.get('telaio', '')
        new_record.values['nomeutente'] = data.get('utente', '')

        new_record.save()

        return HttpResponse({
            'success': True,
            'message': 'Dati ricevuti e processati con successo.'
        }, status=200)
    except Exception as e:
        return HttpResponse({
            'success': False,
            'message': f'Si è verificato un errore inatteso: {str(e)}'
        }, status=500)
    
def save_prova_auto(request):
    if request.method != 'POST':
        return HttpResponse({
            'success': False,
            'message': 'Metodo non permesso. Utilizza POST.'
        }, status=405)

    try:
        data=json.loads(request.body)

        tableid = "proveauto"

        new_record = UserRecord(tableid)
        
        new_record.values['barcode'] = data.get('barcode','')
        new_record.values['telaio'] = data.get('telaio','')
        new_record.values['modello'] = data.get('modello','')
        new_record.values['targa'] = data.get('targa','')
        new_record.values['cognome'] = data.get('cognome','')
        new_record.values['nome'] = data.get('nome','')
        new_record.values['email'] = data.get('email','')
        new_record.values['via'] = data.get('via','')
        new_record.values['cap'] = data.get('cap','')
        new_record.values['citta'] = data.get('citta','')
        new_record.values['telefono'] = data.get('telefono','')
        new_record.values['kmpartenza'] = data.get('kmpartenza','')

        if (data.get('datapartenza',None)):
            new_record.values['datapartenza'] = parse_datetime(data.get('datapartenza',None)).date()
            new_record.values['orapartenza'] = parse_datetime(data.get('datapartenza',None)).time().strftime("%H:%M:%S.%f")

        new_record.values['kmarrivo'] = data.get('kmarrivo','')

        if (data.get('dataarrivo',None)):
            new_record.values['dataarrivo'] = parse_datetime(data.get('dataarrivo',None)).date()
            new_record.values['oraarrivo'] = parse_datetime(data.get('datapartenza',None)).time().strftime("%H:%M:%S.%f")

        new_record.values['note'] = data.get('note','')

        new_record.save()

        return HttpResponse({
            'success': True,
            'message': 'Dati ricevuti e processati con successo.'
        }, status=200)
    except Exception as e:
        return HttpResponse({
            'success': False,
            'message': f'Si è verificato un errore inatteso: {str(e)}'
        }, status=500)
    
def get_prove_auto(request): 
    results = []

    data=json.loads(request.body)

    filter = data.get('filter')

    # TODO: filtrare i risultati

    if (filter == 'precompilate') :
        print(filter)

    if (filter == 'in corso') :
        print(filter)

    tableid = 'proveauto'
    table = UserTable(tableid)
    rows = table.get_records()

    for row in rows:
        cliente = f"{row['nome']} {row['nome']}"

        results.append({
            'id': row['id'],
            'cliente': cliente,
            'venditore': row['venditore'],
            'data': row['datapartenza'],
            'highlight': False,
        })

    return JsonResponse({"proveAuto": results}, safe=False)

def search_scheda_auto(request): 
    results = []

    data=json.loads(request.body)

    barcode = data.get('barcode')
    telaio = data.get('telaio')

    if not barcode and not telaio:
        return JsonResponse(
            {'messaggio': 'Nessun dato fortnito'}, 
            status=400 
        )
    
    tableid = 'auto'
    conditions = f""

    if barcode :
        conditions = f"barcode = {barcode}"
    else :
        conditions = f"telaio = {telaio}"

    auto = HelpderDB.sql_query_row(f"select * from user_{tableid} WHERE {conditions}")

    if (auto):
        results.append({
            'id': auto["id"],
            'barcode': auto["barcode"],
            'modello': auto["modello"],
            'telaio': auto["telaio"],
        })
    else:
        return JsonResponse(
            {'messaggio': 'Nessun dato trovato'}, 
            status=404 
        ) 

    return JsonResponse({"scheda_auto": results[0]}, safe=False)

def get_venditori(request): 
    results = []

    data=json.loads(request.body)

    try:
        tableid = 'venditori'
        table = UserTable(tableid)
        rows = table.get_records()

        for row in rows:
            label = f"{row['nome']} {row['cognome']}"
            results.append({
                'value': row['id'],
                'label': label,
            })

        return JsonResponse({"venditori": results}, safe=False)
    except Exception as e:
        return JsonResponse({"venditori": []}, safe=False)

def get_scheda_auto(request):
    results = []

    data=json.loads(request.body)

    id = data.get('id')

    if not id:
        return JsonResponse(
            {'messaggio': 'Id non valido'}, 
            status=400 
        )

    tableid = 'auto'
    conditions = f"id = {id}"

    auto = HelpderDB.sql_query_row(f"select * from user_{tableid} WHERE {conditions}")

    if (auto):
        results.append({
            'id': auto["id"],
            'dati': {
                'barcode': auto["barcode"],
                'modello': auto["modello"],
                'libro_auto': auto["libroauto"],
                'numero_wb': auto["numerowb"],
                'telaio': auto["telaio"],
                'designazione':auto["designazione"],
            },
            'documento_principale': {
            },
            'allegati': [],
            'collegati': [],
        })
    else:
        return JsonResponse(
            {'messaggio': 'Nessun dato trovato'}, 
            status=404 
        ) 

    return JsonResponse({"scheda_auto": results[0]}, safe=False)
