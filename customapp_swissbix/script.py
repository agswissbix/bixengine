from datetime import date, datetime
import os
import subprocess
from django.http import JsonResponse
from django_q.models import Schedule, Task
from django.db import connection
import psutil, shutil

import requests
from commonapp.bixmodels.user_record import UserRecord
from commonapp.utils.email_sender import EmailSender
from commonapp.bixmodels.helper_db import *
from django.conf import settings
from commonapp.bixmodels.helper_db import HelpderDB
import xml.etree.ElementTree as ET
import json
from django.http import JsonResponse



# ritorna dei contatori (ad esempio: numero di stabili, numero di utenti, ecc.)
def monitor_timesheet_daily_count():
    """
    Conteggio del numero di record su user_timesheet durante la giornata
    """
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
    """
    Controllo delle date
    """
    type = "dates"
    result_status = 'success'
    result_value = {
        'stabili_ultimoinserimento': '2025-07-20',
    }
    return {"status": result_status, "value": result_value, "type": type}

# ritorna lo stato dei servizi, funziona per gli avvii django manage.py, e react con npm, inoltre con servizi windows
def monitor_services():
    """
    Controllo dei servizi in esecuzione Windows e dei progetti attivi
    """

    type = "services"
    result_status = 'success'
    result_value = {}

    # Servizi Windows da controllare (esatti)
    service_names = ['AdiFeed', 'Tomcat9']
    project_keywords = {
        'bixengine': ['manage.py', 'gunicorn', 'bixengine'],
        'bixportal': ['npm', 'react-scripts', 'vite']
    }



    # Controllo dei servizi Windows
    for service in service_names:
        try:
            output = subprocess.check_output(['sc', 'query', service], stderr=subprocess.DEVNULL, text=True)
            if 'RUNNING' in output:
                result_value[service] = 'Running'
            else:
                result_value[service] = 'Disabled'
        except subprocess.CalledProcessError:
            result_value[service] = 'Disabled'

    # Controllo dei progetti Django/React tramite processi attivi
    for project, keywords in project_keywords.items():
        project_running = False

        for proc in psutil.process_iter(['cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if not cmdline:
                    continue
                cmdline_str = " ".join(cmdline).lower()

                if any(keyword.lower() in cmdline_str for keyword in keywords):
                    project_running = True
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        result_value[project] = 'Running' if project_running else 'Disabled'

    # Invia il report se qualcosa è disabilitato
    disabled_items = [name for name, status in result_value.items() if status.lower() == 'disabled']
    if disabled_items:
        #da cambiare
        destinatari = ["marks.iljins@samtrevano.ch"]
        #send_report({"status": result_status,"value": result_value,"type": type}, destinatari)

    return {"status": result_status, "value": result_value, "type": type}

def move_files():
    """
    Sposta tutti i file da: C:/Adiuto/Dispatcher a: C:/Adiuto/Immission/TrashBin
    """
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
    """
    Controlla il numero di file nella cartella: C:/Adiuto/Scansioni/originali ed eventuali sottocartelle
    """

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
    """
    Sposta tutti i file dalla cartella: C:/xampp/htdocs/bixdata_view/bixdata_view/bixdata_app/attachments alla cartella: C:/Adiuto/Dispatcher
    """

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



def test_script():
    """
    Script di test
    """

    type = "counters"
    result_status = 'success'
    result_value = {"message": "Script eseguito correttamente"}

    return {"status": result_status, "value": result_value, "type": type}



def printing_katun_xml_extract_rows(request):
    folder_path_xml = os.path.join(settings.XML_DIR)
    folder_path = os.path.join(settings.MEDIA_ROOT, 'printinginvoice')  # Cartella per i file PDF
    if not os.path.exists(folder_path_xml):
        os.makedirs(folder_path_xml)
    for filename in os.listdir(folder_path_xml):
        if filename.endswith('.xml'):
            file_path = os.path.join(folder_path_xml, filename)
            filename = filename.replace('.xml', '')

            xml_check = HelpderDB.sql_query_row(f"SELECT * FROM user_printinginvoice WHERE filename='{filename}'")

            try:
                if xml_check is None:
                    printing_invoice = UserRecord('printinginvoice')
                else:
                    invoice_recordid = xml_check['recordid_']
                    printing_invoice = UserRecord('printinginvoice',invoice_recordid)

                tree = ET.parse(file_path)
                root = tree.getroot()

                invoice_rows = []
                # Cerca i nodi invoiceRow sotto invoiceRows
                invoice_rows_container = root.find('InvoiceRows')
                if invoice_rows_container is not None:
                    invoice_rows = invoice_rows_container.findall('InvoiceRow')
                
                company_name = root.find('RecipientDescription').text 
                company = HelpderDB.sql_query_row(f"SELECT * FROM user_company WHERE companyname='{company_name}'")
                if not company:
                    recordidcompany = '00000000000000000000000000000394'
                else:
                    recordidcompany = company['recordid_']

                
                printing_invoice.values['recordidcompany_'] = recordidcompany
                printing_invoice.values['title'] = company_name
                printing_invoice.values['totalnet'] = root.find('SubTotal').text
                printing_invoice.values['totalgross'] = root.find('Total').text
                printing_invoice.values['date'] = root.find('IssueDate').text
                printing_invoice.values['status'] = 'Creata'
                printing_invoice.values['katunid'] = root.find('Id').text
                printing_invoice.values['filename'] = filename


                printing_invoice.save()


                if xml_check is None:
                    invoice_recordid = printing_invoice.recordid

                    for row in invoice_rows:
                        row_data = {
                            'Description': row.find('Description').text if row.find('Description') is not None else '',
                            'Quantity': row.find('Quantity').text if row.find('Quantity') is not None else '',
                            'UnitPrice': row.find('UnitPrice').text if row.find('UnitPrice') is not None else '',
                            'Price': row.find('Price').text if row.find('Price') is not None else '',
                            'Amount': row.find('Amount').text if row.find('Amount') is not None else ''
                        }

                        invoiceline = UserRecord('printinginvoiceline')
                        invoiceline.values['recordidprintinginvoice_'] = invoice_recordid
                        invoiceline.values['description'] = row_data['Description']
                        invoiceline.values['quantity'] = row_data['Quantity']
                        invoiceline.values['unitprice'] = row_data['UnitPrice']
                        invoiceline.values['price'] = row_data['Price']
                        invoiceline.values['amount'] = row_data['Amount']

                        invoiceline.save()

                

                folder_path_updated = os.path.join(folder_path, invoice_recordid)

                pdf_file = os.path.join(folder_path_xml, filename + '.pdf')

                if os.path.exists(pdf_file):

                    if not os.path.exists(folder_path_updated):
                        os.makedirs(folder_path_updated)

                    
                    shutil.copy(pdf_file, os.path.join(folder_path_updated, 'pdfkatun.pdf'))

                    printing_invoice_update = UserRecord('printinginvoice', invoice_recordid)
                
                    printing_invoice_update.values['pdfkatun'] = 'printinginvoice/' + invoice_recordid + '/pdfkatun.pdf'

                    printing_invoice_update.save()


                             
            except ET.ParseError as e:
                print("errore")
    return JsonResponse({'status': 'success', 'message': 'Rows extracted successfully.'})

# Gets feedbacks
def get_satisfaction():
    try: 
        url = "https://www.swissbix.ch/sync/get_feedback.php"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        tableid = 'ticketfeedback'
        results = []        

        for feedback in data:
            ticketid = feedback.get("ticketid")
            level = feedback.get("level")
            comment = feedback.get("comment", "")
            technician = feedback.get("technician")
            dateinsert_str = feedback.get("dateinsert")

            try:
                dateinsert = datetime.strptime(dateinsert_str, "%Y-%m-%d")
            except:
                dateinsert = None

            # Check if record (ticket) already exists
            existing = HelpderDB.sql_query_row(
                f"SELECT id FROM user_ticketfeedback WHERE ticketid = '{ticketid}'"
            )

            if existing:
                # If record exists, update record
                recordid = existing['id']
                record = UserRecord(tableid, recordid)
                record.values['level'] = level
                record.values['comment'] = comment
                record.values['technician'] = technician
                record.values['dateinsert'] = dateinsert
                record.save()
                created = False
            else:
                # If record does not exists, create record
                new_record = UserRecord(tableid)
                new_record.values['ticketid'] = ticketid
                new_record.values['level'] = level
                new_record.values['comment'] = comment
                new_record.values['dateinsert'] = dateinsert
                new_record.save()
                created = True
            
                
        results.append({
            "ticketid": ticketid,
            "created": created,
            "level": level,
            "comment": comment,
        })

        return JsonResponse(results, safe=False)
    except requests.RequestException as e:  
        return JsonResponse({"error": "Failed to fetch external data", "details": str(e)}, status=500)