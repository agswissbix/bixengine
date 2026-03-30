from customapp_swissbix.custom_handlers import save_record_fields
from datetime import date, datetime
import hashlib
import hmac
import os
import pprint
import subprocess
from venv import logger
from django.http import HttpResponse, JsonResponse
from django_q.models import Schedule, Task
from django.db import connection
import psutil, shutil
from django.views.decorators.csrf import csrf_exempt

import requests
from bixsettings.models import *
from commonapp.bixmodels.user_record import UserRecord
from commonapp.utils.email_sender import EmailSender
from commonapp.bixmodels.helper_db import *
from commonapp.bixmodels.user_table import *
from django.conf import settings
from commonapp.bixmodels.helper_db import HelpderDB
import xml.etree.ElementTree as ET
import json
from django.http import JsonResponse
from bixscheduler.decorators.safe_schedule_task import safe_schedule_task

import pyodbc
from cryptography.fernet import Fernet, InvalidToken

from commonapp import views
from commonapp.helper import Helper

from customapp_swissbix.helper import HelperSwissbix

def task_monitor(data_type):
    """
    Decoratore che trasforma l'output di una funzione nel template standard.
    Gestisce automaticamente il try-except e il formato del dizionario.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)

                # Gestione di due casi: la funzione ritorna una tupla (value, log) oppure solo un singolo valore
                if isinstance(result, tuple) and len(result) == 2:
                    result_value, hidden_log = result
                else:
                    result_value = result
                    hidden_log = []

                return {
                    "status": "success",
                    "value": result_value,
                    "type": data_type,
                    "timestamp": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    "hidden_log": hidden_log
                }
            except Exception as e:
                logger.error(f"Errore nel task {data_type}: {str(e)}")
                return {
                    "status": "error",
                    "value": {"error": str(e), "message": "Esecuzione fallita"},
                    "type": data_type,
                    "timestamp": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    "hidden_log": []
                }
        return wrapper
    return decorator

@task_monitor(data_type="no_output")
@safe_schedule_task(stop_on_error=True)
@csrf_exempt
def check_deadlines(request):
    """
    Controlla le scadenze ed esegue le relative actions
    """
    actions_to_trigger = Helper.check_all_deadlines()
    for action in actions_to_trigger:
        action_name = action['action_name']
        action_params = action['action_params']
        recordid = action['recordid']
        deadline_date = action['deadline_date']
        condition_code = action['condition_code']

        if condition_code:
            if not HelperSwissbix.evaluate_condition_string(condition_code, action):
                print(f"Azione {action_name} saltata: logica '{condition_code}' non soddisfatta.")
                continue

        match action_name:
            case "email":
                send_email_deadline(recordid, action_params[0] if action_params else None)
            case "notification":
                pass
            case "custom_sb_create_task":
                deadline = UserRecord('deadline', recordid)
                deadline_user = deadline.values.get("assigned_to")

                if not deadline_user:
                    deadline_user = action_params[0] if action_params else None

                # Chiama la funzione interna _save_record_data
                views._save_record_data(
                    tableid='task', 
                    fields={
                        'creator': '1',
                        'description': 'Task automatico da scadenza', 
                        'duedate': deadline_date.strftime('%Y-%m-%d') if deadline_date else None,
                        'user': deadline_user if deadline_user else None
                    }, 
                    userid=1
                )
            case _:
                pass
    
    return {
        "status": "success",
        "value": "Scadenze controllate",
        "type": "no_output"
    }



def send_email_deadline(recordid, send_to):
    """
    Invia un'email di avviso per la scadenza.
    """
    try:
        deadline = UserRecord('deadline', recordid)

        # INFO PRINCIPALI
        descrizione = deadline.values.get("description", "")
        data_scadenza = deadline.values.get("date_deadline", "")
        status = deadline.values.get("status", "")
        
        # UTENTE / DESTINATARIO
        # Si prova a prendere l'utente assegnato, altrimenti il creatore
        user_id = deadline.values.get("assigned_to")
        creator_id = deadline.values.get("creatorid_")
        
        if send_to:
            recipient_id = send_to
        elif user_id:
             recipient_id = user_id
        else:
             recipient_id = creator_id

        recipient_email = SysUser.objects.filter(id=recipient_id).values_list("email", flat=True).first()

        if not recipient_email:
            print(f"Nessun destinatario trovato per deadline {recordid}")
            return

        #OGGETTO
        subject = f"Avviso Scadenza: {descrizione}"

        # CORPO EMAIL HTML
        link_web = "https://bixportal.dc.swissbix.ch/home"
        
        mailbody = f"""
        <p style="margin:0 0 6px 0;">Ciao,</p>

        <p style="margin:0 0 10px 0;">
            Ti ricordiamo la seguente scadenza:
        </p>

        <table style="border-collapse:collapse; width:100%; font-size:14px;">
            <tr><td style="padding:4px 0; font-weight:bold;">Descrizione:</td><td>{descrizione}</td></tr>
            <tr><td style="padding:4px 0; font-weight:bold;">Data Scadenza:</td><td>{data_scadenza}</td></tr>
            <tr><td style="padding:4px 0; font-weight:bold;">Stato:</td><td>{status}</td></tr>
        """
        
        # Aggiungi campi opzionali se presenti (es. progetto)
        project_id = deadline.values.get("recordidproject_")
        if project_id:
            project_val = deadline.fields.get("recordidproject_", {}).get("convertedvalue", "")
            mailbody += f"""
            <tr><td style="padding:4px 0; font-weight:bold;">Progetto:</td><td>{project_val}</td></tr>
            """

        mailbody += "</table>"

        mailbody += f"""
        <p style="margin:16px 0 0 0;">
            Puoi vedere maggiori informazioni accedendo alla piattaforma:
            <a href="{link_web}">{link_web}</a>
        </p>

        <p style="margin:0;">Cordiali saluti,</p>
        <p style="margin:0;">Il team</p>
        """

        email_data = {
            "to": recipient_email,
            "subject": subject,
            "text": mailbody,
            "cc": "",
            "bcc": "",
            "attachment_relativepath": "",
            "attachment_name": ""
        }

        EmailSender.save_email("deadline", recordid, email_data)
        print(f"Email inviata per deadline {recordid} a {recipient_email}")

    except Exception as e:
        print(f"Errore invio email deadline {recordid}: {str(e)}")
        logger.error(f"Errore invio email deadline {recordid}: {str(e)}")    

# ritorna dei contatori (ad esempio: numero di stabili, numero di utenti, ecc.)
@task_monitor(data_type="counters")
def monitor_timesheet_daily_count():
    """
    Conteggio del numero di record su user_timesheet durante la giornata.
    """
    today = date.today().isoformat()

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*) 
            FROM user_timesheet 
            WHERE CAST(date AS DATE) = %s
        """, [today])

        count = cursor.fetchone()[0]
        
    return {"user_timesheet_today": count, "message": "Conteggio completato con successo."}

# ritorna delle date
@task_monitor(data_type="dates")
def monitor_dates():
    """
    Controllo delle date
    """
    result_value = {
        'stabili_ultimoinserimento': '2025-07-20',
        'message': 'Controllo date eseguito con successo.'
    }
    return result_value

# ritorna lo stato dei servizi, funziona per gli avvii django manage.py, e react con npm, inoltre con servizi windows
@task_monitor(data_type="services")
def monitor_services():
    """
    Controllo dei servizi in esecuzione Windows e dei progetti attivi
    """
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
            result_value[service] = 'Running' if 'RUNNING' in output else 'Disabled'
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

    # Logica di notifica: Invia il report se qualcosa è disabilitato
    disabled_items = [name for name, status in result_value.items() if status.lower() == 'disabled']
    
    if disabled_items:
        destinatari = ["marks.iljins@samtrevano.ch"]
        # Qui potresti chiamare una funzione di invio mail
        # send_report(result_value, destinatari) 
        logger.warning(f"Servizi disabilitati rilevati: {disabled_items}")

    result_value["message"] = "Controllo servizi eseguito con successo."
    return result_value

