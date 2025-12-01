import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bixengine.settings")

django.setup()

from django_q.models import Task, Schedule
from bixscheduler.hooks import on_task_success
from bixscheduler.models import ScheduleExtra

task, _ = Task.objects.get_or_create(
    id="1234567890abcdef1234567890abcdef",
    defaults={
        "name": "debug_taskkyyy",
        "func": "myapp.tasks.example_task",
        "started": "2025-10-14T10:00:00Z",
        "stopped": "2025-10-14T10:00:10Z",
        "success": True,
        "result": {'status': 'error', 'value': {'message': 'Script eseguito correttamente'}, 'type': 'counters'}
    }
)

schedule, _ = Schedule.objects.get_or_create(
    name="Debug Schedule",
    func="myapp.tasks.example_task",
    schedule_type="O",
    task=task.id,
)

ScheduleExtra.objects.get_or_create(
    schedule=schedule,
    defaults={
        "send_to_endpoint": False,
        "save_monitoring": True
    }
)

on_task_success(task)

print("Hook eseguito correttamente.")
