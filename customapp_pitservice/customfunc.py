from django.shortcuts import render
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
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

from commonapp.helper import Helper
from commonapp.bixmodels.user_record import UserRecord
from commonapp.bixmodels.user_table import UserTable
from commonapp.bixmodels.helper_db import HelpderDB

# Initialize environment variables
env = environ.Env()
environ.Env.read_env()

def save_record_fields(tableid,recordid):

    # ---ORE MENSILI---
    if tableid == 'oremensili':
        oremensili_record = UserRecord('oremensili', recordid)
        dipendente_recordid = oremensili_record.values['recordiddipendente_']
        save_record_fields('dipendente', dipendente_recordid)


    # ---ASSENZE---
    if tableid == 'assenze':
        assenza_record = UserRecord('assenze', recordid)
        dipendente_recordid= assenza_record.values['recordiddipendente_']
        save_record_fields('dipendente', dipendente_recordid)

    # ---DIPENDENTE---
    if tableid == 'dipendente':
        dipendente_record = UserRecord('dipendente', recordid)
        allegati= HelpderDB.sql_query(f"SELECT * FROM user_attachment WHERE recordiddipendente_='{recordid}' AND deleted_='N'")
        nrallegati=len(allegati) 
        dipendente_record.values['nrallegati'] = nrallegati

        

        #calcolo saldo vacanze
        saldovacanze_iniziale= Helper.safe_float(dipendente_record.values['saldovacanze_iniziale'])
        saldovacanze=saldovacanze_iniziale
        assenze_dict_list=dipendente_record.get_linkedrecords_dict('assenze')
        for assenza in assenze_dict_list:
            data_assenza_dal=assenza.get('dal')
            tipo_assenza=assenza.get('tipo_assenza')
            if tipo_assenza == 'Vacanza':
                if data_assenza_dal:
                    try:
                        dal_date = date.fromisoformat(str(data_assenza_dal))
                    except Exception:
                        try:
                            dal_date = datetime.strptime(str(data_assenza_dal), '%Y-%m-%d').date()
                        except Exception:
                            dal_date = None
                    if dal_date and dal_date > date(2025, 9, 30):
                        giorni_assenza= Helper.safe_float(assenza.get('giorni'))
                        saldovacanze=saldovacanze-giorni_assenza

        dipendente_record.values['saldovacanze'] = saldovacanze
        dipendente_record.save()

        #calcolo saldo ore
        saldoore_iniziale= Helper.safe_float(dipendente_record.values['saldoore_iniziale'])
        saldoore= saldoore_iniziale
        oremensili_dict_list=dipendente_record.get_linkedrecords_dict('oremensili')
        for oremensili in oremensili_dict_list:
            anno= oremensili.get('anno')
            mese= oremensili.get('mese')
            if anno>'2025' or mese=='10-Ottobre' or mese=='11-Novembre' or mese=='12-Dicembre':
                differenza_ore= Helper.safe_float(oremensili.get('diffore'))
                saldoore=saldoore+differenza_ore
        dipendente_record.values['saldoore'] = saldoore
        dipendente_record.save()










def calculate_dependent_fields(request):
    data = json.loads(request.body)
    updated_fields = {}
    recordid=data.get('recordid')
    tableid=data.get('tableid')
    return JsonResponse({'status': 'success', 'updated_fields': updated_fields})
