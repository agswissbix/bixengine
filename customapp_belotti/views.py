from django.shortcuts import render
from rest_framework.response import Response
from django.http import JsonResponse
import pyodbc
import environ
from django.conf import settings
from commonapp.bixmodels.user_record import *
from commonapp.bixmodels.user_table import *
from commonapp.bixmodels.helper_db import *
from commonapp.helper import *

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
                sql_check = f"SELECT recordid_ FROM user_sync_adiuto_prodotti WHERE utentebixdata = '{codice}'"
                existing = HelpderDB.sql_query_value(sql_check, 'recordid_')

                if existing:
                    # Se esiste, aggiorna
                    record = UserRecord('user_sync_adiuto_prodotti', recordid=existing)
                else:
                    # Altrimenti crea un nuovo record
                    record = UserRecord('user_sync_adiuto_prodotti')

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
                    record = UserRecord('user_sync_adiuto_prodotti', recordid=existing)
                else:
                    # Altrimenti crea un nuovo record
                    record = UserRecord('user_sync_adiuto_prodotti')

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