@task_monitor(data_type="no_output")
def move_files():
    """
    Sposta tutti i file da: C:/Adiuto/Dispatcher a: C:/Adiuto/Immission/TrashBin
    """
    dispatcher_dir = r"C:\Adiuto\Dispatcher"
    immission_dir = r"C:\Adiuto\Immission"
    trash_bin_dir = os.path.join(immission_dir, "TrashBin")

    result_value = {
        "moved_files": [],
        "moved_to_trash": []
    }

    if not os.path.exists(dispatcher_dir):
        raise FileNotFoundError(f"Path dispatcher non trovato: {dispatcher_dir}")
    
    if not os.path.exists(immission_dir):
        raise FileNotFoundError(f"Path immission non trovato: {immission_dir}")

    if not os.path.exists(trash_bin_dir):
        os.makedirs(trash_bin_dir)

    # Elaborazione file
    files = os.listdir(dispatcher_dir)

    for file in files:
        old_path = os.path.join(dispatcher_dir, file)
        
        if not os.path.isfile(old_path):
            continue  # ignora cartelle

        parts = file.split('_')

        # Caso A: Meno di due parti -> Sposta nel TrashBin
        if len(parts) < 2:
            new_path = os.path.join(trash_bin_dir, file)
            shutil.move(old_path, new_path)
            result_value["moved_to_trash"].append(file)
            continue

        # Caso B: Almeno due parti (es. PROGETTO_nomefile.ext)
        folder_name = parts[0]
        new_name = "_".join(parts[1:])
        new_folder_path = os.path.join(immission_dir, folder_name)

        if not os.path.exists(new_folder_path):
            os.makedirs(new_folder_path)

        new_file_path = os.path.join(new_folder_path, new_name)
        shutil.move(old_path, new_file_path)
        
        result_value["moved_files"].append({
            "original_name": file, 
            "new_name": new_name, 
            "destination": folder_name
        })

    result_value["message"] = "Spostamento file completato con successo."
    return result_value

@task_monitor(data_type="no_output")
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

    try:
        EmailSender.send_email(
            emails=destinatari,
            subject=subject,
            html_message=html_message,
        )
        return True
    except Exception as e:
        logger.error(f"Errore invio email report: {str(e)}")
        return False

# ritorna conteggi di file in delle cartelle
@task_monitor(data_type="folders")
def monitor_folders():
    """
    Controlla il numero di file nella cartella: C:/Adiuto/Scansioni/originali ed eventuali sottocartelle
    """

    path = r"C:\Adiuto\Scansioni\originali"
    result_value = {}

    if not os.path.exists(path):
        raise FileNotFoundError(f"Path non trovato: {path}")

    for current_path, dirs, files in os.walk(path):
        # Otteniamo il nome della cartella corrente
        folder_name = os.path.basename(current_path)
        
        # Se siamo nella root e basename è vuoto (es. path radice), usa l'intero path
        if not folder_name:
            folder_name = current_path

        # Contiamo solo i file effettivi (escludendo eventuali sottocartelle dalla lista 'files')
        file_count = len([f for f in files if os.path.isfile(os.path.join(current_path, f))])
        
        # Salviamo il risultato
        result_value[folder_name] = file_count

    result_value["message"] = "Controllo cartelle eseguito con successo."
    return result_value

@task_monitor(data_type="no_output")
def move_attachments_to_dispatcher():
    """
    Sposta tutti i file dalla cartella: C:/xampp/htdocs/bixdata_view/bixdata_view/bixdata_app/attachments alla cartella: C:/Adiuto/Dispatcher
    """
    result_value = {}

    adiuto = 'C:\\Adiuto\\Dispatcher'
    bixdata = 'C:\\xampp\\htdocs\\bixdata_view\\bixdata_view\\bixdata_app\\attachments'

    if not os.path.exists(adiuto):
        os.makedirs(adiuto)

    if not os.path.exists(bixdata):
        raise FileNotFoundError(f"Path sorgente non trovato: {bixdata}")

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

    result_value["message"] = "Spostamento file eseguito con successo."
    return result_value


@task_monitor(data_type="counters")
def test_script():
    """
    Script di test
    """
    result_value = {"message": "Script eseguito correttamente"}
    return result_value

@task_monitor(data_type="counters")
def test_fail_script():
    """
    Script di test che genera un errore
    """
    raise Exception("Errore nel script di test")


#stampa trimestrale fatture printing
@task_monitor(data_type="")
def printing_katun_xml_extract_rows():
    folder_path_xml = os.path.join(settings.XML_DIR)
    folder_path = os.path.join(settings.MEDIA_ROOT, 'printinginvoice')  # Cartella per i file PDF
    if not os.path.exists(folder_path_xml):
        os.makedirs(folder_path_xml)
    for filename in os.listdir(folder_path_xml):
        if filename.endswith('.xml'):
            file_path = os.path.join(folder_path_xml, filename)
            filename = filename.replace('.xml', '')

            xml_check = HelpderDB.sql_query_row(f"SELECT * FROM user_printinginvoice WHERE filename='{filename}' AND deleted_='N'")

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
                company = HelpderDB.sql_query_row(f"SELECT * FROM user_company WHERE companyname='{company_name}' AND bexio_status='Active'")
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
    result_value = {'message': 'Rows extracted successfully.'}
    return result_value

# Gets feedbacks
@task_monitor(data_type="sync")
def get_satisfaction():
    """
    Recupera i feedback dal sito e li salva nel database.
    Ottimizzato per la visualizzazione in dashboard.
    """
    url = "https://www.swissbix.ch/sync/get_feedback.php"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        raise Exception(f"Errore connessione Feedback: {str(e)}")

    tableid = 'ticketfeedback'
    results = []        

    for feedback in data:
        ticketid = feedback.get("ticketid")
        level = feedback.get("level")
        comment = feedback.get("comment", "")
        technician = feedback.get("technician")
        dateinsert_str = feedback.get("dateinsert")

        try:
            dateinsert = datetime.datetime.strptime(dateinsert_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            dateinsert = None

        # Controllo se il record esiste già
        existing = HelpderDB.sql_query_row(
            f"SELECT id FROM user_ticketfeedback WHERE ticketid = '{ticketid}'"
        )

        if existing:
            # Aggiornamento
            recordid = existing['id']
            record = UserRecord(tableid, recordid)
            record.values['level'] = level
            record.values['comment'] = comment
            record.values['technician'] = technician
            record.values['dateinsert'] = dateinsert
            record.save()
            created = False
        else:
            # Creazione
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
            "level": level
        })

    output_per_dashboard = {
        "message": f"Script eseguito correttamente: {len(results)} feedback elaborati.",
        "summary": {
            "total": len(results),
            "created": len([r for r in results if r['created']]),
            "updated": len([r for r in results if not r['created']])
        },
        # "results": results,
        "timestamp": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    }

    return output_per_dashboard
    
