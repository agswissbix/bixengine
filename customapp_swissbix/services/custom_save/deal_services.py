from commonapp.bixmodels.user_record import UserRecord
from commonapp.bixmodels.helper_db import HelpderDB
from commonapp.helper import Helper
from datetime import *
from django.db import connection


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
        deal_record = UserRecord('deal', recordid, load_fields=False)
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
        # Non invertire 4.5 con 5 per logica laborcost
        DealService._process_project_timesheets(deal_record, project_recordid)

        # 5. Iterazione Dealline records e calcolo aggregati
        totals = DealService._process_deallines(deal_record, dealline_records, project_recordid)

        # 6. Finalizzazione conteggi master
        DealService._finalize_deal_calculations(deal_record, dealline_records, totals)

        # 7. Completamento progetti
        DealService._check_project_completion(deal_record, dealline_records)

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
                    dl_rec = UserRecord('dealline', found_dl['recordid_'], load_fields=False)
                    dl_rec.values['price'] = 10000
                    dl_rec.save()
            else:
                dl_rec = UserRecord('dealline', load_fields=False)
                dl_rec.values['recordiddeal_'] = recordid
                dl_rec.values['recordidproduct_'] = fixedprice_product
                dl_rec.values['name'] = 'Installazione e configurazione a progetto'
                dl_rec.values['price'] = 10000
                dl_rec.values['quantity'] = 1
                dl_rec.save()
        else:
            if found_dl:
                dl_rec = UserRecord('dealline', found_dl['recordid_'], load_fields=False)
                dl_rec.values['deleted_'] = 'Y'
                dl_rec.save()

    @staticmethod
    def _update_reference(deal_record: UserRecord):
        company_id = deal_record.values.get('recordidcompany_')
        company_record = UserRecord('company', company_id, load_fields=False) if company_id else None
        
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
        residualhours = 0
        expectedhours = 0
        travelhours = 0
        travelcost = 0
        fixedpricehours = 0
        servicecontracthours = 0
        bankhours = 0
        deductedhoursamount = 0
        deductedhoursmargin = 0
        deductedhourscost = 0
        invoicedhours = 0
        invoicedhoursamount = 0
        toinvoicehours = 0
        toinvoicehoursamount = 0
        laborcost = 0
        nonbillablehours = 0
        nonbillablecost = 0
        saleshours = 0
        salescost = 0
        laborhours = 0
        totalhours = 0
        
        timesheets_dict = {}
        
        if project_recordid:
            project_record = UserRecord('project', project_recordid, load_fields=False)
            expectedhours = project_record.values.get('expectedhours') or 0
            for ts in project_record.get_linkedrecords_dict('timesheet'):
                timesheets_dict[ts.get('recordid_')] = ts
                
        for ts in deal_record.get_linkedrecords_dict('timesheet'):
            ts_id = ts.get('recordid_')
            if ts_id in timesheets_dict:
                del timesheets_dict[ts_id]
                
            hours = ts.get('totaltime_decimal') or 0
            price = hours * 60
            try:
                _h = float(hours)
            except (ValueError, TypeError):
                _h = 0
            totalhours += _h
            saleshours += hours
            salescost += price
            
        for ts_dict in timesheets_dict.values():
            invoicestatus = ts_dict.get('invoicestatus')
            hours = ts_dict.get('totaltime_decimal') or 0
            price = ts_dict.get('totalprice') or 0
            worktime = ts_dict.get('worktime_decimal') or 0

            try:
                hours = float(hours)
            except ValueError:
                hours = 0
            
            try:
                price = float(price)
            except ValueError:
                price = 0
                
            try:
                worktime = float(worktime)
            except ValueError:
                worktime = 0
            
            laborhours += worktime
            usedhours += hours
            totalhours += hours

            travel_hours = ts_dict.get('traveltime_decimal') or 0
            travel_price = ts_dict.get('travelprice') or 0

            try:
                travel_hours = float(travel_hours)
            except ValueError:
                travel_hours = 0
            
            try:
                travel_price = float(travel_price)
            except ValueError:
                travel_price = 0

            travelhours += travel_hours
            travelcost += travel_price

            if not invoicestatus or not str(invoicestatus).strip():
                nonbillablehours += hours
                nonbillablecost += hours * 60
                continue

            invoicestatus = str(invoicestatus).strip().lower()
            
            if invoicestatus == 'fixed price project':
                fixedpricehours += hours
            elif invoicestatus == 'service contract: monte ore':
                bankhours += hours
                deductedhoursamount += hours * 100
                deductedhourscost += hours * 60
            elif invoicestatus == 'attività non fatturabile':
                nonbillablehours += hours
                nonbillablecost += hours * 60
            elif invoicestatus == 'invoiced':
                invoicedhours += hours
                invoicedhoursamount += price
                laborcost += hours * 60
            elif invoicestatus and invoicestatus.startswith('to invoice'):
                toinvoicehours += hours
                toinvoicehoursamount += price
                laborcost += hours * 60
            else:
                nonbillablehours += hours
                nonbillablecost += hours * 60
                
        if expectedhours:
            residualhours = expectedhours - usedhours
                
        deal_record.values['usedhours'] = usedhours
        deal_record.values['residualhours'] = residualhours
        deal_record.values['travelhours'] = travelhours
        deal_record.values['travelcost'] = travelcost
        deal_record.values['fixedpricehours'] = fixedpricehours
        deal_record.values['servicecontracthours'] = servicecontracthours
        deal_record.values['bankhours'] = bankhours
        deal_record.values['deductedhours'] = bankhours
        deal_record.values['deductedhoursamount'] = deductedhoursamount
        deal_record.values['deductedhourscost'] = deductedhourscost
        deal_record.values['deductedhoursmargin'] = deductedhoursamount - deductedhourscost
        deal_record.values['invoicedhours'] = invoicedhours
        deal_record.values['invoicedhoursamount'] = invoicedhoursamount
        deal_record.values['saleshours'] = saleshours
        deal_record.values['salescost'] = salescost
        deal_record.values['nonbillablehours'] = nonbillablehours
        deal_record.values['nonbillablecost'] = nonbillablecost
        deal_record.values['unbilledhours'] = toinvoicehours
        deal_record.values['unbilledhoursamount'] = toinvoicehoursamount
        deal_record.values['laborhours'] = laborhours
        deal_record.values['totalhours'] = totalhours

        deal_record.values['actuallaborcost'] = laborcost

        # Generazione nota HTML riepilogativa formattata in modo leggibile anche per i tooltip
        hoursnote = f"""<div class="deal-summary" style="font-size: 1em;color: black;"><strong>Ore: {totalhours}</strong></div>
<div class="deal-details" style="font-family: system-ui, sans-serif; line-height: 1.5; color: #1f2937;">
<div style="font-size: 1.1em; color: #1e40af; margin-bottom: 8px; border-bottom: 1px solid #bfdbfe; padding-bottom: 4px;"><b>Dettaglio Tempistiche</b></div>
&bull; Totale Generale Ore: <b>{totalhours}</b><br/>
&bull; Ore Previste: <b>{expectedhours}</b><br/>
&bull; Ore Utilizzate: <b>{usedhours}</b><br/>
&bull; Ore Residue: <span style="font-weight: 700; color: {'#15803d' if float(residualhours or 0) >= 0 else '#b91c1c'};">{residualhours}</span><br/>
<div style="margin-top: 12px; margin-bottom: 4px;"><i>Ripartizione:</i></div>
&bull; Ore Lavorate (Labor): {laborhours}<br/>
&bull; Ore Fatturate: <span style="color: #047857; font-weight: 500;">{invoicedhours}</span><br/>
&bull; Ore da Fatturare: <span style="color: #d97706; font-weight: 500;">{toinvoicehours}</span><br/>
&bull; Ore Non Fatturabili: <span style="color: #b91c1c; font-weight: 500;">{nonbillablehours}</span><br/>
&bull; Ore di Viaggio: {travelhours}<br/>
&bull; Ore Commerciali (Sales): {saleshours}<br/>
<div style="margin-top: 12px; margin-bottom: 4px;"><i>Contrattualistica:</i></div>
&bull; Ore Progetto (Fixed Price): {fixedpricehours}<br/>
&bull; Ore Contratto/Monte Ore: {bankhours}<br/>
</div>"""
        deal_record.values['hoursnote'] = hoursnote.strip()

    @staticmethod
    def _process_deallines(deal_record: UserRecord, dealline_records: list, project_recordid: str) -> dict:
        deal_fixedpricehours = deal_record.values.get('fixedpricehours') or 0
        
        totals = {
            'amount_sum': 0,
            'expectedcost': 0,
            'expectedhours': 0,
            'actualcost': 0,
            'effectivemargin': 0,
            'annualprice': 0,
            'annualcost': 0,
            'annualmargin': 0,
            'expectedhwservicecost': 0,
            'expectedhwservicemargin': 0,
            'actualhwservicecost': 0,
            'actualhwservicemargin': 0,
            'expectedhwserviceprice': 0,
            'expectedlaborcost': 0,
            'expectedlabormargin': 0,
            'actuallaborcost': 0,
            'actuallabormargin': 0,
            'expectedlaborprice': 0
        }


        for dl_dict in dealline_records:
            dl_recordid = dl_dict['recordid_']
            dl_record = UserRecord('dealline', dl_recordid, load_fields=False)
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

            totals['amount_sum'] += dl_price
            totals['expectedcost'] += dl_expectedcost

            dl_actualcost = dl_unitactualcost * dl_quantity
            
            product_fixedprice = 'No'
            if product_recordid:
                product_record = UserRecord('product', product_recordid, load_fields=False)
                if not Helper.isempty(product_record.recordid) and not Helper.isempty(product_record.values):
                    product_fixedprice = product_record.values.get('fixedprice', 'No')

            expectedhours = dl_dict.get('expectedhours') or 0
            totals['expectedhours'] += expectedhours
            
            if product_fixedprice == 'Si':
                deal_record.values['fixedprice'] = 'Si'
                if Helper.isempty(dl_record.values.get('expectedhours')):
                    dl_record.values['expectedhours'] = dl_price / 140
                    
                if deal_fixedpricehours != 0:
                    dl_record.values['usedhours'] = deal_fixedpricehours
                    dl_actualcost = deal_fixedpricehours * 60
                    deal_fixedpricehours = 0

                    
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
                
                totals['annualprice'] += dl_record.values['annualprice']
                totals['annualcost'] += dl_record.values['annualcost']
                totals['annualmargin'] += dl_record.values['annualmargin']
            
            dl_record.save()

            if product_fixedprice == 'Si':
                totals['expectedlaborcost'] += dl_expectedcost
                totals['expectedlabormargin'] += dl_expectedmargin
                totals['actuallaborcost'] += dl_actualcost
                totals['actuallabormargin'] += dl_actualmargin
                totals['expectedlaborprice'] += dl_price
            else:
                totals['expectedhwservicecost'] += dl_expectedcost
                totals['expectedhwservicemargin'] += dl_expectedmargin
                totals['actualhwservicecost'] += dl_actualcost
                totals['actualhwservicemargin'] += dl_actualmargin
                totals['expectedhwserviceprice'] += dl_price

            totals['actualcost'] += dl_actualcost
            totals['effectivemargin'] += dl_actualmargin

        return totals

    @staticmethod
    def _finalize_deal_calculations(deal_record: UserRecord, dealline_records: list, totals: dict):
        amount = deal_record.values.get('amount') or 0
        expectedcost = deal_record.values.get('expectedcost') or 0
        
        amount = totals['amount_sum']
        expectedcost = totals['expectedcost']
            
        deal_expectedmargin = amount - expectedcost
        
        # Recupero costo e ricavo ore fatturabili generati dai timesheet 
        invoiced_laborcost = deal_record.values.get('actuallaborcost') or 0
        invoiced_amount = deal_record.values.get('invoicedhoursamount') or 0
        invoiced_margin = invoiced_amount - invoiced_laborcost
        salescost = deal_record.values.get('salescost') or 0
        nonbillablecost = deal_record.values.get('nonbillablecost') or 0

        #recupero costo e ricavo ore monte ore
        deductedhours = deal_record.values.get('deductedhours') or 0
        deductedhoursamount = deal_record.values.get('deductedhoursamount') or 0
        deductedhoursmargin = deal_record.values.get('deductedhoursmargin') or 0

        # effectivemargin NON include invoiced_margin
        actualcost = totals['actualcost']
        effectivemargin = totals['effectivemargin']

        if actualcost == 0:
            effectivemargin = deal_expectedmargin

        # actualgrossmargin include invoiced_margin
        actualgrossmargin = effectivemargin + invoiced_margin
        
        # actualnetmargin include invoiced_margin e sottrae salescost e nonbillablecost
        actualnetmargin = actualgrossmargin - salescost - nonbillablecost

        price_safe = amount if amount else 1
        expectedmargin_perc = round((deal_expectedmargin / price_safe) * 100, 2) if amount else 0
        effectivemargin_perc = round((effectivemargin / price_safe) * 100, 2) if amount else 0
        actualgrossmargin_perc = round((actualgrossmargin / price_safe) * 100, 2) if amount else 0
        actualnetmargin_perc = round((actualnetmargin / price_safe) * 100, 2) if amount else 0

        deal_record.values['amount'] = round(amount, 2)
        deal_record.values['grossamount'] = round(amount + invoiced_amount, 2)
        deal_record.values['expectedcost'] = round(expectedcost, 2)
        deal_record.values['expectedmargin'] = round(deal_expectedmargin, 2)
        deal_record.values['expectedmargin_perc'] = expectedmargin_perc
        deal_record.values['expectedhours'] = totals['expectedhours']
        
        deal_record.values['actualcost'] = round(actualcost + invoiced_laborcost, 2)
        
        deal_record.values['effectivemargin'] = round(effectivemargin, 2)
        deal_record.values['effectivemargin_perc'] = effectivemargin_perc
        deal_record.values['margindifference'] = round(effectivemargin - deal_expectedmargin, 2)

        deal_record.values['actualgrossmargin'] = round(actualgrossmargin, 2)
        deal_record.values['actualgrossmargin_perc'] = actualgrossmargin_perc
        deal_record.values['actualgrossmargindifference'] = round(actualgrossmargin - deal_expectedmargin, 2)

        deal_record.values['actualnetmargin'] = round(actualnetmargin, 2)
        deal_record.values['actualnetmargin_perc'] = actualnetmargin_perc
        deal_record.values['actualnetmargindifference'] = round(actualnetmargin - deal_expectedmargin, 2)

        if deductedhours > 0:
            virtualgrossmargin = actualgrossmargin + deductedhoursmargin
            virtualnetmargin = actualnetmargin + deductedhoursmargin
            deal_record.values['virtualamount'] = round(amount + invoiced_amount + deductedhoursamount, 2)
            deal_record.values['virtualgrossmargin'] = round(virtualgrossmargin , 2)
            deal_record.values['virtualgrossmargindifference'] = round(virtualgrossmargin - deal_expectedmargin, 2)
            deal_record.values['virtualnetmargin'] = round(virtualnetmargin, 2)
            deal_record.values['virtualnetmargindifference'] = round(virtualnetmargin - deal_expectedmargin, 2)
        else:
            deal_record.values['virtualamount'] = None
            deal_record.values['virtualgrossmargin'] = None
            deal_record.values['virtualgrossmargindifference'] = None
            deal_record.values['virtualnetmargin'] = None
            deal_record.values['virtualnetmargindifference'] = None
        
        deal_record.values['annualprice'] = totals['annualprice']
        deal_record.values['annualcost'] = totals['annualcost']
        deal_record.values['annualmargin'] = totals['annualmargin']
        deal_record.values['expectedhwserviceprice'] = totals['expectedhwserviceprice']
        deal_record.values['expectedhwservicecost'] = totals['expectedhwservicecost']
        deal_record.values['expectedhwservicemargin'] = totals['expectedhwservicemargin']
        deal_record.values['actualhwservicecost'] = totals['actualhwservicecost']
        deal_record.values['actualhwservicemargin'] = totals['actualhwservicemargin']
        
        deal_record.values['hwservicedifference'] = totals['actualhwservicemargin'] - totals['expectedhwservicemargin']

        deal_record.values['expectedlaborprice'] = totals['expectedlaborprice']
        deal_record.values['expectedlaborcost'] = totals['expectedlaborcost']
        deal_record.values['expectedlabormargin'] = totals['expectedlabormargin']
        
        actuallaborcost = totals['actuallaborcost'] + invoiced_laborcost
        deal_record.values['actuallaborcost'] = actuallaborcost
        
        if totals['expectedhours'] > 0:
            deal_record.values['actuallabormargin'] = totals['actuallabormargin'] + invoiced_margin
        else:
            deal_record.values['actuallabormargin'] = None

        if totals['expectedlaborprice'] > 0:
            deal_record.values['laborcostdifference'] = totals['expectedlaborcost'] - actuallaborcost
        else:
            deal_record.values['laborcostdifference'] = None
            
        laborhours = deal_record.values.get('laborhours') or 0
        if totals['expectedhours'] > 0:
            deal_record.values['laborhoursdifference'] = totals['expectedhours'] - laborhours
        else:
            deal_record.values['laborhoursdifference'] = None

        # Formattazione per la nota inline svizzera (con ' per migliaia e . per decimali)
        def f_ch(val):
            return f"{float(val or 0):,.2f}".replace(",", "'")
            
        hw_rev = deal_record.values.get('expectedhwserviceprice') or 0
        hw_cost_exp = deal_record.values.get('expectedhwservicecost') or 0
        hw_cost_act = deal_record.values.get('actualhwservicecost') or 0
        hw_marg_exp = deal_record.values.get('expectedhwservicemargin') or 0
        hw_marg_act = deal_record.values.get('actualhwservicemargin') or 0
        hw_marg_exp_perc = (hw_marg_exp / hw_rev * 100) if hw_rev else 0
        hw_marg_act_perc = (hw_marg_act / hw_rev * 100) if hw_rev else 0
        
        lab_rev_deal = deal_record.values.get('expectedlaborprice') or 0
        lab_rev = lab_rev_deal + (deal_record.values.get('invoicedhoursamount') or 0)
        lab_cost_exp = deal_record.values.get('expectedlaborcost') or 0
        lab_cost_act = deal_record.values.get('actuallaborcost') or 0
        lab_marg_exp = deal_record.values.get('expectedlabormargin') or 0
        # Inseriamo il margine di lavoro calcolato per allinearci ai fallback del backend
        lab_marg_act = totals['actuallabormargin'] + invoiced_margin 
        lab_marg_exp_perc = (lab_marg_exp / lab_rev * 100) if lab_rev else 0
        lab_marg_act_perc = (lab_marg_act / lab_rev * 100) if lab_rev else 0
        
        tot_rev = deal_record.values.get('grossamount') or 0
        tot_cost_exp = deal_record.values.get('expectedcost') or 0
        tot_cost_act = deal_record.values.get('actualcost') or 0
        tot_marg_exp = deal_record.values.get('expectedmargin') or 0
        tot_marg_act = deal_record.values.get('actualgrossmargin') or 0
        
        expectedmargin_perc = deal_record.values.get('expectedmargin_perc') or 0
        actualgrossmargin_perc = deal_record.values.get('actualgrossmargin_perc') or 0
        actualnetmargin = deal_record.values.get('actualnetmargin') or 0
        actualnetmargin_perc = deal_record.values.get('actualnetmargin_perc') or 0

        # Funzioni di utilità per formattazione HTML e Colori
        def c_rev(v): return f'<span style="color: #047857; font-weight: 500;">{f_ch(v)}</span>'
        def c_cost(v): return f'<span style="color: #b91c1c; font-weight: 500;">{f_ch(v)}</span>'
        def c_marg(v): 
            c = "#15803d" if (v and float(v) >= 0) else "#b91c1c"
            return f'<span style="color: {c}; font-weight: 700;">{f_ch(v)}</span>'
        def c_perc(v):
            c = "#15803d" if (v and float(v) >= 0) else "#b91c1c"
            return f'<span style="color: {c}; font-weight: 700;">{f_ch(v)}%</span>'

        # Helper per generare nota discorsiva sulle discrepanze
        def diff_note(title, rev_exp, rev_act, cost_exp, cost_act, marg_exp, marg_act):
            diff_marg = marg_act - marg_exp
            if abs(diff_marg) < 0.01 and abs(cost_exp - cost_act) < 0.01 and abs(rev_exp - rev_act) < 0.01:
                return ""
            
            trend = "in <span style='color: #b91c1c; font-weight: bold;'>calo</span>" if diff_marg < 0 else "in <span style='color: #15803d; font-weight: bold;'>crescita</span>"
            border_color = "#b91c1c" if diff_marg < 0 else "#15803d"
            
            s = f"<div style='margin-top: 8px; padding: 8px; background-color: #f9fafb; border-left: 4px solid {border_color}; border-radius: 4px; font-size: 0.9em;'>"
            s += f"<b>Nota {title}</b>:<br/> L'utile reale ({c_marg(marg_act)}) risulta {trend} di <b>{f_ch(abs(diff_marg))}</b> rispetto al budget iniziale ({f_ch(marg_exp)})."
            
            reasons = []
            if abs(rev_act - rev_exp) >= 0.01:
                dir_rev = "maggiori" if rev_act > rev_exp else "minori"
                reasons.append(f"<b>{dir_rev} ricavi effettivi</b> ({c_rev(rev_act)} contro {f_ch(rev_exp)})")
                
            if abs(cost_act - cost_exp) >= 0.01:
                dir_cost = "incremento" if cost_act > cost_exp else "risparmio"
                reasons.append(f"un <b>{dir_cost} dei costi</b> ({c_cost(cost_act)} reali contro {f_ch(cost_exp)} previsti)")
                
            if reasons:
                s += f"<br/><span style='color: #4b5563;'>Lo scostamento è causato da: {' e da '.join(reasons)}.</span>"
            s += "</div>"
            return s

        # Generazione nota HTML riepilogativa per Totali e Margini
        lines = []
        lines.append(f'<div class="deal-summary" style="font-size: 1em;color: black"><strong>Fatturato: {c_rev(tot_rev)}</strong></div>')
        lines.append('<div class="deal-details" style="font-family: system-ui, sans-serif; line-height: 1.5; color: #1f2937;">')
        
        # 1. Analisi HARDWARE
        lines.append('<div style="margin-bottom: 20px;">')
        lines.append('<div style="font-size: 1.1em; color: #1e40af; margin-bottom: 8px; border-bottom: 1px solid #bfdbfe; padding-bottom: 4px;"><b>1. Analisi HARDWARE</b></div>')
        lines.append(f"Ricavo: {c_rev(hw_rev)}<br/>")
        lines.append(f"Costo Previsto: {f_ch(hw_cost_exp)}<br/>")
        lines.append(f"Costo Reale: {c_cost(hw_cost_act)}<br/>")
        
        lines.append('<div style="margin-top: 8px;">')
        lines.append("<i>Marginalità Prevista:</i><br/>")
        lines.append(f"Utile Previsto: {f_ch(hw_rev)} - {f_ch(hw_cost_exp)} = <b>{f_ch(hw_marg_exp)}</b><br/>")
        if hw_rev > 0:
            lines.append(f"Margine % Previsto: ({f_ch(hw_marg_exp)} / {f_ch(hw_rev)}) * 100 = <b>{f_ch(hw_marg_exp_perc)}%</b><br/>")
        else:
            lines.append("Margine % Previsto: <span style='color:#6b7280;'>N/A (Ricavo HW assente)</span><br/>")
        lines.append("</div>")
            
        lines.append('<div style="margin-top: 8px;">')
        lines.append("<i>Marginalità Reale:</i><br/>")
        lines.append(f"Utile / Perdita Reale: {c_rev(hw_rev)} - {c_cost(hw_cost_act)} = {c_marg(hw_marg_act)}<br/>")
        if hw_rev > 0:
            lines.append(f"Margine % Reale: ({c_marg(hw_marg_act)} / {c_rev(hw_rev)}) * 100 = {c_perc(hw_marg_act_perc)}<br/>")
        else:
            lines.append("Margine % Reale: <span style='color:#6b7280;'>N/A (Ricavo HW assente)</span><br/>")
        lines.append("</div>")
            
        hw_note = diff_note("Hardware", hw_rev, hw_rev, hw_cost_exp, hw_cost_act, hw_marg_exp, hw_marg_act)
        if hw_note: lines.append(hw_note)
        lines.append('</div>')

        # 2. Analisi LAVORO UOMO
        lines.append('<div style="margin-bottom: 20px;">')
        lines.append('<div style="font-size: 1.1em; color: #1e40af; margin-bottom: 8px; border-bottom: 1px solid #bfdbfe; padding-bottom: 4px;"><b>2. Analisi LAVORO UOMO</b></div>')
            
        lines.append(f"Ricavo <span style='font-size:0.85em; color:#6b7280;'>(Ordine + Fatture)</span>: {c_rev(lab_rev)}<br/>")
        lines.append(f"Costo Previsto: {f_ch(lab_cost_exp)}<br/>")
        lines.append(f"Costo Reale (Labor): {c_cost(lab_cost_act)}<br/>")
        
        lines.append('<div style="margin-top: 8px;">')
        lines.append("<i>Marginalità Prevista:</i><br/>")
        lines.append(f"Utile Previsto: {f_ch(lab_rev_deal)} - {f_ch(lab_cost_exp)} = <b>{f_ch(lab_marg_exp)}</b><br/>")
        if lab_rev_deal > 0:
            lines.append(f"Margine % Previsto: ({f_ch(lab_marg_exp)} / {f_ch(lab_rev_deal)}) * 100 = <b>{f_ch(lab_marg_exp_perc)}%</b><br/>")
        else:
            lines.append("Margine % Previsto: <span style='color:#6b7280;'>N/A (Nessun ricavo labor preventivato)</span><br/>")
        lines.append("</div>")
            
        lines.append('<div style="margin-top: 8px;">')
        lines.append("<i>Marginalità Reale:</i><br/>")
        lines.append(f"Utile / Perdita Reale: {c_rev(lab_rev)} - {c_cost(lab_cost_act)} = {c_marg(lab_marg_act)}<br/>")
        if lab_rev > 0:
            lines.append(f"Margine % Reale: ({c_marg(lab_marg_act)} / {c_rev(lab_rev)}) * 100 = {c_perc(lab_marg_act_perc)}<br/>")
        else:
            lines.append("Margine % Reale: <span style='color:#6b7280;'>N/A (Pura spesa non coperta da ricavi dedicati)</span><br/>")
        lines.append("</div>")
            
        lab_note = diff_note("Lavoro Uomo", lab_rev_deal, lab_rev, lab_cost_exp, lab_cost_act, lab_marg_exp, lab_marg_act)
        if lab_note: lines.append(lab_note)
        lines.append('</div>')

        # 3. Prospetto TOTALE
        lines.append('<div style="margin-bottom: 20px;">')
        lines.append('<div style="font-size: 1.1em; color: #1e40af; margin-bottom: 8px; border-bottom: 1px solid #bfdbfe; padding-bottom: 4px;"><b>3. Prospetto GLOBALE</b></div>')
        lines.append(f"Ricavi Totali: {c_rev(tot_rev)} <span style='font-size:0.85em; color:#6b7280;'>({f_ch(hw_rev)} hw + {f_ch(lab_rev)} uomo)</span><br/>")
        lines.append(f"Costi Previsti Totali: {f_ch(tot_cost_exp)} <span style='font-size:0.85em; color:#6b7280;'>({f_ch(hw_cost_exp)} hw + {f_ch(lab_cost_exp)} uomo)</span><br/>")
        lines.append(f"Costi Reali Totali: {c_cost(tot_cost_act)} <span style='font-size:0.85em; color:#6b7280;'>({f_ch(hw_cost_act)} hw + {f_ch(lab_cost_act)} uomo)</span><br/>")
        
        lines.append('<div style="margin-top: 8px;">')
        lines.append("<i>Marginalità GLOBALE Prevista:</i><br/>")
        lines.append(f"Utile Previsto Totale: {f_ch(tot_rev)} - {f_ch(tot_cost_exp)} = <b>{f_ch(tot_marg_exp)}</b><br/>")
        lines.append(f"Margine % Previsto Totale: <b>{f_ch(expectedmargin_perc)}%</b><br/>")
        lines.append("</div>")
        
        lines.append('<div style="margin-top: 8px;">')
        lines.append("<i>Marginalità GLOBALE Reale:</i><br/>")
        real_sum_marg = hw_marg_act + lab_marg_act
        import math
        if not math.isclose(real_sum_marg, tot_marg_act, abs_tol=0.01):
            lines.append(f"Perdita / Utile Matematico: {f_ch(hw_marg_act)} (hw) + {f_ch(lab_marg_act)} (uomo) = {f_ch(real_sum_marg)}<br/>")
            lines.append(f"👉 <span style='color:#d97706; font-weight:500;'>Valore Riproporzionato a {c_marg(tot_marg_act)}</span> <span style='font-size:0.85em; color:#6b7280;'>(Assenza Costi Reali inseriti)</span><br/>")
        else:
            lines.append(f"Perdita / Utile Reale: {c_marg(hw_marg_act)} (hw) + {c_marg(lab_marg_act)} (uomo) = <span style='font-size:1.1em;'>{c_marg(tot_marg_act)}</span><br/>")
        lines.append(f"Margine % Reale Totale: <span style='font-size:1.1em;'>{c_perc(actualgrossmargin_perc)}</span><br/>")
        lines.append("</div>")
        lines.append('</div>')

        # 4. Analisi aggiuntiva
        lines.append('<div style="margin-bottom: 20px;">')
        lines.append('<div style="font-size: 1.1em; color: #1e40af; margin-bottom: 8px; border-bottom: 1px solid #bfdbfe; padding-bottom: 4px;"><b>4. Analisi aggiuntiva</b></div>')
        lines.append(f"Margine Lordo Reale: {c_marg(tot_marg_act)}<br/>")
        lines.append(f"Costi Commerciali (Sales): {c_cost(salescost)}<br/>")
        lines.append(f"Costi Non Fatturabili: {c_cost(nonbillablecost)}<br/>")
        
        lines.append('<div style="margin-top: 8px;">')
        lines.append(f"<b>Margine Netto Reale</b> <span style='color:#6b7280;'>(Lordo - Sales - Non Fat.)</span>: <span style='font-size:1.1em;'>{c_marg(actualnetmargin)}</span> ({c_perc(actualnetmargin_perc)})<br/>")
        lines.append("</div>")

        if deductedhours > 0:
            lines.append(f"<div style='margin-top:8px; padding-top:8px; border-top:1px dashed #d1d5db;'>")
            lines.append(f"<span style='color:#4b5563; font-weight:600;'>Integrazione Monte Ore (Virtuale):</span><br/>")
            lines.append(f"&bull; Fatturato Virtuale: {c_rev(deal_record.values.get('virtualamount') or 0)}<br/>")
            lines.append(f"&bull; Margine Lordo Virtuale: {c_marg(deal_record.values.get('virtualgrossmargin') or 0)}<br/>")
            lines.append(f"&bull; Margine Netto Virtuale: {c_marg(deal_record.values.get('virtualnetmargin') or 0)}<br/>")
            lines.append("</div>")
            
        an_price = deal_record.values.get('annualprice') or 0
        an_cost = deal_record.values.get('annualcost') or 0
        if an_price > 0 or an_cost > 0:
            lines.append(f"<div style='margin-top:8px; padding-top:8px; border-top:1px dashed #d1d5db;'>")
            lines.append(f"<span style='color:#4b5563; font-weight:600;'>Valori Ricorrenti (Annuity):</span><br/>")
            lines.append(f"&bull; Ricavo Annuo: {c_rev(an_price)}<br/>")
            lines.append(f"&bull; Costo Annuo: {c_cost(an_cost)}<br/>")
            lines.append(f"&bull; Margine Annuo: {c_marg(deal_record.values.get('annualmargin') or 0)}<br/>")
            lines.append("</div>")

        lines.append('</div>')
        lines.append('</div>')
        
        deal_record.values['totalsnote'] = ''.join(lines)

    @staticmethod
    def _check_project_completion(deal_record: UserRecord, dealline_records: list):
        project_records = deal_record.get_linkedrecords_dict(linkedtable='project')
        for pr_dict in project_records:
            deal_record.values['projectcompleted'] = pr_dict.get('completed')

            if pr_dict.get('completed') == 'Si':
                included_subcategories = {
                    'data_security',
                    'mobile_security',
                    'infrastructure',
                    'sophos',
                    'microsoft',
                    'firewall',
                }
                included_subcategories.add('service_and_asset')
                for dl_dict in dealline_records:
                    product = UserRecord('product', dl_dict['recordidproduct_'], load_fields=False)
                    if product and product.recordid and product.values.get('subcategory') in included_subcategories:
                        sql = f"""
                            SELECT recordid_ FROM user_serviceandasset WHERE recordiddeal_ = {deal_record.recordid} AND recordidcompany_ = {deal_record.values.get('recordidcompany_')} AND recordidproduct_ = {dl_dict['recordidproduct_']} AND deleted_ = 'N'
                        """
                        with connection.cursor() as cursor:
                            cursor.execute(sql)
                            row = cursor.fetchone()
                            if row:
                                recordid_serviceandasset = row[0]
                                record_serviceandasset = UserRecord('serviceandasset', recordid_serviceandasset)
                            else:
                                record_serviceandasset = UserRecord('serviceandasset')
                                record_serviceandasset.values['recordiddeal_'] = deal_record.recordid
                                record_serviceandasset.values['recordidcompany_'] = deal_record.values.get('recordidcompany_')
                                record_serviceandasset.values['recordidproduct_'] = dl_dict['recordidproduct_']
                            record_serviceandasset.values['quantity'] = dl_dict.get('quantity')
                            record_serviceandasset.values['description'] = dl_dict.get('name')
                            record_serviceandasset.values['type'] = product.values.get('category')
                            record_serviceandasset.values['sector'] = product.values.get('category')
                            record_serviceandasset.save()
                

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
