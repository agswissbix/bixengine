from commonapp.bixmodels.user_record import UserRecord
from commonapp.bixmodels.user_table import UserTable
from commonapp.helper import Helper
from datetime import *

class TimesheetService:
    @staticmethod
    def process_timesheet(recordid: str) -> list:
        """
        Processa i campi di un timesheet: valuta l'invoice status, opzioni, 
        contratti flat o monte ore, calcola prezzari e tempistiche e aggiorna 
        il record stesso.
        Ritorna una lista di tuple (tableid, recordid) di record collegati
        da salvare a cascata.
        """
        timesheet_record = UserRecord('timesheet', recordid, load_fields=False)
        servicecontract_table = UserTable(tableid='servicecontract')
        
        company_record = UserRecord('company', timesheet_record.values['recordidcompany_'], load_fields=False)
        project_record = UserRecord('project', timesheet_record.values['recordidproject_'], load_fields=False)
        ticket_record = UserRecord('ticket', timesheet_record.values['recordidticket_'], load_fields=False)
        
        servicecontract_record_id = timesheet_record.values['recordidservicecontract_']
        servicecontract_record = UserRecord('servicecontract', servicecontract_record_id, load_fields=False) if not Helper.isempty(servicecontract_record_id) else None
        
        if Helper.isempty(timesheet_record.values.get('invoicestatus')):
            timesheet_record.values['invoicestatus'] = ''

        # 1. Reset campi base
        TimesheetService._reset_timesheet_fields(timesheet_record)

        # 2. Calcolo decimale dei tempi
        work_dec, travel_dec = TimesheetService._calculate_decimal_times(timesheet_record)

        if timesheet_record.values.get('invoicestatus') != 'Invoiced':
            timesheet_record.values['invoicestatus'] = 'To Process'

        # 3. Valutazioni step-by-step
        TimesheetService._evaluate_non_billable(timesheet_record)
        TimesheetService._evaluate_warranty_options(timesheet_record)
        TimesheetService._evaluate_project(timesheet_record, project_record)
        
        # 4. Assegnazione contratti
        sc_rec = TimesheetService._evaluate_flat_service_contract(timesheet_record, servicecontract_table, work_dec, travel_dec)
        if sc_rec: servicecontract_record = sc_rec
        
        sc_rec = TimesheetService._evaluate_monte_ore_remoto_pbx(timesheet_record, servicecontract_table, travel_dec)
        if sc_rec: servicecontract_record = sc_rec

        sc_rec = TimesheetService._evaluate_monte_ore_standard(timesheet_record, servicecontract_table)
        if sc_rec: servicecontract_record = sc_rec

        # 5. Calcolo prezzi e da fatturare
        TimesheetService._calculate_to_invoice(timesheet_record, company_record, project_record, ticket_record, work_dec, travel_dec)
        
        # 6. Validazioni finali
        TimesheetService._evaluate_validation(timesheet_record)

        timesheet_record.save()

        # Preparo l'elenco dei related records da salvare a cascata
        records_to_save = []
        if servicecontract_record and not Helper.isempty(servicecontract_record.recordid):
            records_to_save.append(('servicecontract', servicecontract_record.recordid))
            
        if not Helper.isempty(project_record.recordid):
            records_to_save.append(('project', project_record.recordid))

        return records_to_save

    @staticmethod
    def _reset_timesheet_fields(timesheet_record: UserRecord):
        """Resetta i campi predefiniti del timesheet prima dei ricalcoli."""
        timesheet_record.values['productivity'] = ''
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

    @staticmethod
    def _calculate_decimal_times(timesheet_record: UserRecord) -> tuple[float, float]:
        worktime = timesheet_record.values.get('worktime')
        traveltime = timesheet_record.values.get('traveltime')
        
        worktime_decimal = 0
        travel_time_decimal = 0
        totaltime_decimal = 0
        
        if not Helper.isempty(worktime):
            hours, minutes = map(int, str(worktime).split(':'))
            worktime_decimal = hours + (minutes / 60)
            if not Helper.isempty(traveltime):
                hours_t, minutes_t = map(int, str(traveltime).split(':'))
                travel_time_decimal = hours_t + (minutes_t / 60)
            totaltime_decimal = worktime_decimal + travel_time_decimal
            
            timesheet_record.values['worktime_decimal'] = worktime_decimal
            timesheet_record.values['traveltime_decimal'] = travel_time_decimal
            timesheet_record.values['totaltime_decimal'] = totaltime_decimal

        return worktime_decimal, travel_time_decimal

    @staticmethod
    def _evaluate_non_billable(timesheet_record: UserRecord):
        invoicestatus = timesheet_record.values.get('invoicestatus')
        service = timesheet_record.values.get('service')
        
        if invoicestatus == 'To Process':
            non_fatturabili = [
                'Amministrazione', 'Commerciale', 'Formazione Apprendista', 
                'Formazione e Test', 'Interno', 'Riunione'
            ]
            if service in non_fatturabili:
                timesheet_record.values['invoicestatus'] = 'Attività non fatturabile'
                timesheet_record.values['productivity'] = 'Senza ricavo'

    @staticmethod
    def _evaluate_warranty_options(timesheet_record: UserRecord):
        invoicestatus = timesheet_record.values.get('invoicestatus')
        invoiceoption = timesheet_record.values.get('invoiceoption')

        if invoicestatus == 'To Process':
            warranty_options = [
                'Under Warranty', 'Commercial support', 'Swisscom incident', 
                'Swisscom ServiceNow', 'To check'
            ]
            if invoiceoption in warranty_options:
                timesheet_record.values['invoicestatus'] = invoiceoption
                timesheet_record.values['productivity'] = 'Senza ricavo'
                timesheet_record.values['print_type'] = 'Garanzia'
                timesheet_record.values['print_hourprice'] = 'Garanzia'
                timesheet_record.values['print_travel'] = 'Garanzia'

    @staticmethod
    def _evaluate_project(timesheet_record: UserRecord, project_record: UserRecord):
        invoicestatus = timesheet_record.values.get('invoicestatus')
        invoiceoption = timesheet_record.values.get('invoiceoption')

        if invoicestatus == 'To Process' and not Helper.isempty(project_record.recordid) and invoiceoption != 'Out of contract':
            timesheet_record.values['print_type'] = 'Progetto N. ' + str(project_record.values['id'])
            
            if project_record.values.get('fixedprice') == 'Si':
                timesheet_record.values['invoicestatus'] = 'Fixed price Project'
                timesheet_record.values['productivity'] = 'Ricavo indiretto'
                timesheet_record.values['print_hourprice'] = 'Compreso nel progetto'
                timesheet_record.values['print_travel'] = 'Inclusa'
                
            if invoiceoption == 'Monte ore':
                timesheet_record.values['print_type'] = ''
                timesheet_record.values['invoicestatus'] = 'To Process'
                timesheet_record.values['productivity'] = ''
                timesheet_record.values['print_hourprice'] = ''
                timesheet_record.values['print_travel'] = ''

    @staticmethod
    def _evaluate_flat_service_contract(timesheet_record: UserRecord, servicecontract_table: UserTable, work_dec: float, travel_dec: float) -> UserRecord:
        invoicestatus = timesheet_record.values.get('invoicestatus')
        invoiceoption = timesheet_record.values.get('invoiceoption')
        service = timesheet_record.values.get('service')
        
        if invoicestatus != 'To Process' or Helper.isempty(timesheet_record.values.get('worktime')) or invoiceoption == 'Out of contract':
            return None

        company_id = timesheet_record.values.get('recordidcompany_')
        contract_type = None

        if service == 'Assistenza PBX':
            if (travel_dec == 0 and work_dec == 0.25) or invoiceoption == 'In contract':
                contract_type = 'Manutenzione PBX'
        elif service == 'Assistenza IT':
            if travel_dec == 0 or invoiceoption == 'In contract':
                contract_type = 'BeAll (All-inclusive)'
        elif service == 'Printing':
            contract_type = 'Manutenzione Printing'
            
        flat_service_contract = None
        if contract_type:
            flat_service_contract = servicecontract_table.get_records(
                conditions_list=[
                    f"recordidcompany_='{company_id}'", 
                    f"type='{contract_type}'",  
                    "status='In Progress'"
                ]
            )
        elif service == 'Assistenza Web Hosting':
            flat_service_contract = servicecontract_table.get_records(
                conditions_list=[
                    f"recordidcompany_='{company_id}'",
                    "service='Assistenza Web Hosting'",  
                    "status='In Progress'"
                ]
            )

        if flat_service_contract:
            servicecontract_record = UserRecord('servicecontract', flat_service_contract[0]['recordid_'], load_fields=False)
            timesheet_record.values['recordidservicecontract_'] = servicecontract_record.recordid
            timesheet_record.values['invoicestatus'] = 'Service Contract: ' + servicecontract_record.values.get('type', '')
            timesheet_record.values['productivity'] = 'Ricavo indiretto'
            timesheet_record.values['print_type'] = 'Contratto di servizio'
            timesheet_record.values['print_hourprice'] = 'Compreso nel contratto di servizio'
            timesheet_record.values['print_travel'] = 'Compresa nel contratto di servizio'
            return servicecontract_record
            
        if invoiceoption == 'Monte ore':
            timesheet_record.values['recordidservicecontract_'] = ''
            timesheet_record.values['invoicestatus'] = 'To Process'
            timesheet_record.values['productivity'] = ''
            timesheet_record.values['print_type'] = ''
            timesheet_record.values['print_hourprice'] = ''
            timesheet_record.values['print_travel'] = ''

        return None

    @staticmethod
    def _evaluate_monte_ore_remoto_pbx(timesheet_record: UserRecord, servicecontract_table: UserTable, travel_dec: float) -> UserRecord:
        invoicestatus = timesheet_record.values.get('invoicestatus')
        invoiceoption = timesheet_record.values.get('invoiceoption')

        if invoicestatus in ['To Process', 'Under Warranty', 'Commercial support'] and invoiceoption != 'Out of contract' and travel_dec == 0:
            service_contracts = servicecontract_table.get_records(
                conditions_list=[
                    f"recordidcompany_='{timesheet_record.values.get('recordidcompany_')}'",
                    "type='Monte Ore Remoto PBX'", 
                    "status='In Progress'"
                ]
            )
            if service_contracts:
                timesheet_record.values['recordidservicecontract_'] = service_contracts[0]['recordid_']
                servicecontract_record = UserRecord('servicecontract', service_contracts[0]['recordid_'], load_fields=False)
                
                if invoicestatus == 'To Process':
                    timesheet_record.values['invoicestatus'] = 'Service Contract: Monte Ore Remoto PBX'
                    timesheet_record.values['productivity'] = 'Ricavo diretto'
                elif invoicestatus in ['Under Warranty', 'Commercial support']:
                    timesheet_record.values['productivity'] = 'Senza ricavo'
                    
                timesheet_record.values['print_type'] = 'Monte Ore Remoto PBX'
                timesheet_record.values['print_hourprice'] = 'Scalato dal monte ore'
                if servicecontract_record.values.get('excludetravel'):
                    timesheet_record.values['print_travel'] = 'Non scalata dal monte ore e non fatturata'
                return servicecontract_record
        return None

    @staticmethod
    def _evaluate_monte_ore_standard(timesheet_record: UserRecord, servicecontract_table: UserTable) -> UserRecord:
        invoicestatus = timesheet_record.values.get('invoicestatus')
        invoiceoption = timesheet_record.values.get('invoiceoption')

        if invoicestatus in ['To Process', 'Under Warranty', 'Commercial support'] and invoiceoption != 'Out of contract':
            service_contracts = servicecontract_table.get_records(
                conditions_list=[
                    f"recordidcompany_='{timesheet_record.values.get('recordidcompany_')}'",
                    "type='Monte Ore'", 
                    "status='In Progress'"
                ]
            )
            if service_contracts:
                timesheet_record.values['recordidservicecontract_'] = service_contracts[0]['recordid_']
                servicecontract_record = UserRecord('servicecontract', service_contracts[0]['recordid_'], load_fields=False)
                
                if invoicestatus == 'To Process':
                    timesheet_record.values['invoicestatus'] = 'Service Contract: Monte Ore'
                    timesheet_record.values['productivity'] = 'Ricavo diretto'
                elif invoicestatus in ['Under Warranty', 'Commercial support']:
                    timesheet_record.values['productivity'] = 'Senza ricavo'
                    
                timesheet_record.values['print_type'] = 'Monte Ore'
                timesheet_record.values['print_hourprice'] = 'Scalato dal monte ore'
                if servicecontract_record.values.get('excludetravel'):
                    timesheet_record.values['print_travel'] = 'Non scalata dal monte ore e non fatturata'
                return servicecontract_record
        return None

    @staticmethod
    def _calculate_to_invoice(timesheet_record: UserRecord, company_record: UserRecord, project_record: UserRecord, ticket_record: UserRecord, work_dec: float, travel_dec: float):
        invoicestatus = timesheet_record.values.get('invoicestatus')
        if invoicestatus == 'To Process':
            timesheet_record.values['productivity'] = 'Ricavo diretto'
            hourprice = 140
            travelstandardprice = None
            timesheet_record.values['print_travel'] = 'Da fatturare'

            company_ictpbx_price = company_record.values.get('ictpbx_price')
            if not Helper.isempty(company_ictpbx_price):
                hourprice = company_ictpbx_price
                travelstandardprice = company_record.values.get('travel_price')

            timesheet_record.values['print_hourprice'] = f"Fr.{hourprice}.--"

            if not Helper.isempty(project_record.recordid):
                if project_record.values.get('completed') != 'Si':
                    invoicestatus = 'To invoice when Project Completed'

            if not Helper.isempty(ticket_record.recordid):
                if ticket_record.values.get('vtestatus') != 'Closed':
                    invoicestatus = 'To invoice when Ticket Closed'

            timesheet_record.values['hourprice'] = hourprice
            workprice = hourprice * work_dec
            timesheet_record.values['workprice'] = workprice
            
            travelprice = 0
            if travel_dec > 0:
                if travelstandardprice:
                    travelprice = travelstandardprice
                else:
                    travelprice = hourprice * travel_dec
                timesheet_record.values['travelprice'] = travelprice
                
            timesheet_record.values['totalprice'] = workprice + travelprice
            
            if invoicestatus == 'To Process':
                invoicestatus = 'To Invoice'

            timesheet_record.values['invoicestatus'] = invoicestatus

    @staticmethod
    def _evaluate_validation(timesheet_record: UserRecord):
        service = timesheet_record.values.get('service')
        servizi_da_validare = ['Assistenza IT', 'Assistenza PBX', 'Assistenza SW', 'Assistenza Web Hosting', 'Printing']
        if service in servizi_da_validare:
            if timesheet_record.values.get('validated') != 'Si':
                timesheet_record.values['validated'] = 'No'
