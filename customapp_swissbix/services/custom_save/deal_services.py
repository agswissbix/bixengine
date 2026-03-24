from commonapp.bixmodels.user_record import UserRecord
from commonapp.bixmodels.helper_db import HelpderDB
from commonapp.helper import Helper

class DealService:
    @staticmethod
    def process_deal(recordid: str) -> list:
        """
        Processa i campi di un deal: valuta lo stato del deal, deallines, ore previste/usate,
        margini e costi sia per il deal che per le deallines. Imposta anche flag per il workflow
        (techvalidation, creditcheck, ecc).
        
        Ritorna una lista di tuple (tableid, recordid) di record collegati
        da salvare a cascata.
        """
        deal_record = UserRecord('deal', recordid)
        dealline_records = deal_record.get_linkedrecords_dict(linkedtable='dealline')
        
        # 1. Fixedprice check & Installazione/configurazione
        DealService._evaluate_fixedprice(deal_record, dealline_records, recordid)

        # 2. Riferimento Company & Deal
        DealService._update_reference(deal_record)

        if deal_record.values.get('advancepayment') is None:
            deal_record.values['advancepayment'] = 0
        
        # 3. Aggiorna status se non "Vinta/Persa"
        if deal_record.values.get('dealstatus') not in ['Vinta', 'Persa']:
            deal_record.values['dealstatus'] = 'Aperta'
        
        # 4. Impostazione date & User
        DealService._set_dates_and_users(deal_record)

        # Recupero ID progetto legato se esiste
        project_recordid = DealService._get_project_id(recordid)
        
        # 4.5 Processa timesheets del progetto
        DealService._process_project_timesheets(deal_record, project_recordid)

        # 5. Iterazione Dealline records e calcolo aggregati
        totals = DealService._process_deallines(deal_record, dealline_records, project_recordid)

        # 6. Finalizzazione conteggi master
        DealService._finalize_deal_calculations(deal_record, dealline_records, totals)

        # 7. Completamento progetti
        DealService._check_project_completion(deal_record)

        # 8. Workflow Step & Validazioni
        DealService._evaluate_workflow_steps(deal_record)

        deal_record.save()
        
        # Attualmente non ci sono record dipendenti da triggerare a cascata
        return []


    @staticmethod
    def _evaluate_fixedprice(deal_record: UserRecord, dealline_records: list, recordid: str):
        fixedprice_product = '00000000000000000000000000000180'
        found_dl = next((d for d in dealline_records if d.get('recordidproduct_') == fixedprice_product and d.get('deleted_') == 'N'), None)
        if deal_record.values.get('fixedprice') == 'Si':
            if found_dl:
                if (found_dl.get('price') or 0) < 0:
                    dl_rec = UserRecord('dealline', found_dl['recordid_'])
                    dl_rec.values['price'] = 10000
                    dl_rec.save()
            else:
                dl_rec = UserRecord('dealline')
                dl_rec.values['recordiddeal_'] = recordid
                dl_rec.values['recordidproduct_'] = fixedprice_product
                dl_rec.values['name'] = 'Installazione e configurazione a progetto'
                dl_rec.values['price'] = 10000
                dl_rec.values['quantity'] = 1
                dl_rec.save()
        else:
            if found_dl:
                dl_rec = UserRecord('dealline', found_dl['recordid_'])
                dl_rec.values['deleted_'] = 'Y'
                dl_rec.save()

    @staticmethod
    def _update_reference(deal_record: UserRecord):
        company_id = deal_record.values.get('recordidcompany_')
        company_record = UserRecord('company', company_id) if company_id else None
        
        val_id = str(deal_record.values.get('id') or '')
        val_company = str(company_record.values.get('companyname') or '') if company_record else ''
        val_deal = str(deal_record.values.get('dealname') or '')
        
        deal_record.values['reference'] = f"{val_id} - {val_company} - {val_deal}"

    @staticmethod
    def _set_dates_and_users(deal_record: UserRecord):
        creation = deal_record.values.get('creation_')
        if creation:
            deal_record.values['opendate'] = creation.strftime("%Y-%m-%d")

        dealuser1 = deal_record.values.get('dealuser1')
        if dealuser1:
            deal_user_record_dict = HelpderDB.sql_query_row(f"select * from sys_user where id={dealuser1}")
            deal_record.values['adiuto_dealuser'] = deal_user_record_dict.get('adiutoid') if deal_user_record_dict else None
        else:
            deal_record.values['adiuto_dealuser'] = None

    @staticmethod
    def _get_project_id(recordid: str) -> str:
        deal_project_record_dict = HelpderDB.sql_query_row(f"select * from user_project where recordiddeal_={recordid}")
        return deal_project_record_dict.get('recordid_') if deal_project_record_dict else ''

    @staticmethod
    def _process_project_timesheets(deal_record: UserRecord, project_recordid: str):
        usedhours = 0
        fixedpricehours = 0
        servicecontracthours = 0
        bankhours = 0
        invoicedhours = 0
        invoicedprice = 0
        residualhours = 0
        
        if project_recordid:
            project_record = UserRecord('project', project_recordid)
            expectedhours = project_record.values.get('expectedhours')
            timesheet_records_list = project_record.get_linkedrecords_dict('timesheet')
            
            for ts_dict in timesheet_records_list:
                invoicestatus = ts_dict.get('invoicestatus')
                hours = ts_dict.get('totaltime_decimal') or 0
                price = ts_dict.get('totalprice') or 0
                
                usedhours += hours
                
                if invoicestatus == 'Fixed Price Project':
                    fixedpricehours += hours
                elif invoicestatus == 'Service Contract: Monte Ore':
                    bankhours += hours
                elif invoicestatus == 'Invoiced':
                    invoicedhours += hours
                    invoicedprice += price
                    
            if expectedhours:
                residualhours = expectedhours - usedhours
                    
        deal_record.values['usedhours'] = usedhours
        deal_record.values['fixedpricehours'] = fixedpricehours
        deal_record.values['servicecontracthours'] = servicecontracthours
        deal_record.values['bankhours'] = bankhours
        deal_record.values['invoicedhours'] = invoicedhours
        deal_record.values['invoicedprice'] = invoicedprice
        deal_record.values['residualhours'] = residualhours

    @staticmethod
    def _process_deallines(deal_record: UserRecord, dealline_records: list, project_recordid: str) -> dict:
        deal_usedhours = deal_record.values.get('usedhours') or 0
        
        totals = {
            'deal_price_sum': 0,
            'deal_expectedcost_sum': 0,
            'deal_expectedhours': 0,
            'deal_actualcost': 0,
            'deal_actualmargin': 0,
            'deal_annualprice': 0,
            'deal_annualcost': 0,
            'deal_annualmargin': 0
        }

        for dl_dict in dealline_records:
            dl_recordid = dl_dict['recordid_']
            dl_record = UserRecord('dealline', dl_recordid)
            dl_record.values['recordidproject_'] = project_recordid
            
            product_recordid = dl_dict.get('recordidproduct_')
            dl_quantity = dl_dict.get('quantity') or 0
            dl_price = dl_dict.get('price') or 0
            dl_expectedcost = dl_dict.get('expectedcost') or 0
            dl_expectedmargin = dl_dict.get('expectedmargin') or 0
            dl_unitactualcost = dl_dict.get('uniteffectivecost') or 0
            dl_frequency = dl_dict.get('frequency')

            # Multiplier freq
            multiplier = 1
            if dl_frequency == 'Semestrale': multiplier = 2
            elif dl_frequency == 'Trimestrale': multiplier = 4
            elif dl_frequency == 'Bimestrale': multiplier = 6
            elif dl_frequency == 'Mensile': multiplier = 12

            totals['deal_price_sum'] += dl_price
            totals['deal_expectedcost_sum'] += dl_expectedcost

            dl_actualcost = dl_unitactualcost * dl_quantity
            
            product_fixedprice = 'No'
            if product_recordid:
                product_record = UserRecord('product', product_recordid)
                if not Helper.isempty(product_record.recordid) and not Helper.isempty(product_record.values):
                    product_fixedprice = product_record.values.get('fixedprice', 'No')

            expectedhours = dl_dict.get('expectedhours') or 0
            totals['deal_expectedhours'] += expectedhours
            
            if product_fixedprice == 'Si':
                deal_record.values['fixedprice'] = 'Si'
                if Helper.isempty(dl_record.values.get('expectedhours')):
                    dl_record.values['expectedhours'] = dl_price / 140
                    
                if deal_usedhours != 0:
                    dl_record.values['usedhours'] = deal_usedhours
                    dl_actualcost = deal_usedhours * 60
                    deal_usedhours = 0
                    
            if dl_actualcost != 0:
                dl_actualmargin = dl_price - dl_actualcost
            else:
                dl_actualmargin = dl_expectedmargin
                
            dl_record.values['effectivecost'] = dl_actualcost
            dl_record.values['margin_actual'] = dl_actualmargin

            if not Helper.isempty(dl_frequency):
                dl_record.values['annualprice'] = dl_price * multiplier
                dl_record.values['annualcost'] = dl_actualcost * multiplier if dl_actualcost != 0 else dl_expectedcost * multiplier
                dl_record.values['annualmargin'] = dl_record.values['annualprice'] - dl_record.values['annualcost']
                
                totals['deal_annualprice'] += dl_record.values['annualprice']
                totals['deal_annualcost'] += dl_record.values['annualcost']
                totals['deal_annualmargin'] += dl_record.values['annualmargin']
            
            dl_record.save()

            totals['deal_actualcost'] += dl_actualcost
            totals['deal_actualmargin'] += dl_actualmargin

        return totals

    @staticmethod
    def _finalize_deal_calculations(deal_record: UserRecord, dealline_records: list, totals: dict):
        deal_price = deal_record.values.get('amount') or 0
        deal_expectedcost = deal_record.values.get('expectedcost') or 0
        
        deal_price = totals['deal_price_sum']
        deal_expectedcost = totals['deal_expectedcost_sum']
            
        deal_expectedmargin = deal_price - deal_expectedcost
        
        deal_actualmargin = totals['deal_actualmargin']
        deal_actualcost = totals['deal_actualcost']

        if deal_actualcost == 0:
            deal_actualmargin = deal_expectedmargin

        deal_record.values['amount'] = round(deal_price, 2)
        deal_record.values['expectedcost'] = round(deal_expectedcost, 2)
        deal_record.values['expectedmargin'] = round(deal_expectedmargin, 2)
        deal_record.values['expectedhours'] = totals['deal_expectedhours']
        deal_record.values['actualcost'] = deal_actualcost
        deal_record.values['effectivemargin'] = deal_actualmargin
        deal_record.values['margindifference'] = deal_actualmargin - deal_expectedmargin
        deal_record.values['annualprice'] = totals['deal_annualprice']
        deal_record.values['annualcost'] = totals['deal_annualcost']
        deal_record.values['annualmargin'] = totals['deal_annualmargin']

    @staticmethod
    def _check_project_completion(deal_record: UserRecord):
        project_records = deal_record.get_linkedrecords_dict(linkedtable='project')
        for pr_dict in project_records:
            deal_record.values['projectcompleted'] = pr_dict.get('completed')

    @staticmethod
    def _evaluate_workflow_steps(deal_record: UserRecord):
        deal_type = deal_record.values.get('type')
        
        deal_record.values['techvalidation'] = 'No'
        deal_record.values['creditcheck'] = 'Si'
        deal_record.values['project'] = 'Si'
        deal_record.values['purchaseorder'] = 'Si'
        
        if deal_type == 'Printing':
            deal_record.values['project_default_adiutotech'] = 1019
        elif deal_type in ['Software', 'Hosting']:
            deal_record.values['project_default_adiutotech'] = 1011
            
        if deal_type in ['ICT', 'PBX']:
            deal_record.values['techvalidation'] = 'Si'

        if deal_type in ['Rinnovo Monte ore', 'Riparazione Lenovo'] or deal_record.values.get('amount', 0) < 500:
            deal_record.values['creditcheck'] = 'No'

        if deal_type in ['Aggiunta servizi', 'Materiale senza attività', 'Rinnovo Monte ore']:
            deal_record.values['project'] = 'No'
            deal_record.values['project_default_adiutotech'] = 1019

        if deal_type == 'Rinnovo Monte ore':
            deal_record.values['purchaseorder'] = 'No'
