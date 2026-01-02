import datetime
import traceback
import requests
from django.utils import timezone
from django.db import transaction, connection
import logging
from bixscheduler.utils import get_cliente_id 
from commonapp.bixmodels.user_record import *
from cryptography.fernet import Fernet
import hmac
import hashlib
from django_q.models import Schedule


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)




def encrypt_data(fernet_instance, plaintext: str) -> str:
    """Cifra una stringa con Fernet."""
    return fernet_instance.encrypt(plaintext.encode("utf-8")).decode("utf-8")

def on_task_success(task):
    """
    Hook chiamato quando un task termina con successo.
    Crea il log e invia i dati a un endpoint esterno.
    """
    logger.info(f"[HOOK] Task '{task.func}' completato con successo.")
    try:
        # Passiamo i parametri necessari alla funzione helper
        create_scheduler_log(task)
    except Exception as e:
        logger.error(f"[HOOK ERROR] impossibile creare log nel DB: {e}")
        # In caso di errore, l'hook deve comunque ritornare None.
        pass

    try:
        schedule = Schedule.objects.filter(func=task.func).first()  # ottieni il Schedule
        if not schedule:
            return None

        extra = getattr(schedule, "extra", None)  # ScheduleExtra (OneToOne)
        send_to_endpoint = getattr(extra, "send_to_endpoint", False)
        monitoring = getattr(extra, "save_monitoring", False)

        if monitoring:
            try:
                create_monitoring(schedule, task)
            except Exception as e:
                logger.error(f"[HOOK ERROR] impossibile creare monitoring nel DB: {e}")
                # In caso di errore, l'hook deve comunque ritornare None.
                pass

        if not send_to_endpoint:
            return None

        # Ottieni chiavi da variabili d’ambiente
        hmac_key_str = os.environ.get("HMAC_KEY")
        encryption_key = os.environ.get("LOGS_ENCRYPTION_KEY")
        endpoint_url = os.environ.get("PHP_ENDPOINT_URL")

        if not hmac_key_str or not encryption_key or not endpoint_url:
            logger.error("[HOOK ERROR] Variabili d’ambiente HMAC_KEY, PHP_ENDPOINT_URL e/o LOGS_ENCRYPTION_KEY non impostate.")
            return None

        hmac_key = hmac_key_str.encode("utf-8")
        fernet = Fernet(encryption_key)

        cliente_id = get_cliente_id()

        # Prepara i dati del task
        row = {
            "date": (task.stopped if task.stopped else timezone.now()).isoformat(),
            "function": str(task.func),
            "client": str(cliente_id),
            "output": str(task.result),
        }

        # Calcola hash univoco per verifica di integrità
        hashing_string = f"{row['date']}{row['function']}{row['client']}{row['output']}"
        log_hash = hmac.new(hmac_key, hashing_string.encode("utf-8"), hashlib.sha256).hexdigest()

        encrypted_payload = {
            "date": row["date"],
            "function": encrypt_data(fernet, row["function"]),
            "client": encrypt_data(fernet, row["client"]),
            "output": encrypt_data(fernet, row["output"]),
            "log_hash": log_hash,
        }

        try:
            payload_as_string = json.dumps([encrypted_payload])
        except TypeError as e:
            for k, v in encrypted_payload.items():
                print(f"{k}: {type(v)} → {v}")
            raise
        signature = hmac.new(hmac_key, payload_as_string.encode("utf-8"), hashlib.sha256).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-Signature": signature,
        }

        # Invio HTTP sicuro
        response = requests.post(endpoint_url, data=payload_as_string, headers=headers, timeout=10)
        response.raise_for_status()
        logger.info(f"[HOOK] Dati cifrati inviati con successo a {endpoint_url}")

    except requests.RequestException as req_err:
        logger.error(f"[HOOK ERROR] Errore nell'invio dei dati all'endpoint: {req_err}")
    except Exception as e:
        logger.error(f"[HOOK ERROR] Errore generale nell'elaborazione dell'hook: {e}")
        logger.error(traceback.format_exc())
    
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
        lastupdate_date += datetime.timedelta(hours=2)
        
        # Crea un'istanza di UserRecord
        scheduler_log = UserRecord('scheduler_log')
        
        scheduler_log.values['name'] = task.name
        scheduler_log.values['date'] = lastupdate_date.date()
        scheduler_log.values['function'] = function_name
        scheduler_log.values['output'] = output
        scheduler_log.values['hour'] = lastupdate_date.strftime('%H:%M:%S')

        # Salva il record nel DB
        scheduler_log.save_safe()
            
    except Exception as e:
        logger.error(f"[HOOK ERROR] Errore nel salvataggio: {e}")
        raise # Rilanciamo l'eccezione per farla gestire dal blocco try di on_task_success.

def create_monitoring(schedule, task):
    """
    Crea un log del task nel database usando la connessione di Django.
    """
    try:
        # Prepara i dati da inserire
        function_name = task.func
        output = str(task.result) if task.result is not None else "Nessun output"
        lastupdate_date = task.stopped if task.stopped else timezone.now()
        lastupdate_date += datetime.timedelta(hours=2)

        sql = "SELECT recordid_ FROM user_monitoring WHERE scheduleid = %s"
        record = HelpderDB.sql_query_value(sql, 'recordid_', [schedule.id])
        

        recordid = None 
        if record:
            recordid = record
        # Crea un'istanza di UserRecord
        monitoring = UserRecord('monitoring', recordid)
        
        monitoring.values['name'] = schedule.name
        monitoring.values['date'] = lastupdate_date.date()
        monitoring.values['function'] = function_name
        monitoring.values['monitoring_output'] = output
        monitoring.values['hour'] = lastupdate_date.strftime('%H:%M:%S')
        monitoring.values['status'] = task.result['status']
        monitoring.values['clientid'] = Helper.get_cliente_id()
        monitoring.values['scheduleid'] = schedule.id

        # Salva il record nel DB
        monitoring.save_safe()
            
    except Exception as e:
        logger.error(f"[HOOK ERROR] Errore nel salvataggio: {e}")
        raise # Rilanciamo l'eccezione per farla gestire dal blocco try di on_task_success.