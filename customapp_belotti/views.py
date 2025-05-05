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
                record=UserRecord('sync_adiuto_utenti') 
                record.values['nome'] = row['F1054']
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
