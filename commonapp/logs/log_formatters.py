from pythonjsonlogger import jsonlogger
from datetime import datetime, timezone

class AuditJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        if not log_record.get('timestamp'):
            log_record['timestamp'] = datetime.now(timezone.utc).isoformat()
        
        log_record['level'] = record.levelname
