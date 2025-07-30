import inspect
import importlib

from django.db import connection
from django_q.models import Schedule
import bixscheduler.tasks as tasks_module

def get_available_tasks():
    available = []

    # Funzioni interne di bixscheduler.tasks
    for name, func in inspect.getmembers(tasks_module, inspect.isfunction):
        if not name.startswith('_'):
            path = f'bixscheduler.tasks.{name}'
            label = name.replace('_', ' ').title()
            available.append((path, label))

    # Recupera cliente_id
    cliente_id = get_cliente_id()
    target_module = f"customapp_{cliente_id}"

    # Prova a importare script.py dentro customapp_<cliente_id>
    try:
        module = importlib.import_module(f"{target_module}.script")
    except ImportError:
        module = None

    if module:
        for name, func in inspect.getmembers(module, inspect.isfunction):
            if not name.startswith('_'):
                path = f"{target_module}.script.{name}"
                label = f"{target_module.upper()}: {name.replace('_', ' ').title()}"
                available.append((path, label))

    return available

def is_schedule_active(name):
    return Schedule.objects.filter(name=name).exists()

def get_cliente_id():
    with connection.cursor() as cursor:
        cursor.execute("SELECT value from sys_settings WHERE setting = 'cliente_id'")
        id_cliente = cursor.fetchone()
        if id_cliente:
            return id_cliente[0]
        return None
