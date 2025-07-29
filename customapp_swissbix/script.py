from datetime import datetime
import os
from django_q.models import Schedule, Task
from django.db import connection
import psutil

def script_test():
    type = None
    result_status = 'success'
    result_values = []
    return {"status": result_status, "value": result_values, "type": type}

# ritorna dei contatori (ad esempio: numero di stabili, numero di utenti, ecc.)
def monitor_counters():
    type = "counters"
    result_status = 'success'
    result_value = {
        'stabili_totale': 100,
        'stabili_giornata': 100,
    }
    return {"status": result_status, "value": result_value, "type": type}

# ritorna delle date
def monitor_dates():
    type = "dates"
    result_status = 'success'
    result_value = {
        'stabili_ultimoinserimento': '2025-07-20',
    }
    return {"status": result_status, "value": result_value, "type": type}

# ritorna lo stato dei servizi
def monitor_services():
    type = "services"
    result_status = 'success'
    result_value = {}

    # Controllo processi Django
    for proc in psutil.process_iter(['name', 'cmdline', 'cwd']):
        try:
            cmdline = proc.info.get('cmdline')
            if isinstance(cmdline, (list, tuple)):
                cmdline_str = " ".join(cmdline).lower()
            else:
                cmdline_str = str(cmdline).lower() if cmdline else ""

            if 'manage.py' in cmdline_str or 'django' in cmdline_str:
                cwd = proc.info.get('cwd')
                if cwd:
                    service_name = os.path.basename(cwd)
                else:
                    service_name = proc.info.get('name', 'unknown')

                result_value[service_name] = 'Running'

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    # Controllo servizi MySQL (puoi aggiungere altri nomi a questa lista)
    service_names = ['mysql', 'mysqld']
    for service in service_names:
        service_running = False
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] and service.lower() in proc.info['name'].lower():
                    service_running = True
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        result_value[service] = 'Running' if service_running else 'Stopped'

    # Fallback se non trova niente
    if not result_value:
        result_value = {
            'bixportal': 'Running',
            'adifeed': 'disabled',
        }

    return {"status": result_status, "value": result_value, "type": type}
# ritorna conteggi di file in delle cartelle
def monitor_folders():
    path = r"C:\Users\stagista\Documents\test file"
    type = "folders"
    result_status = 'success'
    result_value = {}

    if not os.path.exists(path):
        return {"status": "error", "value": {"error": "Path non trovato"}, "type": type}

    try:
        for current_path, dirs, files in os.walk(path):
            folder_name = os.path.basename(current_path)
            # Se siamo nella root e basename è vuoto, usa l'intero path
            if not folder_name:
                folder_name = current_path
            result_value[folder_name] = len([f for f in files if os.path.isfile(os.path.join(current_path, f))])

    except Exception as e:
        result_status = "error"
        result_value["error"] = str(e)

    return {"status": result_status, "value": result_value, "type": type}
