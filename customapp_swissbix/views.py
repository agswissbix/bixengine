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
import io
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
from docxtpl import DocxTemplate
from customapp_swissbix.mock.activeMind.products import products as products_data_mock
from customapp_swissbix.mock.activeMind.services import services as services_data_mock

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
    

def chunk(iterable):
    pages = []
    page = []
    counter = 0
    for s in iterable:
        if s.quantity == 0:
            continue
        limit = 2 if len(s.features) > 10 else 3
        page.append(s)
        counter += 1
        if counter >= limit:
            pages.append(page)
            page = []
            counter = 0
    if page:
        pages.append(page)
    return pages

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
        # TODO prendere dati come fe es. servizi e prodotti già fatti
        section1_total = services_data.get('section1', {}).get('price', 0)
        

        raw_service_dicts = []
        for p in services_data.get("services", {}):
            if isinstance(p, dict) and p.get("quantity", 0) > 0:
                enriched = build_service_with_totals(
                    service_id=p["id"],
                    quantity=p["quantity"],
                )
                if enriched:
                    raw_service_dicts.append(enriched)

        section2_services_total = sum(p["total"] for p in raw_service_dicts)


        raw_product_dicts = []
        for p in services_data.get("products", {}):
            if isinstance(p, dict) and p.get("quantity", 0) > 0:
                enriched = build_product_with_totals(
                    product_id=p["id"],
                    quantity=p["quantity"],
                    billing_type=p.get("billingType", "monthly")
                )
                if enriched:
                    raw_product_dicts.append(enriched)

        section2_products_total = sum(p["total"] for p in raw_product_dicts)


        grand_total = section1_total + section2_services_total + section2_products_total


        condition = services_data.get('conditions', {})

        tier_descriptions = {
            'tier1': 'Fino a 5 PC + server',
            'tier2': 'Fino a 10 PC + server', 
            'tier3': 'Fino a 15 PC + server',
            'tier4': 'Fino a 20 PC + server'
        }
        selected_tier = services_data.get('section1', {}).get('selectedTier', '')
        tier_display = tier_descriptions.get(selected_tier, selected_tier)

        totals = {
            "monthly": 0,
            "quarterly": 0,
            "biannual": 0,
            "yearly": 0,
        }

        for p in raw_product_dicts:
            billing = p.get("billingType", "monthly").lower()
            if billing in totals:
                totals[billing] += p.get("total", 0)

        # Servizi → gestiti da 'conditions'
        for s in raw_service_dicts:
            billing = condition.lower() if condition else "monthly"
            if billing in totals:
                totals[billing] += s.get("total", 0)

        # Assegno i valori finali
        monthly_total   = totals["monthly"]
        quarterly_total = totals["quarterly"]
        biannual_total  = totals["biannual"]
        yearly_total    = totals["yearly"]

        monthly_total += section1_total

        # grand total resta invariato
        grand_total = monthly_total + yearly_total

        service_objects_for_chunking = [
            type('Service', (object,), s) for s in raw_service_dicts
        ]
        product_objects_for_chunking = [
            type('Product', (object,), p) for p in raw_product_dicts
        ]


        # Preparo contesto per template
        context = {
            'client_info': cliente,
            'services_data': services_data,
            # Passa i prodotti per la sezione economica
            'section2_products_pages': chunk(product_objects_for_chunking), 
            # I servizi sono già gestiti da 'section2_pages' (codice precedente)
            'section2_services_pages': chunk(service_objects_for_chunking),
            
            # Nuovi totali
            'section1_price': section1_total,
            'section2_services_total': section2_services_total,
            'section2_products_total': section2_products_total,
            'monthly_total': monthly_total,
            'quarterly_total': quarterly_total,
            'biannual_total': biannual_total,
            'yearly_total': yearly_total,
            'grand_total': grand_total,
            
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
    # print(services_data_mock)
    return JsonResponse({"services": services_data_mock}, safe=False)

def get_service_by_id(service_id: str):
    for service in services_data_mock:  # stesso array con categorie
        if service["id"] == service_id:
            return service
    return None

def build_service_with_totals(service_id: str, quantity: int):
    service = get_service_by_id(service_id)
    if not service:
        return None
    unit_price = service.get("unitPrice", 0)
    total = unit_price * quantity
    return {
        "id": service["id"],
        "title": service["title"],
        "description": service.get("description", ""),
        "features": service.get("features", []),
        "category": service.get("category"),
        "unitPrice": unit_price,
        "quantity": quantity,
        "total": total,
    }

def get_products_activemind(request):
    # print(products_data_mock)
    return JsonResponse({"servicesCategory": products_data_mock}, safe=False)

def get_product_by_id(product_id: str):
    """Ritorna il dict del prodotto dal mock (in futuro DB)."""
    for category in products_data_mock:
        for service in category.get("services", []):
            if service["id"] == product_id:
                return service
    return None

def build_product_with_totals(product_id: str, quantity: int, billing_type: str = "monthly"):
    """Arricchisce i dati con calcoli e dettagli dal mock."""
    product = get_product_by_id(product_id)
    if not product:
        return None
    
    unit_price = product.get("monthlyPrice") if billing_type == "monthly" else product.get("yearlyPrice")
    total = unit_price * quantity if unit_price else 0

    return {
        "id": product["id"],
        "title": product["title"],
        "description": product.get("description", ""),
        "features": product.get("features", []),
        "category": product.get("category"),
        "billingType": billing_type,
        "unitPrice": unit_price,
        "quantity": quantity,
        "total": total,
    }

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

    tableid= 'deal'
  
    # Percorso al template Word
    base_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(base_dir, 'templates', 'template.docx')

    if not os.path.exists(template_path):
        return HttpResponse("File non trovato", status=404)

    
    deal_record = UserRecord(tableid, recordid_deal)
    dealname = deal_record.values.get('dealname', 'N/A')
    dealuser1 = deal_record.values.get('dealuser1', 'N/A')
    closedata = deal_record.values.get('closedate', 'N/A')

    companyid = deal_record.values.get('recordidcompany_')
    if companyid:
        company_record = UserRecord('company', deal_record.values.get('recordidcompany_'))
        companyname = company_record.values.get('companyname', 'N/A')
        address = company_record.values.get('address', 'N/A')
        city = company_record.values.get('city', 'N/A')

    user_record=HelpderDB.sql_query_row(f"SELECT * FROM sys_user WHERE id ='{dealuser1}'")
    user = user_record['firstname'] + ' ' + user_record['lastname']
    
    # Definizione economica
    dealline_records = deal_record.get_linkedrecords_dict('dealline')
    items = []

    for idx, line in enumerate(dealline_records, start=1):
        name = line.get('name', 'N/A')
        quantity = line.get('quantity', 0)
        unit_price = line.get('unitprice', 0.0)
        price = line.get('price', 0.0)
        items.append({
            "descrizione": name,
            "qt": quantity,
            "prezzo_unitario": f"{unit_price:.2f}",
            "prezzo_totale": f"{price:.2f}",
        })

    dati_trattativa = {
        "indirizzo": f"{address}, {city}",
        "azienda": companyname,
        "titolo": dealname,
        "venditore": user,
        "data_chiusura_vendita": closedata,
        "data_attuale": datetime.datetime.now().strftime("%d/%m/%Y"),
        'items': items,
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
    response['Content-Disposition'] = 'attachment; filename="documento_trattativa_generato.docx"'
    return response


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
    response={ "status": "ok"}
    return JsonResponse(response)


def get_satisfation(request):
    from customapp_swissbix.script import get_satisfaction
    return get_satisfaction()

def update_deals(request):
    from customapp_swissbix.script import update_deals
    return update_deals(request)
    