import json
from django.shortcuts import render
from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from rest_framework import status

# Create your views here.

@csrf_exempt
@api_view(['POST'])
def winteler_wip_barcode_scan(request):
    """
    Esempio di funzione che riceve un barcode lotto (barcodeLotto)
    e una lista di barcode wip (barcodeWipList).
    """
    # Estraggo i dati dal body della richiesta
    barcode_lotto = request.data.get('barcodeLotto', None)
    barcode_wip_list = request.data.get('barcodeWipList', [])

    # Verifico la presenza di barcodeLotto
    if not barcode_lotto:
        return Response(
            {"detail": "barcodeLotto è obbligatorio"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Verifico che barcodeWipList sia effettivamente una lista
    if not isinstance(barcode_wip_list, list):
        return Response(
            {"detail": "barcodeWipList deve essere una lista di barcode"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Da qui puoi inserire la logica che serve per salvare i dati nel database
    # o processarli come meglio credi. Ad esempio:
    # for wip in barcode_wip_list:
    #     # Salvataggio su DB o altra logica
    #     WipModel.objects.create(lotto=barcode_lotto, wip_code=wip)
    #
    # Oppure puoi semplicemente ritornare una conferma

    return Response(
        {
            "message": "Dati ricevuti con successo!",
            "barcodeLotto": barcode_lotto,
            "barcodeWipList": barcode_wip_list
        },
        status=status.HTTP_200_OK
    )