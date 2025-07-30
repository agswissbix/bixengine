from datetime import date, datetime
import os
from django_q.models import Schedule, Task
from django.db import connection
import psutil, shutil
from commonapp.bixmodels.user_record import UserRecord
from commonapp.utils.email_sender import EmailSender


# ritorna dei contatori (ad esempio: numero di stabili, numero di utenti, ecc.)
def monitor_timesheet_daily_count():
    type = "counters"
    result_status = "success"
    result_value = {}

    today = date.today().isoformat()  # formato 'YYYY-MM-DD'

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) 
                FROM user_timesheet 
                WHERE CAST(date AS DATE) = %s
            """, [today])

            count = cursor.fetchone()[0]
            result_value["user_timesheet_today"] = count

    except Exception as e:
        result_status = "error"
        result_value["error"] = str(e)

    return {
        "status": result_status,
        "value": result_value,
        "type": type
    }

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
    service_names = ['Tomcat9', 'bixportal', 'AdiFeed']

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

def move_files():
    dispatcher_dir = r"C:\Adiuto\Dispatcher"
    immission_dir = r"C:\Adiuto\Immission"
    trash_bin_dir = os.path.join(immission_dir, "TrashBin")

    type = "no_output"
    result_status = "success"
    result_value = {
        "moved_files": [],
        "moved_to_trash": []
    }

    if not os.path.exists(dispatcher_dir):
        return {"status": "error", "value": {"error": f"Path dispatcher non trovato: {dispatcher_dir}"}, "type": type}
    
    if not os.path.exists(immission_dir):
        return {"status": "error", "value": {"error": f"Path immission non trovato: {immission_dir}"}, "type": type}

    try:
        if not os.path.exists(trash_bin_dir):
            os.makedirs(trash_bin_dir)

        files = os.listdir(dispatcher_dir)

        for file in files:
            old_path = os.path.join(dispatcher_dir, file)
            if not os.path.isfile(old_path):
                continue  # ignora cartelle o altro

            parts = file.split('_')
            if len(parts) < 2:
                new_path = os.path.join(trash_bin_dir, file)
                shutil.move(old_path, new_path)
                result_value["moved_to_trash"].append(file)
                print(f"File '{file}' spostato in '{trash_bin_dir}'")
                continue

            folder_name = parts[0]
            new_name = "_".join(parts[1:])
            new_folder_path = os.path.join(immission_dir, folder_name)

            if not os.path.exists(new_folder_path):
                os.makedirs(new_folder_path)

            new_file_path = os.path.join(new_folder_path, new_name)
            shutil.move(old_path, new_file_path)
            result_value["moved_files"].append({"file": file, "destination": new_file_path})
            print(f"File '{file}' spostato in '{new_folder_path}' con il nuovo nome '{new_name}'.")

    except Exception as e:
        result_status = "error"
        result_value = {"error": str(e)}

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
    path = r"C:\Adiuto\Scansioni\originali"
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

def move_attachments_to_dispatcher():
    type = "no_output"
    result_status = "success"
    result_value = {}

    adiuto = 'C:\\Adiuto\\Dispatcher'
    bixdata = 'C:\\xampp\\htdocs\\bixdata_view\\bixdata_view\\bixdata_app\\attachments'

    try:
        if not os.path.exists(adiuto):
            os.makedirs(adiuto)

        if not os.path.exists(bixdata):
            result_status = "error"
            result_value["error"] = f"Path sorgente non trovato: {bixdata}"
            return {"status": result_status, "value": result_value, "type": type}

        files = os.listdir(bixdata)
        moved_files = []

        for file in files:
            source_file = os.path.join(bixdata, file)
            destination_file = os.path.join(adiuto, file)

            if os.path.isfile(source_file):
                shutil.move(source_file, destination_file)
                moved_files.append(file)

        result_value["moved_files"] = moved_files
        result_value["count"] = len(moved_files)

    except Exception as e:
        result_status = "error"
        result_value["error"] = str(e)

    return {"status": result_status, "value": result_value, "type": type}