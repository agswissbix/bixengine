from django.db import models
from django.forms.models import model_to_dict
from commonapp.logs.audit_logger import log_audit_event

class AuditLogMixin(models.Model):
    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._initial_state = self._get_current_state()

    def _get_current_state(self):
        return model_to_dict(self) if self.pk else {}

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_values = {}
        new_values = {}
        
        if not is_new:
            current_state = model_to_dict(self)
            for field, current_value in current_state.items():
                old_value = self._initial_state.get(field)
                if old_value != current_value:
                    old_values[field] = old_value
                    new_values[field] = current_value

        super().save(*args, **kwargs)

        if is_new:
            new_values = model_to_dict(self)
        
        if old_values or is_new:
            log_audit_event(
                action_type='CREATE' if is_new else 'UPDATE',
                table_name=self._meta.db_table,
                record_id=self.pk,
                old_values=old_values if not is_new else {},
                new_values=new_values
            )
            
        self._initial_state = self._get_current_state()

    def delete(self, *args, **kwargs):
        old_values = self._get_current_state()
        super().delete(*args, **kwargs)
        
        log_audit_event(
            action_type='DELETE',
            table_name=self._meta.db_table,
            record_id=self.pk,
            old_values=old_values,
            new_values={}
        )
