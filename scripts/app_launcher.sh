#!/bin/bash
PROJECT_DIR="/Users/yomboulock/Documents/EnterpriseCore"
PORT=5050
VENV="${PROJECT_DIR}/venv/bin/python3"
APP_SCRIPT="${PROJECT_DIR}/web/app.py"
LOG="${PROJECT_DIR}/web/server.log"

# Si le serveur tourne déjà → ouvrir directement
if curl -s "http://localhost:${PORT}/" > /dev/null 2>&1; then
    open "http://localhost:${PORT}/"
    exit 0
fi

# Démarrer Flask en arrière-plan
cd "${PROJECT_DIR}"
nohup "${VENV}" "${APP_SCRIPT}" > "${LOG}" 2>&1 &

# Attendre que le serveur soit prêt (max 15s)
for i in $(seq 1 30); do
    sleep 0.5
    if curl -s "http://localhost:${PORT}/" > /dev/null 2>&1; then
        break
    fi
done

open "http://localhost:${PORT}/"
