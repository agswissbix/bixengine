from django.http import JsonResponse

def superuser_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_superuser:
            return JsonResponse({"success": False, "error": "Accesso riservato ai superuser."}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapper
