import datetime
import traceback
from bixscheduler.utils import get_cliente_id  # percorso reale del file

def on_task_success(task):
    try:
        print("HOOK ATTIVATO - TASK RICEVUTO")
        print("TASK:", task)

        output = getattr(task, 'result', None)
        func = getattr(task, 'func', 'unknown')
        run_at = datetime.datetime.now()
        cliente_id = get_cliente_id()

        from bixmonitoring.views import get_output

        # Passi cliente_id insieme agli altri
        get_output(func=func, output=output, run_at=run_at, cliente_id=cliente_id)
    except Exception:
        print("ERRORE NELL'HOOK:")
        traceback.print_exc()
