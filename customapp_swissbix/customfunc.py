from django.shortcuts import render
import environ
from django.conf import settings
from commonapp.bixmodels.user_record import *
from commonapp.bixmodels.user_table import *
from commonapp.bixmodels.helper_db import *
from commonapp.helper import *
from datetime import *
import qrcode
import pdfkit

from commonapp.helper import Helper
from commonapp.bixmodels.user_record import UserRecord
from commonapp.bixmodels.user_table import UserTable
from commonapp.bixmodels.helper_db import HelpderDB

import datetime
from datetime import timedelta
import os
import uuid
import base64
import json
from django.views.decorators.csrf import csrf_exempt
import pdfkit
import io
from io import BytesIO
from django.template.loader import render_to_string, get_template
from bixengine.settings import BASE_DIR
from commonapp.bixmodels.user_record import *
from commonapp.bixmodels.user_table import *
from commonapp.bixmodels.helper_db import *
from commonapp.helper import *
import qrcode
import shutil
from docxtpl import DocxTemplate, RichText
from playwright.sync_api import sync_playwright
from commonapp.models import SysUser
from PIL import Image
from customapp_swissbix.utils.browser_manager import BrowserManager
from django.core.files.storage import default_storage
from django.http import FileResponse
import logging
from xhtml2pdf import pisa
from .views import link_callback
# Initialize environment variables
env = environ.Env()
environ.Env.read_env()


logger = logging.getLogger(__name__)

def printing_katun_bexio_api_set_invoice(request):
    
    post_data = json.loads(request.body)
    params = post_data.get('params', None)
    recordid = params.get('recordid', None)

    if not recordid:
        bixdata_invoices = HelpderDB.sql_query("SELECT * FROM user_printinginvoice WHERE status='Creata' LIMIT 1")
    else:
        bixdata_invoices = HelpderDB.sql_query(f"SELECT * FROM user_printinginvoice WHERE recordid_='{recordid}'")


    for invoice in bixdata_invoices:

         #invoice data
        recordid_company= invoice['recordidcompany_']
        record_company = UserRecord('company', recordid_company)
        bexio_contact_id= record_company.values.get('id_bexio', None)
        print(invoice['title'])
        invoice_title="Conteggio copie stampanti/Multifunzioni"
        print(bexio_contact_id)
        if (bexio_contact_id == '297'):
            print('Cliente non presente in bexio')
            invoice_title = "Conteggio copie stampanti/Multifunzioni "+invoice['title']
        
        print(invoice_title)
        # 1. Ottieni la data e ora correnti come oggetto datetime
        now = datetime.datetime.now()

        # 2. Aggiungi 20 giorni utilizzando timedelta
        future_date = now + timedelta(days=20)

        # 3. Formatta la nuova data nel formato stringa desiderato
        invoice_dateto = future_date.strftime("%Y-%m-%d")

        # Se vuoi anche la data di partenza formattata
        invoice_datefrom = now.strftime("%Y-%m-%d")

        #invoice lines
        bixdata_invoicelines = HelpderDB.sql_query(f"SELECT * FROM user_printinginvoiceline WHERE recordidprintinginvoice_='{invoice['recordid_']}'")
        invoiceliness = []
        for invoiceline in bixdata_invoicelines:
            invoiceline_unitprice= invoiceline['unitprice']
            invoiceline_quantity= invoiceline['quantity']
            if invoiceline_quantity == "0.00" or invoiceline_quantity == "0":
                invoiceline_quantity="0.0001"
            invoiceline_description= invoiceline['description']
            invoiceline_description_html = invoiceline_description.replace('\n', '<br>')
            invoiceline_description_html += f"<br> Prezzo unitario costo copia: {invoiceline_unitprice}"

            bexio_invoiceline = {
                "tax_id": "39",
                "account_id": "353",
                "text": invoiceline_description_html,
                "unit_id": 1,   
                "amount": invoiceline_quantity,
                "unit_price": invoiceline_unitprice,
                "type": "KbPositionCustom",
            }
            invoiceliness.append(bexio_invoiceline)

        bexio_invoice = {
            "title": invoice_title,
            "contact_id": bexio_contact_id,
            "user_id": 1,
            "language_id": 3,
            "currency_id": 1,
            "payment_type_id": 1,
            "header": "",
            "footer": "Vi ringraziamo per la vostra fiducia, in caso di disaccordo, vi preghiamo di notificarcelo entro 7 giorni.<br/><br/> <b>N.B.</b>: l’importo del costo di stampa riportato nella colonna del prezzo unitario è arrotondato; il valore esatto, utilizzato per il calcolo del costo supplementare effettivo, è indicato nel testo a sinistra. <br/><br/>Rimaniamo a vostra disposizione per qualsiasi domanda,<br/><br/>Con i nostri più cordiali saluti, Swissbix SA ",
            "mwst_type": 0,
            "mwst_is_net": True,
            "show_position_taxes": False,
            "is_valid_from": invoice_datefrom,
            "is_valid_to": invoice_dateto,
            "template_slug": "5a9c000702cf22422a8b4641",
            "positions": invoiceliness,
        }

        payload_invoice=json.dumps(bexio_invoice)

        #payload  = r"""{"title":"ICT: Supporto Cliente","contact_id":"297","user_id":1,"logopaper_id":1,"language_id":3,"currency_id":1,"payment_type_id":1,"header":"","footer":"Vi ringraziamo per la vostra fiducia, in caso di disaccordo, vi preghiamo di notificarcelo entro 7 giorni. Rimaniamo a vostra disposizione per qualsiasi domanda,Con i nostri più cordiali saluti, Swissbix SA","mwst_type":0,"mwst_is_net":true,"show_position_taxes":false,"is_valid_from":"2025-06-25","is_valid_to":"2025-07-15","positions":[{"text":"Interventi</b>","type":"KbPositionText"},{"text":"TEST 25/06/2025 Galli Alessandro </b></span>","tax_id":"39","account_id":"155","unit_id":2,"amount":"1","unit_price":"140","type":"KbPositionCustom"}]}"""


        url = "https://api.bexio.com/2.0/kb_invoice"
        accesstoken=os.environ.get('BEXIO_ACCESSTOKEN')
        
        headers = {
            'Accept': "application/json",
            'Content-Type': "application/json",
            'Authorization': f"Bearer {accesstoken}",
        }

        


        response = requests.request("POST", url, data=payload_invoice, headers=headers)

        status_code = response.status_code
        invoice_record = UserRecord('printinginvoice', invoice['recordid_'])
        if status_code == 201:
            response_data = response.json()
            response_data_json_str= json.dumps(response_data)
            invoice_record.values['bexio_output'] = response_data_json_str
            bexio_invoice_id = response_data.get('id', )
            bexio_document_nr = response_data.get('document_nr', None)
            invoice_record.values['bexioinvoicenr'] = bexio_document_nr
            invoice_record.values['bexioinvoiceid'] = bexio_invoice_id
            invoice_record.values['status'] = 'Caricata'
            invoice_record.save()
        else:
            print(f"Errore nella creazione della fattura su Bexio. Status code: {status_code}, Response: {response.text}")
            invoice_record.values['status'] = 'Errore Bexio'
            invoice_record.save()
    return JsonResponse({'status': status_code, 'message': response.json()})