@task_monitor(data_type="update")
@safe_schedule_task(stop_on_error=True)
def update_deals():
    result_message = ''
    result_log = []

    # Aggiornamento dello stato dal server di Adiuto
    driver = "SQL Server"
    server = os.environ.get('ADIUTO_DB_SERVER')
    database = os.environ.get('ADIUTO_DB_NAME')
    username =  os.environ.get('ADIUTO_DB_USER')
    password =  os.environ.get('ADIUTO_DB_PASSWORD')
    
    connection_string = f'DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password}'

    try:
        cnxn = pyodbc.connect(connection_string)
        cursor = cnxn.cursor()
        
        deal_table=UserTable('deal')
        condition_list=[]
        condition_list.append("sync_adiuto='Si'")
        condition_list.append("dealstatus='Vinta'")
        condition_list.append("dealstage IS NULL OR (dealstage!='Progetto fatturato'  and dealstage!='Invoiced')")
        condition_list.append("deleted_='N'")
        deals=deal_table.get_records(conditions_list=condition_list)
        sorted_deals = sorted(deals, key=lambda deal: deal['recordid_'])
        
        # Numero di record da aggiornare
        deals_count = len(sorted_deals)
        print(f"Trattative da aggiornare: {deals_count}")
        result_log.append(f"Trattative da aggiornare: {deals_count}")
        updated_deal_counter=0
        for deal in sorted_deals:
            print(f"{deal['id']} - {deal['dealname']}") 
            result_log.append(f"{deal['id']} - {deal['dealname']}")
            recordid_deal = deal["recordid_"]
            deal_record=UserRecord('deal', recordid_deal)
            stmt = cursor.execute(f"SELECT * FROM VA1028 WHERE F1052='{recordid_deal}' AND FENA=-1")
            rows = stmt.fetchall()
            print(f"Fetched Rows: {len(rows)}")

            for row in rows:
                if not row:
                    continue

                updated_status = row.F1033
                project = row.F1162
                tech_adiutoid = row.F1067
                deal_record.values['adiuto_tech'] = tech_adiutoid
                
                bixdata_tech = None
                if tech_adiutoid is not None:
                    bixdata_tech = HelpderDB.sql_query_row(f"SELECT * FROM sys_user WHERE adiutoid='{tech_adiutoid}'")

                if (bixdata_tech):
                    deal_record.values['project_assignedto'] = bixdata_tech["id"]

                deal_record.values["dealstage"] = updated_status

                if ((updated_status == "Progetto in corso") or (updated_status == "Ordine materiale")): 
                    deal_record.values["sync_project"] = "Si"
                
                deal_record.save()
                print(updated_status)

            # Aggiornamento dealline
            print("Righe dettaglio: ")
            result_log.append("Righe dettaglio: ")
            
            deal_lines_table=UserTable('dealline')
            condition_list=[]
            condition_list.append(f"recordiddeal_='{recordid_deal}' AND deleted_='N'")
            deal_lines=deal_lines_table.get_records(conditions_list=condition_list)
            
            for deal_line in deal_lines:
                recordid_dealline = deal_line['recordid_']
                dealline_record=UserRecord('dealline', recordid_dealline)
                dealline_name = deal_line['name']
                print(dealline_name)
                result_log.append(dealline_name)

                stmt = cursor.execute(f"SELECT * FROM VA1029 WHERE F1062='{recordid_dealline}' AND FENA=-1")
                rows = stmt.fetchall()

                for row in rows:
                    if not row:
                        continue

                    dealline_uniteffectivecost = row.F1043
                    dealline_record.values['uniteffectivecost'] = dealline_uniteffectivecost
                    dealline_record.save()
                    print("dealline updated")
                    result_log.append("dealline updated")

            save_record_fields('deal', recordid_deal)
            updated_deal_counter += 1
            result_log.append(f"Aggiornata: {deal.get('dealname', recordid_deal)}")

    except Exception as e:
        result_message = f"Errore durante la sincronizzazione: {str(e)}"
        result_log.append(result_message)
        print(result_message)
        raise Exception(result_message)

    finally:
        cnxn.close()

        return {
            "updated_count": updated_deal_counter,
            "message": f"Sincronizzazione completata: {updated_deal_counter} trattative",
        }, {
            "details": "\n".join([str(item) for item in result_log])
        }



@task_monitor(data_type="sync")
def sync_freshdesk_tickets(request):
    api_key = os.environ.get('FRESHDESK_APIKEY')
    password = "x"

    url = f"https://swissbix.freshdesk.com/api/v2/tickets?include=requester,description,stats&updated_since=2025-01-01&per_page=10"

    response = requests.get(url, auth=(api_key, password))

    headers = response.headers
    response = json.loads(response.text)

    updated_tickets = 0
    new_tickets = 0

    for ticket in response:
        field = HelpderDB.sql_query_row(f"select * from user_freshdesk_tickets WHERE ticket_id='{ticket['id']}'")
        if not field:
            new_record = UserRecord('freshdesk_tickets')
            new_record.values['ticket_id'] = ticket['id']
            new_record.values['subject'] = ticket['subject']
            new_record.values['description'] = ticket['description_text']
            new_record.values['created_at'] = ticket['created_at']
            new_record.values['closed_at'] = ticket['stats']['closed_at']
            new_record.values['requester_id'] = ticket['requester']['id']
            new_record.values['requester_name'] = ticket['requester']['name']
            new_record.values['requester_email'] = ticket['requester']['email']
            new_record.values['responder_id'] = ticket['responder_id']
            new_record.values['status'] = ticket['status']

            new_record.save()
            new_tickets += 1
        else:
            record = UserRecord('freshdesk_tickets', field['recordid_'])
            record.values['subject'] = ticket['subject']
            record.values['description'] = ticket['description_text']
            record.values['closed_at'] = ticket['stats']['closed_at']
            record.values['status'] = ticket['status']
            record.values['responder_id'] = ticket['responder_id']
            record.save()
            updated_tickets += 1


    return {"message": "Sincronizzazione freshdesk tickets completata", "updated_tickets": updated_tickets, "new_tickets": new_tickets}

@task_monitor(data_type="sync")
def sync_bexio_contacts():
    url = "https://api.bexio.com/2.0/contact?order_by=id_desc&limit=10&offset=0"
    accesstoken=os.environ.get('BEXIO_ACCESSTOKEN')
    headers = {
        'Accept': "application/json",
        'Content-Type': "application/json",
        'Authorization': f"Bearer {accesstoken}",
    }

    response = requests.request("GET", url, headers=headers)
    response = json.loads(response.text)
    updated_contacts = 0
    new_contacts = 0

    for contact in response:
        print(f"Syncing contact: {contact['name_1']} Bexio nr: {contact['nr']}")
        field = HelpderDB.sql_query_row(f"select * from user_bexio_contact WHERE bexio_id='{contact['id']}'")
        if not field:
            record = UserRecord("bexio_contact")
            new_contacts += 1

        else:
            record = UserRecord("bexio_contact", field['recordid_'])
            updated_contacts += 1
        record.values['bexio_id'] = contact['id']
        record.values['nr'] = contact['nr']
        record.values['contact_type_id'] = contact['contact_type_id']
        record.values['name_1'] = contact['name_1']
        record.values['name_2'] = contact['name_2']
        record.values['address'] = contact['address']
        record.values['postcode'] = contact['postcode']
        record.values['city'] = contact['city']
        record.values['country_id'] = contact['country_id']
        record.values['mail'] = contact['mail']
        record.values['mail_second'] = contact['mail_second']
        record.values['phone_fixed'] = contact['phone_fixed']
        record.values['phone_mobile'] = contact['phone_mobile']
        record.values['contact_group_ids'] = contact['contact_group_ids']
        record.values['contact_branch_ids'] = contact['contact_branch_ids']
        record.values['user_id'] = contact['user_id']
        record.values['owner_id'] = contact['owner_id']
        # record.fields['status'] = contact['status']: Status field does not exists in contact

        record.save()

    return {"message": "Sincronizzazione bexio contacts completata", "updated_contacts": updated_contacts, "new_contacts": new_contacts}

