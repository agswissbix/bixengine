from datetime import date, datetime
import os
import pprint
import subprocess
from django.http import HttpResponse, JsonResponse
from django_q.models import Schedule, Task
from django.db import connection
import psutil, shutil

import requests
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


def sync_bexio_contacts(request):
    url = "https://api.bexio.com/2.0/contact?order_by=id_desc&limit=100&offset=0"
    accesstoken=os.environ.get('BEXIO_ACCESSTOKEN')
    headers = {
        'Accept': "application/json",
        'Content-Type': "application/json",
        'Authorization': f"Bearer {accesstoken}",
    }

    response = requests.request("GET", url, headers=headers)
    response = json.loads(response.text)

    for contact in response:
        field = HelpderDB.sql_query_row(f"select * from user_bexio_contact WHERE bexio_id='{contact['id']}'")
        if not field:
            record = UserRecord("bexio_contact")

        else:
            record = UserRecord("bexio_contact", field['recordid_'])

        record.values['bexio_id'] = contact['id']
        record.values['nr'] = contact['nr']
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

def sync_bexio_orders(request):
    url = "https://api.bexio.com/2.0/kb_order/search/?order_by=id_desc&limit=10&offset=0"
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

    for order in response:
        field = HelpderDB.sql_query_row(f"select * from user_bexio_orders WHERE bexio_id='{order['id']}'")
        if not field:
            record = UserRecord("bexio_orders")

        else:
            record = UserRecord("bexio_orders", field['recordid_'])


        record.values['bexio_id'] = order['id']
        record.values['document_nr'] = order['document_nr']
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
        record.values['is_recurring'] = order['is_recurring']

        order_taxs = order['taxs']
        record.values['taxs_percentage'] = order_taxs[0]['percentage']
        record.values['taxs_value'] = order_taxs[0]['value']

        record.save()

        sync_bexio_positions(request, 'kb_order', order['id'])

    return JsonResponse(response, safe=False)


def sync_bexio_positions_example(request, bexioid):
    return sync_bexio_positions(request,'kb_order',bexioid)


def sync_bexio_positions(request,bexiotable,bexioid):
    url = f"https://api.bexio.com/2.0/{bexiotable}/{bexioid}/kb_position_custom"
    accesstoken=os.environ.get('BEXIO_ACCESSTOKEN')
    headers = {
        'Accept': "application/json",
        'Content-Type': "application/json",
        'Authorization': f"Bearer {accesstoken}",
    }

    response = requests.request("GET", url, headers=headers)
    response = json.loads(response.text)

    for position in response:
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
        record.values['parent_id'] = position['parent_id']
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

# DO NOT EXECUTE
def syncdata(request,tableid):
    sync_table = HelpderDB.sql_query_value(f"SELECT * FROM sys_table WHERE id='{tableid}'", 'sync_table')
    sync_field = HelpderDB.sql_query_value(f"SELECT * FROM sys_table WHERE id='{tableid}'", 'sync_field')
    sync_condition = HelpderDB.sql_query_value(f"SELECT * FROM sys_table WHERE id='{tableid}'", 'sync_condition')
    sync_order = HelpderDB.sql_query_value(f"SELECT * FROM sys_table WHERE id='{tableid}'", 'sync_order')

    bixdata_fields=dict()

    rows = HelpderDB.sql_query(f"SELECT * FROM sys_field WHERE tableid='{tableid}' AND sync_fieldid is not null AND sync_fieldid<>'' ")

    for row in rows:
        bixdata_fields[row['sync_fieldid']]=row['fieldid']

    if sync_condition:
        condition=sync_condition
    else:
        condition='true'

    if sync_order:
        order=f"ORDER BY {sync_order}"
    else:
        order=''

    sql=f"""
        SELECT *
        FROM {sync_table}
        WHERE {condition}
        {order}
    """
    syncrows=HelpderDB.sql_query(sql)

    for syncrow in syncrows:
        sync_fields=dict()
        for key, field in syncrow.items():
            if key in bixdata_fields:
                sync_fields[bixdata_fields[key]]=field
    bixdata_sync_field=bixdata_fields[sync_field]
    print(sync_fields)

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
    
