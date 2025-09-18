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