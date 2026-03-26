#!/bin/bash
# Crée le bundle .app EnterpriseCore sur le Bureau

set -e

PROJECT_DIR="/Users/yomboulock/Documents/EnterpriseCore"
APP_NAME="EnterpriseCore"
APP_PATH="/Users/yomboulock/Desktop/${APP_NAME}.app"
ICNS_SRC="${PROJECT_DIR}/scripts/icon_build/EnterpriseCore.icns"

echo "→ Création du bundle .app..."

# Nettoyer si déjà existant
rm -rf "${APP_PATH}"

# Structure du bundle
mkdir -p "${APP_PATH}/Contents/MacOS"
mkdir -p "${APP_PATH}/Contents/Resources"

# ─── Launcher shell ───────────────────────────────────────────
cat > "${APP_PATH}/Contents/MacOS/${APP_NAME}" << 'LAUNCHER'
#!/bin/bash
PROJECT_DIR="/Users/yomboulock/Documents/EnterpriseCore"
PORT=5050
VENV="${PROJECT_DIR}/venv/bin/python3"
APP_SCRIPT="${PROJECT_DIR}/web/app.py"
LOG="${PROJECT_DIR}/web/server.log"

# Vérifier si le serveur tourne déjà
if curl -s "http://localhost:${PORT}/" > /dev/null 2>&1; then
    open "http://localhost:${PORT}/"
    exit 0
fi

# Démarrer le serveur Flask en arrière-plan
cd "${PROJECT_DIR}"
nohup "${VENV}" "${APP_SCRIPT}" > "${LOG}" 2>&1 &

# Attendre que le serveur soit prêt (max 15 secondes)
for i in $(seq 1 30); do
    sleep 0.5
    if curl -s "http://localhost:${PORT}/" > /dev/null 2>&1; then
        break
    fi
done

open "http://localhost:${PORT}/"
LAUNCHER

chmod +x "${APP_PATH}/Contents/MacOS/${APP_NAME}"

# ─── Info.plist ───────────────────────────────────────────────
cat > "${APP_PATH}/Contents/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>${APP_NAME}</string>
    <key>CFBundleDisplayName</key>
    <string>EnterpriseCore AI</string>
    <key>CFBundleIdentifier</key>
    <string>com.enterprisecore.ailegal</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleExecutable</key>
    <string>${APP_NAME}</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>LSUIElement</key>
    <false/>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
PLIST

# ─── Icône ────────────────────────────────────────────────────
if [ -f "${ICNS_SRC}" ]; then
    cp "${ICNS_SRC}" "${APP_PATH}/Contents/Resources/AppIcon.icns"
    echo "→ Icône appliquée."
fi

# ─── Signalement à macOS que c'est une app ────────────────────
touch "${APP_PATH}"

echo ""
echo "✅  EnterpriseCore.app créé sur le Bureau."
echo "    Double-cliquer pour lancer l'interface."
CONTENT
