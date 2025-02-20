from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from django.shortcuts import render
from commonapp.bixmodels.helper_db import *



def test(request):
    print("Test in customapp_telefonoamico")
    return JsonResponse({"detail": "Test in customapp_telefonoamico"})

@api_view(['GET','POST'])
@permission_classes([IsAuthenticated])  # Protegge l'API con autenticazione
@renderer_classes([JSONRenderer])  # Forza il ritorno di JSON
def get_shifts_and_volunteers(request):
    """Restituisce la lista dei turni, volontari e slot assegnati"""

    shifts = [
        {"value": "B", "label": "Bellinzona"},
        {"value": "C", "label": "Casa"},
        {"value": "L", "label": "Lugano"},
        {"value": "M", "label": "Monti"},
        {"value": "S", "label": "Stabio"}
    ]

    volunteers = [
        "Alessandro Galli",
        "Mariangela Rosa",
        "Giovanni Bianchi",
        "Lucia Verdi"
    ]

    time_slots = [
        "07.30-11.30", "11.30-15.30", "15.30-19.30",
        "19.30-23.30", "23.30-03.30", "03.30-07.30"
    ]

    today = datetime.date.today()

    slots = [
        {"date": "2024-12-02", "timeSlot": "07.30-11.30", "name": "Alessandro Galli", "shift": "B", "dev": "X", "access": "edit"},
        {"date": "2024-12-03", "timeSlot": "11.30-15.30", "name": "Mariangela Rosa", "shift": "C", "dev": "", "access": "view"},
        {"date": "2024-12-07", "timeSlot": "15.30-19.30", "name": "Giovanni Bianchi", "shift": "L", "dev": "X", "access": "delete"},
        {"date": "2024-12-10", "timeSlot": "19.30-23.30", "name": "Lucia Verdi", "shift": "M", "dev": "", "access": "edit"}
    ]

    return Response({"shifts": shifts, "volunteers": volunteers, "slots": slots, "timeSlots": time_slots})



@api_view(['POST'])
@permission_classes([IsAuthenticated])  # Protegge l'API
def save_shift(request):
    """Salva un nuovo turno inviato dal frontend"""

    data = request.data
    date = data.get("date")
    timeSlot = data.get("timeSlot")
    name = data.get("name")
    shift = data.get("shift")
    dev = data.get("dev", "")

    #if not date or not timeSlot or not name or not shift:
        #return Response({"error": "Dati mancanti"}, status=400)

    # Qui puoi salvare nel database se necessario
    new_shift = {
        "date": date,
        "timeSlot": timeSlot,
        "name": name,
        "shift": shift,
        "dev": dev
    }

    print(f"Nuovo turno salvato: {new_shift}")  # Debug

    return Response(new_shift, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])  # Protegge l'API
def delete_shift(request):
    """Elimina un nuovo turno inviato dal frontend"""

    data = request.data
    date = data.get("date")
    timeSlot = data.get("timeSlot")
    name = data.get("name")
    shift = data.get("shift")
    dev = data.get("dev", "")

    #if not date or not timeSlot or not name or not shift:
        #return Response({"error": "Dati mancanti"}, status=400)

    # Qui puoi salvare nel database se necessario
    new_shift = {
        "date": date,
        "timeSlot": timeSlot,
        "name": name,
        "shift": shift,
        "dev": dev
    }

    print(f"Turno eliminato: {new_shift}")  # Debug

    return Response(new_shift, status=201)