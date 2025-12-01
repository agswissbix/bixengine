from django.db import models
from django_q.models import Schedule

class ScheduleExtra(models.Model):
    schedule = models.OneToOneField(
        Schedule,
        on_delete=models.CASCADE,
        related_name="extra",
    )
    send_to_endpoint = models.BooleanField(
        default=False, help_text=("Send task data to endpoint")
    )
    save_monitoring = models.BooleanField(
        default=False, help_text=("Monitor the task")
    )

    class Meta:
        proxy = False 
        db_table = "django_q_schedule_extra"  # evita conflitti



