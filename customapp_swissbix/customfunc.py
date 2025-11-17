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
import qrcode
import base64
import pdfkit

from commonapp.helper import Helper
from commonapp.bixmodels.user_record import UserRecord
from commonapp.bixmodels.user_table import UserTable
from commonapp.bixmodels.helper_db import HelpderDB

from commonapp import views

# Initialize environment variables
env = environ.Env()
environ.Env.read_env()

def save_record_fields(tableid,recordid):

    # ---TIMESHEET---
    if tableid == 'timesheet':
        flat_service_contract = None
        servicecontract_record = None
        # recupero informazioni necessarie
        servicecontract_table = UserTable(tableid='servicecontract')
        timesheet_record = UserRecord('timesheet', recordid)
        company_record = UserRecord('company', timesheet_record.values['recordidcompany_'])
        project_record = UserRecord('project', timesheet_record.values['recordidproject_'])
        ticket_record = UserRecord('ticket', timesheet_record.values['recordidticket_'])
        servicecontract_record = UserRecord('servicecontract', timesheet_record.values['recordidservicecontract_'])
        service = timesheet_record.values['service']
        invoiceoption = timesheet_record.values['invoiceoption']
        invoicestatus = timesheet_record.values['invoicestatus']
        if Helper.isempty(invoicestatus):
            invoicestatus = ''
        worktime = timesheet_record.values['worktime']
        traveltime = timesheet_record.values['traveltime']

        # inizializzo campi
        productivity = ''
        worktime_decimal = 0
        travel_time_decimal = 0
        totaltime_decimal = 0
        workprice = 0
        travelprice = 0
        totalprice = 0
        timesheet_record.values['worktime_decimal'] = ''
        timesheet_record.values['traveltime_decimal'] = ''
        timesheet_record.values['totaltime_decimal'] = ''
        timesheet_record.values['workprice'] = ''
        timesheet_record.values['travelprice'] = ''
        timesheet_record.values['totalprice'] = ''
        timesheet_record.values['recordidservicecontract_'] = ''
        timesheet_record.values['print_type'] = 'Normale'
        timesheet_record.values['print_hourprice'] = ''
        timesheet_record.values['print_travel'] = ''
        # aggiorno dati a prescindere

        if not Helper.isempty(worktime):
            hours, minutes = map(int, worktime.split(':'))
            worktime_decimal = hours + minutes / 60
            if not Helper.isempty(traveltime):
                hours, minutes = map(int, traveltime.split(':'))
                travel_time_decimal = hours + minutes / 60
            totaltime_decimal = worktime_decimal + travel_time_decimal
            timesheet_record.values['worktime_decimal'] = worktime_decimal
            timesheet_record.values['traveltime_decimal'] = travel_time_decimal
            timesheet_record.values['totaltime_decimal'] = totaltime_decimal

        # inizio valutazione invoice status


        if invoicestatus != 'Invoiced':
            invoicestatus = 'To Process'

        # valutazione del tipo di servizio se produttivo o meno
        if invoicestatus == 'To Process':
            if service == 'Amministrazione' or service == 'Commerciale' or service == 'Formazione Apprendista' or service == 'Formazione e Test' or service == 'Interno' or service == 'Riunione':
                invoicestatus = 'Attività non fatturabile'
                productivity = 'Senza ricavo'

        # valutazione delle option
        if invoicestatus == 'To Process':
            if invoiceoption == 'Under Warranty' or invoiceoption == 'Commercial support' or invoiceoption == 'Swisscom incident' or invoiceoption == 'Swisscom ServiceNow' or invoiceoption == 'To check':
                invoicestatus = invoiceoption
                productivity = 'Senza ricavo'
                timesheet_record.values['print_type'] = 'Garanzia'
                timesheet_record.values['print_hourprice'] = 'Garanzia'
                timesheet_record.values['print_travel'] = 'Garanzia'

        # valutazione eventuale project
        if invoicestatus == 'To Process' and (
                (not Helper.isempty(project_record.recordid)) and invoiceoption != 'Out of contract'):
            timesheet_record.values['print_type'] = 'Progetto N. ' + str(project_record.values['id'])
            if project_record.values['fixedprice'] == 'Si':
                invoicestatus = 'Fixed price Project'
                productivity = 'Ricavo indiretto'
                timesheet_record.values['print_hourprice'] = 'Compreso nel progetto'
                timesheet_record.values['print_travel'] = 'Inclusa'
            if invoiceoption == 'Monte ore':
                timesheet_record.values['print_type'] = ''
                invoicestatus = 'To Process'
                productivity = ''
                timesheet_record.values['print_hourprice'] = ''
                timesheet_record.values['print_travel'] = ''


        # valutazione flat service contract
        if invoicestatus == 'To Process':
            if not Helper.isempty(timesheet_record.values['worktime']) and invoiceoption != 'Out of contract':
                
                if service == 'Assistenza PBX':
                    if ((travel_time_decimal == 0 and worktime_decimal == 0.25) or invoiceoption == 'In contract'):
                        flat_service_contract = servicecontract_table.get_records(
                            conditions_list=[f"recordidcompany_='{timesheet_record.values['recordidcompany_']}'",
                                             "(type='Manutenzione PBX')"])

                if service == 'Assistenza IT':
                    if travel_time_decimal == 0 or invoiceoption == 'In contract':
                        flat_service_contract = servicecontract_table.get_records(
                            conditions_list=[f"recordidcompany_='{timesheet_record.values['recordidcompany_']}'",
                                             "(type='BeAll (All-inclusive)')"])

                if service == 'Printing':
                    flat_service_contract = servicecontract_table.get_records(
                        conditions_list=[f"recordidcompany_='{timesheet_record.values['recordidcompany_']}'",
                                         "(type='Manutenzione Printing')"])

                if service == 'Assistenza Web Hosting':
                    flat_service_contract = servicecontract_table.get_records(
                        conditions_list=[f"recordidcompany_='{timesheet_record.values['recordidcompany_']}'",
                                         "(service='Assistenza Web Hosting')"])

                if flat_service_contract:
                    servicecontract_record = UserRecord('servicecontract', flat_service_contract[0]['recordid_'])
                    timesheet_record.values['recordidservicecontract_'] = servicecontract_record.recordid
                    invoicestatus = 'Service Contract: ' + servicecontract_record.values['type']
                    productivity = 'Ricavo indiretto'
                    timesheet_record.values['print_type'] = 'Contratto di servizio'
                    timesheet_record.values['print_hourprice'] = 'Compreso nel contratto di servizio'
                    timesheet_record.values['print_travel'] = 'Compresa nel contratto di servizio'
                if invoiceoption == 'Monte ore':
                    timesheet_record.values['recordidservicecontract_'] = ''
                    invoicestatus = 'To Process'
                    productivity = ''
                    timesheet_record.values['print_type'] = ''
                    timesheet_record.values['print_hourprice'] = ''
                    timesheet_record.values['print_travel'] = ''
        # valutazione monte ore pbx
        if ((invoicestatus == 'To Process' or invoicestatus == 'Under Warranty' or invoicestatus == 'Commercial support') and invoiceoption != 'Out of contract' and travel_time_decimal == 0):
            service_contracts = servicecontract_table.get_records(
                conditions_list=[f"recordidcompany_='{timesheet_record.values['recordidcompany_']}'",
                                 "type='Monte Ore Remoto PBX'", "status='In Progress'"])
            if service_contracts:
                timesheet_record.values['recordidservicecontract_'] = service_contracts[0]['recordid_']
                servicecontract_record = UserRecord('servicecontract', service_contracts[0]['recordid_'])
                if invoicestatus == 'To Process':
                    invoicestatus = 'Service Contract: Monte Ore Remoto PBX'
                    productivity = 'Ricavo diretto'
                if invoicestatus == 'Under Warranty':
                    invoicestatus = 'Under Warranty'
                    productivity = 'Senza ricavo'
                if invoicestatus == 'Commercial support':
                    invoicestatus = 'Commercial support'
                    productivity = 'Senza ricavo'
                timesheet_record.values['print_type'] = 'Monte Ore Remoto PBX'
                timesheet_record.values['print_hourprice'] = 'Scalato dal monte ore'
                if servicecontract_record.values['excludetravel']:
                    timesheet_record.values['print_travel'] = 'Non scalata dal monte ore e non fatturata'
        # valutazione monte ore
        if ((
                invoicestatus == 'To Process' or invoicestatus == 'Under Warranty' or invoicestatus == 'Commercial support') and invoiceoption != 'Out of contract'):
            service_contracts = servicecontract_table.get_records(
                conditions_list=[f"recordidcompany_='{timesheet_record.values['recordidcompany_']}'",
                                 "type='Monte Ore'", "status='In Progress'"])
            if service_contracts:
                timesheet_record.values['recordidservicecontract_'] = service_contracts[0]['recordid_']
                servicecontract_record = UserRecord('servicecontract', service_contracts[0]['recordid_'])
                if invoicestatus == 'To Process':
                    invoicestatus = 'Service Contract: Monte Ore'
                    productivity = 'Ricavo diretto'
                if invoicestatus == 'Under Warranty':
                    invoicestatus = 'Under Warranty'
                    productivity = 'Senza ricavo'
                if invoicestatus == 'Commercial support':
                    invoicestatus = 'Commercial support'
                    productivity = 'Senza ricavo'
                timesheet_record.values['print_type'] = 'Monte Ore'
                timesheet_record.values['print_hourprice'] = 'Scalato dal monte ore'
                if servicecontract_record.values['excludetravel']:
                    timesheet_record.values['print_travel'] = 'Non scalata dal monte ore e non fatturata'

        # da fatturare quando chiusi
        if invoicestatus == 'To Process':
            productivity = 'Ricavo diretto'
            hourprice = 140
            travelstandardprice = None
            timesheet_record.values['print_travel'] = 'Da fatturare'

            if not Helper.isempty(company_record.values['ictpbx_price']):
                hourprice = company_record.values['ictpbx_price']
                travelstandardprice = company_record.values['travel_price']

            timesheet_record.values['print_hourprice'] = 'Fr.' + str(hourprice) + '.--'

            if not Helper.isempty(project_record.recordid):
                if project_record.values['completed'] != 'Si':
                    invoicestatus = 'To invoice when Project Completed'

            if not Helper.isempty(ticket_record.recordid):
                if ticket_record.values['vtestatus'] != 'Closed':
                    invoicestatus = 'To invoice when Ticket Closed'
            timesheet_record.values['hourprice'] = hourprice
            workprice = hourprice * worktime_decimal
            timesheet_record.values['workprice'] = workprice
            if travel_time_decimal:
                if travel_time_decimal > 0:
                    if travelstandardprice:
                        travelprice = travelstandardprice;
                    else:
                        travelprice = hourprice * travel_time_decimal;
                    timesheet_record.values['travelprice'] = travelprice
            timesheet_record.values['totalprice'] = workprice + travelprice
            if invoicestatus == 'To Process':
                invoicestatus = 'To Invoice'

        timesheet_record.values['invoicestatus'] = invoicestatus
        timesheet_record.values['productivity'] = productivity
        if service == 'Assistenza IT' or service == 'Assistenza PBX' or service == 'Assistenza SW' or service == 'Assistenza Web Hosting' or service == 'Printing':
            if timesheet_record.values['validated'] != 'Si':
                timesheet_record.values['validated'] = 'No'

        timesheet_record.save()

        if not Helper.isempty(servicecontract_record.recordid):
            save_record_fields(tableid='servicecontract', recordid=servicecontract_record.recordid)

        if not Helper.isempty(project_record.recordid):
            save_record_fields(tableid='project', recordid=project_record.recordid)


    # ---SERVICE CONTRACT
    if tableid == 'servicecontract':
        servicecontract_table = UserTable(tableid='servicecontract')
        servicecontract_record = UserRecord('servicecontract', recordid)
        salesorderline_record = UserRecord('salesorderline', servicecontract_record.values['recordidsalesorderline_'])

        # recupero campi
        contracthours = servicecontract_record.values['contracthours']
        if contracthours == None:
            contracthours = 0
        previousresidual = servicecontract_record.values['previousresidual']
        if previousresidual == None:
            previousresidual = 0
        excludetravel = servicecontract_record.values['excludetravel']

        # inizializzo campi
        usedhours = 0
        progress = 0
        residualhours = contracthours

        timesheet_linkedrecords = servicecontract_record.get_linkedrecords_dict(linkedtable='timesheet')
        for timesheet_linkedrecord in timesheet_linkedrecords:
            if timesheet_linkedrecord['invoiceoption'] != 'Under Warranty' and timesheet_linkedrecord[
                'invoiceoption'] != 'Commercial support':
                usedhours = usedhours + timesheet_linkedrecord['worktime_decimal']
                if excludetravel != '1' and excludetravel != 'Si':
                    if not Helper.isempty(timesheet_linkedrecord['traveltime_decimal']):
                        usedhours = usedhours + timesheet_linkedrecord['traveltime_decimal']
        residualhours = contracthours + previousresidual - usedhours
        if contracthours + previousresidual != 0:
            progress = (usedhours / (contracthours + previousresidual)) * 100

        if Helper.isempty(servicecontract_record.values['status']):
            servicecontract_record.values['status'] = 'In Progress'

        servicecontract_record.values['usedhours'] = usedhours
        servicecontract_record.values['residualhours'] = residualhours
        servicecontract_record.values['progress'] = progress
        servicecontract_record.save()

        if not Helper.isempty(salesorderline_record.recordid):
            save_record_fields( tableid='salesorderline', recordid=salesorderline_record.recordid)

    # ---DEAL---
    if tableid == 'deal':
        deal_record = UserRecord('deal', recordid)
        company_record = UserRecord('company', deal_record.values['recordidcompany_'])
        val_id = str(deal_record.values.get('id') or '')
        val_company = str(company_record.values.get('companyname') or '')
        val_deal = str(deal_record.values.get('dealname') or '')
        reference = f"{val_id} - {val_company} - {val_deal}"
        deal_record.values['reference'] = reference

        if deal_record.values['advancepayment'] == None:
            deal_record.values['advancepayment'] = 0
        
        if deal_record.values['dealstatus'] is None or (deal_record.values['dealstatus'] != 'Vinta' and deal_record.values['dealstatus'] != 'Persa'):
            deal_record.values['dealstatus']='Aperta'
        

        creation = deal_record.values.get('creation_')
        if creation:
            deal_record.values['opendate'] = creation.strftime("%Y-%m-%d")
        deal_record.values['opendate'] = creation.strftime("%Y-%m-%d")
        deal_user_record_dict =  HelpderDB.sql_query_row(f"select * from sys_user where id={deal_record.values['dealuser1']}")
        if deal_user_record_dict:
            deal_record.values['adiuto_dealuser'] = deal_user_record_dict.get('adiutoid')
        else:
            deal_record.values['adiuto_dealuser'] = None
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
        # dealline records
        dealline_records = deal_record.get_linkedrecords_dict(linkedtable='dealline')
        for dealline_record_dict in dealline_records:
            dealline_recordid = dealline_record_dict['recordid_']
            product_recordid = dealline_record_dict['recordidproduct_']
            dealline_quantity = dealline_record_dict['quantity'] or 0
            dealline_price = dealline_record_dict['price'] or 0
            dealline_expectedcost = dealline_record_dict['expectedcost'] or 0
            dealline_expectedmargin = dealline_record_dict['expectedmargin'] or 0
            dealline_unitactualcost = dealline_record_dict['uniteffectivecost'] or 0
            if not dealline_unitactualcost:
                dealline_unitactualcost = 0
            dealline_frequency = dealline_record_dict['frequency']
            multiplier = 1
            if dealline_frequency == 'Annuale':
                multiplier = 1
            if dealline_frequency == 'Semestrale':
                multiplier = 2
            if dealline_frequency == 'Trimestrale':
                multiplier = 4
            if dealline_frequency == 'Bimestrale':
                multiplier = 6
            if dealline_frequency == 'Mensile':
                multiplier = 12
            deal_price_sum = deal_price_sum + dealline_price
            deal_expectedcost_sum = deal_expectedcost_sum + (dealline_expectedcost or 0)
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
                dealline_record.values['annualmargin'] = dealline_record.values['annualprice'] - dealline_record.values['annualcost']
                deal_annualprice = deal_annualprice + dealline_record.values['annualprice']
                deal_annualcost = deal_annualcost + dealline_record.values['annualcost']
                deal_annualmargin = deal_annualmargin + dealline_record.values['annualmargin']
            dealline_record.save()

            deal_actualcost = deal_actualcost + dealline_actualcost
            deal_actualmargin = deal_actualmargin + dealline_actualmargin

        if(len(dealline_records) > 0): 
            deal_price = deal_price_sum
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


        #projects
        project_records = deal_record.get_linkedrecords_dict(linkedtable='project')
        for project_record_dict in project_records:
            completed= project_record_dict['completed']
            deal_record.values['projectcompleted'] = completed

            
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


    # ---PROJECT
    if tableid == 'project':
        project_record = UserRecord('project', recordid)
        completed = project_record.values['completed']
        deal_record = UserRecord('deal', project_record.values['recordiddeal_'])
        expectedhours = project_record.values['expectedhours']
        usedhours = 0
        residualhours = 0
        fixedpricehours = 0
        servicecontracthours = 0
        bankhours = 0
        invoicedhours = 0
        timesheet_records_list = project_record.get_linkedrecords_dict('timesheet')
        for timesheet_record_dict in timesheet_records_list:
            usedhours = usedhours + timesheet_record_dict['totaltime_decimal'] or 0
            if timesheet_record_dict['invoicestatus'] == 'Fixed Price Project':
                fixedpricehours = fixedpricehours + timesheet_record_dict['totaltime_decimal'] or 0
            if timesheet_record_dict['invoicestatus'] == 'Service Contract: Monte Ore':
                bankhours = bankhours + timesheet_record_dict['totaltime_decimal'] or 0
            if timesheet_record_dict['invoicestatus'] == 'Invoiced':
                invoicedhours = invoicedhours + timesheet_record_dict['totaltime_decimal'] or 0
        if expectedhours:
            residualhours = expectedhours - usedhours
        project_record.values['usedhours'] = usedhours
        project_record.values['residualhours'] = residualhours
        project_record.save()


        #collegamento allegati del deal al progetto
        attachment_records = deal_record.get_linkedrecords_dict(linkedtable='attachment')
        for attachment_record_dict in attachment_records:
            attachment_record = UserRecord('attachment', attachment_record_dict['recordid_'])
            attachment_record.values['recordidproject_'] = project_record.recordid
            attachment_record.save()

        #aggiornamento deal
        #TODO valutare se ha senso aggiornarlo qui o meglio spostare direttamente nel save del deal
        if not isempty(deal_record.recordid):
            deal_record.values['usedhours'] = usedhours
            deal_record.values['fixedpricehours'] = fixedpricehours
            deal_record.values['servicecontracthours'] = servicecontracthours
            deal_record.values['bankhours'] = bankhours
            deal_record.values['invoicedhours'] = invoicedhours
            deal_record.values['residualhours'] = residualhours
            deal_record.values['projectcompleted'] = completed
            deal_record.save()
            save_record_fields(tableid='deal', recordid=deal_record.recordid)


    # ---TIMETRACKING---
    if tableid == 'timetracking':
        timetracking_record = UserRecord('timetracking', recordid)
        if timetracking_record.values['stato'] == 'Terminato':
            if timetracking_record.values['end'] == '':
                timetracking_record.values['end'] = datetime.now().strftime("%H:%M")
            time_format = '%H:%M'
            start = datetime.strptime(timetracking_record.values['start'], time_format)
            end = datetime.strptime(timetracking_record.values['end'], time_format)
            time_difference = end - start

            total_minutes = time_difference.total_seconds() / 60
            hours, minutes = divmod(total_minutes, 60)
            formatted_time = "{:02}:{:02}".format(int(hours), int(minutes))

            timetracking_record.values['worktime_string'] = str(formatted_time)

            hours = time_difference.total_seconds() / 3600
            timetracking_record.values['worktime'] = round(hours, 2)

        if timetracking_record.values['start'] == '':
            timetracking_record.values['start'] =  datetime.now().strftime("%H:%M")
        timetracking_record.save()

    # ---ATTACHMENT---
    if tableid == 'attachment':
        attachment_record = UserRecord('attachment', recordid)
        filename= attachment_record.values['filename']
        file_relative_path = attachment_record.values['file']
        recordiddeal = attachment_record.values['recordiddeal_']
        if not Helper.isempty(recordiddeal):
            adiuto_uplodad=attachment_record.values['adiuto_uploaded']
            if  adiuto_uplodad!='Si':
                filename_adiuto= f"deal_{recordiddeal}_{recordid}_{filename}"
                
                # 1. Definisci il path di destinazione (sempre relativo a MEDIA_ROOT)
                dest_relative_path = f"Adiuto/{filename_adiuto}"

                try:
                    # 2. Apri il file sorgente usando default_storage
                    # 'with' garantisce che il file venga chiuso correttamente
                    with default_storage.open(file_relative_path, 'rb') as source_file:
                        
                        # 3. Salva il contenuto letto in una nuova posizione
                        # default_storage.save riceve il path relativo e l'oggetto File
                        # e gestisce automaticamente la scrittura.
                        new_path = default_storage.save(dest_relative_path, source_file)
                        attachment_record.values['adiuto_uploaded'] = "Si"
                        attachment_record.save()
                        # (Opzionale) 'new_path' contiene il percorso esatto del file salvato
                        # (potrebbe avere un hash se il file esisteva già)
                        print(f"File copiato con successo in: {new_path}")

                except FileNotFoundError:
                    print(f"ERRORE: Impossibile copiare. File sorgente non trovato in: {file_relative_path}")
                except Exception as e:
                    # Gestisci altri possibili errori (es. permessi)
                    print(f"ERRORE durante la copia del file: {e}")
        
    # ---ASSENZE---
    if tableid == 'assenze':
        assenza_record = UserRecord('assenze', recordid)
        tipo_assenza=assenza_record.values['tipo_assenza']
        if tipo_assenza!='Malattia':
            dipendente_recordid = assenza_record.values['recordiddipendente_']
            save_record_fields(tableid='dipendente', recordid=dipendente_recordid)

    # ---DIPENDENTE---
    if tableid == 'dipendente':
        dipendente_record = UserRecord('dipendente', recordid)

        #calcolo saldo vacanze
        saldovacanze_iniziale= Helper.safe_float(dipendente_record.values['saldovacanze_iniziale'])
        saldovacanze=saldovacanze_iniziale
        assenze_dict_list=dipendente_record.get_linkedrecords_dict('assenze')
        for assenza in assenze_dict_list:
            tipo_assenza=assenza.get('tipo_assenza')
            if tipo_assenza == 'Vacanze':
                giorni_assenza= Helper.safe_float(assenza.get('giorni'))
                saldovacanze=saldovacanze-giorni_assenza

        dipendente_record.values['saldovacanze'] = saldovacanze
        dipendente_record.save()

    # ---EVENT---
    if tableid == 'events':
        event_record = UserRecord('events', recordid)
        
        graph_event_id = event_record.values['graph_event_id']
        table=event_record.values['table_id']
        subject=event_record.values['subject']
        start_date=event_record.values['start_date']
        end_date=event_record.values['end_date']
        user=event_record.values['user_id']
        owner=event_record.values['owner']
        body_content=event_record.values['body_content']
        timezone=event_record.values['timezone']

        if not timezone:
            timezone = 'Europe/Zurich'
            event_record.values['timezone'] = timezone

        organizer_email=event_record.values['organizer_email']

        categories=[]
        if  event_record.values['categories']:
            categories=event_record.values['categories'].split(',')

        if table not in categories:
            categories.append(table)
            event_record.values['categories'] = ','.join(categories)
        
        sys_user_details = None
        if user:
            sys_user_details = HelpderDB.sql_query_row(f"SELECT * FROM sys_user WHERE id = {user}")
        
        if not owner and user:
            if sys_user_details and sys_user_details.get('email'):
                owner = sys_user_details['email']
                event_record.values['owner'] = owner

        if not organizer_email and sys_user_details and sys_user_details.get('email'):
            organizer_email = sys_user_details['email']
            event_record.values['organizer_email'] = organizer_email

        if not start_date and end_date:
            start_date = end_date
            event_record.values['start_date'] = start_date

        if not end_date and start_date:
            end_date = start_date
            event_record.values['end_date'] = end_date

        event_data = {
            'graph_event_id': graph_event_id,
            'table': table,
            'subject': subject,
            'start_date': start_date,
            'end_date': end_date,
            'user': user,
            'owner': owner,
            'body_content': body_content,
            'timezone': timezone,
            'organizer_email': organizer_email,
            'categories': categories,
        }

        if graph_event_id:
            result = views.update_event(event_data)
        else:
            result = views.create_event(event_data)

        if not "error" in result:
            event_record.values['graph_event_id'] = result.get('id')
            event_record.values['m365_calendar_id'] =  result.get('calendar', {}).get('id'),
        else:
            print(result)
        
        event_record.save()

    # --- NOTIFICATIONS ---
    if tableid == 'notification':
        notification_record = UserRecord('notifications', recordid)

        if not notification_record.values['date']:
            notification_record.values['date'] = datetime.now().strftime("%Y-%m-%d")

        if not notification_record.values['time']:
            notification_record.values['time'] = datetime.now().strftime("%H:%M")

        views.create_notification(recordid)


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
            response_data_json_str= json.dumps(response_data)
            invoice_record.values['bexio_output'] = response_data_json_str
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




