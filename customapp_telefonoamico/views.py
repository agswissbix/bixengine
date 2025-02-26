from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.csrf import csrf_exempt
from commonapp.bixmodels.helper_db import *
from commonapp.bixmodels.user_record import *
from commonapp.bixmodels.user_table import *
from commonapp.helper import *


def test(request):
    print("Test in customapp_telefonoamico")
    return JsonResponse({"detail": "Test in customapp_telefonoamico"})

@api_view(['GET','POST'])
#@permission_classes([IsAuthenticated])  # Protegge l'API con autenticazione
#@ensure_csrf_cookie
#@csrf_exempt
@login_required_api
@renderer_classes([JSONRenderer])  # Forza il ritorno di JSON
def get_shifts_and_volunteers(request):
    """Restituisce la lista dei turni, volontari e slot assegnati"""

    user_id = request.user.id
    username = request.user.username

    shifts = [
        {"value": "B", "label": "Bellinzona"},
        {"value": "C", "label": "Casa"},
        {"value": "L", "label": "Lugano"},
        {"value": "M", "label": "Monti"},
        {"value": "S", "label": "Stabio"}
    ]

  
    volunteers=[]
    utenti=HelpderDB.sql_query(f"SELECT * FROM user_utenti where deleted_='N'")
    for utente in utenti:
        volunteers.append(utente['nome'])
   
   

    time_slots = [
        "07.30-11.30", "11.30-15.30", "15.30-19.30",
        "19.30-23.30", "23.30-03.30", "03.30-07.30"
    ]

    today = datetime.date.today()
    access1='edit'
    access2='edit'
    access3='edit'
    access4='edit'
    if username=='mariangela.rosa':
        access1='edit'
        access2='edit'
        access3='edit'
        access4='edit'
    if username=='ta.test':
        access4='edit'

    turni_table=UserTable('turni')
    turni=turni_table.get_results_records()
  

    slots = []

    for turno in turni:
        nome=HelpderDB.sql_query_value(f"SELECT nome FROM user_utenti WHERE recordid_='{turno['recordidutenti_']}'",'nome')
        slot = {
            "date": turno["data"],
            "timeSlot": turno["fasciaoraria"],
            "name": nome,
            "shift": turno["sede"],
            "dev": "",
            "access": access4
        }
        slots.append(slot)

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
    #verifico se il turno e' già impostato
    recordid_shift=HelpderDB.sql_query_value(f"SELECT * FROM user_turni WHERE data='{date}' AND fasciaoraria='{timeSlot}'  AND tipo='telefono'",'recordid_')
    if recordid_shift:
        record_shift=UserRecord('turni',recordid_shift)
    else:
        record_shift=UserRecord('turni')
    record_shift.values['data']=date
    record_shift.values['fasciaoraria']=timeSlot
    record_shift.values['sede']=shift
    record_shift.values['tipo']='telefono'
    utente_recordid=HelpderDB.sql_query_value(f"SELECT * FROM user_utenti WHERE nome='{name}'",'recordid_')
    record_shift.values['recordidutenti_']=utente_recordid
    record_shift.save()
    

    


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

    HelpderDB.sql_execute(f"UPDATE user_turni SET deleted_='Y' WHERE data='{date}' AND fasciaoraria='{timeSlot}'  AND tipo='telefono'")

    print(f"Turno eliminato: {new_shift}")  # Debug

    return Response(new_shift, status=201)




