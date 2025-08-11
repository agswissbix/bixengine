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
from datetime import datetime, date

from commonapp.helper import Helper
from commonapp.bixmodels.user_record import UserRecord
from commonapp.bixmodels.user_table import UserTable
from commonapp.bixmodels.helper_db import HelpderDB

# Initialize environment variables
env = environ.Env()
environ.Env.read_env()

def save_record_fields(tableid,recordid):
    # ---TIMESHEET---
    if tableid=='timesheet':
        print("save_record_fields timesheet")

    # ---DEAL---
    if tableid == 'deal':
        record_deal = UserRecord('deal', recordid)
        record_company = UserRecord('company', record_deal.values['recordidcompany_'])
        reference = str(record_deal.values['id']) + ' - ' + record_company.values['companyname'] + ' - ' + \
                    record_deal.values['dealname']
        if record_deal.values['advancepayment'] == None:
            record_deal.values['advancepayment'] = 0
        record_deal.values['reference'] = reference
        if record_deal.values['dealstatus'] is None or (record_deal.values['dealstatus'] != 'Vinta' and record_deal.values['dealstatus'] != 'Persa'):
            record_deal.values['dealstatus']='Aperta'
        record_deal.save()



def card_task_pianificaperoggi(recordid):
    print("card_task_pianificaperoggi")