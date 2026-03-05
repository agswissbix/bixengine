from django.shortcuts import render
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse, StreamingHttpResponse
import pyodbc
import environ
from django.conf import settings
from commonapp.bixmodels.user_record import *
from commonapp.bixmodels.user_table import *
from commonapp.bixmodels.helper_db import *
from commonapp.helper import *
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from datetime import *
import qrcode
import base64
import pdfkit

from commonapp.helper import Helper
from commonapp.bixmodels.user_record import UserRecord
from commonapp.bixmodels.user_table import UserTable
from commonapp.bixmodels.helper_db import HelpderDB

from commonapp import views

from commonapp.utils.email_sender import *

# Initialize environment variables
env = environ.Env()
environ.Env.read_env()

def save_record_fields(tableid,recordid, old_record=""):

    # ---TASK---
    if tableid == 'task':
        from customapp_swissbix.services.custom_save.task_services import TaskService
        records_to_save = TaskService.process_task(recordid, old_record)
        for rel_tableid, rel_recordid in records_to_save:
            save_record_fields(tableid=rel_tableid, recordid=rel_recordid)

    # ---ASSENZE---
    if tableid == 'assenze':
        assenza_record = UserRecord('assenze', recordid)
        tipo_assenza=assenza_record.values['tipo_assenza']
        if tipo_assenza!='Malattia':
            dipendente_recordid = assenza_record.values['recordiddipendente_']
            save_record_fields(tableid='dipendente', recordid=dipendente_recordid)

        employee_record = UserRecord('dipendente', assenza_record.values['recordiddipendente_'])
        assenza_record.userid = employee_record.values['utente']
        event_record = assenza_record.save_record_for_event()

        save_record_fields('events', event_record.recordid)

    # ---TIMESHEET---
    if tableid == 'timesheet':
        from customapp_swissbix.services.custom_save.timesheet_services import TimesheetService
        records_to_save = TimesheetService.process_timesheet(recordid)
        for rel_tableid, rel_recordid in records_to_save:
            save_record_fields(tableid=rel_tableid, recordid=rel_recordid)


    # ---SERVICE CONTRACT
    if tableid == 'servicecontract':
        from customapp_swissbix.services.custom_save.servicecontract_services import ServiceContractService
        records_to_save = ServiceContractService.process_servicecontract(recordid)
        for rel_tableid, rel_recordid in records_to_save:
            save_record_fields(tableid=rel_tableid, recordid=rel_recordid)

    # ---DEAL---
    if tableid == 'deal':
        from customapp_swissbix.services.custom_save.deal_services import DealService
        records_to_save = DealService.process_deal(recordid)
        for rel_tableid, rel_recordid in records_to_save:
            save_record_fields(tableid=rel_tableid, recordid=rel_recordid)


    # ---DEALLINE
    if tableid == 'dealline':
        dealline_record = UserRecord('dealline', recordid)
        save_record_fields(tableid='deal', recordid=dealline_record.values['recordiddeal_'])


    # ---PROJECT
    if tableid == 'project':
        from customapp_swissbix.services.custom_save.project_services import ProjectService
        records_to_save = ProjectService.process_project(recordid)
        for rel_tableid, rel_recordid in records_to_save:
            save_record_fields(tableid=rel_tableid, recordid=rel_recordid)



    # ---TIMETRACKING---
    if tableid == 'timetracking':
        timetracking_record = UserRecord('timetracking', recordid)
        if Helper.isempty(timetracking_record.values['start']):
                timetracking_record.values['start'] = datetime.datetime.now().strftime("%H:%M")
        if timetracking_record.values['stato'] == 'Terminato':
            if not timetracking_record.values['end']:
                timetracking_record.values['end'] = datetime.datetime.now().strftime("%H:%M")
            time_format = '%H:%M'
            start = datetime.datetime.strptime(timetracking_record.values['start'], time_format)
            end = datetime.datetime.strptime(timetracking_record.values['end'], time_format)
            time_difference = end - start

            total_minutes = time_difference.total_seconds() / 60
            hours, minutes = divmod(total_minutes, 60)
            formatted_time = "{:02}:{:02}".format(int(hours), int(minutes))

            timetracking_record.values['worktime_string'] = str(formatted_time)

            hours = time_difference.total_seconds() / 3600
            timetracking_record.values['worktime'] = round(hours, 2)

        if not timetracking_record.values['start']:
            timetracking_record.values['start'] =  datetime.datetime.now().strftime("%H:%M")
        timetracking_record.save()

    # ---ATTACHMENT---
    if tableid == 'attachment':
        attachment_record = UserRecord('attachment', recordid)
        filename= attachment_record.values['filename']
        file_relative_path = attachment_record.values['file']
        recordiddeal = attachment_record.values['recordiddeal_']
        if not Helper.isempty(recordiddeal):
            adiuto_uplodad=attachment_record.values['adiuto_uploaded']
            if  adiuto_uplodad!='Si':
                filename_adiuto= f"deal_{recordiddeal}_{recordid}_{filename}"
                
                # 1. Definisci il path di destinazione (sempre relativo a MEDIA_ROOT)
                dest_relative_path = f"Adiuto/{filename_adiuto}"

                try:
                    # 2. Apri il file sorgente usando default_storage
                    # 'with' garantisce che il file venga chiuso correttamente
                    with default_storage.open(file_relative_path, 'rb') as source_file:
                        
                        # 3. Salva il contenuto letto in una nuova posizione
                        # default_storage.save riceve il path relativo e l'oggetto File
                        # e gestisce automaticamente la scrittura.
                        new_path = default_storage.save(dest_relative_path, source_file)
                        attachment_record.values['adiuto_uploaded'] = "Si"
                        attachment_record.save()
                        # (Opzionale) 'new_path' contiene il percorso esatto del file salvato
                        # (potrebbe avere un hash se il file esisteva già)
                        print(f"File copiato con successo in: {new_path}")

                except FileNotFoundError:
                    print(f"ERRORE: Impossibile copiare. File sorgente non trovato in: {file_relative_path}")
                except Exception as e:
                    # Gestisci altri possibili errori (es. permessi)
                    print(f"ERRORE durante la copia del file: {e}")

    # ---DIPENDENTE---
    if tableid == 'dipendente':
        dipendente_record = UserRecord('dipendente', recordid)

        #calcolo saldo vacanze
        saldovacanze_iniziale= Helper.safe_float(dipendente_record.values['saldovacanze_iniziale'])
        saldovacanze=saldovacanze_iniziale
        assenze_dict_list=dipendente_record.get_linkedrecords_dict('assenze')
        for assenza in assenze_dict_list:
            tipo_assenza=assenza.get('tipo_assenza')
            if tipo_assenza == 'Vacanze':
                giorni_assenza= Helper.safe_float(assenza.get('giorni'))
                saldovacanze=saldovacanze-giorni_assenza

        dipendente_record.values['saldovacanze'] = saldovacanze
        dipendente_record.save()

    # ---EVENT---
    if tableid == 'events':
        from customapp_swissbix.services.custom_save.event_services import EventService
        records_to_save = EventService.process_event(recordid)
        for rel_tableid, rel_recordid in records_to_save:
            save_record_fields(tableid=rel_tableid, recordid=rel_recordid)

    # --- NOTIFICATIONS ---
    if tableid == 'notification':
        notification_record = UserRecord('notifications', recordid)

        if not notification_record.values['date']:
            notification_record.values['date'] = datetime.datetime.now().strftime("%Y-%m-%d")

        if not notification_record.values['time']:
            notification_record.values['time'] = datetime.datetime.now().strftime("%H:%M")

        views.create_notification(recordid)

        notification_record.save()

