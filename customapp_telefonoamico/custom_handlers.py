from django.http import JsonResponse
from commonapp.bixmodels.helper_db import HelpderDB

def get_user_info(request, page):
    sql=f"SELECT * FROM user_utenti WHERE nomeutente='{request.user.username}' AND deleted_='N'"
    record_utente=HelpderDB.sql_query_row(sql)
    if record_utente is None:
        return JsonResponse({
            "isAuthenticated": False,
            "username": request.user.username,
            "name": None,
            "role": None,
            "chat": None,
            "telefono": None,
            "is_2fa_enabled": False
        })
    nome=record_utente['nome']
    ruolo=record_utente['ruolo']
    
    is_auth=True
    if page=="/home" and ruolo != 'Amministratore':
        is_auth=False
        
    return JsonResponse({
        "isAuthenticated": is_auth,
        "username": request.user.username,
        "name": nome,
        "role": record_utente['ruolo'],
        "chat": record_utente['tabchat'],
        "telefono": record_utente['tabtelefono'],
    })
