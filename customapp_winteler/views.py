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


def sync_wipbarcode_bixdata_adiuto(request):

    target_conn_str = (
        'DRIVER={ODBC Driver 17 for SQL Server};'
        'SERVER=WIBGSRV17;'
        'DATABASE=winteler_data;'
        'UID=sa;'
        'PWD=Winteler,.-21;'
    )

    try:
        tgt_conn = pyodbc.connect(target_conn_str, timeout=5)
        tgt_cursor = tgt_conn.cursor()

        tgt_cursor.execute("SELECT TOP 10 * FROM t_wipbarcode")
        rows = tgt_cursor.fetchall()
        
        count = 0
        for row in rows:
            insert_sql = f"""
            INSERT INTO t_wipbarcode (wipbarcode, lottobarcode)
            """

            # Esegui il merge
            #tgt_cursor.execute(insert_sql)
            count += 1

        tgt_cursor.commit()
        return JsonResponse({'status': 'success', 'imported_rows': count})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

    finally:
        try:
            tgt_cursor.close()
            tgt_conn.close()
        except:
            pass




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