@task_monitor(data_type="sync")
def sync_bexio_orders():
    sql="DELETE FROM user_bexio_orders"
    HelpderDB.sql_execute(sql)
    sql="DELETE FROM user_bexio_positions"
    HelpderDB.sql_execute(sql)
    url = "https://api.bexio.com/2.0/kb_order/search/?order_by=id_desc&limit=2000&offset=0"
    accesstoken=os.environ.get('BEXIO_ACCESSTOKEN')
    headers = {
        'Accept': "application/json",
        'Content-Type': "application/json",
        'Authorization': f"Bearer {accesstoken}",
    }

    payload = """
    [
        {
            "field": "kb_item_status_id",
            "value": "5",
            "criteria": "="
        }
    ]
    """

    response = requests.request("POST", url, data=payload, headers=headers)
    response = json.loads(response.text)

    counter = 0
    total_orders = len(response)  # Calcola il numero totale di ordini da elaborare

    for order in response:
        counter += 1
        
        # Stampa l'avanzamento (Esempio: "Elaborazione ordine 5 di 20: Titolo - Nome Ordine")
        print(f"Elaborazione ordine {counter} di {total_orders}: Titolo - {order['title']} Bexio id: {order['id']}")
        
        field = HelpderDB.sql_query_row(f"select * from user_bexio_orders WHERE bexio_id='{order['id']}'")
        if not field:
            record = UserRecord("bexio_orders")

        else:
            record = UserRecord("bexio_orders", field['recordid_'])


        record.values['status'] = "In Progress"
        record.values['bexio_id'] = order['id']
        record.values['document_nr'] = order['document_nr']
        record.values['title'] = order['title']
        record.values['contact_id'] = order['contact_id']
        record.values['user_id'] = order['user_id']
        record.values['total_gross'] = order['total_gross']
        record.values['total_net'] = order['total_net']
        record.values['total_taxes'] = order['total_taxes']
        record.values['total'] = order['total']
        record.values['is_valid_from'] = order['is_valid_from']
        record.values['contact_address'] = order['contact_address']
        record.values['delivery_address'] = order['delivery_address']
        record.values['is_recurring'] = order['is_recurring']

        if order['is_recurring']=='true' or order['is_recurring'] == True:

            url = f"https://api.bexio.com/2.0/kb_order/{order['id']}/repetition"
            accesstoken=os.environ.get('BEXIO_ACCESSTOKEN')
            headers = {
                'Accept': "application/json",
                'Content-Type': "application/json",
                'Authorization': f"Bearer {accesstoken}",
            }


            response = requests.request("GET", url, headers=headers)
            repetition_response = json.loads(response.text)
            record.values['repetition_start']=repetition_response.get("start", "")
            record.values['repetition_end']=repetition_response.get("end", "")
            repetition=repetition_response['repetition']
            
            record.values['repetition_type']=repetition['type']
            record.values['repetition_interval']=repetition['interval']
            
            
            


        #order_taxs = order['taxs']
        #if order_taxs and len(order_taxs) > 0:
        #   record.values['taxs_percentage'] = order_taxs[0]['percentage']
        #  record.values['taxs_value'] = order_taxs[0]['value']

        record.save()

        sync_bexio_positions('kb_order', order['id'])

    return {"message": "Sincronizzazione bexio orders completata", "total_orders": total_orders}

def sync_bexio_positions_example(request, bexioid):
    return sync_bexio_positions(request,'kb_order',bexioid)

@task_monitor(data_type="sync")
def sync_bexio_positions(bexiotable,bexio_parent_id):
    url = f"https://api.bexio.com/2.0/{bexiotable}/{bexio_parent_id}/kb_position_custom"
    accesstoken=os.environ.get('BEXIO_ACCESSTOKEN')
    headers = {
        'Accept': "application/json",
        'Content-Type': "application/json",
        'Authorization': f"Bearer {accesstoken}",
    }

    response = requests.request("GET", url, headers=headers)
    response = json.loads(response.text)

    for position in response:
        print(f"Elaborazione riga ordine con bexioid:{bexio_parent_id}: {position['text']}")
        field = HelpderDB.sql_query_row(f"select * from user_bexio_positions WHERE bexio_id='{position['id']}'")
        if not field:
            record = UserRecord("bexio_positions")
        else:
            record = UserRecord("bexio_positions", field['recordid_'])


        if bexiotable == 'kb_order':
            type='order'
        else:
            type='invoice'

        record.values['status'] = "In Progress"
        record.values['bexio_id'] = position['id']
        record.values['type'] = type
        record.values['amount'] = position['amount']
        record.values['unit_id'] = position['unit_id']
        record.values['account_id'] = position['account_id']
        record.values['unit_name'] = position['unit_name']
        record.values['tax_id'] = position['tax_id']
        record.values['tax_value'] = position['tax_value']
        record.values['text'] = position['text']
        record.values['unit_price'] = position['unit_price']
        record.values['discount_in_percent'] = position['discount_in_percent']
        record.values['position_total'] = position['position_total']
        record.values['pos'] = position['pos']
        record.values['internal_pos'] = position['internal_pos']
        record.values['parent_id'] = bexio_parent_id
        record.values['is_optional'] = position['is_optional']

        record.save()

    return {"message": f"Sincronizzazione bexio positions per {bexiotable} id {bexio_parent_id} completata", "total_positions": len(response)}

@task_monitor(data_type="sync")
def sync_bexio_invoices(request):
    url = "https://api.bexio.com/2.0/kb_invoice?order_by=id_desc&limit=10&offset=0"
    accesstoken=os.environ.get('BEXIO_ACCESSTOKEN')
    headers = {
        'Accept': "application/json",
        'Content-Type': "application/json",
        'Authorization': f"Bearer {accesstoken}",
    }

    response = requests.request("GET", url, headers=headers)
    response = json.loads(response.text)

    new_invoices = 0
    updated_invoices = 0


    for invoice in response:
        field = HelpderDB.sql_query_row(f"select * from user_bexio_invoices WHERE bexio_id='{invoice['id']}'")
        if not field:
            record = UserRecord("bexio_invoices")
            new_invoices += 1
        else:
            record = UserRecord("bexio_invoices", field['recordid_'])
            updated_invoices += 1

        record.values['bexio_id'] = invoice['id']
        record.values['document_nr'] = invoice['document_nr']
        record.values['title'] = invoice['title']
        record.values['contact_id'] = invoice['contact_id']
        record.values['user_id'] = invoice['user_id']
        record.values['total_gross'] = invoice['total_gross']
        record.values['total_net'] = invoice['total_net']
        record.values['total_taxes'] = invoice['total_taxes']
        record.values['total_received_payments'] = invoice['total_received_payments']
        record.values['total_remaining_payments'] = invoice['total_remaining_payments']
        record.values['total'] = invoice['total']
        record.values['is_valid_from'] = invoice['is_valid_from']
        record.values['is_valid_to'] = invoice['is_valid_to']
        record.values['contact_address'] = invoice['contact_address']

        record.save()

        sync_bexio_positions(request, 'kb_invoice', invoice['id'])


    return {"message": "Sincronizzazione bexio invoices completata", "new_invoices": new_invoices, "updated_invoices": updated_invoices}

def sync_contacts(request):
    return syncdata(request,'company')

# DO NOT EXECUTE
@task_monitor(data_type="sync")
def syncdata(request, tableid):
    sql_table = f"SELECT * FROM sys_table WHERE id='{tableid}'"
    sys_table_rows = HelpderDB.sql_query(sql_table)
    
    if not sys_table_rows:
        return HttpResponse(f"Errore: Configurazione per {tableid} non trovata", status=404)
        
    config = sys_table_rows[0]
    
    sync_table_name = config.get('sync_table') 
    sync_key_source = config.get('sync_field') 
    sync_condition = config.get('sync_condition')
    sync_order = config.get('sync_order')

    if sync_table_name == "user_bexio_contacts":
        sync_table_name = "user_bexio_contact"

    dest_table_name = tableid 

    sql_fields = f"SELECT sync_fieldid, fieldid FROM sys_field WHERE tableid='{tableid}' AND sync_fieldid IS NOT NULL AND sync_fieldid <> ''"
    field_rows = HelpderDB.sql_query(sql_fields)

    mapping_map = {row['sync_fieldid']: row['fieldid'] for row in field_rows}
    
    sync_key_dest = mapping_map.get(sync_key_source)

    if not sync_key_dest:
        return HttpResponse(f"Errore: Il campo chiave '{sync_key_source}' non è mappato in sys_field.", status=400)

    condition = sync_condition if sync_condition else '1=1'
    order_clause = f"ORDER BY {sync_order}" if sync_order else ''
    
    source_sql = f"SELECT * FROM {sync_table_name} WHERE {condition} {order_clause}"
    source_rows = HelpderDB.sql_query(source_sql)

    records_created = 0
    records_updated = 0

    for source_row in source_rows:
        raw_key_value = source_row.get(sync_key_source)
        
        if not raw_key_value:
            continue 

        key_value_escaped = str(raw_key_value).replace("'", "''")

        check_sql = f"SELECT * FROM user_{dest_table_name} WHERE {sync_key_dest} = '{key_value_escaped}'"
        existing_match = HelpderDB.sql_query(check_sql)

        if existing_match:
            row_match = existing_match[0]
            if 'recordid_' in row_match:
                recordid_value = row_match['recordid_']
                record = UserRecord(dest_table_name, recordid_value)
                print(f"Aggiornamento record esistente: {dest_table_name} - {recordid_value}")
                records_updated += 1
            else:
                print(f"ERRORE: Record trovato ma colonna 'recordid_' mancante per tabella {dest_table_name}")
                continue 
        else:
            record = UserRecord(dest_table_name)
            print(f"Creazione nuovo record: {dest_table_name}")
            records_created += 1

        for src_col, src_val in source_row.items():
            if src_col in mapping_map:
                dest_col = mapping_map[src_col]
                record.values[dest_col] = src_val
        
        record.save()

    return {"message": f"Sync completato: {records_created} inseriti, {records_updated} aggiornati."}

