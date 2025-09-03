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
from commonapp.bixmodels.user_record import *
from commonapp.bixmodels.user_table import *
from commonapp.bixmodels.helper_db import *
from commonapp.helper import *

logger = logging.getLogger(__name__)


def get_activemind(request):
    response_data = {}
    try:
        data = json.loads(request.body)
        recordid_deal = data.get('recordid', None)
        if recordid_deal:
            record_deal=UserRecord(recordid_deal)
            recordid_company=record_deal.values.get('recordidcompany_', None)
            if recordid_company:
                record_company=UserRecord(recordid_company)
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
        data = json.loads(request.body)
        print("Dati JSON ricevuti:", data)
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
        client_info = data.get('cliente', {})
        digital_signature = data.get('signature', {})

        # Calcolo i totali
        section1_total = services_data.get('section1', {}).get('price', 0)
        section3_total = sum(
            service.get('quantity', 0) * service.get('unitPrice', 0)
            for service in services_data.get('section3', {}).values()
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

        # Preparo il contesto per il template
        context = {
            'client_info': client_info,
            'services_data': services_data,
            'section1_total': section1_total,
            'section3_total': section3_total,
            'grand_total': section3_total,
            'tier_display': tier_display,
            'digital_signature': digital_signature,
        }
        
        # Renderizzo il template HTML
        template = get_template('activeMind/pdf_template.html')
        html = template.render(context)

        from xhtml2pdf import pisa 
        # Crea il PDF
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = 'inline; filename="offerta.pdf"'

        pisa_status = pisa.CreatePDF(
            html, dest=response, link_callback=link_callback
        )

        if pisa_status.err:
            return HttpResponse("Errore durante la creazione del PDF", status=500)
        return response
        # # Creo il PDF
        # result = BytesIO()
        # pdf = pisa.pisaDocument(BytesIO(html_content.encode("UTF-8")), result)
        
        # if not pdf.err:
        #     # Restituisce il PDF come risposta
        #     response = HttpResponse(result.getvalue(), content_type='application/pdf')
        #     response['Content-Disposition'] = f'attachment; filename="ActiveMind_Servizi_{client_info.get("name", "Cliente").replace(" ", "_")}.pdf"'
        #     return response
        # else:
        #     logger.error(f"Errore nella generazione PDF: {pdf.err}")
        #     return JsonResponse({'error': 'Errore nella generazione del PDF'}, status=500)
            
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