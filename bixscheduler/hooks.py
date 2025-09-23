import datetime
import traceback
import requests
from django.utils import timezone
from django.db import transaction, connection
import logging
from bixscheduler.utils import get_cliente_id 
from commonapp.bixmodels.user_record import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def on_task_success(task):
    """
    Hook chiamato quando un task termina con successo.
    Crea il log e invia i dati a un endpoint esterno.
    """
    try:
        # Passiamo i parametri necessari alla funzione helper
        create_scheduler_log(task)
    except Exception as e:
        logger.error(f"[HOOK ERROR] impossibile creare log nel DB: {e}")
        # In caso di errore, l'hook deve comunque ritornare None.
        pass
    
    # L'hook deve sempre ritornare None per un corretto funzionamento.
    return None

def create_scheduler_log(task):
    """
    Crea un log del task nel database usando la connessione di Django.
    """
    try:
        # Prepara i dati da inserire
        function_name = task.func
        output = str(task.result) if task.result is not None else "Nessun output"
        lastupdate_date = task.stopped if task.stopped else timezone.now()
        
        # Crea un'istanza di UserRecord
        scheduler_log = UserRecord('scheduler_log')
        
        scheduler_log.values['date'] = lastupdate_date.date()
        scheduler_log.values['function'] = function_name
        scheduler_log.values['output'] = output
        scheduler_log.values['hour'] = lastupdate_date.strftime('%H:%M:%S')

        # Salva il record nel DB
        scheduler_log.save()
            
    except Exception as e:
        logger.error(f"[HOOK ERROR] Errore nel salvataggio: {e}")
        raise # Rilanciamo l'eccezione per farla gestire dal blocco try di on_task_success.