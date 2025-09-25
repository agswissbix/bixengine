import datetime
from datetime import timedelta
import uuid
import base64
import logging
from pydoc import html
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.csrf import csrf_exempt
import pdfkit
from io import BytesIO
from django.contrib.staticfiles import finders
from django.template.loader import get_template
from bixengine.settings import BASE_DIR
from commonapp.bixmodels.user_record import *
from commonapp.bixmodels.user_table import *
from commonapp.bixmodels.helper_db import *
from commonapp.helper import *
import qrcode
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.oxml import OxmlElement
from docx.enum.section import WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docxcompose.composer import Composer

logger = logging.getLogger(__name__)


def get_activemind(request):
    response_data = {}
    try:
        data = json.loads(request.body)
        recordid_deal = data.get('recordIdTrattativa', None)
        if recordid_deal:
            record_deal=UserRecord('deal',recordid_deal)
            recordid_company=record_deal.values.get('recordidcompany_', None)
            if recordid_company:
                record_company=UserRecord('company',recordid_company)
                response_data = {
                "cliente": {
                    "nome": record_company.values.get('companyname', ''),
                    "indirizzo": record_company.values.get('address', ''),
                    "citta": record_company.values.get('city', '')
                }
            }
        return JsonResponse(response_data)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Si è verificato un errore inatteso: {str(e)}'
        }, status=500)

def save_activemind(request):
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Metodo non permesso. Utilizza POST.'
        }, status=405)

    try:
        request_body = json.loads(request.body)
        data=request_body.get('data', {})
        recordid_deal = data.get('recordIdTrattativa', None)
        #section1
        section1=data.get('section1', {})
        selectdTier=section1.get('selectedTier', '')
        price=section1.get('price', '')
        record_dealline=UserRecord('dealline')
        record_dealline.values['recordiddeal_']=recordid_deal
        record_dealline.values['name']=selectdTier
        record_dealline.values['price']=price
        record_dealline.save()

        #section2

        #section3

        return JsonResponse({
            'success': True,
            'message': 'Dati ricevuti e processati con successo.'
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Si è verificato un errore inatteso: {str(e)}'
        }, status=500)
    

@csrf_exempt
def print_pdf_activemind(request):
    """
    Generate a PDF for ActiveMind services
    """
    try:
        data = json.loads(request.body)
        
        services_data = data.get('data', {})
        recordid_deal = data.get('idTrattativa', None)

        # Recupero info cliente
        cliente = {}
        if recordid_deal:
            record_deal = UserRecord('deal', recordid_deal)
            recordid_company = record_deal.values.get('recordidcompany_', None)
            if recordid_company:
                record_company = UserRecord('company', recordid_company)
                cliente = {
                    "nome": record_company.values.get('companyname', ''),
                    "indirizzo": record_company.values.get('address', ''),
                    "citta": record_company.values.get('city', '')
                }

        # Firma digitale (base64 → file immagine)
        digital_signature_b64 = data.get('signature', None)
        nameSignature = data.get('nameSignature', '')

        signature_url = None
        if digital_signature_b64:
            try:
                # Rimuovo eventuale prefisso "data:image/png;base64,"
                if "," in digital_signature_b64:
                    digital_signature_b64 = digital_signature_b64.split(",")[1]

                signature_bytes = base64.b64decode(digital_signature_b64)

                # Nome univoco
                filename = f"signature_{uuid.uuid4().hex}.png"
                # TODO verificare path corretto
                signature_path = os.path.join(BASE_DIR, "customapp_swissbix/static/signatures", filename)
                os.makedirs(os.path.dirname(signature_path), exist_ok=True)

                # Salvo il file
                with open(signature_path, "wb") as f:
                    f.write(signature_bytes)

                # Creo URL relativo a MEDIA_URL (usato nel template)
                signature_url = f"signatures/{filename}"
            except Exception as e:
                logger.error(f"Errore salvataggio firma: {e}")

        # Calcolo i totali
        section1_total = services_data.get('section1', {}).get('price', 0)
        section2_total = sum(
            service.get('quantity', 0) * service.get('unitPrice', 0)
            for service in services_data.get('section2', {}).values()
            if isinstance(service, dict)
        )
        tier_descriptions = {
            'tier1': 'Fino a 5 PC + server',
            'tier2': 'Fino a 10 PC + server', 
            'tier3': 'Fino a 15 PC + server',
            'tier4': 'Fino a 20 PC + server'
        }
        selected_tier = services_data.get('section1', {}).get('selectedTier', '')
        tier_display = tier_descriptions.get(selected_tier, selected_tier)

        from customapp_swissbix.mock.activeMind.services import services as services_data_mock
        services_data.setdefault('section3', {})['features'] = services_data_mock

        # Preparo contesto per template
        context = {
            'client_info': cliente,
            'services_data': services_data,
            'section1_total': section1_total,
            'section2_total': section2_total,
            'grand_total': section2_total,
            'tier_display': tier_display,
            'digital_signature_url': signature_url,
            'nameSignature': nameSignature,
            'date': datetime.datetime.now().strftime("%d/%m/%Y"),
            'limit_acceptance_date': (datetime.datetime.now() + timedelta(days=10)).strftime("%d/%m/%Y"),
        }
        
        # Render HTML
        template = get_template('activeMind/pdf_template.html')
        html = template.render(context)

        from xhtml2pdf import pisa 
        # Genera PDF
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = 'inline; filename="offerta.pdf"'

        pisa_status = pisa.CreatePDF(
            html, dest=response, link_callback=link_callback
        )

        if pisa_status.err:
            return HttpResponse("Errore durante la creazione del PDF", status=500)
        return response
            
    except Exception as e:
        logger.error(f"Errore nella generazione PDF: {str(e)}")
        return JsonResponse({'error': f'Errore nella generazione del PDF: {str(e)}'}, status=500)


