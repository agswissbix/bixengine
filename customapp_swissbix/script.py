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

import requests
from bixsettings.models import *
from commonapp.bixmodels.user_record import UserRecord
from commonapp.utils.email_sender import EmailSender
from commonapp.bixmodels.helper_db import *
from commonapp.bixmodels.user_table import *
from customapp_swissbix.customfunc import *
from django.conf import settings
from commonapp.bixmodels.helper_db import HelpderDB
import xml.etree.ElementTree as ET
import json
from django.http import JsonResponse
from bixscheduler.decorators.safe_schedule_task import safe_schedule_task

import pyodbc
from cryptography.fernet import Fernet, InvalidToken

from commonapp import views

from xhtml2pdf import pisa
from django.template.loader import get_template
from customapp_swissbix.views import link_callback


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
    

@safe_schedule_task(stop_on_error=True)
def update_deals():
    result_status = 'error'
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
                if (row):
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
                    if (row):
                        dealline_uniteffectivecost = row.F1043
                        dealline_record.values['uniteffectivecost'] = dealline_uniteffectivecost
                        dealline_record.save()
                        print("dealline updated")
                        result_log.append("dealline updated")

                



            save_record_fields('deal', recordid_deal)
            updated_deal_counter+=1
            print("deal updated")
            result_log.append("deal updated")
            print("-----")
            result_log.append("-----")
        

        cnxn.close()
        
        print(f"Trattative aggiornate: {updated_deal_counter}")
        result_log.append(f"Trattative aggiornate: {updated_deal_counter}")

        result_status = 'success'
        result_message=f"Trattative aggiornate: {updated_deal_counter}"
        
        result_log="<br>".join(result_log)

    except pyodbc.Error as ex:
        sqlstate = ex.args[0]
        result_status = 'Errore connessione'
        print(f"Connessione non riuscita: {sqlstate}")

    

    return {"type": "update", "status": result_status, "message": result_message, "log": result_log}




def sync_freshdesk_tickets(request):
    api_key = os.environ.get('FRESHDESK_APIKEY')
    password = "x"

    url = f"https://swissbix.freshdesk.com/api/v2/tickets?include=requester,description,stats&updated_since=2025-01-01&per_page=10"

    response = requests.get(url, auth=(api_key, password))

    headers = response.headers
    response = json.loads(response.text)

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
        else:
            record = UserRecord('freshdesk_tickets', field['recordid_'])
            record.values['subject'] = ticket['subject']
            record.values['description'] = ticket['description_text']
            record.values['closed_at'] = ticket['stats']['closed_at']
            record.values['status'] = ticket['status']
            record.values['responder_id'] = ticket['responder_id']
            record.save()


    return JsonResponse(response, safe=False)


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

    for contact in response:
        print(f"Syncing contact: {contact['name_1']} Bexio nr: {contact['nr']}")
        field = HelpderDB.sql_query_row(f"select * from user_bexio_contact WHERE bexio_id='{contact['id']}'")
        if not field:
            record = UserRecord("bexio_contact")

        else:
            record = UserRecord("bexio_contact", field['recordid_'])
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

    return JsonResponse(response, safe=False)

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

    return JsonResponse(response, safe=False)


def sync_bexio_positions_example(request, bexioid):
    return sync_bexio_positions(request,'kb_order',bexioid)


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

    return JsonResponse(response, safe=False)


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

    for invoice in response:
        field = HelpderDB.sql_query_row(f"select * from user_bexio_invoices WHERE bexio_id='{invoice['id']}'")
        if not field:
            record = UserRecord("bexio_invoices")
        else:
            record = UserRecord("bexio_invoices", field['recordid_'])

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


    return JsonResponse(response, safe=False)

def sync_contacts(request):
    return syncdata(request,'company')

# DO NOT EXECUTE
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

    return HttpResponse(f"Sync completato: {records_created} inseriti, {records_updated} aggiornati.")

