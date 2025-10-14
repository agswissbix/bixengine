import django
import os
from django_q.models import Task
from bixscheduler.hooks import on_task_success
from bixscheduler.models import ScheduleExtra  
from django_q.models import Schedule

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mio_progetto.settings")
django.setup()

# crea un Task fittizio (se non esiste)
task, c = Task.objects.get_or_create(
    id="1234567890abcdef1234567890abcdef",
    name="debug_task",
    func="myapp.tasks.example_task",
    started="2025-10-14T10:00:00Z",
    stopped="2025-10-14T10:00:10Z",
    success=True,
)

# crea un Schedule associato a quel task
schedule, created = Schedule.objects.get_or_create(
    name="Debug Schedule",
    func="myapp.tasks.example_task",
    schedule_type="O",
    task=task.id,
)

# crea la riga extra
ScheduleExtra.objects.create(schedule=schedule, send_to_endpoint=True)

# ora lancia manualmente l'hook come farebbe django-q
on_task_success(task)
