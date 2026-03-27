from django.http import JsonResponse
from commonapp.bixmodels.helper_db import HelpderDB

def get_user_info(request, page):
    sql=f"SELECT * FROM user_utenti WHERE nomeutente='{request.user.username}' AND deleted_='N'"
    record_utente=HelpderDB.sql_query_row(sql)
    nome=record_utente['nome']
    ruolo=record_utente['ruolo']
    
    if page=="/home" and ruolo != 'Amministratore':
        return JsonResponse({
            "isAuthenticated": False,
            "username": request.user.username,
            "name": nome,
            "role": record_utente['ruolo'],
            "chat": record_utente['tabchat'],
            "telefono": record_utente['tabtelefono']
        })
    else:
        return JsonResponse({
            "isAuthenticated": True,
            "username": request.user.username,
            "name": nome,
            "role": record_utente['ruolo'],
            "chat": record_utente['tabchat'],
            "telefono": record_utente['tabtelefono']
        })