def print_timesheet(request):
    """
    Genera (o rigenera) il PDF del timesheet e lo restituisce per il download.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Metodo non consentito'}, status=405)

    try:
        data = json.loads(request.body)
        recordid = data.get('recordid')
        with_signature = data.get('with_signature')

        if not recordid:
            return JsonResponse({'error': 'Recordid mancante'}, status=400)

        attachment_rows = HelpderDB.sql_query(f"""
            SELECT file, filename 
            FROM user_attachment 
            WHERE recordidtimesheet_ = '{recordid}' 
            AND type = 'Signature'
            ORDER BY recordid_ DESC LIMIT 1
        """)

        if not attachment_rows or not with_signature:
            pdf_filename = generate_timesheet_pdf(recordid)
            attachment_rows = HelpderDB.sql_query(f"""
                SELECT file, filename 
                FROM user_attachment 
                WHERE recordidtimesheet_ = '{recordid}' 
                AND type = 'Signature'
                ORDER BY recordid_ DESC LIMIT 1
            """)
        
        file_info = attachment_rows[0]
        relative_path = file_info['file']
        filename = file_info.get('filename', 'timesheet.pdf')

        abs_path = os.path.normpath(os.path.join(settings.UPLOADS_ROOT, relative_path))

        if not os.path.exists(abs_path):
            return JsonResponse({'error': f'File non trovato sul server: {relative_path}'}, status=404)

        response = FileResponse(open(abs_path, 'rb'), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response

    except Exception as e:
        print(f"Errore in print_timesheet: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

def print_timesheet_func(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            recordid = data.get('recordid')

            
            base_path = os.path.join(settings.STATIC_ROOT, 'pdf')




            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=10,
                border=0,
            )

            today = date.today()
            d1 = today.strftime("%d/%m/%Y")

            qrcontent = 'timesheet_' + str(recordid)


            data = qrcontent
            qr.add_data(data)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")

            qr_name = 'qrcode' + recordid + '.png'

            qr_path = os.path.join(base_path, qr_name)

            img.save(qr_path)


            rows = HelpderDB.sql_query(f"SELECT t.*, c.companyname, c.address, c.city, c.email, c.phonenumber, u.firstname, u.lastname FROM user_timesheet AS t JOIN user_company AS c ON t.recordidcompany_=c.recordid_ JOIN sys_user AS u ON t.user = u.id WHERE t.recordid_='{recordid}'")

            server = os.environ.get('BIXENGINE_SERVER')
            qr_url = server + '/static/pdf/' + qr_name


            pdf_filename = f"Timesheet_{str(recordid)}.pdf"
            pdf_filename = re.sub(r'[\\/*?:"<>|]', "", pdf_filename) # Pulisci il nome

            filename_with_path = os.path.join(base_path, 'temp_timesheet_' + str(recordid) + '.pdf')



            row = rows[0]

            for value in row:
                if row[value] is None:
                    row[value] = ''

            row['recordid'] = recordid
            row['qrUrl'] = qr_url


            timesheetlines = HelpderDB.sql_query(f"SELECT * FROM user_timesheetline WHERE recordidtimesheet_='{recordid}'")


            for line in timesheetlines:
                line['note'] = line['note'] or ''   
                line['expectedquantity'] = line['expectedquantity'] or ''
                line['actualquantity'] = line['actualquantity'] or ''

            row['timesheetlines'] = timesheetlines

            script_dir = os.path.dirname(os.path.abspath(__file__))
        
            wkhtmltopdf_path = script_dir + '\\wkhtmltopdf.exe'

            config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
            content = render_to_string('pdf/timesheet_signature.html', row)

            pdfkit.from_string(
                content,
                filename_with_path,
                configuration=config,
                options={
                    "enable-local-file-access": "",
                    # "quiet": ""  # <-- rimuovilo!
                }
            )


            try:
                with open(filename_with_path, 'rb') as f:
                    pdf_data = f.read()
  
                    response = HttpResponse(pdf_data, content_type='application/pdf')
                    response['Content-Disposition'] = f'inline; filename="{pdf_filename}"'
                    return response
            finally:
                if os.path.exists(filename_with_path):
                    os.remove(filename_with_path)
                if os.path.exists(qr_path):
                    os.remove(qr_path)

        except Exception as e:
            print(f"Error in print_timesheet: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

def get_timesheet_emails(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)
    
    try:
        data = json.loads(request.body)
        recordid_timesheet = data.get("recordid")
        
        if not recordid_timesheet:
            return JsonResponse({"error": "Missing recordid"}, status=400)
            
        timesheet = UserRecord("timesheet", recordid_timesheet)
        company_id = timesheet.values.get("recordidcompany_")
        
        emails = []
        
        if company_id:
            company = UserRecord("company", company_id)
            company_email = company.values.get("email")
            if company_email:
                emails.append({
                    "email": company_email,
                    "name": company.values.get("companyname", ""),
                    "type": "Azienda",
                    "role": ""
                })
                
            # fetch contacts
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT name, surname, email, role 
                    FROM user_contact 
                    WHERE recordidcompany_ = %s AND deleted_ = 'N' AND email IS NOT NULL AND email != ''
                """, [company_id])
                contacts = cursor.fetchall()
                
                for contact in contacts:
                    name, surname, email, role = contact
                    full_name = f"{name or ''} {surname or ''}".strip()
                    if email:
                        # Avoid duplicates
                        if not any(e["email"] == email for e in emails):
                            emails.append({
                                "email": email,
                                "name": full_name,
                                "role": role or "",
                                "type": "Contatto"
                            })
                        
        return JsonResponse({"success": True, "emails": emails})
        
    except Exception as e:
        print("Error in get_timesheet_emails:", e)
        return JsonResponse({"error": str(e)}, status=500)


