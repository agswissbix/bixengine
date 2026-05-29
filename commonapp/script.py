import os
import json
import uuid
import time
import datetime
import logging
from functools import wraps

from django.conf import settings
from django.utils import timezone

from commonapp.models import UserUserLog, SysUser
from commonapp.bixmodels.helper_db import HelpderDB

# Inizializzazione corretta del logger al posto di "from venv import logger"
logger = logging.getLogger(__name__)


def task_monitor(data_type):
    """
    Decoratore che trasforma l'output di una funzione nel template standard.
    Gestisce automaticamente il try-except e il formato del dizionario.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)

                # Gestione di due casi: la funzione ritorna una tupla (value, log) oppure solo un singolo valore
                if isinstance(result, tuple) and len(result) == 2:
                    result_value, hidden_log = result
                else:
                    result_value = result
                    hidden_log = []

                return {
                    "status": "success",
                    "value": result_value,
                    "type": data_type,
                    "timestamp": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    "hidden_log": hidden_log
                }
            except Exception as e:
                logger.error(f"Errore nel task {data_type}: {str(e)}")
                return {
                    "status": "error",
                    "value": {"error": str(e), "message": "Esecuzione fallita"},
                    "type": data_type,
                    "timestamp": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    "hidden_log": []
                }
        return wrapper
    return decorator


@task_monitor(data_type="sync")
def import_user_audit_logs():
    """
    Importa i log di audit da user-audit.log (e successivi archiviati) dentro la tabella UserUserLog.
    Utilizza bulk_create con ignore_conflicts=True per ignorare i duplicati basandosi su log_id.
    """

    start_time = time.time()
    
    # Inizializzo un dizionario per le statistiche di processo
    stats = {
        "files_processed": 0,
        "total_lines_read": 0,
        "skipped_system_users": 0,
        "parsing_errors": 0,
        "prepared_for_insert": 0,
        "execution_time_seconds": 0.0
    }

    logs_dir = getattr(settings, 'LOGS_DIR', os.path.join(settings.BASE_DIR, 'logs'))
    
    # Query the max values for BaseUserTable fields
    sql = """
        SELECT 
            MAX(recordid_) as max_recordid,
            MAX(id) as max_id,
            MAX(linkedorder_) as max_order
        FROM user_user_log
    """
    result = HelpderDB.sql_query_row(sql)
    
    max_recordid = result.get('max_recordid') if result else None
    max_id = result.get('max_id') if result else None
    max_order = result.get('max_order') if result else None

    current_recordid_int = int(max_recordid) if max_recordid else 0
    current_id_int = int(max_id) if max_id else 0
    current_order_int = int(max_order) if max_order else 0

    # Recupero i log_id esistenti per saltarli ed evitare cicli infiniti sulle stesse righe
    existing_log_ids = set(UserUserLog.objects.exclude(log_id__isnull=True).exclude(log_id='').values_list('log_id', flat=True))

    logs_to_insert = []
    MAX_LOGS_PER_RUN = 2000
    
    # Controlla se esistono i file
    if not os.path.exists(logs_dir):
        print(f"Cartella log non trovata: {logs_dir}")
        return {"status": "error", "message": "Cartella log non trovata", "details": stats}
        
    for filename in os.listdir(logs_dir):
        if len(logs_to_insert) >= MAX_LOGS_PER_RUN:
            break
            
        if 'user-audit.log' in filename:
            stats["files_processed"] += 1
            file_path = os.path.join(logs_dir, filename)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if len(logs_to_insert) >= MAX_LOGS_PER_RUN:
                        break
                        
                    line = line.strip()
                    if not line:
                        continue
                        
                    stats["total_lines_read"] += 1
                    
                    try:
                        data = json.loads(line)
                        
                        # Se il log_id esiste già, lo salto direttamente
                        log_id = data.get('log_id')
                        if log_id and log_id in existing_log_ids:
                            continue
                            
                        # Se manca, ne genero uno nuovo (come prima)
                        if not log_id:
                            log_id = str(uuid.uuid4())

                        bixid = data.get('user_id')
                        if not bixid or bixid == 1 or bixid == 0:
                            stats["skipped_system_users"] += 1
                            continue

                        userid = SysUser.objects.get(bixid=bixid).id
                        
                        # Calcola tableid (senza 'user_')
                        table_name = data.get('table_name', '')
                        tableid = table_name[5:] if table_name.startswith('user_') else table_name

                        timestamp = data.get('timestamp')
                        log_date = None
                        log_time = None

                        if timestamp:
                            try:
                                aware_dt = datetime.datetime.fromisoformat(timestamp)
                                log_date = aware_dt.date()
                                log_time = aware_dt.time()
                            except ValueError:
                                parsed_dt = datetime.datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                                aware_dt = timezone.make_aware(parsed_dt)
                                log_date = aware_dt.date()
                                log_time = aware_dt.time()
                        
                        current_recordid_int += 1
                        current_id_int += 1
                        current_order_int += 1
                        
                        next_recordid = str(current_recordid_int).zfill(32)
                        
                        logs_to_insert.append(UserUserLog(
                            record_id=next_recordid,
                            creator_id=1, 
                            created_at=timezone.now(),
                            id=current_id_int,
                            linked_order=current_order_int,
                            log_id=log_id,
                            date=log_date,
                            time=log_time,
                            user_id=userid,
                            action_type=data.get('action_type'),
                            tableid=tableid,
                            recordidtable=data.get('record_id'),
                            old_values=data.get('old_values'),
                            new_values=data.get('new_values'),
                            ip_address=data.get('ip_address')
                        ))
                    except Exception as e:
                        stats["parsing_errors"] += 1
                        print(f"Errore parsing riga log: {e}")
                    
    stats["prepared_for_insert"] = len(logs_to_insert)
    stats["execution_time_seconds"] = round(time.time() - start_time, 2)
                    
    if logs_to_insert:
        try:
            UserUserLog.objects.bulk_create(logs_to_insert, batch_size=200, ignore_conflicts=True)
            msg = f"Elaborazione completata. Preparati {len(logs_to_insert)} log per l'inserimento."
            print(msg)
            return {
                "status": "success", 
                "message": msg,
                "details": stats
            }
        except Exception as e:
            return {
                "status": "error", 
                "message": f"Errore bulk_create: {str(e)}",
                "details": stats
            }
            
    return {
        "status": "success", 
        "message": "Nessun log valido da importare",
        "details": stats
    }