def get_scheduler_logs(request):
    try: 
        url = "https://bixdata.swissbix.com/get_scheduler_logs.php"
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

            oggetto_datetime = datetime.strptime(log.get('date'), formato)
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

        return JsonResponse(data, safe=False)
    except requests.RequestException as e:  
        return JsonResponse({"error": "Failed to fetch external data", "details": str(e)}, status=500)
    
def sync_graph_calendar(request):
    print("sync_graph_calendar")

    is_empty = not UserEvents.objects.all().exists()

    if is_empty:
        print("Nessun evento")
        return views.initial_graph_calendar_sync(request)
    else:
        print("Eventi esistenti")
        return views.sync_graph_calendar(request)
    
def sync_tables(request):
    '''
    Sincronizza tutte le tabelle da sincronizzare presenti in sys_table
    '''
    print("sync_tables")
    try:
        tables = HelpderDB.sql_query("SELECT * FROM sys_table WHERE sync_table IS NOT NULL")
        # tables = HelpderDB.sql_query("SELECT * FROM sys_table WHERE sync_table IS NOT NULL AND id = 'company'")

        for table in tables:
            print("Starting sync of table: " + table['sync_table'])
            columns = HelpderDB.sql_query(f"SELECT * FROM sys_field WHERE tableid='{table['id']}' AND sync_fieldid IS NOT NULL AND sync_fieldid != ''")

            sync_fieldid = table['sync_field']
            founded_fieldid = [c for c in columns if c.get('sync_fieldid') == sync_fieldid]
            if not founded_fieldid:
                continue
            fieldid = founded_fieldid[0]['fieldid']

            query = f"SELECT * from {table['sync_table']}"
            condition = table['sync_condition']
            order = table['sync_order']

            if condition:
                query += f" WHERE {condition}"

            if order:
                query += f" ORDER BY {order}"

            data = HelpderDB.sql_query(query)

            for row in data:
                id = row[sync_fieldid]
                
                field = HelpderDB.sql_query_row(f"SELECT * FROM user_{table['id']} WHERE {fieldid}='{id}'")

                if field:
                    print("Updating record")
                    record = UserRecord(table['id'], field['recordid_'])

                    for column in columns:
                        if column['sync_fieldid'] in row:
                            record.values[column['fieldid']] = row[column['sync_fieldid']]
                        else:
                            print("Missing column: " + column['sync_fieldid'])

                    record.save()
                else:
                    print("Creating record")
                    new_record = UserRecord(table['id'])

                    for column in columns:
                        if column['sync_fieldid'] in row:
                            new_record.values[column['fieldid']] = row[column['sync_fieldid']]
                        else:
                            print("Missing column: " + column['sync_fieldid'])
                    
                    new_record.save()
            print("Sync completed of table: " + table['sync_table'])

        print("Syncronization completed")
        return JsonResponse(data, safe=False)
    except requests.RequestException as e:  
        return JsonResponse({"error": "Failed to fetch external data", "details": str(e)}, status=500)

def sync_table(tableid):
    '''
    Sincronizza una singola tabella identificata da tableid
    '''
    print("sync_tables")

    if not tableid:
            return JsonResponse({"error": "Missing parameter"}, status=500)
    try:
        table = HelpderDB.sql_query_row(f"SELECT * FROM sys_table WHERE sync_table IS NOT NULL AND id = '{tableid}'")

        if not table:
            return JsonResponse({"error": "Table not found"}, status=500)

        print("Starting sync of table: " + table['sync_table'])
        columns = HelpderDB.sql_query(f"SELECT * FROM sys_field WHERE tableid='{table['id']}' AND sync_fieldid IS NOT NULL AND sync_fieldid != ''")

        sync_fieldid_origin = table['sync_field']
        founded_fieldid = [c for c in columns if c.get('sync_fieldid') == sync_fieldid_origin]
        if not founded_fieldid:
            return JsonResponse({"error": "Missing sync_fieldid"}, status=500)
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
        return JsonResponse(data, safe=False)
    except requests.RequestException as e:  
        return JsonResponse({"error": "Failed to fetch external data", "details": str(e)}, status=500)