def swissbix_create_timesheet_from_timetracking(request):
    print("Function: swissbix_create_timesheet_from_timetracking")
    from customapp_swissbix.views import get_timetracking_ai_summary, check_ai_server

    try:
        userid = Helper.get_userid(request)
        data = json.loads(request.body)

        raw_ai = data.get('use_ai', {})
        
        if isinstance(raw_ai, dict) and 'use_ai' in raw_ai:
            use_ai_config = raw_ai['use_ai']
        else:
            use_ai_config = raw_ai

        use_ai = use_ai_config.get('useAI', False) if isinstance(use_ai_config, dict) else False
        instructions = use_ai_config.get('instructions', "") if isinstance(use_ai_config, dict) else ""
        
        params = data.get('params', {})
        
        tableid = params.get("tableid")
        viewid = params.get("view")
        searchTerm = params.get("searchTerm", '')
        master_tableid = params.get("masterTableid")
        master_recordid = params.get("masterRecordid")
        filtersList = params.get("filtersList", [])
        
        # order = params.get("order", {"fieldid": "recordid_", "direction": "desc"})
        # order_str = f"{order.get('fieldid', 'recordid_')} {order.get('direction', 'desc')}"
        order_str = "creation_ asc"

        table = UserTable(tableid, userid)

        timetrackings = table.get_table_records_obj(
            viewid=viewid,
            searchTerm=searchTerm,
            master_tableid=master_tableid,
            master_recordid=master_recordid,
            filters_list=filtersList,
            offset=0,
            limit=100000, 
            orderby=order_str
        )

        if not timetrackings:
            return JsonResponse({
                'status': 'success',
                'message': 'Nessun record trovato',
                'count': 0
            })

        azienda = None
        date = None
        worktime_decimal = 0

        timetracking_list = []
        processed_count = 0

        sanitized_service = None

        for timetracking in timetrackings:
            azienda = timetracking.fields.get('recordidcompany_', {}).get('value', azienda)
            date = timetracking.fields.get('date', {}).get('value', date)
            desc_val = timetracking.fields.get('description', {}).get('value', '')
            service_val = timetracking.fields.get('service', {}).get('value', '')
            worktime_val = timetracking.fields.get('worktime', {}).get('value', 0)
            pausetime_val = timetracking.fields.get('pausetime', {}).get('value', 0)

            if service_val:
                sanitized_service = service_val

            sanitized_pausetime = float(pausetime_val) if pausetime_val is not None else 0.0
            sanitized_worktime = float(worktime_val) if worktime_val is not None else 0.0
            sanitized_description = str(desc_val) if desc_val is not None else ""

            net_worktime = sanitized_worktime - sanitized_pausetime

            timetracking_list.append({
                "description": sanitized_description,
                "worktime": net_worktime
            })

            worktime_decimal += net_worktime
            
            processed_count += 1

        new_timesheet = {}

        # worktime convertito e arrotondato ai 15 mins
        minutes_raw = worktime_decimal * 60
        total_minutes = int(round(minutes_raw / 15) * 15)
        hours, minutes = divmod(total_minutes, 60)
        worktime = f"{hours:02d}:{minutes:02d}"

        summary = None
        if use_ai:
            is_online, message = check_ai_server()

            if is_online:
                print(f"✅  {message}")
                summary = get_timetracking_ai_summary(timetracking_list, instructions)
            else:
                print(f"❌  {message}")

        description = ', '.join([t['description'] for t in timetracking_list if t['description']])

        new_timesheet['user'] = userid
        new_timesheet['recordidcompany_'] = azienda
        new_timesheet['date'] = date
        new_timesheet['description'] = summary or description
        new_timesheet['worktime'] = worktime
        new_timesheet['worktime_decimal'] = worktime_decimal
        new_timesheet['service'] = sanitized_service

        return JsonResponse({
            'status': 'success', 
            'message': f'Processati {processed_count} record di timetracking',
            'timesheet': new_timesheet,
            'count': processed_count
        })
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

def start_timetracking_from_task(request):
    print("Function: start_timetracking_from_task")

    userid = Helper.get_userid(request)

    data = json.loads(request.body)
    params = data.get('params', {})
    recordid = params.get('recordid')
    tableid = 'task'

    from customapp_swissbix.views import stop_active_timetracking
    stop_active_timetracking(userid)

    conditions = []
    conditions.append(f"recordid_='{recordid}'")
    task_table = UserTable(tableid).get_table_records(conditions_list=conditions)
    task = task_table[0]
    if not task:
        return JsonResponse({'status': 'error', 'message': 'Task non trovato'}, status=404)

    timetracking = UserRecord('timetracking')

    timetracking.values['user'] = userid
    timetracking.values['description'] = task.get('description')
    timetracking.values['date'] = datetime.datetime.now().strftime("%Y-%m-%d")
    timetracking.values['start'] = datetime.datetime.now().strftime("%H:%M")
    timetracking.values['stato'] = "Attivo"
    timetracking.values['recordidtask_'] = task.get('recordid_')

    if task.get('recordidcompany_'):
        timetracking.values['recordidcompany_'] = task.get('recordidcompany_')

    timetracking.save()

    # Ottenimento URL per reindirizzamento
    fn = SysCustomFunction.objects.filter(
        context='link',
        tableid='timetracking'
    ).order_by('order').values('params').first()

    if not fn or not fn.get('params'):
        return JsonResponse({'status': 'error', 'message': 'Configurazione mancante'}, status=500)

    params = fn['params']
    if isinstance(params, str):
        params = json.loads(params)

    url = params.get('url', 'https://default.url')
    

    return JsonResponse({'status': 'success', 'url': url})

