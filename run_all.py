"""
Lance Flask (UI), FastAPI (API) et le Bot Telegram simultanément.

Local  : python3 run_all.py
         Flask      → http://localhost:5050
         FastAPI    → http://localhost:8000
         Telegram   → polling (TELEGRAM_TOKEN dans .env)

Render : le port principal (PORT env var) est pris par Flask.
         FastAPI tourne sur PORT+1.
         Le bot Telegram tourne en thread séparé.
"""
import subprocess
import sys
import os
import time
import signal
import threading

BASE   = os.path.dirname(os.path.abspath(__file__))
PYTHON = os.path.join(BASE, "venv", "bin", "python3")
if not os.path.exists(PYTHON):
    PYTHON = sys.executable   # fallback : python du PATH (prod)

# Render/Railway assigne PORT dynamiquement ; en local on utilise 5050/8000
FLASK_PORT = int(os.getenv("PORT", 5050))
API_PORT   = int(os.getenv("API_PORT", FLASK_PORT + 1 if os.getenv("PORT") else 8000))

processes = []


def _start_telegram_bot():
    """Lance le bot Telegram dans un thread séparé (ne bloque pas le reste)."""
    try:
        sys.path.insert(0, BASE)
        from telegram_bot.bot import run_bot
        run_bot()
    except Exception as e:
        print(f"⚠️  Bot Telegram non démarré : {e}")


def _start_scheduler():
    """Lance APScheduler en thread daemon pour les missions planifiées."""
    try:
        sys.path.insert(0, BASE)
        from core.scheduler import start_scheduler
        start_scheduler()
        print("✅ Scheduler  APScheduler démarré (missions planifiées actives)")
    except Exception as e:
        print(f"⚠️  Scheduler non démarré : {e}")


def start():
    # ── Flask ────────────────────────────────────────────────────
    flask_proc = subprocess.Popen(
        [PYTHON, "-m", "gunicorn", "web.app:app",
         "--bind", f"0.0.0.0:{FLASK_PORT}",
         "--workers", "2", "--timeout", "120"],
        cwd=BASE,
    )
    processes.append(flask_proc)
    print(f"✅ Flask      démarré (PID {flask_proc.pid}) → port {FLASK_PORT}")

    time.sleep(1)

    # ── FastAPI ──────────────────────────────────────────────────
    api_proc = subprocess.Popen(
        [PYTHON, "-m", "uvicorn", "api.main:app",
         "--host", "0.0.0.0", "--port", str(API_PORT),
         "--log-level", "warning"],
        cwd=BASE,
    )
    processes.append(api_proc)
    print(f"✅ FastAPI    démarré (PID {api_proc.pid}) → port {API_PORT}")
    print(f"   Docs Swagger : http://localhost:{API_PORT}/docs")

    # ── Bot Telegram ─────────────────────────────────────────────
    telegram_token = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
    if telegram_token:
        bot_thread = threading.Thread(target=_start_telegram_bot, daemon=True, name="TelegramBot")
        bot_thread.start()
        print("✅ Telegram   bot démarré (thread daemon)")
    else:
        print("⚠️  Telegram   bot ignoré (TELEGRAM_TOKEN absent du .env)")

    # ── APScheduler ──────────────────────────────────────────────
    sched_thread = threading.Thread(target=_start_scheduler, daemon=True, name="APScheduler")
    sched_thread.start()

    print("\nCtrl+C pour arrêter tous les services.\n")

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
