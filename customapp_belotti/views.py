from django.shortcuts import render
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
import pyodbc
import environ
from django.conf import settings
from commonapp.bixmodels.user_record import *
from commonapp.bixmodels.user_table import *
from commonapp.bixmodels.helper_db import *
from commonapp.helper import *
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view

# Initialize environment variables
env = environ.Env()
environ.Env.read_env()

def dictfetchall(cursor):
        "Return all rows from a cursor as a dict"
        columns = [col[0] for col in cursor.description]
        return [
            dict(zip(columns, row))
            for row in cursor.fetchall()
        ]


def sync_utenti_adiutobixdata(request):
    try:
        DRIVER = env('DB_DRIVER')
        SERVER = env('DB_SERVER')
        DATABASE = env('DB_NAME')
        UID = env('DB_USER')
        PWD = env('DB_PASSWORD')
        conn = pyodbc.connect(
            f"DRIVER={DRIVER};"
            f"SERVER={SERVER};"
            f"DATABASE={DATABASE};"
            f"UID={UID};"
            f"PWD={PWD};",
            timeout=5
        )
        cursor = conn.cursor()

        data = []
        try:
            cursor.execute("SELECT  * FROM A1014")
            rows = dictfetchall(cursor)

            for row in rows:
                utente_bix = row['F1053']
                
                # Verifica se il record esiste in base a utentebixdata
                sql_check = f"SELECT recordid_ FROM user_sync_adiuto_utenti WHERE utentebixdata = '{utente_bix}'"
                existing = HelpderDB.sql_query_value(sql_check, 'recordid_')

                if existing:
                    # Se esiste, aggiorna
                    record = UserRecord('sync_adiuto_utenti', recordid=existing)
                else:
                    # Altrimenti crea un nuovo record
                    record = UserRecord('sync_adiuto_utenti')

                # Imposta i valori
                record.values['utentebixdata'] = utente_bix  # Chiave logica
                record.values['gruppo'] = row['F1050']
                record.values['email'] = row['F1017']
                record.values['nome'] = row['F1054']
                # ... aggiungi altri campi se necessario

                record.save()

        except pyodbc.ProgrammingError as e:
            return JsonResponse({"success": False, "error": f"Errore nella query SQL: {str(e)}"})
        except Exception as e:
            return JsonResponse({"success": False, "error": f"Errore durante l'esecuzione della query: {str(e)}"})
        finally:
            cursor.close()

    except pyodbc.InterfaceError as e:
        return JsonResponse({"success": False, "error": f"Errore di connessione (InterfaceError): {str(e)}"})
    except pyodbc.OperationalError as e:
        return JsonResponse({"success": False, "error": f"Errore operativo nella connessione al database: {str(e)}"})
    except Exception as e:
        return JsonResponse({"success": False, "error": f"Errore generico di connessione: {str(e)}"})
    finally:
        try:
            if conn:
                conn.close()
        except NameError:
            pass  # conn non definita se la connessione è fallita

    return JsonResponse({"success": True, "rows": rows})


def sync_prodotti_adiutobixdata(request):
    try:
        DRIVER = env('DB_DRIVER')
        SERVER = env('DB_SERVER')
        DATABASE = env('DB_NAME')
        UID = env('DB_USER')
        PWD = env('DB_PASSWORD')
        conn = pyodbc.connect(
            f"DRIVER={DRIVER};"
            f"SERVER={SERVER};"
            f"DATABASE={DATABASE};"
            f"UID={UID};"
            f"PWD={PWD};",
            timeout=5
        )
        cursor = conn.cursor()

        data = []
        try:
            cursor.execute("SELECT  * FROM A1009")
            rows = dictfetchall(cursor)

            for row in rows:
                codice = row['F1029']
                
                # Verifica se il record esiste in base a utentebixdata
                sql_check = f"SELECT recordid_ FROM user_sync_adiuto_prodotti WHERE codice = '{codice}'"
                existing = HelpderDB.sql_query_value(sql_check, 'recordid_')

                if existing:
                    # Se esiste, aggiorna
                    record = UserRecord('sync_adiuto_prodotti', recordid=existing)
                else:
                    # Altrimenti crea un nuovo record
                    record = UserRecord('sync_adiuto_prodotti')

                # Imposta i valori
                record.values['codice'] = codice  # Chiave logica
                record.values['descrizione'] = row['F1030']
                record.values['formato'] = row['F1031']
                record.values['categoria'] = row['F1032']
                record.values['gruppo'] = row['F1033']
                # ... aggiungi altri campi se necessario

                record.save()

        except pyodbc.ProgrammingError as e:
            return JsonResponse({"success": False, "error": f"Errore nella query SQL: {str(e)}"})
        except Exception as e:
            return JsonResponse({"success": False, "error": f"Errore durante l'esecuzione della query: {str(e)}"})
        finally:
            cursor.close()

    except pyodbc.InterfaceError as e:
        return JsonResponse({"success": False, "error": f"Errore di connessione (InterfaceError): {str(e)}"})
    except pyodbc.OperationalError as e:
        return JsonResponse({"success": False, "error": f"Errore operativo nella connessione al database: {str(e)}"})
    except Exception as e:
        return JsonResponse({"success": False, "error": f"Errore generico di connessione: {str(e)}"})
    finally:
        try:
            if conn:
                conn.close()
        except NameError:
            pass  # conn non definita se la connessione è fallita

    return JsonResponse({"success": True, "rows": rows})