def delete_record(tableid, recordid):    
    # ---TIMESHEET---
    if tableid == 'timesheet':
        timesheet = UserRecord('timesheet', recordid)
        if timesheet.values.get('recordidproject_'):
            save_record_fields(tableid='project', recordid=timesheet.values.get('recordidproject_'))
        if timesheet.values.get('recordidservicecontract_'):
            save_record_fields(tableid='servicecontract', recordid=timesheet.values.get('recordidservicecontract_'))

    # ---DEALLINE---
    elif tableid == 'dealline':
        dealline = UserRecord('dealline', recordid)
        if dealline.values.get('recordiddeal_'):
            save_record_fields(tableid='deal', recordid=dealline.values.get('recordiddeal_'))

    # ---PROJECT---
    elif tableid == 'project':
        project = UserRecord('project', recordid)
        save_record_fields(tableid='project', recordid=recordid)

    # ---ASSENZE---
    elif tableid == 'assenze':
        assenze = UserRecord('assenze', recordid)
        if assenze.values.get('recordiddipendente_'):
            save_record_fields(tableid='dipendente', recordid=assenze.values.get('recordiddipendente_'))



def card_task_pianificaperoggi(recordid):
    print("card_task_pianificaperoggi")


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
            if invoiceline_quantity == "0.00":
                invoiceline_quantity="0.0001"
            invoiceline_description= invoiceline['description']
            invoiceline_description_html = invoiceline_description.replace('\n', '<br>')

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
            "footer": "Vi ringraziamo per la vostra fiducia, in caso di disaccordo, vi preghiamo di notificarcelo entro 7 giorni. <br/>Rimaniamo a vostra disposizione per qualsiasi domanda,<br/><br/>Con i nostri più cordiali saluti, Swissbix SA",
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

        


        payload = """
            {
                "title": "TEST3",
                "contact_id": 308,
                "user_id": 1,
                "language_id": 1,
                "currency_id": 1,
                "payment_type_id": 1,
                "header": "",
                "footer": "We hope that our offer meets your expectations and will be happy to answer your questions.",
                "mwst_type": 0,
                "mwst_is_net": true,
                "show_position_taxes": false,
                "is_valid_from": "2025-10-01",
                "is_valid_to": "2025-10-21",
                "template_slug": "5a9c000702cf22422a8b4641",
                "positions":[{"text":"Interventi</b>","type":"KbPositionText"},{"text":"TEST 25/06/2025 Galli Alessandro </b></span>","tax_id":"39","account_id":"155","unit_id":2,"amount":"1","unit_price":"140","type":"KbPositionCustom"}]
            }
            """

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




def calculate_dependent_fields(request):
    data = json.loads(request.body)
    updated_fields = {}
    recordid=data.get('recordid')
    tableid=data.get('tableid')
    fields = data.get('fields', {})
    
    #---DEALLINE---
    if tableid=='dealline':
        updated_fields = Helper.compute_dealline_fields(fields, UserRecord)
    
    #---ASSENZE---
    if tableid=='assenze':
        fields= data.get('fields')
        #giorni= Helper.safe_float(fields.get('giorni', 0))
        #ore= Helper.safe_float(fields.get('ore', 0))
        #if ore == '' or ore is None:
         #   ore_updated=giorni * 8
          #  updated_fields['ore']=ore_updated   

    return JsonResponse({'status': 'success', 'updated_fields': updated_fields})


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

def swissbix_create_timesheet_from_timetracking(request):
    print("Function: swissbix_create_timesheet_from_timetracking")
    from customapp_swissbix.script import get_timetracking_ai_summary, check_ai_server

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

    from customapp_swissbix.script import stop_active_timetracking
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
    from customapp_swissbix.script import check_ai_server, get_timesheet_ai_summary

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
