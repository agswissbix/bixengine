from django.shortcuts import render
from django.http import JsonResponse
import environ
from django.conf import settings
from commonapp.bixmodels.user_record import *
from commonapp.bixmodels.user_table import *
from commonapp.bixmodels.helper_db import *
from commonapp.helper import *
from customapp_swissbix.helper import HelperSwissbix
from datetime import *

from commonapp.helper import Helper
from commonapp.bixmodels.user_record import UserRecord
from commonapp.bixmodels.helper_db import HelpderDB

from commonapp import views

from commonapp.utils.email_sender import *

# Initialize environment variables
env = environ.Env()
environ.Env.read_env()

def save_record_fields(tableid,recordid, old_values=""):

    # ---TASK---
    if tableid == 'task':
        from customapp_swissbix.services.custom_save.task_services import TaskService
        records_to_save = TaskService.process_task(recordid, old_values)
        for rel_tableid, rel_recordid in records_to_save:
            save_record_fields(tableid=rel_tableid, recordid=rel_recordid)

    # ---ASSENZE---
    if tableid == 'assenze':
        assenza_record = UserRecord('assenze', recordid)
        tipo_assenza=assenza_record.values['tipo_assenza']
        if tipo_assenza!='Malattia':
            dipendente_recordid = assenza_record.values['recordiddipendente_']
            save_record_fields(tableid='dipendente', recordid=dipendente_recordid)

        employee_record = UserRecord('dipendente', assenza_record.values['recordiddipendente_'])
        assenza_record.userid = employee_record.values['utente']
        event_record = assenza_record.save_record_for_event()

        save_record_fields('events', event_record.recordid)
    
    
    # ---ACCREDITO FERIE---
    elif tableid == 'accredito_ferie':
        accredito_ferie = UserRecord('accredito_ferie', recordid)
        if accredito_ferie.values.get('recordiddipendente_'):
            save_record_fields(tableid='dipendente', recordid=accredito_ferie.values.get('recordiddipendente_'))

    # ---TIMESHEET---
    if tableid == 'timesheet':
        from customapp_swissbix.services.custom_save.timesheet_services import TimesheetService
        records_to_save = TimesheetService.process_timesheet(recordid)
        for rel_tableid, rel_recordid in records_to_save:
            save_record_fields(tableid=rel_tableid, recordid=rel_recordid)


    # ---SERVICE CONTRACT
    if tableid == 'servicecontract':
        from customapp_swissbix.services.custom_save.servicecontract_services import ServiceContractService
        records_to_save = ServiceContractService.process_servicecontract(recordid)
        for rel_tableid, rel_recordid in records_to_save:
            save_record_fields(tableid=rel_tableid, recordid=rel_recordid)

      # ---SERVICEANDASSET---
    if tableid == 'serviceandasset':
        from customapp_swissbix.services.custom_save.serviceandasset_services import ServiceAndAssetService
        records_to_save = ServiceAndAssetService.process_serviceandasset(recordid)
        for rel_tableid, rel_recordid in records_to_save:
            save_record_fields(tableid=rel_tableid, recordid=rel_recordid)
            
    # ---ASSET---
    if tableid == 'asset_transactions':
        from customapp_swissbix.services.custom_save.asset_transactions_services import AssetTransactionsService
        records_to_save = AssetTransactionsService.process_asset_transactions(recordid)
        for rel_tableid, rel_recordid in records_to_save:
            save_record_fields(tableid=rel_tableid, recordid=rel_recordid)

    # ---DEAL---
    if tableid == 'deal':
        from customapp_swissbix.services.custom_save.deal_services import DealService
        records_to_save = DealService.process_deal(recordid)
        for rel_tableid, rel_recordid in records_to_save:
            save_record_fields(tableid=rel_tableid, recordid=rel_recordid)


    # ---DEALLINE
    if tableid == 'dealline':
        dealline_record = UserRecord('dealline', recordid)
        save_record_fields(tableid='deal', recordid=dealline_record.values['recordiddeal_'])

    # ---SALESORDERLINE---
    if tableid == 'salesorderline':
        from customapp_swissbix.services.custom_save.salesorderline_services import SalesOrderLineService
        records_to_save = SalesOrderLineService.process_salesorderline(recordid)
        for rel_tableid, rel_recordid in records_to_save:
            save_record_fields(tableid=rel_tableid, recordid=rel_recordid)
            
    # ---PROJECT
    if tableid == 'project':
        from customapp_swissbix.services.custom_save.project_services import ProjectService
        records_to_save = ProjectService.process_project(recordid)
        for rel_tableid, rel_recordid in records_to_save:
            save_record_fields(tableid=rel_tableid, recordid=rel_recordid)



    # ---TIMETRACKING---
    if tableid == 'timetracking':
        timetracking_record = UserRecord('timetracking', recordid)
        if Helper.isempty(timetracking_record.values['start']):
                timetracking_record.values['start'] = datetime.datetime.now().strftime("%H:%M")
        if timetracking_record.values['stato'] == 'Terminato':
            if not timetracking_record.values['end']:
                timetracking_record.values['end'] = datetime.datetime.now().strftime("%H:%M")
            time_format = '%H:%M'
            start = datetime.datetime.strptime(timetracking_record.values['start'], time_format)
            end = datetime.datetime.strptime(timetracking_record.values['end'], time_format)
            time_difference = end - start

            total_minutes = time_difference.total_seconds() / 60
            hours, minutes = divmod(total_minutes, 60)
            formatted_time = "{:02}:{:02}".format(int(hours), int(minutes))

            timetracking_record.values['worktime_string'] = str(formatted_time)

            hours = time_difference.total_seconds() / 3600
            timetracking_record.values['worktime'] = round(hours, 2)

        if not timetracking_record.values['start']:
            timetracking_record.values['start'] =  datetime.datetime.now().strftime("%H:%M")
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

    # ---DIPENDENTE---
    if tableid == 'dipendente':
        dipendente_record = UserRecord('dipendente', recordid)
        print(f"dipendente_record: {dipendente_record.values}")
        #calcolo saldo vacanze
        saldovacanze_iniziale= Helper.safe_float(dipendente_record.values['saldovacanze_iniziale'])
        saldovacanze=saldovacanze_iniziale
        assenze_dict_list=dipendente_record.get_linkedrecords_dict('assenze')
        for assenza in assenze_dict_list:
            tipo_assenza=assenza.get('tipo_assenza')
            if tipo_assenza == 'Vacanze':
                giorni_assenza= Helper.safe_float(assenza.get('giorni'))
                saldovacanze=saldovacanze-giorni_assenza

        accrediti_dict_list=dipendente_record.get_linkedrecords_dict('accredito_ferie')
        for accredito in accrediti_dict_list:
            giorni_accredito= Helper.safe_float(accredito.get('giorni'))
            saldovacanze=saldovacanze+giorni_accredito

        dipendente_record.values['saldovacanze'] = saldovacanze
        dipendente_record.save()
        print(f"Save record dipendente eseguita")

    # ---EVENT---
    if tableid == 'events':
        from customapp_swissbix.services.custom_save.event_services import EventService
        records_to_save = EventService.process_event(recordid)
        for rel_tableid, rel_recordid in records_to_save:
            save_record_fields(tableid=rel_tableid, recordid=rel_recordid)

    # --- NOTIFICATIONS ---
    if tableid == 'notification':
        notification_record = UserRecord('notifications', recordid)

        if not notification_record.values['date']:
            notification_record.values['date'] = datetime.datetime.now().strftime("%Y-%m-%d")

        if not notification_record.values['time']:
            notification_record.values['time'] = datetime.datetime.now().strftime("%H:%M")

        views.create_notification(recordid)

        notification_record.save()

