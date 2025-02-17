from waitress import serve
from bixengine.wsgi import application

serve(application, host='localhost', port=8000)
