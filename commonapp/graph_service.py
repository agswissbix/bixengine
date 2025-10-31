import datetime
from django.core.cache import cache
import msal
import requests
from django.conf import settings

__token_cache = {}

def get_graph_access_token():
    """
    Ottiene un token di accesso per l'API Graph usando il flusso Client Credentials.
    Utilizza una cache in-memory semplice.
    """
    global __token_cache

    if "access_token" in __token_cache:
        return __token_cache.get("access_token")

    config = settings.MS_GRAPH

    app = msal.ConfidentialClientApplication(
        config['CLIENT_ID'],
        authority=config['AUTHORITY'],
        client_credential=config['CLIENT_SECRET'],
    )

    result = app.acquire_token_silent(config['SCOPE'], account=None)

    if not result:
        print("Nessun token in cache, ne richiedo uno nuovo a Entra ID...")
        result = app.acquire_token_for_client(scopes=config['SCOPE'])

    if "access_token" in result:
        __token_cache = result
        return result['access_token']
    else:
        print(f"Errore nell'ottenere il token: {result.get('error')}")
        print(result.get('error_description'))
        return None
    
def get_all_users():
    """
    Ottiene un elenco di utenti che hanno un calendario attivo, 
    utilizzando una cache per migliorare le prestazioni.
    """
    # cached_users = cache.get('users_with_calendar')
    # if cached_users is not None:
    #     print("Restituisco la lista di utenti dalla cache.")
    #     return cached_users

    # print("Cache vuota. Eseguo un controllo completo degli utenti e dei loro calendari...")
    token = get_graph_access_token()
    if not token:
        return {"error": "Impossibile ottenere il token di accesso"}

    endpoint = f"{settings.MS_GRAPH['GRAPH_ENDPOINT']}/users?$select=id,userPrincipalName,displayName,mail"
    headers = {'Authorization': f'Bearer {token}'}
    
    try:
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()
        all_users = response.json().get('value', [])
        
        users_with_calendar = []
        
        for user in all_users:
            user_id = user.get('id')
            if not user_id:
                continue

            calendar_check_endpoint = f"{settings.MS_GRAPH['GRAPH_ENDPOINT']}/users/{user_id}/calendar?$select=id"
            try:
                calendar_response = requests.get(calendar_check_endpoint, headers=headers)
                if calendar_response.status_code == 200:
                    users_with_calendar.append(user)
            except requests.exceptions.RequestException:
                continue
        
        # cache.set('users_with_calendar', users_with_calendar, 3600)
        
        print(f"Controllo completato. Trovati {len(users_with_calendar)} utenti con calendario attivo.")
        return users_with_calendar

    except requests.exceptions.HTTPError as e:
        return {"error": str(e), "details": e.response.json()}
    except Exception as e:
        return {"error": str(e)}


def get_user_details(user_email):
    """
    Ottiene i dettagli di un singolo utente tramite la sua email.
    """
    token = get_graph_access_token()
    if not token:
        return {"error": "Impossibile ottenere il token di accesso"}

    endpoint = f"{settings.MS_GRAPH['GRAPH_ENDPOINT']}/users/{user_email}?$select=id,displayName,userPrincipalName"
    headers = {'Authorization': f'Bearer {token}'}

    try:
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        return {"error": str(e), "details": e.response.json()}
    except Exception as e:
        return {"error": str(e)}

def find_calendar_by_name(user_id_or_email, calendar_name):
    """
    Cerca un calendario specifico di un utente tramite il suo nome.
    Restituisce il primo calendario che corrisponde esattamente al nome (case-insensitive).
    """
    calendars = get_user_calendars(user_id_or_email)

    if isinstance(calendars, dict) and 'error' in calendars:
        return calendars

    for cal in calendars:
        if cal.get('name', '').lower() == calendar_name.lower():
            return cal  
    
    return None  