def link_callback(uri, rel):
    """
    Converti i percorsi HTML (es. /static/ o STATIC_URL) in percorsi assoluti
    leggibili da xhtml2pdf.
    """
    # Cerca nei files statici gestiti da Django
    result = finders.find(uri.replace(settings.STATIC_URL, ""))
    if result:
        if not isinstance(result, (list, tuple)):
            result = [result]
        return result[0]

    # Prova a gestire MEDIA_URL
    if uri.startswith(settings.MEDIA_URL):
        path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, ""))
        if os.path.isfile(path):
            return path

    raise Exception(f"Immagine o file statico non trovato: {uri}")

def get_services_activemind(request):
    from customapp_swissbix.mock.activeMind.services import services as services_data_mock
    # print(services_data_mock)
    return JsonResponse({"services": services_data_mock}, safe=False)

def get_conditions_activemind(request):
    from customapp_swissbix.mock.activeMind.conditions import frequencies as conditions_data_mock
    return JsonResponse({"frequencies": conditions_data_mock}, safe=False)


def get_record_badge_swissbix_company(request):
    data = json.loads(request.body)
    tableid= data.get("tableid")
    recordid= data.get("recordid")

    record=UserRecord(tableid,recordid)
    return_badgeItems={}

    # sql=f"SELECT logo FROM user_company WHERE recordid_='{recordid}' AND deleted_='N'"
    # company_logo=HelpderDB.sql_query_value(sql, 'logo')
    company_logo=''

    sql=f"SELECT email, phonenumber, address FROM user_company WHERE recordid_='{recordid}' AND deleted_='N'"
    company_email  =HelpderDB.sql_query_value(sql, 'email')
    company_address=HelpderDB.sql_query_value(sql, 'phonenumber')
    company_phone=HelpderDB.sql_query_value(sql, 'address')


    sql=f"SELECT COUNT(worktime_decimal) as total FROM user_timesheet WHERE recordidcompany_='{recordid}' AND deleted_='N'"
    total_timesheet=HelpderDB.sql_query_value(sql, 'total')

    sql=f"SELECT COUNT(*) as total FROM user_deal WHERE dealstatus='Vinta' AND recordidcompany_='{recordid}' AND deleted_='N'"
    total_deals=HelpderDB.sql_query_value(sql, 'total')

    sql=f"SELECT customertype FROM user_company WHERE recordid_='{recordid}' AND deleted_='N'"
    customertype=HelpderDB.sql_query_value(sql, 'customertype')

    sql=f"SELECT paymentstatus FROM user_company WHERE recordid_='{recordid}' AND deleted_='N'"
    paymentstatus=HelpderDB.sql_query_value(sql, 'paymentstatus')

    sql=f"SELECT salesuser FROM user_company WHERE recordid_='{recordid}' AND deleted_='N'"
    salesuser=HelpderDB.sql_query_value(sql, 'salesuser')
    if salesuser:
        from commonapp.models import SysUser
        user_sales=SysUser.objects.filter(id=salesuser).first()
        return_badgeItems["sales_user_name"] = user_sales.firstname + ' ' + user_sales.lastname if user_sales else ''
        return_badgeItems["sales_user_photo"] = user_sales.id if user_sales else ''
    else:
        return_badgeItems["sales_user_name"] = ''
        return_badgeItems["sales_user_photo"] = ''

    sql=f"SELECT SUM(totalnet) as total FROM user_invoice WHERE recordidcompany_='{recordid}' AND status='Paid' AND deleted_='N'"
    total_invoices=round(HelpderDB.sql_query_value(sql, 'total'), 0) if HelpderDB.sql_query_value(sql, 'total') else 0.00

    return_badgeItems["company_logo"] = company_logo
    return_badgeItems["company_name"] = record.values.get("companyname", '')
    return_badgeItems["company_email"] = company_email  
    return_badgeItems["company_address"] = company_address
    return_badgeItems["company_phone"] = company_phone
    return_badgeItems["payment_status"] = paymentstatus 
    return_badgeItems["customer_type"] = customertype
    return_badgeItems["total_timesheet"] = total_timesheet
    return_badgeItems["total_deals"] = total_deals
    return_badgeItems["total_invoices"] = total_invoices
    response={ "badgeItems": return_badgeItems}
    return JsonResponse(response)   


