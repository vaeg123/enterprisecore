"""
EnterpriseCore — Scheduler de missions planifiées (APScheduler)
===============================================================

Charge les missions planifiées depuis la DB et les exécute selon leur cron_expr.
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from database.db_config import get_connection

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    _HAS_APSCHEDULER = True
except ImportError:
    _HAS_APSCHEDULER = False

log = logging.getLogger(__name__)

_scheduler = None


def _parse_cron(cron_expr: str) -> dict:
    """Convertit une expression cron '0 9 * * 1' en kwargs CronTrigger."""
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Expression cron invalide : {cron_expr} (attendu: minute heure jour mois jourSemaine)")
    return {
        "minute":      parts[0],
        "hour":        parts[1],
        "day":         parts[2],
        "month":       parts[3],
        "day_of_week": parts[4],
    }


def _run_scheduled_mission(mission_id: int, title: str, objective: str) -> None:
    """Exécute une mission planifiée et met à jour last_run / next_run."""
    log.info(f"[Scheduler] Lancement mission planifiée #{mission_id} : {title}")
    try:
        from core.planning.mission_orchestrator import MissionOrchestrator
        orchestrator = MissionOrchestrator()
        orchestrator.run(title=title, objective=objective)
        log.info(f"[Scheduler] Mission #{mission_id} terminée.")
    except Exception as e:
        log.error(f"[Scheduler] Erreur mission #{mission_id} : {e}")
    finally:
        _update_run_times(mission_id)


def _update_run_times(mission_id: int) -> None:
    """Met à jour last_run et next_run dans la DB."""
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE scheduled_missions SET last_run=%s WHERE id=%s",
            (datetime.now(), mission_id)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        log.error(f"[Scheduler] Erreur mise à jour last_run : {e}")


def _ensure_table() -> None:
    """Crée la table scheduled_missions si elle n'existe pas."""
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_missions (
            id         INT AUTO_INCREMENT PRIMARY KEY,
            title      VARCHAR(255) NOT NULL,
            objective  TEXT NOT NULL,
            cron_expr  VARCHAR(100) NOT NULL,
            label      VARCHAR(255),
            active     TINYINT(1) DEFAULT 1,
            last_run   DATETIME NULL,
            next_run   DATETIME NULL,
            created_by INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    conn.commit()
    cursor.close()
    conn.close()


def load_and_schedule_all() -> None:
    """Charge toutes les missions actives et les planifie."""
    global _scheduler
    if not _HAS_APSCHEDULER or _scheduler is None:
        return

    conn   = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, title, objective, cron_expr FROM scheduled_missions WHERE active=1"
    )
    missions = cursor.fetchall()
    cursor.close()
    conn.close()

    for m in missions:
        _add_job(m["id"], m["title"], m["objective"], m["cron_expr"])

    log.info(f"[Scheduler] {len(missions)} mission(s) planifiée(s) chargée(s).")


def _add_job(mission_id: int, title: str, objective: str, cron_expr: str) -> None:
    """Ajoute un job APScheduler pour une mission."""
    global _scheduler
    if not _HAS_APSCHEDULER or _scheduler is None:
        return
    job_id = f"scheduled_mission_{mission_id}"
    # Supprimer le job s'il existe déjà
    if _scheduler.get_job(job_id):
        _scheduler.remove_job(job_id)
    try:
        kwargs = _parse_cron(cron_expr)
        _scheduler.add_job(
            _run_scheduled_mission,
            trigger=CronTrigger(**kwargs),
            id=job_id,
            args=[mission_id, title, objective],
            replace_existing=True,
        )
        log.info(f"[Scheduler] Job planifié : {job_id} ({cron_expr})")
    except Exception as e:
        log.error(f"[Scheduler] Impossible de planifier le job {job_id} : {e}")


def _remove_job(mission_id: int) -> None:
    """Supprime un job APScheduler."""
    global _scheduler
    if not _HAS_APSCHEDULER or _scheduler is None:
        return
    job_id = f"scheduled_mission_{mission_id}"
    if _scheduler.get_job(job_id):
        _scheduler.remove_job(job_id)


def start_scheduler() -> None:
    """Démarre le scheduler en arrière-plan."""
    global _scheduler
    if not _HAS_APSCHEDULER:
        log.warning("[Scheduler] APScheduler non installé — missions planifiées désactivées.")
        return
    if _scheduler and _scheduler.running:
        return

    _ensure_table()
    _scheduler = BackgroundScheduler(timezone="Europe/Paris")
    _scheduler.start()
    load_and_schedule_all()
    log.info("[Scheduler] APScheduler démarré.")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("[Scheduler] APScheduler arrêté.")


# ── API publique pour Flask ────────────────────────────────────

def create_scheduled_mission(title: str, objective: str, cron_expr: str,
                             label: str = "", created_by: int = None) -> int:
    """Crée une nouvelle mission planifiée et la schedule."""
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO scheduled_missions (title, objective, cron_expr, label, active, created_by) "
        "VALUES (%s, %s, %s, %s, 1, %s)",
        (title, objective, cron_expr, label or title, created_by)
    )
    new_id = cursor.lastrowid
    conn.commit()
    cursor.close()
    conn.close()

    _add_job(new_id, title, objective, cron_expr)
    return new_id


def toggle_scheduled_mission(mission_id: int) -> bool:
    """Active/désactive une mission planifiée. Retourne le nouvel état."""
    conn   = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT active, title, objective, cron_expr FROM scheduled_missions WHERE id=%s",
                   (mission_id,))
    row = cursor.fetchone()
    if not row:
        cursor.close()
        conn.close()
        return False
    new_active = 0 if row["active"] else 1
    cursor.execute("UPDATE scheduled_missions SET active=%s WHERE id=%s", (new_active, mission_id))
    conn.commit()
    cursor.close()
    conn.close()

    if new_active:
        _add_job(mission_id, row["title"], row["objective"], row["cron_expr"])
    else:
        _remove_job(mission_id)

    return bool(new_active)


def delete_scheduled_mission(mission_id: int) -> None:
    _remove_job(mission_id)
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM scheduled_missions WHERE id=%s", (mission_id,))
    conn.commit()
    cursor.close()
    conn.close()


def list_scheduled_missions() -> list:
    _ensure_table()
    conn   = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, title, objective, cron_expr, label, active, last_run, next_run, created_at "
        "FROM scheduled_missions ORDER BY created_at DESC"
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    for r in rows:
        r["created_at"] = str(r["created_at"])
        r["last_run"]   = str(r["last_run"]) if r["last_run"] else None
        r["next_run"]   = str(r["next_run"]) if r["next_run"] else None
    return rows