def get_user_calendars(user_id_or_email):
    """
    Ottiene tutti i calendari di un utente.
    """
    token = get_graph_access_token()
    if not token:
        return {"error": "Impossibile ottenere il token di accesso"}

    endpoint = f"{settings.MS_GRAPH['GRAPH_ENDPOINT']}/users/{user_id_or_email}/calendars"
    headers = {'Authorization': f'Bearer {token}'}

    try:
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()
        return response.json().get('value', [])
    except requests.exceptions.HTTPError as e:
        return {"error": str(e), "details": e.response.json()}
    except Exception as e:
        return {"error": str(e)}

def get_events_for_user(user_id_or_email, start_date_iso, end_date_iso, calendar_id=None):
    """
    Ottiene gli eventi per un singolo utente in un intervallo di date.
    Usa 'calendarView' che è l'endpoint corretto per gestire le date.
    Accetta sia l'ID Utente (GUID) che l'email (UPN).
    Se `calendar_id` è specificato, agisce su quel calendario, altrimenti sul predefinito.
    """
    token = get_graph_access_token()
    if not token:
        return {"error": "Impossibile ottenere il token di accesso"}

    if calendar_id:
        base_endpoint = f"{settings.MS_GRAPH['GRAPH_ENDPOINT']}/users/{user_id_or_email}/calendars/{calendar_id}"
    else:
        base_endpoint = f"{settings.MS_GRAPH['GRAPH_ENDPOINT']}/users/{user_id_or_email}"

    endpoint = (
        f"{base_endpoint}/calendarView"
        f"?startDateTime={start_date_iso}&endDateTime={end_date_iso}"
        "&$select=id,subject,start,end,organizer,body,categories"
        "&$expand=calendar"
    )
    headers = {'Authorization': f'Bearer {token}'}

    try:
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data.get('value', [])
    except requests.exceptions.HTTPError as e:
       if e.response.status_code == 404:
           return [] 
       print(f"Errore HTTP per utente {user_id_or_email}: {e.response.status_code}")
       return {"error": str(e), "details": e.response.json()}
    except Exception as e:
        return {"error": str(e)}
    
def get_calendar_view_delta(user_id, start_date_iso, end_date_iso, delta_link=None, calendar_id=None):
    """
    Esegue una query delta sulla calendarView di un utente.
    Se viene fornito un delta_link, lo usa per ottenere solo le modifiche.
    Altrimenti, inizia una nuova sequenza delta.
    """
    token = get_graph_access_token()
    if not token:
        return {"error": "Impossibile ottenere il token di accesso"}

    headers = {
        'Authorization': f'Bearer {token}',
        'Prefer': 'odata.track-changes' 
    }

    if delta_link:
        endpoint = delta_link
    else:
        if calendar_id:
            base_endpoint = f"{settings.MS_GRAPH['GRAPH_ENDPOINT']}/users/{user_id}/calendars/{calendar_id}"
        else:
            base_endpoint = f"{settings.MS_GRAPH['GRAPH_ENDPOINT']}/users/{user_id}"

        endpoint = (
            f"{base_endpoint}/calendarView/delta"
            f"?startDateTime={start_date_iso}&endDateTime={end_date_iso}"
        )

    try:
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        return {"error": str(e), "details": e.response.json()}
    
def create_calendar_event(user_email, subject, start_time, end_time, body_content, categories=None, timezone="Europe/Rome", calendar_id=None):
    """
    Crea un evento nel calendario dell'utente specificato.
    'start_time' e 'end_time' devono essere stringhe in formato ISO 8601 (es. "2024-10-30T10:00:00")
    """
    token = get_graph_access_token()
    if not token:
        return {"error": "Impossibile ottenere il token di accesso"}

    if calendar_id:
        endpoint = f"{settings.MS_GRAPH['GRAPH_ENDPOINT']}/users/{user_email}/calendars/{calendar_id}/events"
    else:
        endpoint = f"{settings.MS_GRAPH['GRAPH_ENDPOINT']}/users/{user_email}/calendar/events"

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    event_data = {
        "subject": subject,
        "body": {
            "contentType": "HTML",
            "content": body_content
        },
        "start": {
            "dateTime": start_time,
            "timeZone": timezone
        },
        "end": {
            "dateTime": end_time,
            "timeZone": timezone
        },
        "isReminderOn": False
    }

    if categories:
        event_data['categories'] = categories

    try:
        response = requests.post(endpoint, headers=headers, json=event_data)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.HTTPError as e:
        return {"error": str(e), "details": e.response.json()}
    except Exception as e:
        return {"error": str(e)}
    
