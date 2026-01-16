# 1. Configurazione variabili
$CLIENT_ID="il_tuo_client_id"
$GITHUB_USER="tuo_utente"

Write-Host "--- Inizio Deployment per $CLIENT_ID ---" -ForegroundColor Cyan

# 2. Creazione automatica della rete
$networkCheck = docker network ls --filter name=bix-network -q
if (-not $networkCheck) {
    Write-Host "Creazione rete bix-network..."
    docker network create bix-network
}

# 3. Pull delle ultime immagini
Write-Host "Scaricamento immagini aggiornate..." -ForegroundColor Yellow
docker compose -f ./bixengine/docker-compose.yml pull
docker compose -f ./bixportal/docker-compose.yml pull

# 4. Riavvio dei servizi
Write-Host "Avvio Backend (BixEngine)..."
docker compose -f ./bixengine/docker-compose.yml up -d

Write-Host "Avvio Frontend (BixPortal)..."
docker compose -f ./bixportal/docker-compose.yml up -d

# 5. Pulizia immagini vecchie
Write-Host "Pulizia immagini inutilizzate..."
docker image prune -f

Write-Host "--- Deployment completato con successo! ---" -ForegroundColor Green