@task_monitor(data_type="logs")
def get_scheduler_logs(request):
    monitor_values = {}

    url = os.environ.get('SCHEDULER_LOGS_URL')
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()

    formato = "%Y-%m-%d %H:%M:%S"

    key = os.environ.get('LOGS_ENCRYPTION_KEY')
    f = Fernet(key)

    for log in data:
        id = log.get("id")

        oggetto_datetime = datetime.datetime.strptime(log.get('date'), formato)
        date = oggetto_datetime.date()
        ora = oggetto_datetime.time()

        funzione_criptata = log.get('function')
        funzione = f.decrypt(funzione_criptata.encode())

        cliente_criptato = log.get('client')
        cliente = f.decrypt(cliente_criptato.encode())

        output_criptato = log.get('output')
        output = f.decrypt(output_criptato.encode())

        numero_chiamate = log.get('calls_number')

        monitoring_table=UserTable('monitoring')
        condition_list=[]
        condition_list.append(f"id={id}")
        field=monitoring_table.get_records(conditions_list=condition_list)

        if not field:
            new_record = UserRecord('monitoring') 
            new_record.values['id'] = id
            new_record.values['data'] = date
            new_record.values['ora'] = ora
            new_record.values['funzione'] = funzione
            new_record.values['client_id'] = cliente
            new_record.values['output'] = output
            new_record.values['calls_counter'] = numero_chiamate

            # new_record.save()
        else:
            record = UserRecord('monitoring', id) 
            record.values['id'] = id
            record.values['data'] = date
            record.values['ora'] = ora
            record.values['funzione'] = funzione
            record.values['client_id'] = cliente
            record.values['output'] = output
            record.values['calls_counter'] = numero_chiamate

            # record.save()

    monitor_values["message"] = "Logs sincronizzati correttamente"
    monitor_values["data"] = data

    return monitor_values
    
@task_monitor(data_type="sync")
def sync_graph_calendar_task(request):
    """
    Coordinatore della sincronizzazione: decide se eseguire 
    la sincronizzazione iniziale o quella delta.
    """
    print("Function: sync_graph_calendar_task")

    # Verifica se il database locale è vuoto
    is_empty = not UserEvents.objects.all().exists()

    if is_empty:
        print("-> Database vuoto: Avvio Sincronizzazione Iniziale")
        # Chiamata alla funzione (che ora deve restituire un dict)
        result = views.initial_graph_calendar_sync(request)
    else:
        print(f"-> Eventi presenti: Avvio Sincronizzazione Delta")
        # Chiamata alla funzione (che ora deve restituire un dict)
        result = views.sync_graph_calendar(request)

    try:
        data = json.loads(result.content.decode('utf-8'))
    except Exception as e:
        raise Exception(f"Impossibile decodificare la risposta della funzione: {str(e)}")

    if result.status_code >= 400 or data.get('success') is False:
        error_msg = data.get('detail') or data.get('error') or "Errore sconosciuto nella sincronizzazione"
        raise Exception(error_msg)

    return data
    
@task_monitor(data_type="sync")
def sync_tables(request):
    """
    Sincronizza dinamicamente le tabelle definite in sys_table.
    """
    print("Function: sync_tables")
    sync_summary = []

    try:
        # Recupero tabelle da sincronizzare
        tables = HelpderDB.sql_query("SELECT * FROM sys_table WHERE sync_table IS NOT NULL")
        
        if not tables:
            return "Nessuna tabella configurata per la sincronizzazione."

        for table in tables:
            table_id = table['id']
            sync_table_name = table['sync_table']
            print(f"Starting sync of table: {sync_table_name}")
            
            # Recupero mappatura colonne
            columns = HelpderDB.sql_query(
                f"SELECT * FROM sys_field WHERE tableid='{table_id}' "
                f"AND sync_fieldid IS NOT NULL AND sync_fieldid != ''"
            )

            sync_fieldid = table['sync_field']
            founded_fieldid = [c for c in columns if c.get('sync_fieldid') == sync_fieldid]
            
            if not founded_fieldid:
                print(f"Skipping {sync_table_name}: sync_field non trovato.")
                continue
                
            fieldid = founded_fieldid[0]['fieldid']

            # Costruzione query sorgente
            query = f"SELECT * FROM {sync_table_name}"
            if table['sync_condition']:
                query += f" WHERE {table['sync_condition']}"
            if table['sync_order']:
                query += f" ORDER BY {table['sync_order']}"

            data = HelpderDB.sql_query(query)
            
            records_updated = 0
            records_created = 0

            for row in data:
                external_id = row[sync_fieldid]
                
                # Controllo esistenza locale
                existing_record = HelpderDB.sql_query_row(
                    f"SELECT recordid_ FROM user_{table_id} WHERE {fieldid}='{external_id}'"
                )

                if existing_record:
                    record = UserRecord(table_id, existing_record['recordid_'])
                    records_updated += 1
                else:
                    record = UserRecord(table_id)
                    records_created += 1

                # Mappatura campi
                for column in columns:
                    src_col = column['sync_fieldid']
                    dst_col = column['fieldid']
                    if src_col in row:
                        record.values[dst_col] = row[src_col]
                
                record.save()
            
            sync_summary.append({
                "message": f"Sync completed for {sync_table_name}",
                "table": sync_table_name,
                "created": records_created,
                "updated": records_updated
            })
            print(f"Sync completed for {sync_table_name}")

        return sync_summary

    except Exception as e:
        raise Exception(f"Errore durante la sincronizzazione tabelle: {str(e)}")

@task_monitor(data_type="sync")
def sync_table(tableid):
    '''
    Sincronizza una singola tabella identificata da tableid
    '''
    print("sync_tables")

    if not tableid:
            return "Missing parameter"
    try:
        table = HelpderDB.sql_query_row(f"SELECT * FROM sys_table WHERE sync_table IS NOT NULL AND id = '{tableid}'")

        if not table:
            return "Table not found"

        print("Starting sync of table: " + table['sync_table'])
        columns = HelpderDB.sql_query(f"SELECT * FROM sys_field WHERE tableid='{table['id']}' AND sync_fieldid IS NOT NULL AND sync_fieldid != ''")

        sync_fieldid_origin = table['sync_field']
        founded_fieldid = [c for c in columns if c.get('sync_fieldid') == sync_fieldid_origin]
        if not founded_fieldid:
            return "Missing sync_fieldid"
        sync_fieldid_target = founded_fieldid[0]['fieldid']

        query = f"SELECT * from {table['sync_table']}"
        condition = table['sync_condition']
        order = table['sync_order']

        if condition:
            query += f" WHERE {condition}"

        if order:
            query += f" ORDER BY {order}"

        data = HelpderDB.sql_query(query)

        # --- INIZIO MODIFICHE ---
        
        # Ottieni il numero totale di righe
        total_rows = len(data)
        print(f"**Found {total_rows} total rows to process from {table['sync_table']}**")

        # Usa enumerate per ottenere l'indice (i) e la riga (row)
        # start=1 fa partire il conteggio da 1 invece che da 0
        for i, row in enumerate(data, start=1):
            
            # Stampa il feedback di avanzamento
            print(f"**Processing row {i}/{total_rows}...**")
            
            sync_value = row[sync_fieldid_origin]
            
            record_target = HelpderDB.sql_query_row(f"SELECT * FROM user_{table['id']} WHERE {sync_fieldid_target}='{sync_value}'")

            if record_target:
                # Modificato il print per maggiore chiarezza
                print(f"  -> Updating record (ID: {id})")
                record = UserRecord(table['id'], record_target['recordid_'])

                for column in columns:
                    if column['sync_fieldid'] in row:
                        record.values[column['fieldid']] = row[column['sync_fieldid']]
                    else:
                        print("Missing column: " + column['sync_fieldid'])

                record.save()
            else:
                # Modificato il print per maggiore chiarezza
                print(f"  -> Creating record (Sync value: {sync_value})")
                new_record = UserRecord(table['id'])

                for column in columns:
                    if column['sync_fieldid'] in row:
                        new_record.values[column['fieldid']] = row[column['sync_fieldid']]
                    else:
                        print("Missing column: " + column['sync_fieldid'])
                
                new_record.save()
        
        # --- FINE MODIFICHE ---

        print("Sync completed of table: " + table['sync_table'])

        print("Syncronization completed")
        return "Sync completed for " + table['sync_table']
    except requests.RequestException as e:  
        return "Failed to fetch external data" + str(e)
    
