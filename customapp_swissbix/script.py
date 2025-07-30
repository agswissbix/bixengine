from datetime import datetime
import os
from django_q.models import Schedule, Task
from django.db import connection
import psutil
from commonapp.utils.email_sender import EmailSender

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

    # Lista servizi da controllare
    service_names = ['mysql', 'bixengine', 'bixadmin', 'bixspento']

    # Controlla processi in esecuzione per i servizi specifici
    for service in service_names:
        service_running = False
        for proc in psutil.process_iter(['name', 'cmdline', 'cwd']):
            try:
                name = proc.info.get('name', '').lower()
                cmdline = proc.info.get('cmdline', [])
                cmdline_str = " ".join(cmdline).lower() if isinstance(cmdline, (list, tuple)) else str(cmdline).lower()

                if service in name or service in cmdline_str:
                    service_running = True
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        result_value[service] = 'Running' if service_running else 'Disabled'

    # Se ci sono servizi Disabled, invia il report via email
    disabled_services = [srv for srv, status in result_value.items() if status.lower() == 'disabled']
    if disabled_services:
        destinatari = ["marks.iljins@samtrevano.ch"]  # Cambia con la tua lista destinatari
        send_report({"status": result_status, "value": result_value, "type": type}, destinatari)

    return {"status": result_status, "value": result_value, "type": type}


def send_report(monitoring_result, destinatari):
    # monitoring_result = {"status": ..., "value": {...}, "type": ...}
    disabled_services = [srv for srv, status in monitoring_result['value'].items() if status.lower() == 'disabled']

    if not disabled_services:
        # Nessun servizio disabilitato, non inviare nulla
        return False

    subject = "Report Servizi Disabilitati"
    servizi_lista = "\n".join(f"- {srv}" for srv in disabled_services)
    html_message = f"""
    <html>
        <body>
            <p>Attenzione, i seguenti servizi risultano <strong>DISABILITATI</strong>:</p>
            <pre>{servizi_lista}</pre>
            <p>Controlla il sistema per risolvere il problema.</p>
        </body>
    </html>
    """

    # Usa EmailSender per inviare l’email
    EmailSender.send_email(
        emails=destinatari,
        subject=subject,
        html_message=html_message,
    )
    return True


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
