"""
Lance Flask (UI) et FastAPI (API) simultanément.

Local  : python3 run_all.py
         Flask  → http://localhost:5050
         FastAPI → http://localhost:8000

Railway: le port principal (PORT env var) est pris par Flask.
         FastAPI tourne sur PORT+1.
"""
import subprocess
import sys
import os
import time
import signal

BASE   = os.path.dirname(os.path.abspath(__file__))
PYTHON = os.path.join(BASE, "venv", "bin", "python3")
if not os.path.exists(PYTHON):
    PYTHON = sys.executable   # fallback : python du PATH (prod)

# Railway assigne PORT dynamiquement ; en local on utilise 5050/8000
FLASK_PORT = int(os.getenv("PORT", 5050))
API_PORT   = int(os.getenv("API_PORT", FLASK_PORT + 1 if os.getenv("PORT") else 8000))

processes = []


def start():
    flask_proc = subprocess.Popen(
        [PYTHON, "-m", "gunicorn", "web.app:app",
         "--bind", f"0.0.0.0:{FLASK_PORT}",
         "--workers", "2", "--timeout", "120"],
        cwd=BASE,
    )
    processes.append(flask_proc)
    print(f"✅ Flask  démarré (PID {flask_proc.pid}) → port {FLASK_PORT}")

    time.sleep(1)

    api_proc = subprocess.Popen(
        [PYTHON, "-m", "uvicorn", "api.main:app",
         "--host", "0.0.0.0", "--port", str(API_PORT),
         "--log-level", "warning"],
        cwd=BASE,
    )
    processes.append(api_proc)
    print(f"✅ FastAPI démarré (PID {api_proc.pid}) → port {API_PORT}")
    print(f"   Docs Swagger : http://localhost:{API_PORT}/docs")
    print("\nCtrl+C pour arrêter les deux services.\n")

    def shutdown(sig, frame):
        print("\nArrêt...")
        for p in processes:
            p.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    for p in processes:
        p.wait()


if __name__ == "__main__":
    start()