def sync_bixdata_salesorders():
    print("sync_salesorders")
    sync_output = sync_table('salesorderline')
    sync_output = sync_table('salesorder')
    sql="UPDATE user_salesorder SET status='Complete'"
    HelpderDB.sql_execute(sql)
    sql="UPDATE user_salesorderline SET status='Complete'"
    HelpderDB.sql_execute(sql)

    #esecuzione sync_table
    


    #aggiornamento stato ordini in progress
    sql="UPDATE user_salesorder JOIN user_bexio_orders ON user_salesorder.id_bexio=user_bexio_orders.bexio_id SET user_salesorder.status='In Progress'"
    HelpderDB.sql_execute(sql)

    #aggiornamento company in salesorder
    sql="UPDATE user_salesorder JOIN user_company ON user_salesorder.id_bexio_company=user_company.id_bexio SET user_salesorder.recordidcompany_=user_company.recordid_"
    HelpderDB.sql_execute(sql)

    #aggiornamento stato righe ordini in progress
    sql="UPDATE user_salesorderline JOIN user_bexio_orders ON user_salesorderline.id_bexio_order=user_bexio_orders.bexio_id SET user_salesorderline.status='In Progress',user_salesorderline.bexio_repetition_type=user_bexio_orders.repetition_type,user_salesorderline.bexio_repetition_interval=user_bexio_orders.repetition_interval "
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

   
    
    return JsonResponse({"status": "completed"}, safe=False)

def print_servicecontract(request):
    print("print_servicecontract")

    try:
        recordid_servicecontract = None
        if request.method == 'POST':
            try:
                data = json.loads(request.body)
                recordid_servicecontract = data.get('recordid')
            except:
                pass
        elif request.method == 'GET':
            recordid_servicecontract = request.GET.get('recordid')

        if not recordid_servicecontract:
            return JsonResponse({'error': 'Missing recordid'}, status=400)
        
        servicecontract = UserRecord('servicecontract', recordid_servicecontract)
        
        if not servicecontract:
            return JsonResponse({'error': 'Record not found'}, status=404)
        
        company_id = servicecontract.values.get('recordidcompany_', '')
        company = UserRecord('company', company_id)

        companyname = "N/A"
        address = "N/A"
        cap = ""
        city = "N/A"
        
        if company:
            companyname = company.values.get('companyname', 'N/A')
            address = company.values.get('address', 'N/A')
            cap = company.values.get('cap', '')
            city = company.values.get('city', 'N/A')

        date_start = servicecontract.values.get('startdate', 'N/A')
        contracthours = servicecontract.values.get('contracthours', 0)
        invoiceno = servicecontract.values.get('invoiceno', 'N/A')
        previousresidual = servicecontract.values.get('previousresidual', 0)
        excludetravel = servicecontract.values.get('excludetravel', 'No')

        timesheets_dict = servicecontract.get_linkedrecords_dict('timesheet')

        timesheets_updated = []
        total_used_hours = 0.0 

        for timesheet in timesheets_dict:
            work_time = float(timesheet.get('worktime_decimal', 0) or 0)
            travel_time = float(timesheet.get('traveltime_decimal', 0) or 0)
            invoice_opt = timesheet.get('invoiceoption', '')

            if invoice_opt not in ['Under Warranty', 'Commercial support']:
                total_used_hours += work_time

            firstname = ''
            lastname = ''
            user_id = timesheet.get('user', '')
            if user_id:
                user_rec = SysUser.objects.get(id=user_id)
                if user_rec:
                    firstname = user_rec.firstname
                    lastname = user_rec.lastname

            ticket_subject = ''
            ticket_id = timesheet.get('recordidticketbixdata_', '')
            if ticket_id:
                ticket_record = UserRecord('ticket', ticket_id)
                if ticket_record:
                    ticket_subject = ticket_record.values.get('subject', '')

            tms = {
                'date': timesheet.get('date'), 
                'firstname': firstname or "",
                'lastname': lastname or "",
                'worktime_decimal': work_time, 
                'invoiceoption': invoice_opt,
                'traveltime_decimal': travel_time if travel_time > 0 else None, 
                'ticket_subject': ticket_subject,
                'description': timesheet.get('description', '')
            }

            timesheets_updated.append(tms)

        try:
            timesheets_updated.sort(key=lambda x: x['date'] if x['date'] else datetime.date.min)
        except Exception as e:
            print(f"Errore ordinamento date: {e}")

        try:
            c_hours = float(contracthours) if str(contracthours).replace('.','',1).isdigit() else 0.0
            p_res = float(previousresidual) if str(previousresidual).replace('.','',1).isdigit() else 0.0
            
            residual_val = c_hours + p_res - total_used_hours
            residualhours = "{:.2f}".format(residual_val)
        except:
            residualhours = "N/A"

        context = {
            'companyname': companyname,
            'address': address,
            'city': f"{cap} {city}".strip(),
            'date': date_start,
            'contracthours': contracthours,
            'invoiceno': invoiceno,
            'previousresidual': previousresidual,
            'excludetravel': excludetravel,
            'timesheets': timesheets_updated,
            'residualhours': residualhours, 
        }

        template = get_template('servicecontract.html')
        html = template.render(context)
        
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = 'inline; filename="service_contract.pdf"'
        
        pisa_status = pisa.CreatePDF(html, dest=response, link_callback=link_callback)
        
        if pisa_status.err:
            return HttpResponse("Errore durante la creazione del PDF", status=500)
            
        return response

    except Exception as e:
        logger.error(f"Errore nella generazione PDF: {str(e)}")
        return JsonResponse({'error': f'Errore nella generazione del PDF: {str(e)}'}, status=500)

