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
import locale
import re
from docx import Document
import os


@csrf_exempt
def script_test(request):
    type = None
    result_status = 'success'
    result_values = []
    return JsonResponse({"status": result_status, "value": result_values, "type": type})


@csrf_exempt
#ritorna dei contatori (ad esempio: numero di stabili, numero di utenti, ecc.)
def monitor_counters(request):
    type = "counters"
    result_status = 'success'
    result_values = []
    result_value=dict()
    result_value['stabili_totale']= 100
    result_value['stabili_giornata']= 100
    return JsonResponse({"status": result_status, "value": result_values, "type": type})

@csrf_exempt
#ritorna delle date
def monitor_dates(request):
    type = "dates"
    result_status = 'success'
    result_values = []
    result_value=dict()
    result_value['stabili_ultimoinserimento']= '2025-07-20'
    return JsonResponse({"status": result_status, "value": result_values, "type": type})

@csrf_exempt
#ritorna lo stato dei servizi
def monitor_services(request):
    type = "services"
    result_status = 'success'
    result_values = []
    result_value=dict()
    result_value['bixportal']= 'Running' #puo' essere disabled, running, stopped, error
    result_value['adifeed']= 'disabled'
    return JsonResponse({"status": result_status, "value": result_values, "type": type})


@csrf_exempt
#ritorna conteggi di file in delle cartelle
def monitor_folders(request):
    type = "services"
    result_status = 'success'
    result_values = []
    result_value=dict()
    result_value['adiuto_scan']= 100 #puo' essere disabled, running, stopped, error
    result_value['bixdata_uploads']= 50
    return JsonResponse({"status": result_status, "value": result_values, "type": type})