@task_monitor(data_type="sync")
def sync_bixdata_salesorders():
    print("sync_salesorders")
    sync_output = sync_table('salesorder')
    sync_output = sync_table('salesorderline')
    
    sql="UPDATE user_salesorder SET status='Complete'"
    HelpderDB.sql_execute(sql)
    sql="UPDATE user_salesorderline SET status='Complete'"
    HelpderDB.sql_execute(sql)

    #esecuzione sync_table
    


    #aggiornamento stato ordini in progress
    sql="UPDATE user_salesorder JOIN user_bexio_orders ON user_salesorder.id_bexio=user_bexio_orders.bexio_id SET user_salesorder.status='In Progress'"
    HelpderDB.sql_execute(sql)

    #aggiornamento stato righe in progress
    sql="UPDATE user_salesorderline JOIN user_bexio_positions ON user_salesorderline.id_bexio=user_bexio_positions.bexio_id SET user_salesorderline.status='In Progress'"
    HelpderDB.sql_execute(sql)

    #aggiornamento company in salesorder
    sql="UPDATE user_salesorder JOIN user_company ON user_salesorder.id_bexio_company=user_company.id_bexio SET user_salesorder.recordidcompany_=user_company.recordid_"
    HelpderDB.sql_execute(sql)

    #aggiornamento  righe ordini 
    sql="UPDATE user_salesorderline JOIN user_bexio_orders ON user_salesorderline.id_bexio_order=user_bexio_orders.bexio_id SET user_salesorderline.bexio_repetition_type=user_bexio_orders.repetition_type,user_salesorderline.bexio_repetition_interval=user_bexio_orders.repetition_interval "
    HelpderDB.sql_execute(sql)

    # aggiornamento conti nr conti
    sql="UPDATE user_salesorderline JOIN user_bexio_account ON user_salesorderline.bexio_account_id=user_bexio_account.account_id SET user_salesorderline.account_no=user_bexio_account.account_no,user_salesorderline.account=user_bexio_account.name "
    HelpderDB.sql_execute(sql)

    #LINK TABLES
    #linked salesorderline-salesorder e salesorder-company
    sql="UPDATE user_salesorderline JOIN user_salesorder ON user_salesorderline.id_bexio_order=user_salesorder.id_bexio SET user_salesorderline.recordidsalesorder_=user_salesorder.recordid_, user_salesorderline.recordidcompany_=user_salesorder.recordidcompany_"
    HelpderDB.sql_execute(sql)

    sql="UPDATE user_salesorderline JOIN user_salesorder ON user_salesorderline.id_bexio_order=user_salesorder.id_bexio SET user_salesorderline.recordidsalesorder_=user_salesorder.recordid_"
    HelpderDB.sql_execute(sql)

   
    
    return {"message": "Sincronizzazione salesorder completata"}


@task_monitor(data_type="sync")
def sync_servicecontract():
    print("sync_servicecontract")
    sync_output = sync_table('servicecontract')
    return {"message": "Sincronizzazione servicecontract completata"}


    
@task_monitor(data_type="logs")
def get_monitoring():
    try:
        clientid = Helper.get_cliente_id()
        
        timestamp = str(int(time.time()))

        string_to_sign = f"clientid={clientid}&timestamp={timestamp}"
        
        hmac_key_str = os.environ.get("HMAC_KEY")
        if not hmac_key_str:
            return JsonResponse({"error": "HMAC Key missing"}, status=500)
            
        hmac_key = hmac_key_str.encode()
        signature = hmac.new(hmac_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

        url = f"https://bixdata.swissbix.com/get_monitoring.php?{string_to_sign}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'X-Signature': signature
        }
    
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        data = response.json()

        key = os.environ.get('LOGS_ENCRYPTION_KEY')
        if not key: return JsonResponse({"error": "Key missing"}, status=500)
        f = Fernet(key)

        def safe_decrypt(encrypted_val):
            if not encrypted_val: return ""
            try: return f.decrypt(encrypted_val.encode('utf-8')).decode('utf-8')
            except: return ""

        count = 0
        for item in data:
            dec_clientid = safe_decrypt(item.get("clientid"))
            dec_date = safe_decrypt(item.get("date"))
            dec_hour = safe_decrypt(item.get("hour"))
            dec_name = safe_decrypt(item.get("name"))
            dec_function = safe_decrypt(item.get("function"))

            mon_id = item.get("id")

            sql = f"SELECT recordid_ FROM user_monitoring WHERE clientid='{dec_clientid}' AND function='{dec_function}'"
            exists = HelpderDB.sql_query_row(sql)

            rec = None
            if exists:
                rec = UserRecord('monitoring', exists['recordid_'])
            else:
                rec = UserRecord('monitoring')

            rec.values['clientid'] = dec_clientid
            rec.values['date'] = dec_date
            rec.values['hour'] = dec_hour
            rec.values['name'] = dec_name
            rec.values['function'] = dec_function
            
            rec.values['scheduleid'] = safe_decrypt(item.get("scheduleid"))
            rec.values['status'] = safe_decrypt(item.get("status"))
            rec.values['monitoring_output'] = safe_decrypt(item.get("monitoring_output"))

            rec.save()
            count += 1
   
        result_value = {'message': 'Rows extracted successfully.', 'processed': count}
        print(result_value)
        return result_value

    except Exception as e:
        result_message = f"Errore durante la sincronizzazione: {str(e)}"
        print(result_message)
        raise Exception(result_message)

@task_monitor(data_type="sync")  
def sync_monitoring():
    """Invia i dati a Plesk e forza l'unione tramite log_hash."""
    try: 
        hmac_key_str = os.environ.get("HMAC_KEY")
        encryption_key = os.environ.get("LOGS_ENCRYPTION_KEY")
        endpoint_url = os.environ.get("MONITORING_SYNC_ENDPOINT_URL")

        if not hmac_key_str or not encryption_key or not endpoint_url:
            return JsonResponse({"error": "Variabili d'ambiente mancanti"}, status=500)

        hmac_key = hmac_key_str.encode()
        fernet = Fernet(encryption_key)

        data = UserTable('monitoring').get_records(conditions_list=[])
        clientid = Helper.get_cliente_id()
        payload = []

        for job in data:
            raw_function = str(job.get('function'))
            raw_recordid = str(job.get('recordid_') or '')
            raw_clientid = str(clientid or '')
            
            hashing_string = f"{raw_clientid}|{raw_function}"
            unique_hash = hmac.new(hmac_key, hashing_string.encode(), hashlib.sha256).hexdigest()

            def enc(val):
                return fernet.encrypt(str(val or '').encode()).decode()

            job_dict = {
                "log_hash": unique_hash,
                'recordid_': enc(raw_recordid),
                'clientid': enc(raw_clientid),
                'scheduleid': enc(job.get('scheduleid')),
                'date': enc(job.get('date')),
                'hour': enc(job.get('hour')),
                'name': enc(job.get('name')),
                'function': enc(raw_function),
                'status': enc(job.get('status')),
                'monitoring_output': enc(job.get('monitoring_output'))
            }
            payload.append(job_dict)

        payload_as_string = json.dumps(payload)
        signature = hmac.new(hmac_key, payload_as_string.encode("utf-8"), hashlib.sha256).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-Signature": signature,
        }

        response = requests.post(endpoint_url, data=payload_as_string, headers=headers, timeout=20)
        response.raise_for_status()

        return {"message": "Sincronizzazione completata con successo", "inviati": len(payload)}
        
    except Exception as e:
        raise Exception(f"Errore durante la sincronizzazione: {str(e)}")
    