def swissbix_summarize_day(request):
    print("Function: swissbix_summarize_day")
    from customapp_swissbix.views import check_ai_server, get_timesheet_ai_summary

    userid = Helper.get_userid(request)
    tablesettings = TableSettings("timesheet", userid)
    can_view_settings = tablesettings.get_specific_settings('view')['view']
    permitted = can_view_settings.get('value')
    if not permitted:
        return JsonResponse({'status': 'error', 'message': 'Non autorizzato'}, status=403)

    is_online, message = check_ai_server()

    if is_online:
        print(f"✅  {message}")
    else:
        print(f"❌  {message}")
        return JsonResponse({'status': 'error', 'message': message}, status=500)

    current_date = datetime.datetime.now().strftime("%Y-%m-%d")

    condition_list = []
    condition_list.append(f"date='{current_date}'")

    todays_timesheets = UserTable('timesheet').get_table_records(conditions_list=condition_list)

    blacklist = ['test', 'wip', 'guest', 'group', 'user', 'admin', 'super', 'nome']
    sql = "SELECT * FROM sys_user WHERE firstname IS NOT NULL"
    all_users = HelpderDB.sql_query(sql)

    filtered_users = []
    for u in all_users:
        first_name = str(u.get('firstname', '')).lower()
        
        if not any(word in first_name for word in blacklist):
            filtered_users.append(u)

    timesheets_per_utente = defaultdict(list)
    for ts in todays_timesheets:
        user_id = ts.get('user')
        timesheets_per_utente[user_id].append(ts)

    timesheets_per_user = []
    
    for dipendente in filtered_users:
        user_id = str(dipendente.get('id'))
        
        ts_associati = timesheets_per_utente.get(user_id, [])
        
        timesheets_per_user.append({
            'anagrafica': dipendente,
            'timesheets': ts_associati,
            'totale_record': len(ts_associati)
        })

    summary = get_timesheet_ai_summary(timesheets_per_user)

    return JsonResponse({'status': 'success', 'summary': summary})

def ask_ai(request):
    """
    Riceve una domanda e restituisce la risposta completa in formato JSON.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Metodo non consentito'}, status=405)

    try:
        question = request.POST.get("question")
        if not question:
            try:
                data = json.loads(request.body)
                question = data.get("question")
            except:
                pass

        if not question:
            return JsonResponse({'status': 'error', 'message': 'Nessuna domanda specificata'}, status=400)

        answer = f"Funzione non implementata. Impossibile rispondere alla domanda:'{question}'.\n"

        return JsonResponse({
            "status": "completed",
            "answer": answer,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f"Errore interno: {str(e)}"}, status=500)


def deal_update_status(request):
    print('test')
    data = json.loads(request.body)
    params = data.get('params')
    recordid = params.get('recordid')
    status= params.get('status')
    stage= params.get('stage')
    deal_record=UserRecord('deal',recordid)
    deal_record.values['dealstage']=stage
    deal_record.values['dealstatus']=status
    deal_record.save()
    response={ "status": "ok"}
    return JsonResponse(response)

def stampa_offerta(request):
    data = json.loads(request.body)
    recordid_deal = data.get('recordid')
    

    tableid= 'deal'
  
    # Percorso al template Word
    base_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(base_dir, 'templates', 'template.docx')


    if not os.path.exists(template_path):
        return HttpResponse("File non trovato", status=404)

    
    deal_record = UserRecord(tableid, recordid_deal)
    reference = deal_record.values.get('reference', 'N/A')
    dealname = deal_record.values.get('dealname', 'N/A')
    dealuser1 = deal_record.values.get('dealuser1', 'N/A')
    closedata = deal_record.values.get('closedate', 'N/A')
    
    filename = re.sub(r'[^a-zA-Z0-9\-_]', '', reference.replace(' ', '_')) if reference else f"offerta_{recordid_deal}"

    companyid = deal_record.values.get('recordidcompany_')
    if companyid:
        company_record = UserRecord('company', deal_record.values.get('recordidcompany_'))
        companyname = company_record.values.get('companyname', 'N/A')
        address = company_record.values.get('address', 'N/A')
        cap = company_record.values.get('cap', 'N/A')
        city = company_record.values.get('city', 'N/A')

    user_record=HelpderDB.sql_query_row(f"SELECT * FROM sys_user WHERE id ='{dealuser1}'")
    user = user_record['firstname'] + ' ' + user_record['lastname']
    
    # Definizione economica
    dealline_records = deal_record.get_linkedrecords_dict('dealline')
    lines = []
    total = 0.0

    for idx, line in enumerate(dealline_records, 1):
        name = line.get('name', 'N/A')
        quantity = line.get('quantity', 0)
        unit_price = line.get('unitprice', 0.0)
        price = line.get('price', 0.0)
        total += price
        
        # Formatta i numeri in stile italiano
        qty_str = f"{quantity:.0f}".replace('.', ',')
        unit_str = f"CHF {unit_price:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        price_str = f"CHF {price:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        
        # Crea RichText per questa riga prodotto
        rt_prodotto = RichText()
        rt_prodotto.add(f"{name}:\n", size=20, underline=True)
        rt_prodotto.add("\tQuantità: ", size=20)
        rt_prodotto.add(qty_str, bold=True, size=20)
        rt_prodotto.add("\t|\tPrezzo unitario: ", size=20)
        rt_prodotto.add(unit_str, bold=True, size=20)
        rt_prodotto.add("\t|\tTotale: ", size=20)
        rt_prodotto.add(price_str, bold=True, size=20)
        rt_prodotto.add("\n\n", size=20)

        lines.append(rt_prodotto)

    # Crea il titolo
    # Crea il separatore
    separatore = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Crea il totale finale
    total_str = f"CHF {total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    rt_totale = RichText()
    rt_totale.add('TOTALE COMPLESSIVO: ', bold=True, size=22)
    rt_totale.add(total_str, bold=True, size=22)

    # Combina tutti i prodotti in un unico RichText
    rt_all_products = RichText()
    for rt_prod in lines:
        # Aggiungi il contenuto di ogni prodotto
        rt_all_products.add(rt_prod)

    # Crea il documento completo
    tabella_completa = RichText()
    tabella_completa.add(separatore, color='gray', size=18)
    tabella_completa.add('\n\n')
    tabella_completa.add(rt_all_products)
    tabella_completa.add(separatore, color='gray', size=18)
    tabella_completa.add('\n\n')
    tabella_completa.add(rt_totale)
    tabella_completa.add('\n\n')
    tabella_completa.add(separatore, color='gray', size=18)

    dati_trattativa = {
        "indirizzo": f"{address}, {cap} {city}",
        "azienda": companyname,
        "titolo": dealname,
        "venditore": user,
        "data_chiusura_vendita": closedata.strftime("%d/%m/%Y") if isinstance(closedata, datetime.date) else closedata,
        "data_attuale": datetime.datetime.now().strftime("%d/%m/%Y"),
        'tabella_prodotti': tabella_completa,
    }


    # Carica il template e fai il rendering
    doc = DocxTemplate(template_path)
    doc.render(dati_trattativa)

    # Salva il documento in memoria
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}.docx"'
    return response

def get_project_templates(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT recordid_, templatename
                FROM user_projecttemplate
                WHERE deleted_ = 'N'
            """)
            rows = cursor.fetchall()

        # Mappo i risultati per il FE
        templates = [
            {
                "id": str(row[0]),
                "value": row[1]
            }
            for row in rows
        ]

        return JsonResponse({"templates": templates}, safe=False)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
