import time
import logging
import uuid
import threading

logger = logging.getLogger(__name__)

class PerformanceLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = str(uuid.uuid4())
        request.start_time = time.time()
        request.request_id = request_id

        response = self.get_response(request)

        duration = time.time() - request.start_time
        logger.info(f"[{request_id}] {request.method} {request.path} took {duration:.3f}s")

        response["X-Request-ID"] = request_id
        return response

from django.contrib.auth import get_user_model

class ImpersonateMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if hasattr(request, 'user') and request.user.is_authenticated and 'impersonated_user_id' in request.session:
            impersonated_user_id = request.session['impersonated_user_id']
            try:
                User = get_user_model()
                target_user = User.objects.get(id=impersonated_user_id)
                # Store the original user in request.impersonator
                request.impersonator = request.user
                # Overwrite request.user
                request.user = target_user
            except User.DoesNotExist:
                # If target user doesn't exist, clear session
                del request.session['impersonated_user_id']
        
        response = self.get_response(request)
        return response

_thread_locals = threading.local()

def get_current_request():
    return getattr(_thread_locals, 'request', None)

def get_current_user():
    request = get_current_request()
    if request and hasattr(request, 'user'):
        return request.user
    return None

def get_client_ip():
    request = get_current_request()
    if not request:
        return None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')

class CurrentRequestMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_locals.request = request
        response = self.get_response(request)
        if hasattr(_thread_locals, 'request'):
            del _thread_locals.request
        return response