def encrypt_data(fernet_instance, plaintext):
    """Cifra una stringa con Fernet. Gestisce None e altri tipi."""
    
    if plaintext is None:
        plaintext = ""
        
    if not isinstance(plaintext, str):
        plaintext = str(plaintext)

    return fernet_instance.encrypt(plaintext.encode("utf-8")).decode("utf-8")

@csrf_exempt
def sync_job_status(request):
    print("sync_job_status")

    try: 
        payload = []

        hmac_key_str = os.environ.get("HMAC_KEY")
        encryption_key = os.environ.get("LOGS_ENCRYPTION_KEY")
        endpoint_url = os.environ.get("SYNC_JOB_STATUS_ENDPOINT_URL")

        if not hmac_key_str or not encryption_key or not endpoint_url:
            return JsonResponse({"error": "Missing environment variables"}, status=500)

        hmac_key = hmac_key_str.encode()
        fernet = Fernet(encryption_key)

        data = UserTable('job_status').get_records(conditions_list=[])

        for job in data:
            hashing_string = f"{job['recordid_']}"

            job_dict = {
                "log_hash": hmac.new(hmac_key, hashing_string.encode(), hashlib.sha256).hexdigest(),
                'recordid_': encrypt_data(fernet, job['recordid_']),
                'id': encrypt_data(fernet, job['id']),
                'description': encrypt_data(fernet, job['description']),
                'source': encrypt_data(fernet, job['source']),
                'sourcenote': encrypt_data(fernet, job['sourcenote']),
                'status': encrypt_data(fernet, job['status']),
                'creationdate': encrypt_data(fernet, str(job['creationdate'])),
                'closedate': encrypt_data(fernet, str(job['closedate']  if job['closedate'] else "")),
                'technote': encrypt_data(fernet, job['technote']),
                'context': encrypt_data(fernet, job['context']),
                'title': encrypt_data(fernet, job['title']),
                'file': encrypt_data(fernet, job['file']),
                'clientid': encrypt_data(fernet, job['clientid']),
                'duration': encrypt_data(fernet, job['duration']),
                'reporter': encrypt_data(fernet, job['reporter']),
                'type': encrypt_data(fernet, job['type'])
            }
            payload.append(job_dict)

        try:
            payload_as_string = json.dumps(payload)
        except TypeError as e:
            for k, v in payload.items():
                print(f"{k}: {type(v)} → {v}")
            raise
        signature = hmac.new(hmac_key, payload_as_string.encode("utf-8"), hashlib.sha256).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-Signature": signature,
        }

        response = requests.post(endpoint_url, data=payload_as_string, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        logger.info("Job status sync completed successfully.")

        return JsonResponse(data, safe=False)
    except requests.RequestException as e:  
        return JsonResponse({"error": "Failed to fetch external data", "details": str(e)}, status=500)
    
def get_timesheets_to_invoice(request):
    print("get_timesheets_to_invoice")

    try:
        bexio_accounts = UserTable('bexio_account').get_records(conditions_list=["servicecontract_service IS NOT NULL"])

        condition_list = []
        condition_list.append("invoicestatus='To Invoice'")
        condition_list.append("validated='Si'")
        ts = UserTable('timesheet').get_records(conditions_list=condition_list)

        timesheets = []

        for timesheet in ts:
            company_record = UserRecord('company', timesheet['recordidcompany_'])
            company_name = company_record.values.get('companyname', '') if company_record else ''

            user = SysUser.objects.get(id=timesheet['user'])
            if user:
                fullname = f"{user.firstname} {user.lastname}"
            else:
                fullname = "N/A"

            servicecontract_service = timesheet.get('service', '')
            count = next((acc['account_no'] for acc in bexio_accounts if acc['servicecontract_service'] == servicecontract_service), None)
            countTravel = next((acc['account_no'] for acc in bexio_accounts if acc['servicecontract_service'] == "Trasferta"), None)

            timesheet_data = {
                'id': timesheet['recordid_'],
                'count': count if count else "",
                'countTravel': countTravel,
                'company_id': timesheet['recordidcompany_'],
                'company': company_name,
                'description': timesheet['description'],
                'date': timesheet['date'],
                'user': fullname,
                'worktime_decimal': timesheet['worktime_decimal'],
                'workprice': timesheet['workprice'],
                'hourprice': timesheet['hourprice'],
                'travelprice': timesheet['travelprice'],
                'total_price': timesheet['totalprice'],
            }
            timesheets.append(timesheet_data)

        return JsonResponse({"timesheets": timesheets}, safe=False)
    except Exception as e:
        logger.error(f"Errore nel recupero dei timesheet da fatturare: {str(e)}")
        return JsonResponse({'error': f'Errore nel recupero dei timesheet da fatturare: {str(e)}'}, status=500)
    
def upload_timesheet_in_bexio(request):
    print("upload_invoices_in_bexio")
    bexio_accesstoken = os.environ.get('BEXIO_ACCESSTOKEN')

    headers = {
        'Accept': "application/json",
        'Authorization': f"Bearer {bexio_accesstoken}"
    }

    url = "https://api.bexio.com/2.0/kb_invoice"

    try:
        data = json.loads(request.body)
        invoice_date = data.get('invoiceDate')
        invoices = data.get('invoices', [])

        for invoice in invoices:
            request_body = {}

            datefrom = invoice_date
            dateto = datetime.datetime.strptime(datefrom, "%Y-%m-%d") + datetime.timedelta(days=20)

            companyname = invoice['company']
            company = UserRecord('company', invoice['company_id'])
            bexioid = ''
            if company:
                bexioid = company.values.get('id_bexio')

            positions = []

            # Texts
            text = {}
            text['type'] = 'KbPositionText'
            text['description'] = "<b>Interventi</b>"
            positions.append(text)

            total = 0
            # Timesheets
            for timesheet in invoice['timesheets']:
                position = {}

                count = timesheet['count']
                countid = ''
                if count:
                    condition_list = []
                    condition_list.append(f"account_no={count}")
                    accounts = UserTable('bexio_account').get_records(conditions_list=condition_list)
                    countid = accounts[0].get('id')

                position['tax_id'] = "39"
                position['account_id'] = countid
                position['unit_id'] = 2
                position['amount'] = timesheet['worktime_decimal']
                position['unit_price'] = timesheet['hourprice']
                position['type'] = 'KbPositionCustom'

                travelprice = timesheet['travelprice']
                if travelprice > 0:
                    travel = {}

                    count = timesheet['countTravel']
                    countid = ''
                    if count:
                        condition_list = []
                        condition_list.append(f"account_no={count}")
                        accounts = UserTable('bexio_account').get_records(conditions_list=condition_list)
                        countid = accounts[0].get('id')

                    travel['tax_id'] = "39"
                    travel['account_id'] = countid
                    travel['unit_id'] = 2
                    travel['amount'] = 1
                    travel['unit_price'] = travelprice
                    travel['type'] = 'KbPositionCustom'
                    positions.append(travel)

                positions.append(position)
                total += timesheet['total_price']

            request_body['title'] = "ICT: Supporto Cliente"
            request_body['contact_id'] = bexioid
            request_body['user_id'] = 1
            request_body['logopaper_id'] = 1
            request_body['language_id'] = 3
            request_body['currency_id'] = 1
            request_body['payment_type_id'] = 1
            request_body['header'] = ""
            request_body['footer'] = "Vi ringraziamo per la vostra fiducia, in caso di disaccordo, vi preghiamo di notificarcelo entro 7 giorni. <br/>Rimaniamo a vostra disposizione per qualsiasi domanda,<br/><br/>Con i nostri più cordiali saluti, Swissbix SA"
            request_body['mwst_type'] = 0
            request_body['mwst_is_net'] = True
            request_body['show_position_taxes'] = False
            request_body['is_valid_from']=datefrom.strftime("%Y-%m-%d")
            request_body['is_valid_to']=dateto.strftime("%Y-%m-%d")
            request_body['positions'] = positions

            # request_body_json = json.dumps(request_body)

            # response = requests.post(url, headers=headers, data=request_body_json)
            # response_json = response.content.decode('utf-8')
            # response_json = json.loads(response_json)
            # bexio_invoice_nr = response_json.get('document_nr', '')
            # bexio_id = response_json.get('id', '')

            # for row in timesheet:
            #     timesheetid = row['id']
            #     timesheet = UserRecord('timesheet', timesheetid)
            #     timesheet.values['invoicenr'] = bexio_invoice_nr
            #     timesheet.save()

            # print(f"Account name: {companyname} - Bexio Invoice Nr: {bexio_invoice_nr} - Bexio ID: {bexio_id}")

        return JsonResponse({'status': 'Invoices uploaded successfully'})
    except Exception as e:
        logger.error(f"Errore nell'upload del timesheet in Bexio: {str(e)}")
        return JsonResponse({'error': f'Errore nell\'upload del timesheet in Bexio: {str(e)}'}, status=500)


@task_monitor(data_type="update")
@safe_schedule_task(stop_on_error=True)
def sync_adiuto_assenze():
    result_message = ''
    result_log = []
    sql="DELETE FROM user_adiuto_assenze"
    HelpderDB.sql_execute(sql)

    # Aggiornamento dello stato dal server di Adiuto
    driver = "SQL Server"
    server = os.environ.get('ADIUTO_DB_SERVER')
    database = os.environ.get('ADIUTO_DB_NAME')
    username =  os.environ.get('ADIUTO_DB_USER')
    password =  os.environ.get('ADIUTO_DB_PASSWORD')
    
    connection_string = f'DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password}'

    try:
        cnxn = pyodbc.connect(connection_string)
        cursor = cnxn.cursor()
        stmt = cursor.execute(f"SELECT * FROM VA1034 WHERE FENA=-1")
        rows = stmt.fetchall()
        rows_counter=len(rows)
        print(f"Fetched Rows: {rows_counter}")
        result_log.append(f"Fetched Rows: {rows_counter}")

        for row in rows:
            print(f"Richiesta: {row.F1075} - {row.F1049}")
            result_log.append(f"Richiesta: {row.F1075} - {row.F1049}")
            record = UserRecord("adiuto_assenze")
            record.values['richiestoda_f1075'] = row.F1075
            record.values['datainizio_f1049'] = row.F1049
            record.values['datafine_f1050'] = row.F1050
            record.values['giorni_f1051'] = row.F1051
            record.values['ore_f1079'] = row.F1079
            record.values['tipoassenza_f1031'] = row.F1031
            record.values['note_f1002'] = row.F1002
            record.values['sync_id'] = f"{row.F1075}-{row.F1049}-{row.F1050}"
            record.save()


    except Exception as e:
        result_message = f"Errore durante la sincronizzazione: {str(e)}"
        result_log.append(result_message)
        print(result_message)
        raise Exception(result_message)

    finally:
        cnxn.close()

        return {
            "rows_counter": rows_counter,
            "message": f"Sincronizzazione completata: {rows_counter} righe",
            
        }, {
            "details": "\n".join(result_log)
        }

@task_monitor(data_type="sync")
@safe_schedule_task(stop_on_error=True)
def sync_bixdata_assenze():
    result_log = []
    try:
        print("sync_bixdata_assenze")
        sync_output = sync_table('assenze')
        result_log.append("sync_bixdata_assenze")

        #aggiornamento dipendente
        sql="UPDATE user_assenze JOIN user_dipendente ON user_assenze.adiuto_user=user_dipendente.adiuto_user SET user_assenze.recordiddipendente_=user_dipendente.recordid_"
        HelpderDB.sql_execute(sql)
        

        #aggiornamento tipo assenza
        sql="UPDATE user_assenze as a SET a.tipo_assenza='Vacanze' WHERE a.tipo_assenza='01.Vacanza'"
        HelpderDB.sql_execute(sql)
        sql="UPDATE user_assenze as a SET a.tipo_assenza='Visita medica' WHERE a.tipo_assenza='02.Visita medica'"
        HelpderDB.sql_execute(sql)

        #aggiornamento ore
        sql="""
        UPDATE user_assenze AS ba 
        JOIN user_adiuto_assenze AS aa ON ba.sync_id = aa.sync_id 
        SET 
            -- Aggiorna ba.ore solo se c'è un valore valido, altrimenti lo lascia com'è
            ba.ore = IF(
                aa.ore_f1079 IS NULL OR TRIM(aa.ore_f1079) = '', 
                ba.ore, 
                aa.ore_f1079 + 0
            ),
            
            -- Aggiorna ba.giorni sommandolo solo se c'è un valore valido, altrimenti lo lascia com'è
            ba.giorni = IF(
                aa.ore_f1079 IS NULL OR TRIM(aa.ore_f1079) = '', 
                ba.giorni, 
                IFNULL(ba.giorni, 0) + ((aa.ore_f1079 + 0) / 8)
            );
        """
        HelpderDB.sql_execute(sql)

        dipendenti_records=UserTable('dipendente').get_records(conditions_list=["deleted_='N'"])
        for dipendente in dipendenti_records:
            recordid_dipendente=dipendente.get('recordid_')
            save_record_fields('dipendente', recordid_dipendente)
            
        

    except Exception as e:
        result_message = f"Errore durante la sincronizzazione: {str(e)}"
        result_log.append(result_message)
        print(result_message)
        raise Exception(result_message)

    finally:

        return {
            "message": f"Sincronizzazione completata",
            
        }, {
            "details": "\n".join(result_log)
        }


from commonapp.views import custom_save_record_fields

@task_monitor(data_type="test")
@safe_schedule_task(stop_on_error=True)
def run_test():

    print("Inizio iterazione sui deal...")
    
    # Prepara la query per recuperare tutti i deal con data di apertura successiva al 01-01-2026.
    # Assumiamo che la tabella fisica nel database per 'deal' sia 'user_deal'
    query = "SELECT recordid_ FROM user_deal WHERE closedate >= '2026-01-01' AND deleted_='N'"
    
    try:
        rows = HelpderDB.sql_query(query)
    except Exception as e:
        print(f"Errore durante l'esecuzione della query al DB: {e}")
        return
        
    if not rows:
        print("Nessun deal trovato con opendate >= 2026-01-01.")
        return
    
    print(f"Trovati {len(rows)} record da processare.")
    success_count = 0
    
    for row in rows:
        recordid = row.get('recordid_')
        if not recordid:
            continue
            
        print(f"Chiamata a custom_save_record_fields per deal con recordid_: {recordid}")
        
        try:
            # Creiamo l'istanza UserRecord. Questo non è strettamente necessario se vuoti il dict dei params,
            # ma passandogli i values attuali simuliamo correttamente la post-save.
            deal_record = UserRecord('deal', recordid)
            old_values = deal_record.values.copy() if deal_record.values else {}
            
            # Richiama commonapp.views.custom_save_record_fields come richiesto.
            custom_save_record_fields('deal', recordid, old_values)
            success_count += 1
            
        except Exception as e:
            print(f"Errore durante l'elaborazione del deal {recordid}: {e}")

    print(f"Elaborazione terminata. Aggiornati {success_count} su {len(rows)} deal.")