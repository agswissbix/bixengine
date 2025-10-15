import functools
import traceback
from django.http import JsonResponse

def safe_schedule_task(stop_on_error=False):
    """
    Decoratore per eseguire in sicurezza le funzioni schedulate.
    - Cattura eccezioni senza bloccare il cluster.
    - Logga l’errore.
    - Optional: disattiva lo Schedule se stop_on_error=True.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                print(f"Esecuzione task sicuro: {func.__name__}")
                return func(*args, **kwargs)
            except Exception as e:
                print(f"❌ Errore in {func.__name__}: {e}")
                traceback.print_exc()
                # Se richiesto, stoppa lo Schedule associato
                if stop_on_error:
                    from django_q.models import Schedule
                    Schedule.objects.filter(func=f"{func.__module__}.{func.__name__}").update(next_run=None)
                return JsonResponse({"error": str(e)}, status=500)
        return wrapper
    return decorator