def calculate_dependent_fields(request):
    data = json.loads(request.body)
    updated_fields = {}
    recordid=data.get('recordid')
    tableid=data.get('tableid')
    
    #---DEALLINE---
    if tableid=='dealline':
        fields= data.get('fields')
        quantity = fields.get('quantity', 0)
        unitprice = fields.get('unitprice', 0)
        unitexpectedcost = fields.get('unitexpectedcost', 0)
        recordidproduct=fields.get('recordidproduct_',None)
        if recordidproduct:
            product=UserRecord('product',recordidproduct)
            if product:
                if unitprice=='' or unitprice is None:
                    unitprice=product.values.get('price',0)
                    updated_fields['unitprice']=unitprice
                if unitexpectedcost=='' or unitexpectedcost is None:
                    unitexpectedcost=product.values.get('cost',0)
                    updated_fields['unitexpectedcost']=unitexpectedcost
        
        if quantity == '' or quantity is None:
            quantity = 0
        if unitprice == '' or unitprice is None:
            unitprice = 0
        if unitexpectedcost == '' or unitexpectedcost is None:
            unitexpectedcost = 0

        try:
            quantity_num = float(quantity)
        except (ValueError, TypeError):
            quantity_num = 0
        try:
            unitprice_num = float(unitprice)
        except (ValueError, TypeError):
            unitprice_num = 0
        try:
            unitexpectedcost_num = float(unitexpectedcost)
        except (ValueError, TypeError):
            unitexpectedcost_num = 0

        updated_fields['price'] = round(quantity_num * unitprice_num, 2)
        updated_fields['expectedcost'] = round(quantity_num * unitexpectedcost_num, 2)
        updated_fields['expectedmargin'] = round(updated_fields['price'] - updated_fields['expectedcost'], 2)
    
    #---ASSENZE---
    if tableid=='assenze':
        fields= data.get('fields')
        #giorni= Helper.safe_float(fields.get('giorni', 0))
        #ore= Helper.safe_float(fields.get('ore', 0))
        #if ore == '' or ore is None:
         #   ore_updated=giorni * 8
          #  updated_fields['ore']=ore_updated   

    return JsonResponse({'status': 'success', 'updated_fields': updated_fields})