def save_project_as_template(request):
    if request.method != "POST":
        return JsonResponse({"error": "Metodo non permesso"}, status=405)

    try:
        data = json.loads(request.body)

        project_id = data.get("recordid")
        template_id = data.get("template")

        if not project_id or not template_id:
            return JsonResponse({"error": "Parametri mancanti"}, status=400)

        userid = Helper.get_userid(request)
        # 🔹 Carico il record del progetto
        project_record = UserRecord("project", project_id, userid)

        if not project_record.values:
            return JsonResponse({"error": "Record progetto non trovato"}, status=404)

        # 🔹 Carico il record del template
        template_record = UserRecord("projecttemplate", template_id, userid)

        if not template_record.values:
            return JsonResponse({"error": "Template non trovato"}, status=404)

        # 🔥 Sovrascrivo i valori del progetto con quelli del template
        project_values = project_record.values
        template_values = template_record.values

        exclueded_fields = ['id', 'recordid_', 'creatorid_', 'creation_', 'lastupdaterid_', 'lastupdate_', 'totpages_', 'firstpagefilename_', 'recordstatus_', 'deleted_',]

        for fieldid, template_value in template_values.items():
            # ❗ non sovrascrivere ID o altre chiavi protette
            if fieldid in exclueded_fields:
                continue

            # aggiorna solo se esiste anche nel progetto
            if fieldid in project_values:
                project_values[fieldid] = template_value

        # 🔥 Salvo le modifiche
        project_record.save()

        tables = template_record.get_linked_tables()

        linked_tables_real_raw = project_record.get_linked_tables()
        linked_tables_real = [t["tableid"] for t in linked_tables_real_raw]

        for table in tables:
            template_table_id = table["tableid"]
            
            # es: da "projecttemplatechecklist" → "projectchecklist"
            real_table_id = template_table_id.replace("projecttemplate", "")

            if real_table_id not in linked_tables_real:
                continue

            old_records = project_record.get_linkedrecords_dict(real_table_id)

            for old in old_records:
                old_rec = UserRecord(real_table_id, old["recordid_"])
                old_rec.values["deleted_"] = "Y"
                old_rec.save()

            linked_records = template_record.get_linkedrecords_dict(template_table_id)

            for record in linked_records:

                # 🔥 CREO NUOVO RECORD NELLA TABELLA REALE
                new_rec = UserRecord(real_table_id)

                # Copio tutti i campi tranne quelli di sistema
                for fieldid, val in record.items():
                    if fieldid in exclueded_fields:
                        continue

                    # Se il campo contiene "projecttemplate", trasformalo in "project"
                    # Es: recordidprojecttemplate_ → recordidproject_
                    new_fieldid = fieldid.replace("projecttemplate", "project")

                    # TODO handle fields type FILE
                    new_rec.values[new_fieldid] = val

                # Imposto il recordid del progetto (campo di relazione)
                new_rec.values[f"recordidproject_"] = project_id

                # Salvo il nuovo record
                new_rec.save()

        return JsonResponse({"success": True, "message": "Template applicato correttamente."})

    except Exception as e:
        print("Errore:", e)
        return JsonResponse({"error": str(e)}, status=500)


def ensure_playwright_installed():
    """Garantisce che il browser Chromium sia presente."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
    except Exception:
        # subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        print("Playwright non installato")

def to_base64(path):
    """Converte immagine locale in Base64 per l'incorporamento nel PDF."""
    if path and os.path.exists(path):
        try:
            with open(path, "rb") as f:
                return f"data:image/png;base64,{base64.b64encode(f.read()).decode('utf-8')}"
        except Exception as e:
            print(f"Errore conversione Base64: {e}")
    return None

