import os
import sys

# Imposta il percorso corretto al progetto Django (la directory che contiene manage.py)
sys.path.append(r'D:\BixProjects\BixData\bixengine')
# Imposta le variabili di ambiente per Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bixengine.settings')

import django
django.setup()

from commonapp.bixmodels.helper_db import HelpderDB
from commonapp.views import custom_save_record_fields
from commonapp.bixmodels.user_record import UserRecord

def run_test():
    print("Inizio iterazione sui deal...")
    
    # Prepara la query per recuperare tutti i deal con data di apertura successiva al 01-01-2026.
    # Assumiamo che la tabella fisica nel database per 'deal' sia 'user_deal'
    query = "SELECT recordid_ FROM user_deal WHERE opendate >= '2026-01-01' AND deleted_='N'"
    
    try:
        rows = HelpderDB.sql_query(query)
    except Exception as e:
        print(f"Errore durante l'esecuzione della query al DB: {e}")
        return
        
    if not rows:
        print("Nessun deal trovato con opendate >= 2026-01-01.")
        return
    
    print(f"Trovati {len(rows)} record da processare.")
    success_count = 0
    
    for row in rows:
        recordid = row.get('recordid_')
        if not recordid:
            continue
            
        print(f"Chiamata a custom_save_record_fields per deal con recordid_: {recordid}")
        
        try:
            # Creiamo l'istanza UserRecord. Questo non è strettamente necessario se vuoti il dict dei params,
            # ma passandogli i values attuali simuliamo correttamente la post-save.
            deal_record = UserRecord('deal', recordid)
            old_values = deal_record.values.copy() if deal_record.values else {}
            
            # Richiama commonapp.views.custom_save_record_fields come richiesto.
            custom_save_record_fields('deal', recordid, old_values)
            success_count += 1
            
        except Exception as e:
            print(f"Errore durante l'elaborazione del deal {recordid}: {e}")

    print(f"Elaborazione terminata. Aggiornati {success_count} su {len(rows)} deal.")

if __name__ == '__main__':
    run_test()
