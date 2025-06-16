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
from datetime import datetime, date

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
                record.values['utenteadiuto'] = row['F1052']
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
    print("Fun: belotti_salva_formulario")
    # Estraggo i dati dal body della richiesta
    username = Helper.get_username(request)
    record_richiesta=UserRecord('richieste')
    record_richiesta.values['tiporichiesta']=''
    record_richiesta.values['data'] = datetime.now().strftime("%Y-%m-%d")
    record_richiesta.values['stato'] = 'Richiesta inviata'
    record_richiesta.save()
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
                    record_richieste_righedettaglio = UserRecord('richieste_righedettaglio')
                    record_richieste_righedettaglio.values['recordidrichieste_'] = record_richiesta.recordid
                    record_richieste_righedettaglio.values['codice'] =codice
                    record_richieste_righedettaglio.values['prodotto'] = descrizione
                    record_richieste_righedettaglio.values['quantita'] = quantita
                    record_richieste_righedettaglio.values['gruppo'] = categoria
                    record_richieste_righedettaglio.save()
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
            merge_sql = f"""
            MERGE dbo.T_SIRIO_FATTUREFORNITORE AS T
            USING (SELECT {sql_safe(row.barcode_adiuto)} AS barcode_adiuto,
              {sql_safe(row.id_sirio)} AS id_sirio,
              {sql_safe(row.numero_fattura)} AS numero_fattura,
              {sql_safe(row.titolo)} AS titolo,
              {sql_safe(row.data_fattura)} AS data_fattura,
              {sql_safe(row.data_scadenza)} AS data_scadenza,
              {sql_safe(row.importo)} AS importo,
              {sql_safe(row.sigla_valuta)} AS sigla_valuta,
              {sql_safe(row.tipo_documento)} AS tipo_documento,
              {sql_safe(row.id_fornitore)} AS id_fornitore,
              {sql_safe(row.nome_fornitore)} AS nome_fornitore,
              {sql_safe(row.indirizzo_fornitore)} AS indirizzo_fornitore,
              {sql_safe(row.altro_indirizzo_fornitore)} AS altro_indirizzo_fornitore,
              {sql_safe(row.via_fornitore)} AS via_fornitore,
              {sql_safe(row.npa_fornitore)} AS npa_fornitore,
              {sql_safe(row.luogo_fornitore)} AS luogo_fornitore,
              {sql_safe(row.telefono_fornitore)} AS telefono_fornitore,
              {sql_safe(row.altro_telefono_fornitore)} AS altro_telefono_fornitore,
              {sql_safe(row.email_fornitore)} AS email_fornitore) AS S
            ON T.id_sirio = S.id_sirio AND T.numero_fattura = S.numero_fattura

            WHEN MATCHED THEN
                UPDATE SET
                    barcode_adiuto = S.barcode_adiuto,
                    titolo = S.titolo,
                    data_fattura = S.data_fattura,
                    data_scadenza = S.data_scadenza,
                    importo = S.importo,
                    sigla_valuta = S.sigla_valuta,
                    tipo_documento = S.tipo_documento,
                    id_fornitore = S.id_fornitore,
                    nome_fornitore = S.nome_fornitore,
                    indirizzo_fornitore = S.indirizzo_fornitore,
                    altro_indirizzo_fornitore = S.altro_indirizzo_fornitore,
                    via_fornitore = S.via_fornitore,
                    npa_fornitore = S.npa_fornitore,
                    luogo_fornitore = S.luogo_fornitore,
                    telefono_fornitore = S.telefono_fornitore,
                    altro_telefono_fornitore = S.altro_telefono_fornitore,
                    email_fornitore = S.email_fornitore

            WHEN NOT MATCHED THEN
                INSERT (barcode_adiuto, id_sirio, numero_fattura, titolo, data_fattura,
                        data_scadenza, importo, sigla_valuta, tipo_documento, id_fornitore,
                        nome_fornitore, indirizzo_fornitore, altro_indirizzo_fornitore,
                        via_fornitore, npa_fornitore, luogo_fornitore, telefono_fornitore,
                        altro_telefono_fornitore, email_fornitore)
                VALUES (S.barcode_adiuto, S.id_sirio, S.numero_fattura, S.titolo,
                        S.data_fattura, S.data_scadenza, S.importo, S.sigla_valuta,
                        S.tipo_documento, S.id_fornitore, S.nome_fornitore,
                        S.indirizzo_fornitore, S.altro_indirizzo_fornitore,
                        S.via_fornitore, S.npa_fornitore, S.luogo_fornitore,
                        S.telefono_fornitore, S.altro_telefono_fornitore,
                        S.email_fornitore);
            """

            # Esegui il merge
            tgt_cursor.execute(merge_sql)
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



