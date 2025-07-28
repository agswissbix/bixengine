from datetime import datetime
from django.http import JsonResponse
from django_q.models import Schedule, Task
from django.db import connection



def script_test():
    type = None
    result_status = 'success'
    result_values = []
    return JsonResponse({"status": result_status, "value": result_values, "type": type})



#ritorna dei contatori (ad esempio: numero di stabili, numero di utenti, ecc.)
def monitor_counters():
    type = "counters"
    result_status = 'success'
    result_values = []
    result_value=dict()
    result_value['stabili_totale']= 100
    result_value['stabili_giornata']= 100
    return JsonResponse({"status": result_status, "value": result_values, "type": type})


#ritorna delle date
def monitor_dates():
    type = "dates"
    result_status = 'success'
    result_values = []
    result_value=dict()
    result_value['stabili_ultimoinserimento']= '2025-07-20'
    return JsonResponse({"status": result_status, "value": result_values, "type": type})


#ritorna lo stato dei servizi
def monitor_services():
    type = "services"
    result_status = 'success'
    result_values = []
    result_value=dict()
    result_value['bixportal']= 'Running' #puo' essere disabled, running, stopped, error
    result_value['adifeed']= 'disabled'
    return JsonResponse({"status": result_status, "value": result_values, "type": type})


#ritorna conteggi di file in delle cartelle
def monitor_folders():
    type = "services"
    result_status = 'success'
    result_values = []
    result_value=dict()
    result_value['adiuto_scan']= 100 #puo' essere disabled, running, stopped, error
    result_value['bixdata_uploads']= 50
    return JsonResponse({"status": result_status, "value": result_values, "type": type})