def get_record_badge_swissbix_deals(request):
    data = json.loads(request.body)
    tableid= data.get("tableid")
    recordid= data.get("recordid")

    record=UserRecord(tableid,recordid)
    return_badgeItems={}

    sql=f"SELECT dealname, amount , effectivemargin, dealuser1, dealstage, recordidcompany_ FROM user_deal WHERE recordid_='{recordid}' AND deleted_='N'"

    deal_name=HelpderDB.sql_query_value(sql, 'dealname')
    deal_amount=HelpderDB.sql_query_value(sql, 'amount')
    deal_effectivemargin=HelpderDB.sql_query_value(sql, 'effectivemargin')
    dealstage=HelpderDB.sql_query_value(sql, 'dealstage')


    salesuser=HelpderDB.sql_query_value(sql, 'dealuser1')
    if salesuser:
        from commonapp.models import SysUser
        user_sales=SysUser.objects.filter(id=salesuser).first()
        return_badgeItems["sales_user_name"] = user_sales.firstname + ' ' + user_sales.lastname if user_sales else ''
        return_badgeItems["sales_user_photo"] = user_sales.id if user_sales else ''
    else:
        return_badgeItems["sales_user_name"] = ''
        return_badgeItems["sales_user_photo"] = ''

    recordidcompany_=HelpderDB.sql_query_value(sql, 'recordidcompany_')
    sql=f"SELECT companyname FROM user_company WHERE recordid_='{recordidcompany_}' AND deleted_='N'"
    company_name=HelpderDB.sql_query_value(sql, 'companyname')

    return_badgeItems["deal_name"] = deal_name
    return_badgeItems["deal_amount"] = deal_amount
    return_badgeItems["deal_effectivemargin"] = deal_effectivemargin
    return_badgeItems["company_name"] = company_name
    return_badgeItems["deal_stage"] = dealstage
    response={ "badgeItems": return_badgeItems}
    return JsonResponse(response)   