def generate_timesheet_pdf(recordid, signature_path=None):
    """
    Genera il PDF del timesheet con firma condizionale e footer fisso.
    """
    try:
        ensure_playwright_installed()

        base_path = os.path.normpath(os.path.join(settings.STATIC_ROOT, 'pdf'))
        os.makedirs(base_path, exist_ok=True)

        q_path = os.path.join(base_path, f"qr_{uuid.uuid4().hex}.png")
        qr = qrcode.QRCode(box_size=10, border=0)
        qr.add_data(f"timesheet_{recordid}")
        qr.make(fit=True)
        qr.make_image(fill_color="black", back_color="white").save(q_path)

        rows = HelpderDB.sql_query(f"""
            SELECT t.*, c.companyname, c.address, c.city, c.email, c.phonenumber, 
                   u.firstname, u.lastname 
            FROM user_timesheet AS t 
            JOIN user_company AS c ON t.recordidcompany_=c.recordid_ 
            JOIN sys_user AS u ON t.user = u.id 
            WHERE t.recordid_='{recordid}'
        """)

        if not rows:
            raise Exception(f"Nessun timesheet trovato per recordid {recordid}")

        row = rows[0]
        for k in row: row[k] = row[k] or ''

        # get nr. deal
        nr_deal = HelpderDB.sql_query_value(f"SELECT iddeal FROM user_project WHERE recordid_=%s", 'iddeal', {rows[0]['recordidproject_']})
        row['nr_deal'] = nr_deal

        import pathlib
        firma_path = None
        if signature_path:
            firma_path = pathlib.Path(signature_path)
        qr_path = pathlib.Path(q_path)

        # -------------------------
        # 4️⃣ Prepara i dati per il template
        # -------------------------
        static_img_path = os.path.join(settings.BASE_DIR, "customapp_swissbix/static/images")
        row['recordid'] = recordid
        row['logoUrl'] = to_base64(os.path.join(static_img_path, "logo_w.png"))
        row['qrUrl'] = to_base64(qr_path.resolve())
        if firma_path:
            row['signatureUrl'] = to_base64(firma_path.resolve())
        else:
            row['signatureUrl'] = None

        print("GPDF: signatureUrl", row['signatureUrl'])
        print("GPDF: qrUrl", row['qrUrl'])

        timesheetlines = HelpderDB.sql_query(
            f"SELECT * FROM user_timesheetline WHERE recordidtimesheet_='{recordid}'"
        )
        for line in timesheetlines:
            line['note'] = line.get('note') or ''
            line['expectedquantity'] = line.get('expectedquantity') or ''
            line['actualquantity'] = line.get('actualquantity') or ''
        row['timesheetlines'] = timesheetlines

        html_content = render_to_string('pdf/timesheet_signature.html', row)
        pdf_filename = f"timesheet_{recordid}.pdf"
        temp_pdf_path = os.path.join(base_path, pdf_filename)

        css = """
                /* Rimuove l'altezza forzata che spesso crea la seconda pagina */
                html, body { 
                    height: auto !important; 
                    overflow: hidden !important; 
                    margin: 0 !important; 
                    padding: 0 !important;
                }
                
                /* Evita che il footer fixed forzi un salto pagina se troppo vicino al bordo */
                div[style*="position:fixed"] {
                    position: absolute !important;
                    bottom: 0 !important;
                }

                /* Rimuove spazi bianchi finali indesiderati */
                body:after {
                    content: none !important;
                }
                
                /* Ottimizzazione scala */
                body {
                    zoom: 0.75;
                }
        """

        BrowserManager.generate_pdf(
            html_content=html_content,
            output_path=temp_pdf_path,
            css_styles=css
        )

        attachment_record = UserRecord('attachment')
        attachment_record.values['type'] = "Signature"
        attachment_record.values['recordidtimesheet_'] = recordid
        attachment_record.save()

        dest_dir = os.path.join(settings.UPLOADS_ROOT, "attachment", str(recordid))
        os.makedirs(dest_dir, exist_ok=True)
        final_pdf_path = os.path.join(dest_dir, pdf_filename)
        shutil.move(temp_pdf_path, final_pdf_path)

        attachment_record.values['file'] = f"attachment/{recordid}/{pdf_filename}"
        attachment_record.values['filename'] = pdf_filename
        attachment_record.save()

        if os.path.exists(q_path): os.remove(q_path)

        return pdf_filename

    except Exception as e:
        print(f"Errore in generate_timesheet_pdf: {e}")
        raise