def renew_servicecontract(request):
    try:
        data = json.loads(request.body)
        old_recordid = data.get('recordid')
        old_record = UserRecord('servicecontract', old_recordid)

        old_record.values['status'] = 'Complete'
        old_record.save()

        contracthours = data.get('contracthours')

        new_record = UserRecord('servicecontract')

        new_record.values['recordidcompany_'] = old_record.values['recordidcompany_']
        new_record.values['subject'] = old_record.values['subject']
        new_record.values['service'] = old_record.values['service']
        new_record.values['type'] = old_record.values['type']
        new_record.values['excludetravel'] = old_record.values['excludetravel']
        new_record.values['note'] = old_record.values['note']

        new_record.values['previousinvoiceno'] = old_record.values['invoiceno']
        new_record.values['previousresidual'] = old_record.values['residualhours']
        new_record.values['contracthours'] = float(contracthours) if str(contracthours).replace('.','',1).isdigit() else 0.0
        new_record.values['residualhours'] = float(contracthours) if str(contracthours).replace('.','',1).isdigit() else 0.0 + old_record.values['residualhours']
        new_record.values['invoiceno'] = data.get('invoiceno')
        new_record.values['startdate'] = data.get('startdate')
        new_record.values['status'] = 'In Progress'
        new_record.values['progress'] = 0
        new_record.values['recordidcompany_'] = old_record.values['recordidcompany_']

        new_record.save()

        return HttpResponse(f"Nuovo rinnovo effettuato")
    except Exception as e:
        logger.error(f"Errore nel rinnovo: {str(e)}")
        return JsonResponse({'error': f'Errore nel rinnovo: {str(e)}'}, status=500)
    

def get_monitoring(request):
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

            sql = "SELECT recordid_ FROM user_monitoring WHERE id = %s"
            exists = HelpderDB.sql_query_value(sql, "recordid_", [mon_id])

            rec = None
            if exists:
                rec = UserRecord('monitoring', exists)
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

        return JsonResponse({"status": "success", "processed": count}, safe=False)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
def encrypt_data(fernet_instance, plaintext):
    """Cifra una stringa con Fernet. Gestisce None e altri tipi."""
    
    if plaintext is None:
        plaintext = ""
        
    if not isinstance(plaintext, str):
        plaintext = str(plaintext)

    return fernet_instance.encrypt(plaintext.encode("utf-8")).decode("utf-8")

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
