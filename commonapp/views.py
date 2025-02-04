from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.shortcuts import redirect

@ensure_csrf_cookie
def get_csrf_token(request):
    """
    Assicura che venga impostato un cookie CSRF in risposta.
    """
    return JsonResponse({"detail": "CSRF cookie set"})

@require_POST
def login_view(request):
    username = request.POST.get("username")
    password = request.POST.get("password")

    user = authenticate(request, username=username, password=password)

    if user is not None:
        login(request, user)
        return JsonResponse({"success": True, "detail": "User logged in"})
    else:
        return JsonResponse({"success": False, "detail": "Invalid credentials"}, status=401)

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
