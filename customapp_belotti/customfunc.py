from django.http import JsonResponse
from commonapp.bixmodels.user_record import *
from commonapp.bixmodels.helper_db import *
from customapp_belotti.utils.crypto import get_recordid_from_hashedid

def conferma_ricezione(request):
    try:
        data = json.loads(request.body)
        recordidhashed = data.get('recordid_hashed', None)
        recordid = data.get('recordid', None)
        if not recordidhashed and not recordid:
            return JsonResponse({"success": False, "error": "recordid_hashed o recordid richiesto"}, status=400)
        if recordidhashed is not None:
            recordid = get_recordid_from_hashedid(recordidhashed)
        if not recordid:
            return JsonResponse({"success": False, "error": "recordid non valido"}, status=400)
        record = UserRecord('richieste', recordid=recordid)
        if not record:
            return JsonResponse({"success": False, "error": "Record non trovato"}, status=404)

        record.values['stato'] = 'Merce Ricevuta'
        record.save()

        return JsonResponse({"success": True, "message": "Stato aggiornato a 'Merce Ricevuta'", "record": record.values})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)