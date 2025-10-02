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
    # ---TIMESHEET---
    if tableid=='timesheet':
        print("save_record_fields timesheet")

    # ---DEAL---
    if tableid == 'deal':
        deal_record = UserRecord('deal', recordid)
        company_record = UserRecord('company', deal_record.values['recordidcompany_'])
        reference = str(deal_record.values['id']) + ' - ' + company_record.values['companyname'] + ' - ' + deal_record.values['dealname']
        deal_record.values['reference'] = reference

        if deal_record.values['advancepayment'] == None:
            deal_record.values['advancepayment'] = 0
        
        if deal_record.values['dealstatus'] is None or (deal_record.values['dealstatus'] != 'Vinta' and deal_record.values['dealstatus'] != 'Persa'):
            deal_record.values['dealstatus']='Aperta'
        

        creation = deal_record.values['creation_']
        deal_record.values['opendate'] = creation.strftime("%Y-%m-%d")
        deal_user_record_dict =  HelpderDB.sql_query_row(f"select * from sys_user where id={deal_record.values['dealuser1']}")
        deal_record.values['adiuto_dealuser'] = deal_user_record_dict['adiutoid']
        deal_project_record_dict = HelpderDB.sql_query_row(f"select * from user_project where recordiddeal_={recordid}")
        project_recordid = ''
        if deal_project_record_dict:
            project_recordid = deal_project_record_dict['recordid_']

        deal_price = deal_record.values['amount']
        if not deal_price:
            deal_price = 0
        deal_price_sum = 0
        deal_expectedcost = deal_record.values['expectedcost']
        if not deal_expectedcost:
            deal_expectedcost = 0
        deal_expectedcost_sum = 0
        deal_actualcost = 0
        deal_expectedhours = 0
        deal_usedhours = deal_record.values['usedhours']
        if not deal_usedhours:
            deal_usedhours = 0
        deal_expectedmargin = 0
        deal_actualmargin = 0
        deal_annualprice = 0
        deal_annualcost = 0
        deal_annualmargin = 0

        deal_record.values['fixedprice'] = 'No'
        dealline_records = deal_record.get_linkedrecords_dict(linkedtable='dealline')
        for dealline_record_dict in dealline_records:
            dealline_recordid = dealline_record_dict['recordid_']
            product_recordid = dealline_record_dict['recordidproduct_']
            dealline_recordid = dealline_record_dict['recordid_']
            dealline_quantity = dealline_record_dict['quantity']
            dealline_price = dealline_record_dict['price']
            dealline_expectedcost = dealline_record_dict['expectedcost']
            dealline_expectedmargin = dealline_record_dict['expectedmargin']
            dealline_unitactualcost = dealline_record_dict['uniteffectivecost']
            if not dealline_unitactualcost:
                dealline_unitactualcost = 0
            dealline_frequency = dealline_record_dict['frequency']
            multiplier = 1
            if dealline_frequency == 'Annuale':
                multiplier = 1
            if dealline_frequency == 'Semestrale':
                multiplier = 2
            if dealline_frequency == 'Trimestrale':
                multiplier = 3
            if dealline_frequency == 'Bimestrale':
                multiplier = 6
            if dealline_frequency == 'Mensile':
                multiplier = 12
            deal_price_sum = deal_price_sum + dealline_price
            deal_expectedcost_sum = deal_expectedcost_sum + dealline_expectedcost
            dealline_record = UserRecord('dealline', dealline_recordid)
            dealline_record.values['recordidproject_'] = project_recordid

            dealline_actualcost = dealline_unitactualcost * dealline_quantity
            product_fixedprice = 'No'
            if product_recordid and product_recordid != '':
                product_record = UserRecord('product', product_recordid)
                if not Helper.isempty(product_record.recordid):
                    product_fixedprice = product_record.values['fixedprice']
            if not dealline_record_dict['expectedhours']:
                dealline_record_dict['expectedhours'] = 0
            deal_expectedhours = deal_expectedhours + dealline_record_dict['expectedhours']
            if product_fixedprice == 'Si':
                deal_record.values['fixedprice'] = 'Si'
                if Helper.isempty(dealline_record.values['expectedhours']):
                    dealline_record.values['expectedhours'] = dealline_price / 140
                if deal_usedhours != 0:
                    dealline_record.values['usedhours'] = deal_usedhours
                    dealline_actualcost = deal_usedhours * 60
                    deal_usedhours = 0
            if dealline_actualcost != 0:
                dealline_actualmargin = dealline_price - dealline_actualcost
            else:
                dealline_actualmargin = dealline_expectedmargin
            dealline_record.values['effectivecost'] = dealline_actualcost
            dealline_record.values['margin_actual'] = dealline_actualmargin

            if not Helper.isempty(dealline_frequency):
                dealline_record.values['annualprice'] = dealline_price * multiplier
                if dealline_actualcost != 0:
                    dealline_record.values['annualcost'] = dealline_actualcost * multiplier
                else:
                    dealline_record.values['annualcost'] = dealline_expectedcost * multiplier
                dealline_record.values['annualmargin'] = dealline_record.values['annualprice'] - dealline_record.fields[
                    'annualcost']
                deal_annualprice = deal_annualprice + dealline_record.values['annualprice']
                deal_annualcost = deal_annualcost + dealline_record.values['annualcost']
                deal_annualmargin = deal_annualmargin + dealline_record.values['annualmargin']
            dealline_record.save()

            deal_actualcost = deal_actualcost + dealline_actualcost
            deal_actualmargin = deal_actualmargin + dealline_actualmargin

        if(len(dealline_records) > 0): 
            deal_price = deal_price_sum
        if(len(dealline_records) > 0): 
            deal_expectedcost = deal_expectedcost_sum
        deal_expectedmargin = deal_price - deal_expectedcost
        if deal_actualcost == 0:
            deal_actualmargin = deal_expectedmargin

        deal_record.values['amount'] = round(deal_price, 2)
        deal_record.values['expectedcost'] = round(deal_expectedcost, 2)
        deal_record.values['expectedmargin'] = round(deal_expectedmargin, 2)
        deal_record.values['expectedhours'] = deal_expectedhours
        deal_record.values['actualcost'] = deal_actualcost
        deal_record.values['effectivemargin'] = deal_actualmargin
        deal_record.values['margindifference'] = deal_actualmargin - deal_expectedmargin
        deal_record.values['annualprice'] = deal_annualprice
        deal_record.values['annualcost'] = deal_annualcost
        deal_record.values['annualmargin'] = deal_annualmargin

        # valutazione step workflow
        deal_type = deal_record.values['type']
        deal_record.values['techvalidation'] = 'No'
        deal_record.values['creditcheck'] = 'Si'
        deal_record.values['project'] = 'Si'
        deal_record.values['purchaseorder'] = 'Si'
        # default tech
        if deal_type == 'Printing':
            deal_record.values['project_default_adiutotech'] = 1019
        if deal_type == 'Software' or deal_type == 'Hosting':
            deal_record.values['project_default_adiutotech'] = 1011
        # tech validation
        if deal_type == 'ICT' or deal_type == 'PBX':
            deal_record.values['techvalidation'] = 'Si'

        # credit check
        if deal_type == 'Rinnovo Monte ore' or deal_type == 'Riparazione Lenovo':
            deal_record.values['creditcheck'] = 'No'
        if deal_record.values['amount'] < 500:
            deal_record.values['creditcheck'] = 'No'

        # progetto
        if deal_type == 'Aggiunta servizi' or deal_type == 'Materiale senza attività' or deal_type == 'Rinnovo Monte ore':
            deal_record.values['project'] = 'No'
            deal_record.values['project_default_adiutotech'] = 1019

        # ordine materiale
        if deal_type == 'Rinnovo Monte ore':
            deal_record.values['purchaseorder'] = 'No'

        deal_record.save()

    # ---DEALLINE
    if tableid == 'dealline':
        dealline_record = UserRecord('dealline', recordid)
        save_record_fields(tableid='deal', recordid=dealline_record.values['recordiddeal_'])