@csrf_exempt
def save_signature(request):
    """
    Riceve una firma in base64, genera il PDF del timesheet con la firma
    e salva il file come allegato nel DB (tabella attachment).
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)

    try:
        ensure_playwright_installed()
        
        data = json.loads(request.body)
        recordid = data.get('recordid')
        img_base64 = data.get('image')

        if not recordid:
            return JsonResponse({'error': 'Missing recordid'}, status=400)
        if not img_base64:
            return JsonResponse({'error': 'No image data'}, status=400)

        # -------------------------
        # 1️⃣ Salva la firma come immagine PNG
        # -------------------------
        if ',' in img_base64:
            _, img_base64 = img_base64.split(',', 1)
        img_data = base64.b64decode(img_base64)

        base_path = os.path.join(settings.STATIC_ROOT, 'pdf')
        os.makedirs(base_path, exist_ok=True)

        filename_firma = f"firma_{recordid}_{uuid.uuid4().hex}.png"
        firma_path = os.path.join(base_path, filename_firma)

        img_pil = Image.open(BytesIO(img_data))
        if img_pil.mode in ('RGBA', 'LA') or (img_pil.mode == 'P' and 'transparency' in img_pil.info):
            background = Image.new('RGB', img_pil.size, (255, 255, 255))
            background.paste(img_pil, mask=img_pil.split()[-1])
            img_pil = background
        else:
            img_pil = img_pil.convert('RGB')
        img_pil.save(firma_path, format='PNG')

        # -------------------------
        # 2️⃣ Genera QR Code
        # -------------------------
        uid = uuid.uuid4().hex
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=0,
        )
        qrcontent = f"timesheet_{recordid}"
        qr.add_data(qrcontent)
        qr.make(fit=True)

        img_qr = qr.make_image(fill_color="black", back_color="white")
        qr_name = f"qrcode_{uid}.png"
        qr_path = os.path.join(base_path, qr_name)
        img_qr.save(qr_path)

        # -------------------------
        # 3️⃣ Recupera i dati del timesheet
        # -------------------------
        rows = HelpderDB.sql_query(f"""
            SELECT t.*, c.companyname, c.address, c.city, c.email, c.phonenumber, 
                   u.firstname, u.lastname 
            FROM user_timesheet AS t 
            JOIN user_company AS c ON t.recordidcompany_=c.recordid_ 
            JOIN sys_user AS u ON t.user = u.id 
            WHERE t.recordid_='{recordid}'
        """)

        if not rows:
            return JsonResponse({'error': f'Timesheet {recordid} non trovato'}, status=404)

        row = rows[0]
        for value in row:
            row[value] = row[value] or ''

        
        import pathlib
        firma_path = pathlib.Path(settings.STATIC_ROOT) / "pdf" / filename_firma
        qr_path = pathlib.Path(settings.STATIC_ROOT) / "pdf" / qr_name

        server = os.environ.get('BIXENGINE_SERVER')
        # firma_url = f"{server}/static/pdf/{filename_firma}"
        # qr_url = f"{server}/static/pdf/{qr_name}"

        # -------------------------
        # 4️⃣ Prepara i dati per il template
        # -------------------------
        static_img_path = os.path.join(settings.BASE_DIR, "customapp_swissbix/static/images")
        row['recordid'] = recordid
        row['logoUrl'] = to_base64(os.path.join(static_img_path, "logo_w.png"))
        row['qrUrl'] = to_base64(qr_path.resolve())
        row['signatureUrl'] = to_base64(firma_path.resolve())


        condition_list = [f"recordidtimesheet_='{recordid}'"]
        timesheetlines = UserTable('timesheetline').get_records(conditions_list=condition_list)
        for line in timesheetlines:
            product = UserRecord('product', line.get('recordidproduct_'))
            line['product'] = product.values.get('name') or ''
            line['description'] = line.get('description') or ''
            line['actualquantity'] = line.get('actualquantity') or ''
        row['timesheetlines'] = timesheetlines

        # -------------------------
        # 5️⃣ Genera il PDF
        # -------------------------
        content = render_to_string('pdf/timesheet_signature.html', row)
        pdf_filename = f"allegato.pdf"
        pdf_path = os.path.join(base_path, pdf_filename)

        css = """
                /* Rimuove l'altezza forzata che spesso crea la seconda pagina */
                html, body { 
                    height: auto !important; 
                    overflow: hidden !important; 
                    margin: 0 !important; 
                    padding: 0 !important;
                }
                
                /* Evita che il footer fixed forzi un salto pagina se troppo vicino al bordo */
                div[style*="position:fixed"] {
                    position: absolute !important;
                    bottom: 0 !important;
                }

                /* Rimuove spazi bianchi finali indesiderati */
                body:after {
                    content: none !important;
                }
                
                /* Ottimizzazione scala */
                body {
                    zoom: 0.75;
                }
        """
        
        BrowserManager.generate_pdf(
            html_content=content, 
            output_path=pdf_path, 
            css_styles=css
        )

        # -------------------------
        # 6️⃣ Crea il record allegato
        # -------------------------
        attachment_record = UserRecord('attachment')
        attachment_record.values['type'] = "Signature"
        attachment_record.values['recordidtimesheet_'] = recordid
        attachment_record.save()

        uploads_dir = os.path.join(settings.UPLOADS_ROOT, f"attachment/{attachment_record.values['recordidtimesheet_']}")
        os.makedirs(uploads_dir, exist_ok=True)

        final_pdf_path = os.path.join(uploads_dir, pdf_filename)
        shutil.copy(pdf_path, final_pdf_path)

        relative_path = f"attachment/{attachment_record.values['recordidtimesheet_']}/{pdf_filename}"
        attachment_record.values['file'] = relative_path
        attachment_record.values['filename'] = pdf_filename
        attachment_record.save()

        # -------------------------
        # 7️⃣ Risposta finale
        # -------------------------
        return JsonResponse({
            'success': True,
            'message': 'PDF con firma salvato con successo',
            'recordid': recordid,
            'attachment_recordid': attachment_record.recordid,
            'pdf_filename': pdf_filename,
            'pdf_path': relative_path
        })

    except Exception as e:
        print(f"Error in save_signature: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
     

from commonapp.utils.email_sender import *
def save_email_timesheet(request):
    """
    Crea un record email collegato ad un timesheet e allega il PDF del timesheet.
    Si aspetta:
    {
        "recordidTimesheet": "XXXX",
        "recordidAttachment": "YYYY",   # opzionale
        "mailbody": "",
        "subject": "",
        "recipient": ""
    }
    """
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    try:
        data = json.loads(request.body)

        recordid_timesheet = data.get("recordid")
        recordid_attachment = data.get("recordidAttachment")

        if not recordid_timesheet:
            return JsonResponse({"error": "Missing recordidTimesheet"}, status=400)

        timesheet = UserRecord("timesheet", recordid_timesheet)

        # INFO PRINCIPALI
        company_id = timesheet.values.get("recordidcompany_")
        company_name = timesheet.fields["recordidcompany_"]["convertedvalue"]

        # DESTINATARIO EMAIL
        recipient = data.get("recipient")

        if not recipient:
            # DESTINATARIO EMAIL
            # esempio: email al responsabile (creator)
            recipient = UserRecord('company', company_id).values['email']
            if not recipient:
                return JsonResponse({"status": "error", "messagecustom": "L'azienda non ha un email associata."}, status=400)


        # DATI PER IL CORPO EMAIL
        descrizione = timesheet.values.get("description", "Nessuna descrizione")
        data_lavoro = timesheet.values.get("date")

        if isinstance(data_lavoro, datetime.date):
            data_lavoro = data_lavoro.strftime("%d.%m.%Y")
        elif isinstance(data_lavoro, str):
            try:
                data_lavoro = datetime.datetime.strptime(data_lavoro, "%Y-%m-%d").strftime("%d.%m.%Y")
            except ValueError:
                data_lavoro = "Data non valida"
        else:
            data_lavoro = "Nessuna data"
        
        worktime = timesheet.values.get("worktime", "Nessun tempo di lavoro")
        if not worktime:
            worktime = "Nessun tempo di lavoro"
        traveltime = timesheet.values.get("traveltime", "Nessun tempo di trasferta")
        if not traveltime:
            traveltime = "Nessun tempo di trasferta"
        totalprice = timesheet.values.get("totalprice", "Nessun prezzo totale")

        # PROGETTO
        project = timesheet.fields["recordidproject_"]["convertedvalue"] \
            if timesheet.values.get("recordidproject_") else ""

        # TASK (opzionale)
        task = timesheet.fields["recordidtask_"]["convertedvalue"] \
            if timesheet.values.get("recordidtask_") else ""

        # UTENTE CHE HA FATTO IL LAVORO
        worker_name = timesheet.fields["user"]["convertedvalue"]

        # SUBJECT
        subject = f"{company_name}: Rapporto di lavoro {recordid_timesheet.lstrip('0')} del {data_lavoro}"

        # ----------------------------------------------------
        #               CORPO EMAIL HTML
        # ----------------------------------------------------
        mailbody = f"""
        <p style="margin:0 0 10px 0;">
            La ringraziamo per la fiducia e le trasmettiamo una copia del rapporto di lavoro eseguito in PDF.
            <br/>
            I dettagli principali dell’intervento sono i seguenti:
        </p>

        <table style="border-collapse:collapse; width:100%; font-size:14px;">
            <tr><td style="padding:4px 0; font-weight:bold;">Tecnico:</td><td>{worker_name}</td></tr>
            <tr><td style="padding:4px 0; font-weight:bold;">Data:</td><td>{data_lavoro}</td></tr>
            <tr><td style="padding:4px 0; font-weight:bold;">Descrizione:</td><td>{descrizione}</td></tr>
            <tr><td style="padding:4px 0; font-weight:bold;">Tempo di lavoro:</td><td>{worktime}</td></tr>
            <tr><td style="padding:4px 0; font-weight:bold;">Tempo della trasferta:</td><td>{traveltime}</td></tr>
        """

        if totalprice:
            mailbody += f"<tr><td style=\"padding:4px 0; font-weight:bold;\">Prezzo totale:</td><td>{totalprice}</td></tr>"

        if project:
            mailbody += f"""
            <tr><td style="padding:4px 0; font-weight:bold;">Progetto:</td><td>{project}</td></tr>
            """

        if task:
            mailbody += f"""
            <tr><td style="padding:4px 0; font-weight:bold;">Attività:</td><td>{task}</td></tr>
            """

        mailbody += "</table>"

        mailbody += f"""
        <p style="margin:16px 0 0 0;">
            Per qualsiasi informazione o chiarimento in merito al lavoro svolto, rimaniamo volentieri a disposizione scrivendo a <a href="mailto:backoffice@swissbix.ch">backoffice@swissbix.ch</a>.
            <br/>
            Per richieste di carattere tecnico potete contattarci ad <a href="mailto:helpdesk@swissbix.ch">helpdesk@swissbix.ch</a>.
        </p>

        <p style="margin:0;">Cordiali saluti,</p>
        <p style="margin:0;">Swissbix SA</p>
        """


        # Dati email da salvare

        # --- Gestione allegato ---
        file_rel_path = ""
        
        if recordid_attachment:
            try:
                attach_record = UserRecord("attachment", recordid_attachment)
                file_rel_path = attach_record.values.get("file", "")
            except Exception as ex:
                print("Errore nel recupero allegato tramite ID:", ex)
        else:
            # Fallback: find the latest Signature attachment for this timesheet
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT file
                    FROM user_attachment
                    WHERE recordidtimesheet_ = %s
                      AND type = 'Signature'
                      AND deleted_ = 'N'
                    ORDER BY creation_ DESC
                    LIMIT 1
                """, [recordid_timesheet])
                row = cursor.fetchone()
                if row and row[0]:
                    file_rel_path = row[0]
                    
        if not file_rel_path:
            print("Errore nel recupero allegato:", ex)
            return JsonResponse({"error": "Nessun allegato di firma trovato per questo timesheet."}, status=400)

        email_data = {
            "to": recipient,
            "subject": subject,
            "text": mailbody,
            "cc": "",
            "bcc": "",
            "attachment_relativepath": file_rel_path if file_rel_path else "",
            "attachment_name": os.path.basename(file_rel_path) if file_rel_path else ""
        }
        # Salvataggio finale email
        EmailSender.save_email("timesheet", recordid_timesheet, email_data)

        return JsonResponse({"success": True})

    except Exception as e:
        print("Error in save_email_timesheet:", e)
        return JsonResponse({"error": str(e)}, status=500)


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

        

        residualhours = servicecontract.values.get('residualhours', 'N/A')
        
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
        new_record.values['invoiceno'] = f"F-{data.get('invoiceno')}"
        new_record.values['startdate'] = data.get('startdate')
        new_record.values['status'] = 'In Progress'
        new_record.values['progress'] = 0
        new_record.values['recordidcompany_'] = old_record.values['recordidcompany_']

        new_record.save()

        return HttpResponse(f"Nuovo rinnovo effettuato")
    except Exception as e:
        logger.error(f"Errore nel rinnovo: {str(e)}")
        return JsonResponse({'error': f'Errore nel rinnovo: {str(e)}'}, status=500)
