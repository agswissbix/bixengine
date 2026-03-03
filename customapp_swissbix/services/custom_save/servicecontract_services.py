from commonapp.bixmodels.user_record import UserRecord
from commonapp.bixmodels.user_table import UserTable
from commonapp.helper import Helper

class ServiceContractService:
    @staticmethod
    def process_servicecontract(recordid: str) -> list:
        servicecontract_record = UserRecord('servicecontract', recordid)
        salesorderline_recordid = servicecontract_record.values.get('recordidsalesorderline_')
        salesorderline_record = UserRecord('salesorderline', salesorderline_recordid) if salesorderline_recordid else None

        # recupero campi
        contracthours = servicecontract_record.values.get('contracthours')
        if contracthours is None:
            contracthours = 0
            
        previousresidual = servicecontract_record.values.get('previousresidual')
        if previousresidual is None:
            previousresidual = 0
            
        excludetravel = servicecontract_record.values.get('excludetravel')

        # inizializzo campi
        usedhours = 0
        progress = 0
        residualhours = contracthours

        timesheet_linkedrecords = servicecontract_record.get_linkedrecords_dict(linkedtable='timesheet')
        for timesheet_linkedrecord in timesheet_linkedrecords:
            if timesheet_linkedrecord.get('invoiceoption') not in ['Under Warranty', 'Commercial support']:
                usedhours = usedhours + (timesheet_linkedrecord.get('worktime_decimal') or 0)
                
                if excludetravel not in ['1', 'Si']:
                    if not Helper.isempty(timesheet_linkedrecord.get('traveltime_decimal')):
                        usedhours = usedhours + timesheet_linkedrecord['traveltime_decimal']
                        
        residualhours = contracthours + previousresidual - usedhours
        if contracthours + previousresidual != 0:
            progress = (usedhours / (contracthours + previousresidual)) * 100

        if Helper.isempty(servicecontract_record.values.get('status')):
            servicecontract_record.values['status'] = 'In Progress'

        servicecontract_record.values['usedhours'] = usedhours
        servicecontract_record.values['residualhours'] = residualhours
        servicecontract_record.values['progress'] = progress
        servicecontract_record.save()

        records_to_save = []
        if salesorderline_record and not Helper.isempty(salesorderline_record.recordid):
            records_to_save.append(('salesorderline', salesorderline_record.recordid))
            
        return records_to_save
