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
        dipendente_record = UserRecord('dipendente', dipendente_recordid)
        ruolo= dipendente_record.values['ruolo']
        oremensili_record.values['ruolo'] = ruolo
        oremensili_record.save()


    # ---ASSENZE---
    if tableid == 'assenze':
        assenza_record = UserRecord('assenze', recordid)
        tipo_assenza=assenza_record.values['tipo_assenza']
        if tipo_assenza!='Malattia':
            ore_assenza= Helper.safe_float(assenza_record.values['ore'])
            giorni_assenza = ore_assenza / 8
            dipendente_recordid = assenza_record.values['recordiddipendente_']
            dipendente_record = UserRecord('dipendente', dipendente_recordid)
            saldovacanze_attuale=Helper.safe_float(dipendente_record.values['saldovacanze'])
            if not saldovacanze_attuale:
                saldovacanze_attuale=0
            saldovacanze=saldovacanze_attuale-giorni_assenza
            dipendente_record.values['saldovacanze'] = saldovacanze
            dipendente_record.save()

    # ---DIPENDENTE---
    if tableid == 'dipendente':
        dipendente_record = UserRecord('dipendente', recordid)
        allegati= HelpderDB.sql_query(f"SELECT * FROM user_attachment WHERE recordiddipendente_='{recordid}' AND deleted_='N'")
        nrallegati=len(allegati) 
        dipendente_record.values['nrallegati'] = nrallegati

        saldoore_iniziale= Helper.safe_float(dipendente_record.values['saldoore_iniziale'])

        dipendente_record.save()