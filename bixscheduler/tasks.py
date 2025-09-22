from datetime import datetime
from django_q.models import Schedule, Task
from django.db import connection




#DA LASCIARE SENNO DA TANTI ERRORI!
def aggiorna_cache():
    print("Eseguo aggiorna_cache")
    return 32



def esempio_task(param1, param2):
    print(f"Eseguo esempio_task con param1={param1} e param2={param2}")
    return param1 + param2

