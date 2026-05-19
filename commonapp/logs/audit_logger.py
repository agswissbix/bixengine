import logging
import uuid
from commonapp.utils.middleware import get_current_user, get_client_ip

logger = logging.getLogger('audit_logger')

def log_audit_event(action_type: str, table_name: str, record_id: str, old_values: dict = None, new_values: dict = None, user_id=None):
    """
    Utility centralizzata per l'User Audit Log.
    Supporta sia il mondo ORM (tramite Mixin) che il mondo SQL/Dinamico (tramite UserRecord).
    """
    user = get_current_user()
    ip_address = get_client_ip()

    final_user_id = user.id if user and user.is_authenticated else user_id

    old_values = old_values or {}
    new_values = new_values or {}

    # Cast to str or clean logic
    str_record_id = str(record_id) if record_id is not None else None

    log_payload = {
        'log_id': str(uuid.uuid4()),
        'user_id': final_user_id,
        'action_type': action_type.upper(),
        'table_name': str(table_name),
        'record_id': str_record_id,
        'old_values': old_values,
        'new_values': new_values,
        'ip_address': ip_address,
    }
    
    logger.info('Audit Event', extra=log_payload)
