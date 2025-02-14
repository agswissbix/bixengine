from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.shortcuts import redirect

from django.views.decorators.csrf import csrf_exempt
import json
from django.middleware.csrf import get_token
from django.contrib.auth.decorators import login_required
from functools import wraps
from .bixmodels.sys_table import *
from .bixmodels.user_record import *
from .bixmodels.user_table import *

@ensure_csrf_cookie
def get_csrf_token(request):
    """
    Assicura che venga impostato un cookie CSRF in risposta.
    """
    token = get_token(request)
    print("CSRF Token impostato:", token)
    return JsonResponse({"detail": "CSRF cookie set"})


def login_required_api(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        print("sessionid:", request.COOKIES.get("sessionid"))
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapped

@require_POST
@csrf_exempt
def login_view(request):
    print("Function: login_view")
    print("Header X-CSRFToken:", request.META.get('HTTP_X_CSRFTOKEN'))
    print("Cookie csrftoken:", request.COOKIES.get('csrftoken'))
    print("SessionID:", request.COOKIES.get('sessionid'))
    username = request.POST.get("username")
    password = request.POST.get("password")

    user = authenticate(request, username=username, password=password)

    if user is not None:
        login(request, user)
        return JsonResponse({"success": True, "detail": "User logged in"})
    else:
        return JsonResponse({"success": False, "detail": "Invalid credentials"}, status=401)

@csrf_exempt
def logout_view(request):
    logout(request)
    return JsonResponse({"success": True, "detail": "User logged out"})

def user_info(request):
    if request.user.is_authenticated:
        return JsonResponse({
            "isAuthenticated": True,
            "username": request.user.username
        })
    else:
        return JsonResponse({"isAuthenticated": False}, status=401)

@login_required_api  
def get_examplepost(request):  
    print("Function: get_examplepost")
    csrf_header = request.META.get('HTTP_X_CSRFTOKEN')
    print("Header X-CSRFToken:", csrf_header)
    print("Cookie csrftoken:", request.COOKIES.get('csrftoken'))
    if request.method == 'POST':
        try:
            # Decodifica il corpo della richiesta JSON
            data = json.loads(request.body)

            # Crea una risposta basata sui dati ricevuti
            response_data = {
                "responseExampleValue": "Risposta dal backend"
            }

            return JsonResponse(response_data)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=405)

@login_required_api  
def get_sidebarmenu_items(request):  
    print("Function: get_sidebarmenu_items")
    tables=SysTable.get_user_tables(1)
    workspaces_tables=dict()
    for table in tables:
        workspace = table["workspace"]
        
        if workspace not in workspaces_tables:
            workspaces_tables[workspace] = {}
            workspaces_tables[workspace]["id"]=table['workspace']
            workspaces_tables[workspace]["title"]=table['workspace']
            workspaces_tables[workspace]["icon"]='Home'
        subitem={}
        subitem['id']=table['id']
        subitem['title']=table['description']
        subitem['href']="#"
        if "subItems" not in workspaces_tables[workspace]:
            workspaces_tables[workspace]['subItems']=[]
        workspaces_tables[workspace]["subItems"].append(subitem)

    response = {
        "menuItems": workspaces_tables
    }
    return JsonResponse(response, safe=False)

@csrf_exempt
def test_connection(request):
    response = {
        "Stato": "Connessione riuscita",
    }
    return JsonResponse(response, safe=False)

@csrf_exempt
def check_csrf(request):
    print("Header X-CSRFToken:", request.META.get('HTTP_X_CSRFTOKEN'))
    print("Cookie csrftoken:", request.COOKIES.get('csrftoken'))
    response = {
        "X-CSRFToken": "OK",
    }
    return JsonResponse(response, safe=False)


@ensure_csrf_cookie
@csrf_exempt
def csrf_test_view(request):
    print("Function: csrf_test_view")
    csrf_header = request.META.get('HTTP_X_CSRFTOKEN')
    print("Header X-CSRFToken:", csrf_header)
    print("Cookie csrftoken:", request.COOKIES.get('csrftoken'))
    print("Session ID:", request.COOKIES.get('sessionid'))
    if request.method == 'GET':
        # La GET serve a far impostare il cookie CSRF dal browser
        return JsonResponse({
            'message': 'CSRF cookie impostato. Usa questo endpoint per inviare la POST.'
        })
    elif request.method == 'POST':
        # La POST è protetta dal middleware CSRF; se il token non è valido, la richiesta fallirà
        try:
            data = json.loads(request.body)
        except Exception:
            data = {}
        return JsonResponse({
            'message': 'POST ricevuta correttamente!',
            'data': data
        })
    else:
        return JsonResponse({'message': 'Metodo non consentito'}, status=405)
    


from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
import pyotp
import qrcode
import base64
from io import BytesIO

@csrf_exempt
@login_required
def enable_2fa(request):
    user = request.user
    
    if request.method != "POST":
        return JsonResponse({"message": "Metodo non permesso"}, status=405)

    # Controlla se il 2FA è già attivo
    if request.session.get("otp_secret"):
        return JsonResponse({"message": "2FA già attivato"}, status=400)

    try:
        # Genera un segreto OTP per l'utente
        secret = pyotp.random_base32()
        request.session["otp_secret"] = secret
        request.session.save()

        # Genera l'URL del QR Code
        totp = pyotp.TOTP(secret)
        otp_url = totp.provisioning_uri(name=user.username, issuer_name="MyApp")

        # Genera il QR Code e convertilo in base64
        img = qrcode.make(otp_url)
        img_io = BytesIO()
        img.save(img_io, format="PNG")
        qr_base64 = base64.b64encode(img_io.getvalue()).decode('utf-8')

        return JsonResponse({"otp_url": otp_url, "qr_code": qr_base64})

    except Exception as e:
        return JsonResponse({"message": f"Errore nel generare il QR: {str(e)}"}, status=500)



@csrf_exempt
@login_required
def verify_2fa(request):
    if request.method != "POST":
        return JsonResponse({"message": "Metodo non permesso"}, status=405)

    # Ottieni i dati JSON
    data = json.loads(request.body)
    otp_token = data.get("otp")
    
    if not otp_token:
        return JsonResponse({"message": "Codice OTP mancante"}, status=400)
    
    secret = request.session.get("otp_secret")
    if not secret:
        return JsonResponse({"message": "2FA non attivato per questo utente"}, status=400)

    totp = pyotp.TOTP(secret)
    if totp.verify(otp_token):
        return JsonResponse({"message": "Autenticazione 2FA riuscita"})
    else:
        return JsonResponse({"message": "Codice OTP errato"}, status=400)
    

@csrf_exempt
@login_required
def disable_2fa(request):
    if request.method != "POST":
        return JsonResponse({"message": "Metodo non permesso"}, status=405)
    
    # Controlla se il 2FA è attivo
    if not request.session.get("otp_secret"):
        return JsonResponse({"message": "2FA non è attivo per questo utente"}, status=400)

    # Rimuovi il segreto dalla sessione
    del request.session["otp_secret"]
    request.session.save()
    
    return JsonResponse({"message": "2FA disabilitato con successo"})


