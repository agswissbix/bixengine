import datetime
import traceback
import requests
from django.utils import timezone
import logging
from bixscheduler.utils import get_cliente_id  # percorso reale del file

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

EXTERNAL_ENDPOINT = "https://devstagista.swissbix.com:3022/bixadmin/monitoring"

def on_task_success(task):
    """
    Hook chiamato quando un task termina con successo.
    Invia i dati via POST a un endpoint esterno.
    """
    payload = {
        "func": task.func,
        "result": task.result if task.result is not None else "Nessun output",
        "started": task.started.isoformat() if task.started else None,
        "stopped": task.stopped.isoformat() if task.stopped else timezone.now().isoformat(),
        "success": task.success,
    }
    headers = {"Authorization": "Bearer TOKEN"}

    try:
        response = requests.post(EXTERNAL_ENDPOINT, json=payload, headers=headers, timeout=10, 
                                 verify=False # Disabilita la verifica SSL (non in produzione!)
                                 )
        response.raise_for_status()
    except Exception as e:
        # Log interno, così non rompe il worker
        logger.info(f"[HOOK ERROR] impossibile inviare a {EXTERNAL_ENDPOINT}: {e}")

# def on_task_success(task):
#     try:
#         print("HOOK ATTIVATO - TASK RICEVUTO")
#         print("TASK:", task)

#         output = getattr(task, 'result', None)
#         func = getattr(task, 'func', 'unknown')
#         run_at = datetime.datetime.now()
#         cliente_id = get_cliente_id()

#         from bixmonitoring.views import get_output

#         # Passi cliente_id insieme agli altri
#         get_output(func=func, output=output, run_at=run_at, cliente_id=cliente_id)
#     except Exception:
#         print("ERRORE NELL'HOOK:")
#         traceback.print_exc()
