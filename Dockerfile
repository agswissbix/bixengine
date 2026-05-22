FROM python:3.11.1

# Variabili d'ambiente Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV IN_DOCKER=1

WORKDIR /app

# Timezone
ENV TZ=Europe/Rome

# Installazione dipendenze di sistema (Base per il progetto)
RUN apt-get update && apt-get install -y \
    tzdata \
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

# --- INSTALLAZIONE DRIVER MICROSOFT SQL SERVER ---
RUN apt-get update && apt-get install -y curl apt-transport-https gnupg2

# 1. Scarica la chiave e salvala nella cartella TRADIZIONALE dei certificati fidati
RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /etc/apt/trusted.gpg.d/microsoft-prod.gpg

# 2. Aggiungi il repository per Debian 11
RUN curl -fsSL https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list

# 3. Installa il driver accettando la licenza
RUN apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql18

# 4. Pulisci la cache per mantenere l'immagine leggera
RUN rm -rf /var/lib/apt/lists/*
# --------------------------------------------------

# Installazione dipendenze Python
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# --- FIX PLAYWRIGHT ---
# Installiamo Chromium e le dipendenze di sistema necessarie (libnss, libgbm, ecc.)
# Questo DEVE essere fatto dopo aver installato il pacchetto pip 'playwright'
RUN playwright install --with-deps chromium

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

# Chiavi Fernet
ENV QR_FERNET_KEY="dummy-key-per-la-build-non-usare-in-prod"
ENV HASHEDID_FERNET_KEY="dummy-key-per-la-build-non-usare-in-prod"

# Esecuzione collectstatic
RUN python manage.py collectstatic --noinput --clear

EXPOSE 8000

# Avvio con Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "bixengine.wsgi:application"]