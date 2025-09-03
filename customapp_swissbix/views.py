from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.csrf import csrf_exempt
import pdfkit
from commonapp.bixmodels.user_record import *
from commonapp.bixmodels.user_table import *
from commonapp.bixmodels.helper_db import *
from commonapp.helper import *




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