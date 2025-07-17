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
        #wip_record=UserRecord('wipbarcode')
        #wip_record.values['wipbarcode']=barcode_wip
        #wip_record.values['lottobarcode']=barcode_lotto
        #wip_record.save()
        sql=f"INSERT INTO t_wipbarcode (wipbarcode,lottobarcode) VALUES ('{barcode_wip}','{barcode_lotto}')"
        HelpderDB.sql_execute(sql)

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


        rows=HelpderDB.sql_query("SELECT wipbarcode, lottobarcode, datascansione FROM user_wipbarcode where deleted_='N'")



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
    sql="SEleCT * FRom user_wipbarcode where deleted_='N' AND statowip='Barcodato'  LIMIT 10  "
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