def get_record_badge_swissbix_project(request):
    data = json.loads(request.body)
    tableid= data.get("tableid")
    recordid= data.get("recordid")

    record=UserRecord(tableid,recordid)
    return_badgeItems={}

    sql=f"SELECT projectname, assignedto, status, expectedhours, usedhours, residualhours, recordidcompany_ FROM user_project WHERE recordid_='{recordid}' AND deleted_='N'"

    project_name=HelpderDB.sql_query_value(sql, 'projectname')
    project_status=HelpderDB.sql_query_value(sql, 'status')
    expected_hours=HelpderDB.sql_query_value(sql, 'expectedhours')
    used_hours=HelpderDB.sql_query_value(sql, 'usedhours')
    residual_hours=HelpderDB.sql_query_value(sql, 'residualhours')
    print(f"expected_hours: {expected_hours}, used_hours: {used_hours}, residual_hours: {residual_hours}")
    recordidcompany_=HelpderDB.sql_query_value(sql, 'recordidcompany_')


    manager=HelpderDB.sql_query_value(sql, 'assignedto')
    if manager:
        from commonapp.models import SysUser
        user_sales=SysUser.objects.filter(id=manager).first()
        return_badgeItems["manager_name"] = user_sales.firstname + ' ' + user_sales.lastname if user_sales else ''
        return_badgeItems["manager_photo"] = user_sales.id if user_sales else ''
    else:
        return_badgeItems["manager_name"] = ''
        return_badgeItems["manager_photo"] = ''
    
    sql=f"SELECT companyname FROM user_company WHERE recordid_='{recordidcompany_}' AND deleted_='N'"
    company_name=HelpderDB.sql_query_value(sql, 'companyname')

    return_badgeItems["project_name"] = project_name
    return_badgeItems["project_status"] = project_status
    return_badgeItems["expected_hours"] = expected_hours
    return_badgeItems["used_hours"] = used_hours
    return_badgeItems["residual_hours"] = residual_hours
    return_badgeItems["company_name"] = company_name
    response={ "badgeItems": return_badgeItems}
    return JsonResponse(response)

