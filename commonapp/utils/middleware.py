import time
import logging
import uuid

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
