FROM python:3.13-slim-bookworm

# Variabili d'ambiente Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV IN_DOCKER=1

WORKDIR /app

# Installazione dipendenze di sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
    git \
    default-libmysqlclient-dev \
    unixodbc-dev \
    libcairo2-dev \
    libpango1.0-dev \
    libjpeg-dev \
    zlib1g-dev \
    libgdk-pixbuf-2.0-dev \
    libffi-dev \
    shared-mime-info \
    poppler-utils \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Installazione dipendenze Python
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copia del codice sorgente
COPY . /app/

# Creazione cartelle necessarie
RUN mkdir -p /app/staticfiles /app/uploads /app/xml /app/tempfile

# --- VARIABILI DUMMY PER IL COLLECTSTATIC ---
# Base e Database
ENV SECRET_KEY="build-time-secret-key"
ENV DATABASE_ENGINE="django.db.backends.sqlite3"
ENV DATABASE_NAME=":memory:"
ENV DATABASE_USER="dummy"
ENV DATABASE_PASSWORD="dummy"
ENV DATABASE_HOST="localhost"
ENV DATABASE_PORT="5432"

# Domini e IP (per ALLOWED_HOSTS e CORS)
ENV BIXENGINE_DOMAIN="localhost"
ENV BIXPORTAL_DOMAIN="localhost"
ENV BIXMOBILE_DOMAIN="localhost"
ENV BIXENGINE_IP="127.0.0.1"
ENV BIXPORTAL_IP="127.0.0.1"
ENV BIXMOBILE_IP="127.0.0.1"
ENV BIXVERIFY_IP="127.0.0.1"

# Porte e Server
ENV BIXENGINE_PORT="8000"
ENV BIXPORTAL_PORT="80"
ENV BIXCUSTOM_PORT="81"
ENV BIXPORTAL_NGINX_PORT="80"
ENV BIXCUSTOM_NGINX_PORT="81"
ENV BIXMOBILE_PORT="82"
ENV BIXENGINE_SERVER="http://localhost"
ENV BIXPORTAL_SERVER="http://localhost"

# Email
ENV EMAIL_HOST="localhost"
ENV EMAIL_PORT="587"
ENV EMAIL_TLS="True"
ENV EMAIL_HOST_USER="dummy"
ENV EMAIL_HOST_PASSWORD="dummy"

# Microsoft Graph
ENV GRAPH_CLIENT_ID="dummy"
ENV GRAPH_CLIENT_SECRET="dummy"
ENV GRAPH_TENANT_ID="dummy"

# Chiavi Fernet (Evitano il RuntimeError del tuo settings.py)
ENV QR_FERNET_KEY="dummy-key-per-la-build-non-usare-in-prod"
ENV HASHEDID_FERNET_KEY="dummy-key-per-la-build-non-usare-in-prod"


# Esecuzione collectstatic
RUN python manage.py collectstatic --noinput --clear

EXPOSE 8000

# Avvio con Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "bixengine.wsgi:application"]