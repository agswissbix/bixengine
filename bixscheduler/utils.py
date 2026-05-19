import inspect
import importlib

from django.db import connection
from django_q.models import Schedule
import bixscheduler.tasks as tasks_module

def get_available_tasks():
    available = []

    # 1. Funzioni interne di bixscheduler.tasks
    for name, func in inspect.getmembers(tasks_module, inspect.isfunction):
        if not name.startswith('_'):
            path = f'bixscheduler.tasks.{name}'
            label = name.replace('_', ' ').title()
            description = inspect.getdoc(func) or ''
            available.append((path, label, description))

    # 2. Funzioni della commonapp
    try:
        common_module = importlib.import_module("commonapp.script")
        for name, func in inspect.getmembers(common_module, inspect.isfunction):
            if not name.startswith('_'):
                path = f"commonapp.script.{name}"
                label = f"COMMONAPP: {name.replace('_', ' ').title()}"
                description = inspect.getdoc(func) or ''
                available.append((path, label, description))
    except ImportError:
        pass  # In caso di errore di importazione, ignora e prosegue

    # 3. Funzioni della customapp specifica per il cliente
    cliente_id = get_cliente_id()
    target_module = f"customapp_{cliente_id}"

    try:
        custom_module = importlib.import_module(f"{target_module}.script")
        for name, func in inspect.getmembers(custom_module, inspect.isfunction):
            if not name.startswith('_'):
                path = f"{target_module}.script.{name}"
                label = f"{target_module.upper()}: {name.replace('_', ' ').title()}"
                description = inspect.getdoc(func) or ''
                available.append((path, label, description))
    except ImportError:
        pass

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