def card_task_pianificaperoggi(recordid):
    print("card_task_pianificaperoggi")


def printing_katun_bexio_api_set_invoice(request):
    
    post_data = json.loads(request.body)
    params = post_data.get('params', None)
    recordid = params.get('recordid', None)

    if not recordid:
        bixdata_invoices = HelpderDB.sql_query("SELECT * FROM user_printinginvoice WHERE status='Creata' LIMIT 1")
    else:
        bixdata_invoices = HelpderDB.sql_query(f"SELECT * FROM user_printinginvoice WHERE recordid_='{recordid}'")


    for invoice in bixdata_invoices:

        #invoice data
        recordid_company= invoice['recordidcompany_']
        record_company = UserRecord('company', recordid_company)
        bexio_contact_id= record_company.values.get('id_bexio', None)
        invoice_title="Conteggio copie stampanti/Multifunzioni"
        if (bexio_contact_id is  None) or (bexio_contact_id == ''):
            bexio_contact_id = 297 #contact id di Swissbix SA
            invoice_title = "Conteggio copie stampanti/Multifunzioni Swissbix SA "+invoice['title']
        # 1. Ottieni la data e ora correnti come oggetto datetime
        now = datetime.now()

        # 2. Aggiungi 20 giorni utilizzando timedelta
        future_date = now + timedelta(days=30)

        # 3. Formatta la nuova data nel formato stringa desiderato
        invoice_dateto = future_date.strftime("%Y-%m-%d")

        # Se vuoi anche la data di partenza formattata
        invoice_datefrom = now.strftime("%Y-%m-%d")

        #invoice lines
        bixdata_invoicelines = HelpderDB.sql_query(f"SELECT * FROM user_printinginvoiceline WHERE recordidprintinginvoice_='{invoice['recordid_']}'")
        invoiceliness = []
        for invoiceline in bixdata_invoicelines:
            invoiceline_unitprice= invoiceline['unitprice']
            invoiceline_quantity= invoiceline['quantity']
            if invoiceline_quantity == "0.00":
                invoiceline_quantity="0.0001"
            invoiceline_description= invoiceline['description']
            invoiceline_description_html = invoiceline_description.replace('\n', '<br>')

            bexio_invoiceline = {
                "tax_id": "39",
                "account_id": "353",
                "text": invoiceline_description_html,
                "unit_id": 2,   
                "amount": invoiceline_quantity,
                "unit_price": invoiceline_unitprice,
                "type": "KbPositionCustom",
            }
            invoiceliness.append(bexio_invoiceline)

        bexio_invoice = {
            "title": "Conteggio copie stampanti/Multifunzioni",
            "contact_id": bexio_contact_id,
            "user_id": 1,
            "language_id": 3,
            "currency_id": 1,
            "payment_type_id": 1,
            "header": "",
            "footer": "Vi ringraziamo per la vostra fiducia, in caso di disaccordo, vi preghiamo di notificarcelo entro 7 giorni. <br/>Rimaniamo a vostra disposizione per qualsiasi domanda,<br/><br/>Con i nostri più cordiali saluti, Swissbix SA",
            "mwst_type": 0,
            "mwst_is_net": True,
            "show_position_taxes": False,
            "is_valid_from": invoice_datefrom,
            "is_valid_to": invoice_dateto,
            "template_slug": "5a9c000702cf22422a8b4641",
            "positions": invoiceliness,
        }

        payload_invoice=json.dumps(bexio_invoice)

        #payload  = r"""{"title":"ICT: Supporto Cliente","contact_id":"297","user_id":1,"logopaper_id":1,"language_id":3,"currency_id":1,"payment_type_id":1,"header":"","footer":"Vi ringraziamo per la vostra fiducia, in caso di disaccordo, vi preghiamo di notificarcelo entro 7 giorni. Rimaniamo a vostra disposizione per qualsiasi domanda,Con i nostri più cordiali saluti, Swissbix SA","mwst_type":0,"mwst_is_net":true,"show_position_taxes":false,"is_valid_from":"2025-06-25","is_valid_to":"2025-07-15","positions":[{"text":"Interventi</b>","type":"KbPositionText"},{"text":"TEST 25/06/2025 Galli Alessandro </b></span>","tax_id":"39","account_id":"155","unit_id":2,"amount":"1","unit_price":"140","type":"KbPositionCustom"}]}"""


        url = "https://api.bexio.com/2.0/kb_invoice"
        accesstoken=os.environ.get('BEXIO_ACCESSTOKEN')
        
        headers = {
            'Accept': "application/json",
            'Content-Type': "application/json",
            'Authorization': f"Bearer {accesstoken}",
        }

        


        payload = """
            {
                "title": "TEST3",
                "contact_id": 308,
                "user_id": 1,
                "language_id": 1,
                "currency_id": 1,
                "payment_type_id": 1,
                "header": "",
                "footer": "We hope that our offer meets your expectations and will be happy to answer your questions.",
                "mwst_type": 0,
                "mwst_is_net": true,
                "show_position_taxes": false,
                "is_valid_from": "2025-10-01",
                "is_valid_to": "2025-10-21",
                "template_slug": "5a9c000702cf22422a8b4641",
                "positions":[{"text":"Interventi</b>","type":"KbPositionText"},{"text":"TEST 25/06/2025 Galli Alessandro </b></span>","tax_id":"39","account_id":"155","unit_id":2,"amount":"1","unit_price":"140","type":"KbPositionCustom"}]
            }
            """

        response = requests.request("POST", url, data=payload_invoice, headers=headers)

        status_code = response.status_code
        invoice_record = UserRecord('printinginvoice', invoice['recordid_'])
        if status_code == 201:
            response_data = response.json()
            bexio_invoice_id = response_data.get('id', )
            bexio_document_nr = response_data.get('document_nr', None)
            invoice_record.values['bexioinvoicenr'] = bexio_document_nr
            invoice_record.values['bexioinvoiceid'] = bexio_invoice_id
            invoice_record.values['status'] = 'Caricata'
            invoice_record.save()
        else:
            print(f"Errore nella creazione della fattura su Bexio. Status code: {status_code}, Response: {response.text}")
            invoice_record.values['status'] = 'Errore Bexio'
            invoice_record.save()
    return JsonResponse({'status': status_code, 'message': response.json()})