def get_event_details(user_id_or_email, event_id, calendar_id=None):
    """
    Ottiene i dettagli completi di un singolo evento.
    Se `calendar_id` è specificato, agisce su quel calendario, altrimenti sul predefinito.
    """
    token = get_graph_access_token()
    if not token:
        return {"error": "Impossibile ottenere il token di accesso"}

    if calendar_id:
        endpoint = f"{settings.MS_GRAPH['GRAPH_ENDPOINT']}/users/{user_id_or_email}/calendars/{calendar_id}/events/{event_id}"
    else:
        endpoint = (
            f"{settings.MS_GRAPH['GRAPH_ENDPOINT']}/users/{user_id_or_email}/events/{event_id}"
            "?$select=id,subject,start,end,body,organizer,categories"
        )
    headers = {'Authorization': f'Bearer {token}'}

    try:
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        return {"error": str(e), "details": e.response.json()}
    except Exception as e:
        return {"error": str(e)}
    
def update_calendar_event(user_email, event_id, subject=None, start_time=None, end_time=None, body_content=None, categories=None, timezone="Europe/Rome", calendar_id=None):
    """
    Modifica un evento esistente nel calendario di un utente.
    Invia solo i campi che vengono effettivamente forniti.
    Se `calendar_id` è specificato, agisce su quel calendario, altrimenti sul predefinito.
    """
    token = get_graph_access_token()
    if not token:
        return {"error": "Impossibile ottenere il token di accesso"}

    if calendar_id:
        endpoint = f"{settings.MS_GRAPH['GRAPH_ENDPOINT']}/users/{user_email}/calendars/{calendar_id}/events/{event_id}"
    else:
        endpoint = f"{settings.MS_GRAPH['GRAPH_ENDPOINT']}/users/{user_email}/events/{event_id}"

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    event_data = {}
    if subject:
        event_data["subject"] = subject
    if body_content:
        event_data["body"] = {"contentType": "HTML", "content": body_content}
    if start_time:
        event_data["start"] = {"dateTime": start_time, "timeZone": timezone}
    if end_time:
        event_data["end"] = {"dateTime": end_time, "timeZone": timezone}
    if categories is not None:
        event_data["categories"] = categories

    if not event_data:
        return {"error": "Nessun dato fornito per la modifica."}

    try:
        response = requests.patch(endpoint, headers=headers, json=event_data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        return {"error": str(e), "details": e.response.json()}

def delete_event(user_id_or_email, event_id, calendar_id=None):
    """
    Elimina un singolo evento.
    Se `calendar_id` è specificato, agisce su quel calendario, altrimenti sul predefinito.
    """
    token = get_graph_access_token()
    if not token:
        return {"error": "Impossibile ottenere il token di accesso"}

    if calendar_id:
        endpoint = f"{settings.MS_GRAPH['GRAPH_ENDPOINT']}/users/{user_id_or_email}/calendars/{calendar_id}/events/{event_id}"
    else:
        endpoint = f"{settings.MS_GRAPH['GRAPH_ENDPOINT']}/users/{user_id_or_email}/events/{event_id}"
    headers = {'Authorization': f'Bearer {token}'}

    try:
        response = requests.delete(endpoint, headers=headers)
        if response.status_code == 204:
            return {"success": True}
        response.raise_for_status() 
        return {"success": True}
    except requests.exceptions.HTTPError as e:
        return {"error": str(e), "details": e.response.json()}
    except Exception as e:
        return {"error": str(e)}