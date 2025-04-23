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