def delete_record(tableid, recordid):    
    # ---TIMESHEET---
    if tableid == 'timesheet':
        timesheet = UserRecord('timesheet', recordid)
        if timesheet.values.get('recordidproject_'):
            save_record_fields(tableid='project', recordid=timesheet.values.get('recordidproject_'))
        if timesheet.values.get('recordidservicecontract_'):
            save_record_fields(tableid='servicecontract', recordid=timesheet.values.get('recordidservicecontract_'))

    # ---DEALLINE---
    elif tableid == 'dealline':
        dealline = UserRecord('dealline', recordid)
        if dealline.values.get('recordiddeal_'):
            save_record_fields(tableid='deal', recordid=dealline.values.get('recordiddeal_'))

    # ---PROJECT---
    elif tableid == 'project':
        project = UserRecord('project', recordid)
        save_record_fields(tableid='project', recordid=recordid)

    # ---ASSENZE---
    elif tableid == 'assenze':
        assenze = UserRecord('assenze', recordid)
        if assenze.values.get('recordiddipendente_'):
            save_record_fields(tableid='dipendente', recordid=assenze.values.get('recordiddipendente_'))

    # ---ACCREDITO FERIE---
    elif tableid == 'accredito_ferie':
        accredito_ferie = UserRecord('accredito_ferie', recordid)
        if accredito_ferie.values.get('recordiddipendente_'):
            save_record_fields(tableid='dipendente', recordid=accredito_ferie.values.get('recordiddipendente_'))


def calculate_dependent_fields(request):
    data = json.loads(request.body)
    updated_fields = {}
    recordid=data.get('recordid')
    tableid=data.get('tableid')
    fields = data.get('fields', {})
    
    #---DEALLINE---
    if tableid=='dealline':
        updated_fields = HelperSwissbix.compute_dealline_fields(fields, UserRecord)
    
    #---ASSENZE---
    if tableid=='assenze':
        fields= data.get('fields')
        #giorni= Helper.safe_float(fields.get('giorni', 0))
        #ore= Helper.safe_float(fields.get('ore', 0))
        #if ore == '' or ore is None:
         #   ore_updated=giorni * 8
          #  updated_fields['ore']=ore_updated   

    return JsonResponse({'status': 'success', 'updated_fields': updated_fields})


def get_input_linked_conditions(linkedmaster_tableid, tableid, fieldid, form_values):
    """
    Ritorna condizioni SQL aggiuntive per get_input_linked, specifiche per swissbix.
    """
    # Filtra la tabella company per mostrare solo i record attivi su Bexio
    if linkedmaster_tableid == 'company':
        return "AND bexio_status = 'Active'"
    
    return ''