def sync_formularigruppo_adiutobixdata(request):
    try:
        DRIVER = env('DB_DRIVER')
        SERVER = env('DB_SERVER')
        DATABASE = env('DB_NAME')
        UID = env('DB_USER')
        PWD = env('DB_PASSWORD')
        conn = pyodbc.connect(
            f"DRIVER={DRIVER};"
            f"SERVER={SERVER};"
            f"DATABASE={DATABASE};"
            f"UID={UID};"
            f"PWD={PWD};",
            timeout=5
        )
        cursor = conn.cursor()

        data = []
        try:
            cursor.execute("SELECT  * FROM A1012")
            rows = dictfetchall(cursor)

            for row in rows:
                gruppo = row['F1050']
                
                # Verifica se il record esiste in base a utentebixdata
                sql_check = f"SELECT recordid_ FROM user_sync_adiuto_formularigruppo WHERE gruppo = '{gruppo}'"
                existing = HelpderDB.sql_query_value(sql_check, 'recordid_')

                if existing:
                    # Se esiste, aggiorna
                    record = UserRecord('sync_adiuto_formularigruppo', recordid=existing)
                else:
                    # Altrimenti crea un nuovo record
                    record = UserRecord('sync_adiuto_formularigruppo')

                # Imposta i valori
                record.values['gruppo'] = gruppo  # Chiave logica
                record.values['formulari'] = row['F1033']
                # ... aggiungi altri campi se necessario

                record.save()

        except pyodbc.ProgrammingError as e:
            return JsonResponse({"success": False, "error": f"Errore nella query SQL: {str(e)}"})
        except Exception as e:
            return JsonResponse({"success": False, "error": f"Errore durante l'esecuzione della query: {str(e)}"})
        finally:
            cursor.close()

    except pyodbc.InterfaceError as e:
        return JsonResponse({"success": False, "error": f"Errore di connessione (InterfaceError): {str(e)}"})
    except pyodbc.OperationalError as e:
        return JsonResponse({"success": False, "error": f"Errore operativo nella connessione al database: {str(e)}"})
    except Exception as e:
        return JsonResponse({"success": False, "error": f"Errore generico di connessione: {str(e)}"})
    finally:
        try:
            if conn:
                conn.close()
        except NameError:
            pass  # conn non definita se la connessione è fallita

    return JsonResponse({"success": True, "rows": rows})



@csrf_exempt
@api_view(['POST'])
def belotti_salva_formulario(request):
    """
    Esempio di funzione che riceve un barcode lotto (barcodeLotto)
    e una lista di barcode wip (barcodeWipList).
    """
    # Estraggo i dati dal body della richiesta
    username = Helper.get_username(request)
    completeOrder = request.data.get('completeOrder', [])
    for order_row in completeOrder:
        categoria=order_row.get('title', None)
        products=order_row.get('products', [])
        for product in products:
            codice=product.get('id', None)
            descrizione=product.get('name', None)
            quantita=product.get('quantity', None)
            if not Helper.isempty(quantita):
                if quantita > 0:
                   
                    print(product)
                else:
                    print("Vuoto")

    return Response(
        {
            "message": "Dati salvati!",
        },
        status=status.HTTP_200_OK
    )


def sync_fatture_sirioadiuto(request):
    source_conn_str = (
        'DRIVER={Pervasive ODBC Unicode Interface};'
        'ServerName=SIRIO;'
        'DBQ=OTTICABELOTTI;'
        'UID=Sirio;'
    )

    target_conn_str = (
        'DRIVER={ODBC Driver 17 for SQL Server};'
        'SERVER=BGCASVM-ADI01;'
        'DATABASE=belotti_data;'
        'UID=sa;'
        'PWD=Belotti,.-23;'
    )

    try:
        src_conn = pyodbc.connect(source_conn_str, timeout=5)
        tgt_conn = pyodbc.connect(target_conn_str, timeout=5)
        src_cursor = src_conn.cursor()
        tgt_cursor = tgt_conn.cursor()

        src_cursor.execute("SELECT TOP 1000 * FROM Documenti ORDER BY id_sirio DESC")
        rows = src_cursor.fetchall()

        count = 0
        for row in rows:
            
            count += 1

        tgt_conn.commit()
        return JsonResponse({'status': 'success', 'imported_rows': count})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

    finally:
        try:
            src_cursor.close()
            src_conn.close()
            tgt_cursor.close()
            tgt_conn.close()
        except:
            pass
