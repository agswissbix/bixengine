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



def save_record_fields(tableid,recordid, old_record=""):

    if tableid == 'fattura':
        fattura = UserRecord(tableid, recordid)
        nr = fattura.values.get('nr_documento')
        if not nr:
            current_date = datetime.now()
            current_year_short = current_date.strftime("%y") # '26'
            prefix = f"{current_year_short}-"

            # Cerca l'ultimo numero con questo prefisso
            sql = f"SELECT nr_documento FROM user_fattura WHERE nr_documento LIKE '{prefix}%' AND deleted_='N' ORDER BY nr_documento DESC LIMIT 1"
            last_invoice_row = HelpderDB.sql_query_row(sql)

            new_sequence = 1
            if last_invoice_row and last_invoice_row.get('nr_documento'):
                last_nr = last_invoice_row['nr_documento']
                try:
                    # Assumiamo formato YY-NNNNNNNN
                    parts = last_nr.split('-')
                    if len(parts) == 2:
                        new_sequence = int(parts[1]) + 1
                except ValueError:
                    # Se il parsing fallisce, ripartiamo da 1 (o potremmo loggare errore)
                    pass
            
            # Formatta: YY-00000001
            new_nr = f"{prefix}{new_sequence:08d}"
            
            fattura.values['nr_documento'] = new_nr
            fattura.save()
            
    elif tableid == 'azienda':
        azienda = UserRecord(tableid, recordid)
        codice = azienda.values.get('codicecliente')
        if not codice:
            sql = "SELECT MAX(codicecliente) as max_code FROM user_azienda WHERE deleted_='N'"
            row = HelpderDB.sql_query_row(sql)
            max_code = row.get('max_code') if row else 0
            if max_code is None:
                max_code = 0
            
            azienda.values['codicecliente'] = float(max_code) + 1
            azienda.save()

    elif tableid == 'fornitori':
        fornitore = UserRecord(tableid, recordid)
        codice = fornitore.values.get('codice')
        if not codice:
            sql = "SELECT MAX(codice) as max_code FROM user_fornitori WHERE deleted_='N'"
            row = HelpderDB.sql_query_row(sql)
            max_code = row.get('max_code') if row else 0
            if max_code is None:
                max_code = 0
            
            fornitore.values['codice'] = float(max_code) + 1
            fornitore.save()