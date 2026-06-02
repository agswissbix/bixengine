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
        
        # 5. Processa timesheets, deallines e finalizza calcoli
        DealService._process_deal_calculations(deal_record, dealline_records, project_recordid)

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
    def _process_deal_calculations(deal_record: UserRecord, dealline_records: list, project_recordid: str):
        import math
        
        # --- INIT ACCUMULATORI ---
        # Hardware/Servizi dealline
        totals = {
            'amount_sum': 0,
            'expectedcost': 0,
            'totalcontractvalue': 0,
            'totalcontractmargin_act': 0,
            'totalcontractexpectedcost': 0,
            
            'expectedhwserviceprice': 0,
            'expectedhwservicecost': 0,
            'expectedhwservicemargin': 0,
            'actualhwservicecost': 0,
            'actualhwservicemargin': 0,
            
            'expectedlaborprice': 0,
            'expectedlaborcost': 0,
            'expectedlabormargin': 0,
            
            'expectedhours': 0,
            
            'annualprice': 0,
            'annualcost': 0,
            'annualmargin': 0,
            
            'actualcost': 0,
            'effectivemargin': 0,
        }
        
        actual_labor_cost_deallines = 0
        actual_labor_margin_deallines = 0
        deal_fixedpricehours = deal_record.values.get('fixedpricehours') or 0

        # --- 1. LETTURA DEALLINES ---
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
            expectedhours = dl_dict.get('expectedhours') or 0

            product_fixedprice = 'No'
            if product_recordid:
                product_record = UserRecord('product', product_recordid, load_fields=False)
                if not Helper.isempty(product_record.recordid) and not Helper.isempty(product_record.values):
                    product_fixedprice = product_record.values.get('fixedprice', 'No')

            if product_fixedprice == 'Si':
                deal_record.values['fixedprice'] = 'Si'
                if Helper.isempty(dl_record.values.get('expectedhours')):
                    dl_record.values['expectedhours'] = dl_price / 140
                    expectedhours = dl_record.values['expectedhours']

            totals['expectedhours'] += expectedhours
            dl_actualcost = dl_unitactualcost * dl_quantity

            if product_fixedprice == 'Si' and deal_fixedpricehours != 0:
                dl_record.values['usedhours'] = deal_fixedpricehours
                dl_actualcost = deal_fixedpricehours * 60
                deal_fixedpricehours = 0

            dl_actualmargin = (dl_price - dl_actualcost) if dl_actualcost != 0 else dl_expectedmargin
                
            dl_record.values['effectivecost'] = dl_actualcost
            dl_record.values['margin_actual'] = dl_actualmargin

            # Multiplier freq
            multiplier = 1
            if dl_frequency == 'Semestrale': multiplier = 2
            elif dl_frequency == 'Trimestrale': multiplier = 4
            elif dl_frequency == 'Bimestrale': multiplier = 6
            elif dl_frequency == 'Mensile': multiplier = 12

            totals['amount_sum'] += dl_price
            totals['expectedcost'] += dl_expectedcost

            contractual_obligation_raw = dl_dict.get('contractual_obligation')
            try:
                contract_ob = int(contractual_obligation_raw)
            except (ValueError, TypeError):
                contract_ob = 0
                
            if not Helper.isempty(dl_frequency):
                monthly_price = (dl_price * multiplier) / 12.0
                totals['totalcontractvalue'] += (monthly_price * contract_ob)
                monthly_expcost = (dl_expectedcost * multiplier) / 12.0
                totals['totalcontractexpectedcost'] += (monthly_expcost * contract_ob)
                monthly_marg_act = (dl_actualmargin * multiplier) / 12.0
                totals['totalcontractmargin_act'] += (monthly_marg_act * contract_ob)
                
                dl_record.values['annualprice'] = dl_price * multiplier
                dl_record.values['annualcost'] = dl_actualcost * multiplier if dl_actualcost != 0 else dl_expectedcost * multiplier
                dl_record.values['annualmargin'] = dl_record.values['annualprice'] - dl_record.values['annualcost']
                
                totals['annualprice'] += dl_record.values['annualprice']
                totals['annualcost'] += dl_record.values['annualcost']
                totals['annualmargin'] += dl_record.values['annualmargin']
            else:
                totals['totalcontractvalue'] += dl_price
                totals['totalcontractexpectedcost'] += dl_expectedcost
                totals['totalcontractmargin_act'] += dl_actualmargin
            
            dl_record.save()

            if product_fixedprice == 'Si':
                totals['expectedlaborprice'] += dl_price
                totals['expectedlaborcost'] += dl_expectedcost
                totals['expectedlabormargin'] += dl_expectedmargin
            else:
                totals['expectedhwserviceprice'] += dl_price
                totals['expectedhwservicecost'] += dl_expectedcost
                totals['expectedhwservicemargin'] += dl_price - dl_expectedcost
                totals['actualhwservicecost'] += dl_actualcost
                totals['actualhwservicemargin'] += dl_price - dl_actualcost

            totals['actualcost'] += dl_actualcost
            totals['effectivemargin'] += dl_price - dl_actualcost


        # --- 2. LETTURA TIMESHEETS ---
        usedhours = 0
        residualhours = 0
        travelhours = 0
        travelcost = 0
        fixedpricehours = 0
        servicecontracthours = 0
        bankhours = 0
        deductedhoursamount = 0
        deductedhourscost = 0
        invoicedhours = 0
        invoicedhoursamount = 0
        toinvoicehours = 0
        toinvoicehoursamount = 0
        laborcost_timesheets = 0
        nonbillablehours = 0
        nonbillablecost = 0
        saleshours = 0
        salescost = 0
        laborhours = 0
        totalhours = 0
        
        timesheets_dict = {}

        if project_recordid:
            project_record = UserRecord('project', project_recordid, load_fields=False)
            for ts in project_record.get_linkedrecords_dict('timesheet'):
                ts_id = ts.get('recordid_')
                if ts_id:
                    timesheets_dict[ts_id] = ts

        for ts in deal_record.get_linkedrecords_dict('timesheet'):
            ts_id = ts.get('recordid_')
            if ts_id:
                timesheets_dict[ts_id] = ts

        for ts_dict in timesheets_dict.values():
            invoicestatus = ts_dict.get('invoicestatus')
            try: hours = float(ts_dict.get('totaltime_decimal') or 0)
            except ValueError: hours = 0
            try: price = float(ts_dict.get('totalprice') or 0)
            except ValueError: price = 0
            try: worktime = float(ts_dict.get('worktime_decimal') or 0)
            except ValueError: worktime = 0
            try: travel_hours = float(ts_dict.get('traveltime_decimal') or 0)
            except ValueError: travel_hours = 0
            try: travel_price = float(ts_dict.get('travelprice') or 0)
            except ValueError: travel_price = 0

            

            
            
            travelhours += travel_hours
            travelcost += travelhours *60
            totalhours += hours
            

            service = ts_dict.get('service')
            invoicestatus = str(invoicestatus).strip().lower()

            service_lower = str(service).strip().lower() if service else ''
            
            if service_lower == 'commerciale':
                saleshours += worktime
                salescost += worktime * 60
            elif service_lower in ['formazione e test', 'interno', 'amministrazione', 'riunione']:
                usedhours += worktime
                nonbillablehours += worktime
                nonbillablecost += worktime * 60
            else:
                usedhours += worktime
                laborhours += worktime
                laborcost_timesheets += worktime * 60
                


            
            if invoicestatus == 'fixed price project':
                fixedpricehours += worktime
            elif invoicestatus == 'service contract: monte ore':
                bankhours += worktime
                deductedhoursamount += worktime * 100
                deductedhourscost += worktime * 60
            elif invoicestatus == 'invoiced':
                invoicedhours += worktime
                invoicedhoursamount += price
            elif invoicestatus and invoicestatus.startswith('to invoice'):
                toinvoicehours += worktime
                toinvoicehoursamount += price
                


        expectedhours_total = totals['expectedhours'] or deal_record.values.get('expectedhours') or 0
        if expectedhours_total:
            residualhours = expectedhours_total - usedhours
                
        # Salvataggio totali ore su record
        deal_record.values['expectedhours'] = expectedhours_total
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

        # --- 3. CALCOLO FINALE CAMPI (Margini, Costi, Differenze) ---
        
        # A. Hardware / Servizi Base
        amount = totals['amount_sum']
        expectedcost = totals['expectedcost']
        deal_expectedmargin = amount - expectedcost
        
        deal_record.values['expectedhwserviceprice'] = totals['expectedhwserviceprice']
        deal_record.values['expectedhwservicecost'] = totals['expectedhwservicecost']
        deal_record.values['expectedhwservicemargin'] = totals['expectedhwservicemargin']
        deal_record.values['actualhwservicecost'] = totals['actualhwservicecost']
        deal_record.values['actualhwservicemargin'] = totals['actualhwservicemargin']
        deal_record.values['hwservicedifference'] = totals['actualhwservicemargin'] - totals['expectedhwservicemargin']

        # B. Lavoro Uomo (Labor) - Integrato con actuallaborprice
        actuallaborprice = invoicedhoursamount + toinvoicehoursamount + totals['expectedlaborprice']
        actuallaborcost = laborcost_timesheets
        actual_labor_cost_deallines = actuallaborcost
        actuallabormargin = actuallaborprice - actuallaborcost

        deal_record.values['expectedlaborprice'] = totals['expectedlaborprice']
        deal_record.values['expectedlaborcost'] = totals['expectedlaborcost']
        deal_record.values['expectedlabormargin'] = totals['expectedlabormargin']
        deal_record.values['actuallaborprice'] = actuallaborprice
        deal_record.values['actuallaborcost'] = actuallaborcost
        
        if expectedhours_total > 0:
            deal_record.values['actuallabormargin'] = actuallabormargin
        else:
            deal_record.values['actuallabormargin'] = None
            
        if totals['expectedlaborprice'] > 0:
            deal_record.values['laborcostdifference'] = totals['expectedlaborcost'] - actuallaborcost
        else:
            deal_record.values['laborcostdifference'] = None
            
        if expectedhours_total > 0:
            deal_record.values['laborhoursdifference'] = expectedhours_total - laborhours
        else:
            deal_record.values['laborhoursdifference'] = None

        # C. Valori Globali (Hardware + Labor)
        # effectivemargin = hardware actual margin + labor fixed price actual margin (NO timesheets)
        # Ma logicamente i costi reali globali devono includere i timesheet
        actualcost = totals['actualcost'] + laborcost_timesheets
        actualgrossmargin = totals['actualhwservicemargin'] + actuallabormargin
        
        deal_record.values['amount'] = round(amount, 2)
        deal_record.values['grossamount'] = round(amount + invoicedhoursamount + toinvoicehoursamount, 2)
        deal_record.values['expectedcost'] = round(expectedcost, 2)
        deal_record.values['expectedmargin'] = round(deal_expectedmargin, 2)
        
        price_safe = amount if amount else 1
        deal_record.values['expectedmargin_perc'] = round((deal_expectedmargin / price_safe) * 100, 2) if amount else 0
        
        deal_record.values['actualcost'] = round(actualcost, 2)
        
        # Effectivemargin viene usato storico per indicare il margine "base", ma qui impostiamo quello calcolato globalmente
        deal_record.values['effectivemargin'] = round(totals['effectivemargin'], 2)
        deal_record.values['effectivemargin_perc'] = round((totals['effectivemargin'] / price_safe) * 100, 2) if amount else 0
        deal_record.values['margindifference'] = round(actualgrossmargin - deal_expectedmargin, 2)

        deal_record.values['actualgrossmargin'] = round(actualgrossmargin, 2)
        gross_rev = amount + invoicedhoursamount + toinvoicehoursamount
        gross_rev_safe = gross_rev if gross_rev else 1
        deal_record.values['actualgrossmargin_perc'] = round((actualgrossmargin / gross_rev_safe) * 100, 2) if gross_rev else 0
        deal_record.values['actualgrossmargindifference'] = round(actualgrossmargin - deal_expectedmargin, 2)

        # D. Margine Netto (Sottrae sales & non billable & travel cost)
        actualnetmargin = actualgrossmargin - salescost - nonbillablecost - travelcost
        deal_record.values['actualnetmargin'] = round(actualnetmargin, 2)
        deal_record.values['actualnetmargin_perc'] = round((actualnetmargin / gross_rev_safe) * 100, 2) if gross_rev else 0
        deal_record.values['actualnetmargindifference'] = round(actualnetmargin - deal_expectedmargin, 2)

        # E. Valori di Contratto
        contract_expectedmargin = totals['totalcontractvalue'] - totals['totalcontractexpectedcost']
        contract_effectivemargin = totals['totalcontractmargin_act']
        if totals['actualcost'] == 0:
            contract_effectivemargin = contract_expectedmargin
            
        contract_grossmargin = contract_effectivemargin + (invoicedhoursamount + toinvoicehoursamount - laborcost_timesheets)
        totalcontractnetmargin = contract_grossmargin - salescost - nonbillablecost - travelcost
        
        deal_record.values['totalcontractvalue'] = round(totals['totalcontractvalue'], 2)
        deal_record.values['totalcontractnetmargin'] = round(totalcontractnetmargin, 2)

        # F. Valori Integrati Monte Ore
        if bankhours > 0:
            virtualgrossmargin = actualgrossmargin + deal_record.values['deductedhoursmargin']
            virtualnetmargin = actualnetmargin + deal_record.values['deductedhoursmargin']
            deal_record.values['virtualamount'] = round(gross_rev + deductedhoursamount, 2)
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


        # --- 4. GENERAZIONE NOTA ESPLICATIVA (HTML) ---

        def f_ch(val):
            return f"{float(val or 0):,.2f}".replace(",", "'")
        def c_rev(v): return f'<span style="color: #047857; font-weight: 500;">{f_ch(v)}</span>'
        def c_cost(v): return f'<span style="color: #b91c1c; font-weight: 500;">{f_ch(v)}</span>'
        def c_marg(v): 
            c = "#15803d" if (v and float(v) >= 0) else "#b91c1c"
            return f'<span style="color: {c}; font-weight: 700;">{f_ch(v)}</span>'
        def c_perc(v):
            c = "#15803d" if (v and float(v) >= 0) else "#b91c1c"
            return f'<span style="color: {c}; font-weight: 700;">{f_ch(v)}%</span>'

        hoursnote = f"""<div class="deal-summary" style="font-size: 1em;color: black;"><strong>{usedhours:.0f}/{expectedhours_total:.0f}</strong></div>
            <div class="deal-details" style="font-family: system-ui, sans-serif; line-height: 1.5; color: #1f2937;">
            <div style="font-size: 1.1em; color: #1e40af; margin-bottom: 8px; border-bottom: 1px solid #bfdbfe; padding-bottom: 4px;"><b>Dettaglio Tempistiche</b></div>
            &bull; Ore Previste: <b>{expectedhours_total}</b><br/>
            &bull; Ore Utilizzate: <b>{usedhours}</b><br/>
            &bull; Ore Residue: <span style="font-weight: 700; color: {'#15803d' if float(residualhours or 0) >= 0 else '#b91c1c'};">{residualhours}</span><br/>
            &bull; Ore di Viaggio: {travelhours}<br/>
            &bull; Totale Generale Ore: <b>{totalhours}</b><br/>
            <div style="margin-top: 12px; margin-bottom: 4px;"><i>Ripartizione:</i></div>
            &bull; Ore Progetto (Fixed Price): {fixedpricehours}<br/>
            &bull; Ore Contratto/Monte Ore: {bankhours}<br/>
            &bull; Ore Fatturate / da Fatturare: <span style="color: #047857; font-weight: 500;">{invoicedhours} / {toinvoicehours}</span><br/>
            &bull; Ore Non Fatturabili: <span style="color: #b91c1c; font-weight: 500;">{nonbillablehours}</span><br/>
            &bull; Ore Commerciali (Sales): {saleshours}<br/>
            
            </div>"""
        deal_record.values['hoursnote'] = hoursnote.strip()

        lines = []
        lines.append(f'<div class="deal-summary" style="font-size: 1em;color: black"><strong>Marg: {c_marg(actualnetmargin)}  ({c_perc(deal_record.values["actualnetmargin_perc"])})</strong></div>')
        lines.append('<div class="deal-details" style="font-family: system-ui, sans-serif; line-height: 1.5; color: #1f2937;">')
        lines.append(f'<div style="font-size: 0.9em; color: #4b5563; margin-top: 4px; margin-bottom: 8px;">Margine Netto: <b>{c_marg(actualnetmargin)}  ({c_perc(deal_record.values["actualnetmargin_perc"])})</b></div>')
        lines.append(f'<div style="font-size: 0.9em; color: #4b5563; margin-top: 4px; margin-bottom: 8px;">Margine Netto fino a fine contratto: <b>{c_marg(totalcontractnetmargin)}</b></div>')

        # 1. Base Preventivo
        lines.append('<div style="margin-bottom: 20px;">')
        lines.append('<div style="font-size: 1.1em; color: #1e40af; margin-bottom: 8px; border-bottom: 1px solid #bfdbfe; padding-bottom: 4px;"><b>1. Base Preventivo (Deallines)</b></div>')
        lines.append(f"Ricavo HW: {f_ch(totals['expectedhwserviceprice'])} &nbsp;|&nbsp; Ricavo Lavoro: {f_ch(totals['expectedlaborprice'])}<br/>")
        lines.append(f"Costo Prev. HW: {f_ch(totals['expectedhwservicecost'])} &nbsp;|&nbsp; Costo Prev. Lavoro: {f_ch(totals['expectedlaborcost'])}<br/>")
        lines.append('</div>')

        # 2. Analisi Hardware
        lines.append('<div style="margin-bottom: 20px;">')
        lines.append('<div style="font-size: 1.1em; color: #1e40af; margin-bottom: 8px; border-bottom: 1px solid #bfdbfe; padding-bottom: 4px;"><b>2. Analisi HARDWARE</b></div>')
        lines.append(f"Ricavo Previsto/Reale: {c_rev(totals['expectedhwserviceprice'])}<br/>")
        lines.append(f"Costo Previsto: {f_ch(totals['expectedhwservicecost'])} &nbsp;>&nbsp; Costo Reale: {c_cost(totals['actualhwservicecost'])}<br/>")
        lines.append(f"<i>Margine Reale:</i> {c_rev(totals['expectedhwserviceprice'])} - {c_cost(totals['actualhwservicecost'])} = <b>{c_marg(totals['actualhwservicemargin'])}</b><br/>")
        lines.append('</div>')

        # 3. Analisi Lavoro
        lines.append('<div style="margin-bottom: 20px;">')
        lines.append('<div style="font-size: 1.1em; color: #1e40af; margin-bottom: 8px; border-bottom: 1px solid #bfdbfe; padding-bottom: 4px;"><b>3. Analisi LAVORO UOMO</b></div>')
        lines.append(f"Ricavo Previsto Base: {f_ch(totals['expectedlaborprice'])}<br/>")
        lines.append(f"Extra Ricavo (Timesheet fatturati e da fat.): {f_ch(invoicedhoursamount + toinvoicehoursamount)}<br/>")
        lines.append(f"Ricavo Reale Totale: {c_rev(actuallaborprice)}<br/><br/>")
        
        lines.append(f"Costo Previsto Base: {f_ch(totals['expectedlaborcost'])}<br/>")
        lines.append(f"Costo Reale (Da preventivo): {f_ch(actual_labor_cost_deallines)}<br/>")
        lines.append(f"Costo Reale (Extra Timesheet): {f_ch(laborcost_timesheets)}<br/>")
        lines.append(f"Costo Reale Totale: {c_cost(actuallaborcost)}<br/><br/>")
        
        lines.append(f"<i>Margine Reale:</i> {c_rev(actuallaborprice)} - {c_cost(actuallaborcost)} = <b>{c_marg(actuallabormargin)}</b><br/>")
        lab_marg_exp_perc = (totals['expectedlabormargin'] / totals['expectedlaborprice'] * 100) if totals['expectedlaborprice'] else 0
        lab_marg_act_perc = (actuallabormargin / actuallaborprice * 100) if actuallaborprice else 0
        lines.append(f"Margine Previsto %: {f_ch(lab_marg_exp_perc)}% &nbsp;>&nbsp; Margine Reale %: {c_perc(lab_marg_act_perc)}<br/>")
        lines.append('</div>')

        # 4. Analisi Globale
        lines.append('<div style="margin-bottom: 20px;">')
        lines.append('<div style="font-size: 1.1em; color: #1e40af; margin-bottom: 8px; border-bottom: 1px solid #bfdbfe; padding-bottom: 4px;"><b>4. Margine GLOBALE e NETTO</b></div>')
        lines.append(f"Ricavo Lordo Totale: {c_rev(gross_rev)} <span style='font-size:0.85em; color:#6b7280;'>(HW + Lavoro)</span><br/>")
        lines.append(f"Costo Reale Totale: {c_cost(actualcost)} <span style='font-size:0.85em; color:#6b7280;'>(HW + Lavoro)</span><br/>")
        lines.append(f"Margine Lordo Reale: {c_marg(actualgrossmargin)}<br/><br/>")
        
        lines.append(f"Costi Commerciali (Sales): {c_cost(salescost)}<br/>")
        lines.append(f"Costi Non Fatturabili: {c_cost(nonbillablecost)}<br/><br/>")
        lines.append(f"<b>Margine Netto Reale</b> <span style='color:#6b7280;'>(Lordo - Sales - Non Fat.)</span>: <span style='font-size:1.1em;'>{c_marg(actualnetmargin)}</span> ({c_perc(deal_record.values['actualnetmargin_perc'])})<br/>")
        lines.append('</div>')

        if bankhours > 0:
            lines.append(f"<div style='margin-top:8px; padding-top:8px; border-top:1px dashed #d1d5db;'>")
            lines.append(f"<span style='color:#4b5563; font-weight:600;'>Integrazione Monte Ore (Virtuale):</span><br/>")
            lines.append(f"&bull; Margine Netto Virtuale: {c_marg(deal_record.values.get('virtualnetmargin') or 0)}<br/>")
            lines.append("</div>")
            
        if totals['annualprice'] > 0 or totals['annualcost'] > 0:
            lines.append(f"<div style='margin-top:8px; padding-top:8px; border-top:1px dashed #d1d5db;'>")
            lines.append(f"<span style='color:#4b5563; font-weight:600;'>Valori Ricorrenti (Annuity):</span><br/>")
            lines.append(f"&bull; Margine Annuo: {c_marg(deal_record.values.get('annualmargin') or 0)}<br/>")
            lines.append("</div>")

        lines.append('</div>')
        deal_record.values['totalsnote'] = ''.join(lines)



    @staticmethod
    def _process_service_contracts(deal_record: UserRecord, dealline_records: list):
        services_subcategories = {'services', 'services_bwbix'}
        services_to_contract = []
        for dl_dict in dealline_records:
            product = UserRecord('product', dl_dict.get('recordidproduct_'), load_fields=False)
            if product and product.recordid and product.values.get('subcategory') in services_subcategories:
                services_to_contract.append(dl_dict)

        if not services_to_contract:
            return
            
        import datetime
        from django.db import connection
        
        first_ob = next((s.get('contractual_obligation', '') for s in services_to_contract if s.get('contractual_obligation')), '')
        current_date_str = datetime.datetime.now().strftime('%Y-%m-%d')
        
        sql_contract = f"""
            SELECT recordid_ FROM user_servicecontract 
            WHERE recordidcompany_ = {deal_record.values.get('recordidcompany_')} 
            AND status = 'In Progress' AND type = 'Manutenzione IT' AND deleted_ = 'N'
        """
        with connection.cursor() as cursor:
            cursor.execute(sql_contract)
            row = cursor.fetchone()
            if row:
                record_servicecontract = UserRecord('servicecontract', row[0])
            else:
                record_servicecontract = UserRecord('servicecontract')
                record_servicecontract.values['recordidcompany_'] = deal_record.values.get('recordidcompany_')
                record_servicecontract.values['type'] = 'Manutenzione IT'
                record_servicecontract.values['status'] = 'In Progress'
                record_servicecontract.values['service'] = 'Assistenza IT'
                record_servicecontract.values['startdate'] = current_date_str
        
        record_servicecontract.values['subject'] = 'Manutenzione servizi'
        record_servicecontract.values['note'] = first_ob
        record_servicecontract.save()

        deal_record.values['recordidservicecontract_'] = record_servicecontract.recordid

        frequencies = set(s.get('intervention_frequency', s.get('frequency', '')) for s in services_to_contract)
        contractual_planning_records = record_servicecontract.get_linkedrecords_dict(linkedtable='contractual_planning')
        planning_by_freq = {}
        
        for freq in frequencies:
            if not freq: continue
                
            freq_services = [s for s in services_to_contract if s.get('intervention_frequency', s.get('frequency', '')) == freq]
            freq_names = [s.get('name', '') for s in freq_services if s.get('name')]
            
            record_planning_id = next((p.get('recordid_') for p in (contractual_planning_records or []) if p.get('frequency') == freq and p.get('deleted_') == 'N'), None)
                        
            if record_planning_id:
                record_planning = UserRecord('contractual_planning', record_planning_id)
            else:
                record_planning = UserRecord('contractual_planning')
                record_planning.values['recordidservicecontract_'] = record_servicecontract.recordid
            
            record_planning.values['title'] = f'Manutenzione servizi - {record_servicecontract.fields.get("recordidcompany_").get("convertedvalue")}'
            record_planning.values['description'] = '<br/>'.join(freq_names)
            record_planning.values['frequency'] = freq
            record_planning.values['start_date'] = current_date_str
            record_planning.save()
            planning_by_freq[freq] = record_planning.recordid

        unique_products = {dl.get('recordidproduct_'): dl for dl in services_to_contract}

        for pid, dl_dict in unique_products.items():
            freq = dl_dict.get('intervention_frequency', dl_dict.get('frequency', ''))
            planning_id = planning_by_freq.get(freq, '')

            from customapp_swissbix.services.custom_save.serviceandasset_services import ServiceAndAssetService
            tot_qty = ServiceAndAssetService.get_recalculated_quantity(
                'recordidservicecontract_', record_servicecontract.recordid, 
                pid, deal_record.recordid
            )
            
            tot_qty += sum(float(dl.get('quantity') or 0) for dl in services_to_contract if dl.get('recordidproduct_') == pid)

            sql_line = f"""
                SELECT recordid_ FROM user_servicecontractlines 
                WHERE recordidservicecontract_ = '{record_servicecontract.recordid}' 
                AND recordidproduct_ = '{pid}' AND deleted_ = 'N'
            """
            with connection.cursor() as cursor:
                cursor.execute(sql_line)
                row = cursor.fetchone()
                if row:
                    record_line = UserRecord('servicecontractlines', row[0])
                else:
                    record_line = UserRecord('servicecontractlines')
                    record_line.values['recordidservicecontract_'] = record_servicecontract.recordid
                    record_line.values['recordidproduct_'] = pid
            
            record_line.values['quantity'] = tot_qty
            record_line.values['recordidcontractual_planning_'] = planning_id
            record_line.values['name'] = dl_dict.get('name')
            record_line.save()

    @staticmethod
    def _check_project_completion(deal_record: UserRecord, dealline_records: list):
        project_records = deal_record.get_linkedrecords_dict(linkedtable='project')
        for pr_dict in project_records:
            deal_record.values['projectcompleted'] = pr_dict.get('completed')

            if pr_dict.get('completed') == 'Si':
                from customapp_swissbix.services.custom_save.serviceandasset_services import ServiceAndAssetService
                ServiceAndAssetService.process_service_and_assets_from_deal(deal_record, dealline_records)
                DealService._process_service_contracts(deal_record, dealline_records)
            

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
