#!/bin/bash

# DEPLOY Automatico

# 1. Configurazione variabili
CLIENT_ID="il_tuo_client_id"
GITHUB_USER="tuo_utente"

echo "--- Inizio Deployment per $CLIENT_ID ---"

# 2. Creazione automatica della rete
docker network inspect bix-network >/dev/null 2>&1 || \
    (echo "Creazione rete bix-network..." && docker network create bix-network)

# 3. Pull delle ultime immagini dal registro GHCR
echo "Scaricamento immagini aggiornate..."
docker compose -f ./bixengine/docker-compose.yml pull
docker compose -f ./bixportal/docker-compose.yml pull

# 4. Riavvio dei servizi (Backend prima, Frontend dopo)
echo "Avvio Backend (BixEngine)..."
docker compose -f ./bixengine/docker-compose.yml up -d

echo "Avvio Frontend (BixPortal)..."
docker compose -f ./bixportal/docker-compose.yml up -d

# 5. Pulizia immagini vecchie
echo "Pulizia immagini inutilizzate..."
docker image prune -f

echo "--- Deployment completato con successo! ---"