def stampa_offerta(request):
    data = json.loads(request.body)
    recordid = data.get('recordid')
    recordid_deal=recordid
    #tableid = data.get('tableid')
    tableid= 'deal'

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=0,
    )

    today = datetime.date.today()
    d1 = today.strftime("%d/%m/%Y")

    qrcontent = str(tableid) + '_' + str(recordid)

    data = qrcontent
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    qr_name = 'qrcode' + uuid.uuid4().hex + '.png'

    img.save(qr_name)

    deal_record = UserRecord('deal', recordid_deal)
    dealuser1 = deal_record.values['dealuser1']
    closedate = deal_record.values['closedate']
    #TODO
    #dealline_records = deal_record.get_linkedrecords('dealline')
    dealline_records=[]

    dealname = deal_record.values['dealname']
    amount = deal_record.values['amount']
    company_record = UserRecord('company', deal_record.values['recordidcompany_'])

    deal_description = deal_record.values['description']

    companyname = company_record.values['companyname']
    address = company_record.values['address']
    city = company_record.values['city']

    
    user_record=HelpderDB.sql_query_row(f"SELECT * FROM sys_user WHERE id ='{dealuser1}'")
    user = user_record['firstname'] + ' ' + user_record['lastname']

    id = uuid.uuid4().hex

    filename = dealname + id + '.docx'
    filename = filename.replace("/", "-")
    filename = filename.replace("\\", "-")
    filename = filename.replace("'", "")
    filename = filename.replace('"', "")

    # instead of creating a word i want to open one

    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Navigate to the 'views' directory and locate 'template.docx'
    file_path = os.path.join(script_dir, 'template.docx')

    # doc = Document(file_path)

    doc = Document(file_path)

    paragraph = doc.add_paragraph()
    run = paragraph.add_run()
    picture = run.add_picture(qr_name, width=Inches(1))

    # Set the paragraph alignment to right
    paragraph.alignment = 2  # 2 corresponds to the right alignment

    # Set spacing to minimize any additional space
    paragraph.paragraph_format.space_before = Inches(0)
    paragraph.paragraph_format.space_after = Inches(0)

    os.remove(qr_name)

    section = doc.sections[0]
    section.left_margin = Inches(1)
    section.top_margin = Inches(1)

    grey = RGBColor(0x89, 0x89, 0x89)

    p1 = doc.add_paragraph()
    text1 = f"Spett.le"
    run1 = p1.add_run(text1)
    font1 = run1.font
    font1.size = Pt(10.5)
    font1.name = 'Calibri'
    font1.bold = False
    font1.color.rgb = grey
    p1.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT


    p_companyname = doc.add_paragraph()
    text_companyname = f"{companyname}"
    run_companyname = p_companyname.add_run(text_companyname)
    font_companyname = run_companyname.font
    font_companyname.size = Pt(12)
    font_companyname.name = 'Calibri'
    font_companyname.bold = True
    font_companyname.color.rgb = grey
    p_companyname.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

    p2 = doc.add_paragraph()
    text2 = f"{address}, {city}"
    run2 = p2.add_run(text2)
    font2 = run2.font
    font2.size = Pt(10)
    font2.name = 'Calibri'
    font2.bold = False
    font2.color.rgb = grey
    p2.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

    p_space = doc.add_paragraph()
    text_space = ''
    run_space = p_space.add_run(text_space)
    font_space = run_space.font
    font_space.size = Pt(10)
    font_space.name = 'Calibri'
    font_space.bold = False
    font_space.italic = True
    p_space.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

    p_date = doc.add_paragraph()
    text_date = f"Massagno {d1}"
    run_date = p_date.add_run(text_date)
    font_date = run_date.font
    font_date.size = Pt(11)
    font_date.name = 'Calibri'
    font_date.bold = True
    font_date.color.rgb = grey
    p_date.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

    p3 = doc.add_paragraph()
    text3 = dealname
    run3 = p3.add_run(text3)
    font3 = run3.font
    font3.size = Pt(16)
    font3.name = 'Lato'
    font3.color.rgb = RGBColor(0xC0, 0x00, 0x00)
    font3.bold = True
    p3.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

    """
    section = doc.sections[0]
    header = section.header
    watermark_path = 'background.jpg'  # Replace with your image path
    watermark = header.paragraphs[0].add_run().add_picture(watermark_path)
    watermark.alignment = WD_SECTION.DISTRIBUTE
    """

    """
    img_path = 'background.jpg'
    doc.add_picture(img_path, width=Inches(4))
    """
    doc.add_section(WD_SECTION.NEW_PAGE)

    p3 = doc.add_paragraph()
    text3 = 'Definizione Economica'
    run3 = p3.add_run(text3)
    font3 = run3.font
    font3.size = Pt(15)
    font3.name = 'Calibri'
    font3.color.rgb = RGBColor(0xC0, 0x00, 0x00)
    font3.bold = False
    p3.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

    dealline_records_length = len(dealline_records)

    table = doc.add_table(rows=dealline_records_length + 1, cols=4)  # +1 for header

    table.style = 'bixstyle'

    # Add the table header
    header_cells = ['Descrizione', 'Qt.', 'Prezzo unitario', 'Prezzo totale']
    for i, header_text in enumerate(header_cells):
        table.cell(0, i).text = header_text

    def format_chf(amount):
        if amount is None:
            return f"CHF 0.00"
        else:
            return f"CHF {amount:,.2f}".replace(",", "'")


    # Add data for each dealline
    for i, dealline in enumerate(dealline_records, start=1):
        row = table.rows[i]
        row.cells[0].text = str(dealline['name'])
        row.cells[0].paragraphs[0].runs[0].font.bold = True
        row.cells[1].text = "{:.2f}".format(dealline['quantity'])
        row.cells[2].text = format_chf(dealline['unitprice'])
        row.cells[3].text = format_chf (dealline['price'])
        row.cells[3].paragraphs[0].runs[0].font.bold = True

    p_space = doc.add_paragraph()
    text_space = ''
    run_space = p_space.add_run(text_space)

    p_space = doc.add_paragraph()
    text_space = ''
    run_space = p_space.add_run(text_space)

    doc.add_page_break()

    p_space = doc.add_paragraph()
    text_space = ''
    run_space = p_space.add_run(text_space)

    table2 = doc.add_table(rows=1, cols=1)

    table2.style = 'bixstyle'

    row_table2 = table2.rows[0]
    cell_table2 = row_table2.cells[0]
    cell_table2.text = 'Condizioni contrattuali di vendita'

    p_space = doc.add_paragraph()
    text_space = ''
    run_space = p_space.add_run(text_space)

    p5 = doc.add_paragraph()
    text5 = 'Contatti per Assistenza Tecnica:'
    run5 = p5.add_run(text5)
    font5 = run5.font
    font5.size = Pt(10)
    font5.name = 'Calibri'
    font5.bold = True
    font5.italic = False
    font5.color.rgb = grey
    p5.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

    p6 = doc.add_paragraph()  # Stile per elenco puntato con due punti
    text6 = '          •      Per tutte le richieste di assistenza: apertura ticket scrivendo all’indirizzo helpdesk@swissbix.ch  \n                  verrete ricontattati dal nostro servizio tecnico'
    run6 = p6.add_run(text6)
    font6 = run6.font
    font6.size = Pt(10)
    font6.name = 'Calibri'
    font6.bold = False
    font6.color.rgb = grey
    p6.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

    p7 = doc.add_paragraph()
    text7 = '          •      Orari di ufficio per supporto tecnico; dalle 9:00 alle 12:00 e dalle 14:00 alle 17:00'
    run7 = p7.add_run(text7)
    font7 = run7.font
    font7.size = Pt(10)
    font7.name = 'Calibri'
    font7.bold = False
    font7.color.rgb = grey
    p7.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

    p8 = doc.add_paragraph()
    text8 = 'Metodo di pagamento e fatturazione Hardware e Servizi:'
    run8 = p8.add_run(text8)
    font8 = run8.font
    font8.size = Pt(10)
    font8.name = 'Calibri'
    font8.bold = True
    font8.italic = False
    font8.color.rgb = grey
    p8.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

    p9 = doc.add_paragraph()
    text9 = '          •       Hardware e Consumabili: Acconto 50% all’ordine, Saldo a 20gg fine lavori'
    run9 = p9.add_run(text9)
    font9 = run9.font
    font9.size = Pt(10)
    font9.name = 'Calibri'
    font9.bold = False
    font9.color.rgb = grey
    p9.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

    p10 = doc.add_paragraph()
    text10 = '          •       Servizi a canone: Trimestrali anticipati a 20 giorni data fattura'
    run10 = p10.add_run(text10)
    font10 = run10.font
    font10.size = Pt(10)
    font10.name = 'Calibri'
    font10.bold = False
    font10.italic = False
    font10.color.rgb = grey
    p10.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

    p11 = doc.add_paragraph()
    text11 = 'Condizioni generali di vendita:'
    run11 = p11.add_run(text11)
    font11 = run11.font
    font11.size = Pt(10)
    font11.name = 'Calibri'
    font11.bold = True
    font11.color.rgb = grey
    p11.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

    p12 = doc.add_paragraph()
    text12 = '           •      condizioni generali di vendita sono visionabili al link: https://www.swissbix.ch/cgv.pdf'
    run12 = p12.add_run(text12)
    font12 = run12.font
    font12.size = Pt(10)
    font12.name = 'Calibri'
    font12.bold = False
    font12.color.rgb = grey
    p12.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

    p13 = doc.add_paragraph()
    text13 = '           •      La presente offerta comprende un servizio “chiavi in mano” al fine di \n                    garantire al cliente una totale garanzia della buona riuscita del progetto'
    run13 = p13.add_run(text13)
    font13 = run13.font
    font13.size = Pt(10)
    font13.name = 'Calibri'
    font13.bold = False
    font13.color.rgb = grey
    p13.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

    p14 = doc.add_paragraph()
    text14 = '           •      Offerta valida fino al ' + str(closedate) + ' o fino ad esaurimento scorte'
    run14 = p14.add_run(text14)
    font14 = run14.font
    font14.size = Pt(10)
    font14.name = 'Calibri'
    font14.bold = False
    font14.color.rgb = grey
    p14.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

    p15 = doc.add_paragraph()
    text15 = '           •      Swissbix SA non sarà ritenuta responsabile in caso di ritardi nella consegna del materiale \n                   dovuti a causa di forza maggiore o problemi legati ai fornitori dei prodotti o dei servizi logistici'
    run15 = p15.add_run(text15)
    font15 = run15.font
    font15.size = Pt(10)
    font15.name = 'Calibri'
    font15.bold = False
    font15.color.rgb = grey
    p15.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

    p16 = doc.add_paragraph()
    text16 = '           •      Sono esclusi dalla presente proposta commerciale:'
    run16 = p16.add_run(text16)
    font16 = run16.font
    font16.size = Pt(10)
    font16.name = 'Calibri'
    font16.bold = False
    font16.color.rgb = grey
    p15.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

    p17 = doc.add_paragraph()
    text17 = '                          o      Supporto, installazione ed eventuali uscite di fornitori esterni per gli applicativi \n                                  di terze parti utilizzati dal cliente'
    run17 = p17.add_run(text17)
    font17 = run17.font
    font17.size = Pt(10)
    font17.name = 'Calibri'
    font17.bold = False
    font17.color.rgb = grey
    p17.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

    p17 = doc.add_paragraph()
    text17 = '                          o      Lavori di cablaggio, lavori a muro di fissaggio e/o montaggio di ogni dispositivo, \n                                  lavori elettrici'
    run17 = p17.add_run(text17)
    font17 = run17.font
    font17.size = Pt(10)
    font17.name = 'Calibri'
    font17.bold = False
    font17.color.rgb = grey
    p17.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

    p17 = doc.add_paragraph()
    text17 = '                          o      Eventuali cavi, adattatori o convertitori che saranno fatturati a parte.'
    run17 = p17.add_run(text17)
    font17 = run17.font
    font17.size = Pt(10)
    font17.name = 'Calibri'
    font17.bold = False
    font17.color.rgb = grey
    p17.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

    p17 = doc.add_paragraph()
    text17 = '           •      I prezzi indicati sono Iva Esclusa'
    run17 = p17.add_run(text17)
    font17 = run17.font
    font17.size = Pt(10)
    font17.name = 'Calibri'
    font17.bold = False
    font17.color.rgb = grey
    p17.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

    p_space = doc.add_paragraph()
    text_space = ''
    run_space = p_space.add_run(text_space)

    p18 = doc.add_paragraph()
    text18 = 'Massagno' + ', ' + d1
    run18 = p18.add_run(text18)
    font18 = run18.font
    font18.size = Pt(10)
    font18.name = 'Calibri'
    font18.bold = False
    font18.italic = False
    font18.color.rgb = grey
    p18.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

    p19 = doc.add_paragraph()
    text19 = user
    run19 = p19.add_run(text19)
    font19 = run19.font
    font19.size = Pt(10)
    font19.name = 'Calibri'
    font19.bold = False
    font19.italic = False
    font19.color.rgb = grey
    p19.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

    p20 = doc.add_paragraph()
    text20 = 'Per Accettazione'
    run20 = p20.add_run(text20)
    font20 = run20.font
    font20.size = Pt(10)
    font20.name = 'Calibri'
    font20.bold = False
    font20.italic = False
    font20.color.rgb = grey
    p20.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT

    p_space = doc.add_paragraph()
    text_space = ''
    run_space = p_space.add_run(text_space)

    p21 = doc.add_paragraph()
    text21 = '─────────────────────────────────────'
    run21 = p21.add_run(text21)
    font21 = run21.font
    font21.size = Pt(10)
    font21.name = 'Calibri'
    font21.bold = True
    font21.italic = False
    p21.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT

    # Access the section of the document (assuming there's only one section)
    section = doc.sections[0]

    # Create a footer
    footer = section.footer

    # Add a paragraph to the footer
    p22 = footer.paragraphs[0]
    text22 = 'Swissbix SA Via Baroffio 6, 6900 Lugano E-Mail: finance@swissbix.ch Telefono: +41 91 960 22 00 Banca: UBS Switzerland AG \n Titolare del conto: Swissbix SA BIC: UBSWCHZH80A IBAN: CH62 0024 7247 2096 9101 U N. IVA UE: CHE-136.887.933 '
    run22 = p22.add_run(text22)

    # Set font properties
    font22 = run22.font
    font22.size = Pt(8)
    font22.name = 'Calibri'
    font22.bold = False
    font22.italic = False

    # Set text color to grey
    font22.color.rgb = grey

    # Set paragraph alignment to center
    p22.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

    doc.save(filename)

    try:
            with open(filename, 'rb') as fh:
                response = HttpResponse(fh.read(),
                                        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                response['Content-Disposition'] = f'inline; filename={dealname}.docx'

            return response

    finally:
        os.remove(filename)