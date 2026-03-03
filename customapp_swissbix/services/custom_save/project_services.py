from commonapp.bixmodels.user_record import UserRecord
from commonapp.helper import Helper

class ProjectService:
    @staticmethod
    def process_project(recordid: str) -> list:
        project_record = UserRecord('project', recordid)
        completed = project_record.values.get('completed')
        deal_recordid = project_record.values.get('recordiddeal_')
        deal_record = UserRecord('deal', deal_recordid) if deal_recordid else None
        
        expectedhours = project_record.values.get('expectedhours')
        usedhours = 0
        residualhours = 0
        fixedpricehours = 0
        servicecontracthours = 0
        bankhours = 0
        invoicedhours = 0
        
        timesheet_records_list = project_record.get_linkedrecords_dict('timesheet')
        for timesheet_record_dict in timesheet_records_list:
            usedhours = usedhours + (timesheet_record_dict.get('totaltime_decimal') or 0)
            invoicestatus = timesheet_record_dict.get('invoicestatus')
            if invoicestatus == 'Fixed Price Project':
                fixedpricehours = fixedpricehours + (timesheet_record_dict.get('totaltime_decimal') or 0)
            if invoicestatus == 'Service Contract: Monte Ore':
                bankhours = bankhours + (timesheet_record_dict.get('totaltime_decimal') or 0)
            if invoicestatus == 'Invoiced':
                invoicedhours = invoicedhours + (timesheet_record_dict.get('totaltime_decimal') or 0)
                
        if expectedhours:
            residualhours = expectedhours - usedhours
            
        project_record.values['usedhours'] = usedhours
        project_record.values['residualhours'] = residualhours
        project_record.save()

        #collegamento allegati del deal al progetto
        if deal_record:
            attachment_records = deal_record.get_linkedrecords_dict(linkedtable='attachment')
            for attachment_record_dict in attachment_records:
                attachment_record = UserRecord('attachment', attachment_record_dict.get('recordid_'))
                attachment_record.values['recordidproject_'] = project_record.recordid
                attachment_record.save()

            #aggiornamento deal
            if not Helper.isempty(deal_record.recordid):
                deal_record.values['usedhours'] = usedhours
                deal_record.values['fixedpricehours'] = fixedpricehours
                deal_record.values['servicecontracthours'] = servicecontracthours
                deal_record.values['bankhours'] = bankhours
                deal_record.values['invoicedhours'] = invoicedhours
                deal_record.values['residualhours'] = residualhours
                deal_record.values['projectcompleted'] = completed
                deal_record.save()
                
                return [('deal', deal_record.recordid)]
        
        return []