def print_timesheet(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            recordid = data.get('recordid')

            
            base_path = os.path.join(settings.STATIC_ROOT, 'pdf')




            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=10,
                border=0,
            )

            today = date.today()
            d1 = today.strftime("%d/%m/%Y")

            qrcontent = 'timesheet_' + str(recordid)


            data = qrcontent
            qr.add_data(data)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")

            qr_name = 'qrcode' + recordid + '.png'

            qr_path = os.path.join(base_path, qr_name)

            img.save(qr_path)


            rows = HelpderDB.sql_query(f"SELECT t.*, c.companyname, c.address, c.city, c.email, c.phonenumber, u.firstname, u.lastname FROM user_timesheet AS t JOIN user_company AS c ON t.recordidcompany_=c.recordid_ JOIN sys_user AS u ON t.user = u.id WHERE t.recordid_='{recordid}'")

            server = os.environ.get('BIXENGINE_SERVER')
            qr_url = server + '/static/pdf/' + qr_name


            pdf_filename = f"Timesheet_{str(recordid)}.pdf"
            pdf_filename = re.sub(r'[\\/*?:"<>|]', "", pdf_filename) # Pulisci il nome

            filename_with_path = os.path.join(base_path, 'temp_timesheet_' + str(recordid) + '.pdf')



            row = rows[0]

            for value in row:
                if row[value] is None:
                    row[value] = ''

            row['recordid'] = recordid
            row['qrUrl'] = qr_url


            timesheetlines = HelpderDB.sql_query(f"SELECT * FROM user_timesheetline WHERE recordidtimesheet_='{recordid}'")


            for line in timesheetlines:
                line['note'] = line['note'] or ''   
                line['expectedquantity'] = line['expectedquantity'] or ''
                line['actualquantity'] = line['actualquantity'] or ''

            row['timesheetlines'] = timesheetlines

            script_dir = os.path.dirname(os.path.abspath(__file__))
        
            wkhtmltopdf_path = script_dir + '\\wkhtmltopdf.exe'

            config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
            content = render_to_string('pdf/timesheet_signature.html', row)

            pdfkit.from_string(
                content,
                filename_with_path,
                configuration=config,
                options={
                    "enable-local-file-access": "",
                    # "quiet": ""  # <-- rimuovilo!
                }
            )


            try:
                with open(filename_with_path, 'rb') as f:
                    pdf_data = f.read()
  
                    response = HttpResponse(pdf_data, content_type='application/pdf')
                    response['Content-Disposition'] = f'inline; filename="{pdf_filename}"'
                    return response
            finally:
                if os.path.exists(filename_with_path):
                    os.remove(filename_with_path)
                if os.path.exists(qr_path):
                    os.remove(qr_path)

        except Exception as e:
            print(f"Error in print_timesheet: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


