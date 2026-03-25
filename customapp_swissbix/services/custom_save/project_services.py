from commonapp.bixmodels.user_record import UserRecord
from commonapp.helper import Helper
from datetime import *


class ProjectService:
    @staticmethod
    def process_project(recordid: str) -> list:
        project_record = UserRecord('project', recordid, load_fields=False)
        completed = project_record.values.get('completed')
        deal_recordid = project_record.values.get('recordiddeal_')
        deal_record = UserRecord('deal', deal_recordid, load_fields=False) if deal_recordid else None
        
        expectedhours = project_record.values.get('expectedhours')
        usedhours = 0
        residualhours = 0
        
        timesheet_records_list = project_record.get_linkedrecords_dict('timesheet')
        for timesheet_record_dict in timesheet_records_list:
            usedhours = usedhours + (timesheet_record_dict.get('totaltime_decimal') or 0)
                
        if expectedhours:
            residualhours = expectedhours - usedhours
            
        project_record.values['usedhours'] = usedhours
        project_record.values['residualhours'] = residualhours
        project_record.save()

        #collegamento allegati del deal al progetto
        if deal_record:
            attachment_records = deal_record.get_linkedrecords_dict(linkedtable='attachment')
            for attachment_record_dict in attachment_records:
                attachment_record = UserRecord('attachment', attachment_record_dict.get('recordid_'), load_fields=False)
                attachment_record.values['recordidproject_'] = project_record.recordid
                attachment_record.save()

            #aggiornamento deal
            if not Helper.isempty(deal_record.recordid):
                return [('deal', deal_record.recordid)]
        
        return []
