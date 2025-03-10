import json
from django.shortcuts import render
from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from django.views.decorators.csrf import csrf_exempt

# Create your views here.

@csrf_exempt
def winteler_wip_barcode_scan(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            barcode_lotto = data.get("barcode_lotto")
            barcode_wip = data.get("barcode_wip", [])

            # Controlli di validità
            if not barcode_lotto:
                return JsonResponse({"success": False, "message": "Barcode lotto mancante"}, status=400)
            if not isinstance(barcode_wip, list):
                return JsonResponse({"success": False, "message": "Barcode WIP deve essere una lista"}, status=400)

            # Simulazione salvataggio dati (puoi aggiungere il salvataggio nel database)
            print(f"Salvataggio barcode lotto: {barcode_lotto}")
            print(f"Salvataggio barcode WIP: {barcode_wip}")

            return JsonResponse({"success": True, "message": "Salvataggio completato con successo"})

        except json.JSONDecodeError:
            return JsonResponse({"success": False, "message": "Dati JSON non validi"}, status=400)

    return JsonResponse({"success": False, "message": "Metodo non consentito"}, status=405)