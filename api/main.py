"""
EnterpriseCore AI — API REST v1
Démarrer : uvicorn api.main:app --port 8000 --reload
Docs      : http://localhost:8000/docs
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import queue
import threading
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from api.auth import require_api_key, generate_api_key, save_key, get_all_keys, deactivate_key
from api.schemas import (
    MissionCreate, MissionOut, MissionDetail, MissionCreateOut,
    MissionStatusOut, TaskOut, ApiKeyCreate, ApiKeyOut, ApiKeyCreated, HealthOut
)
from database.db_config import get_connection
from core.planning.mission_orchestrator import MissionOrchestrator
from web.pdf_generator import generate_mission_pdf


# ── App ───────────────────────────────────────────────────────
app = FastAPI(
    title="EnterpriseCore AI",
    description=(
        "API REST du système d'IA juridique d'entreprise.\n\n"
        "**Authentification** : ajoutez votre clé dans le header `X-API-Key`.\n\n"
        "Générez une clé via `POST /v1/api-keys` (depuis l'interface web)."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5050", "http://127.0.0.1:5050"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Suivi des missions en cours
_runs: dict = {}
_runs_lock = threading.Lock()


# ─────────────────────────────────────────────────────────────
# Santé
# ─────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthOut, tags=["System"])
def health():
    """Vérifie l'état de la base de données et des services."""
    try:
        conn = get_connection()
        conn.cursor().execute("SELECT 1")
        conn.close()
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "database": db_status,
        "version": "1.0.0",
        "services": {
            "mission_planner": "ok",
            "legal_debate_engine": "ok",
            "analysis_memory": "ok",
        }
    }


# ─────────────────────────────────────────────────────────────
# Missions
# ─────────────────────────────────────────────────────────────

@app.get("/v1/missions", response_model=list[MissionOut], tags=["Missions"],
         summary="Lister les missions")
def list_missions(
    q:    Optional[str] = Query(None, description="Recherche dans titre et objectif"),
    risk: Optional[str] = Query(None, description="Filtrer par risque : HIGH | MEDIUM | LOW"),
    limit: int          = Query(50, ge=1, le=200),
    offset: int         = Query(0, ge=0),
    _key: str = Depends(require_api_key),
):
    conn   = get_connection()
    cursor = conn.cursor(dictionary=True)

    sql    = ("SELECT id, title, objective, status, tasks_count, completed_tasks, "
              "created_at, completed_at FROM missions WHERE 1=1")
    params = []

    if q:
        sql += " AND (title LIKE %s OR objective LIKE %s)"
        params += [f"%{q}%", f"%{q}%"]

    sql += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
    params += [limit, offset]

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    result = []
    for r in rows:
        r["created_at"]       = str(r["created_at"])
        r["completed_at"]     = str(r["completed_at"]) if r["completed_at"] else None
        r["final_risk_level"] = _get_risk(r["id"])
        if risk and r["final_risk_level"] != risk.upper():
            continue
        result.append(r)

    return result


@app.get("/v1/missions/{mission_id}", response_model=MissionDetail, tags=["Missions"],
         summary="Détail d'une mission")
def get_mission(mission_id: int, _key: str = Depends(require_api_key)):
    mission = _fetch_mission(mission_id)
    if not mission:
        raise HTTPException(404, "Mission introuvable")
    mission["tasks"] = _fetch_tasks(mission_id)
    return mission


@app.post("/v1/missions", response_model=MissionCreateOut, status_code=202, tags=["Missions"],
          summary="Lancer une nouvelle mission (asynchrone)")
def create_mission(body: MissionCreate, _key: str = Depends(require_api_key)):
    run_id  = f"api_{body.title[:16]}_{datetime.now().strftime('%H%M%S%f')}"
    event_q: queue.Queue = queue.Queue()

    with _runs_lock:
        _runs[run_id] = {"status": "running", "mission_id": None, "queue": event_q}

    def run():
        try:
            orch   = MissionOrchestrator()
            result = orch.run(title=body.title, objective=body.objective,
                              on_progress=lambda e: event_q.put(e))
            event_q.put({"type": "mission_done", "mission_id": result["mission_id"]})
            with _runs_lock:
                _runs[run_id]["status"]     = "done"
                _runs[run_id]["mission_id"] = result["mission_id"]
        except Exception as e:
            event_q.put({"type": "mission_error", "error": str(e)})
            with _runs_lock:
                _runs[run_id]["status"] = "error"

    threading.Thread(target=run, daemon=True).start()

    return {
        "run_id":  run_id,
        "status":  "running",
        "message": f"Mission démarrée. Utilisez GET /v1/missions/run/{run_id}/status pour suivre la progression.",
    }


@app.get("/v1/missions/run/{run_id}/status", response_model=MissionStatusOut, tags=["Missions"],
         summary="Statut d'une mission en cours")
def mission_run_status(run_id: str, _key: str = Depends(require_api_key)):
    with _runs_lock:
        state = _runs.get(run_id)
    if not state:
        raise HTTPException(404, f"run_id '{run_id}' introuvable")
    return {"run_id": run_id, "status": state["status"], "mission_id": state.get("mission_id")}


@app.get("/v1/missions/{mission_id}/pdf", tags=["Missions"],
         summary="Télécharger le rapport PDF")
def mission_pdf(mission_id: int, _key: str = Depends(require_api_key)):
    mission = _fetch_mission(mission_id)
    if not mission:
        raise HTTPException(404, "Mission introuvable")

    tasks     = _fetch_tasks(mission_id)
    pdf_bytes = generate_mission_pdf(mission, tasks)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="rapport_mission_{mission_id}.pdf"'},
    )


# ─────────────────────────────────────────────────────────────
# Clés API
# ─────────────────────────────────────────────────────────────

@app.get("/v1/api-keys", response_model=list[ApiKeyOut], tags=["API Keys"],
         summary="Lister les clés API actives")
def list_api_keys(_key: str = Depends(require_api_key)):
    return get_all_keys()


@app.post("/v1/api-keys", response_model=ApiKeyCreated, status_code=201, tags=["API Keys"],
          summary="Créer une nouvelle clé API")
def create_api_key(body: ApiKeyCreate, _key: str = Depends(require_api_key)):
    full, prefix, hashed = generate_api_key()
    key_id = save_key(body.name, prefix, hashed)
    return {"id": key_id, "name": body.name, "key": full, "key_prefix": prefix}


@app.delete("/v1/api-keys/{key_id}", status_code=204, tags=["API Keys"],
            summary="Révoquer une clé API")
def revoke_api_key(key_id: int, _key: str = Depends(require_api_key)):
    if not deactivate_key(key_id):
        raise HTTPException(404, "Clé introuvable")


# ─────────────────────────────────────────────────────────────
# Helpers DB
# ─────────────────────────────────────────────────────────────

def _fetch_mission(mission_id: int) -> dict | None:
    conn   = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, title, objective, status, tasks_count, completed_tasks, "
        "final_report, created_at, completed_at FROM missions WHERE id=%s",
        (mission_id,)
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row:
        return None

    row["created_at"]       = str(row["created_at"])
    row["completed_at"]     = str(row["completed_at"]) if row["completed_at"] else None
    row["final_risk_level"] = _get_risk(mission_id)

    if row.get("final_report"):
        try:
            row["final_report"] = json.loads(row["final_report"])
        except Exception:
            pass

    return row


def _fetch_tasks(mission_id: int) -> list:
    conn   = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, task_order, task_title, task_description, agent_type, "
        "status, result, risk_level, confidence, created_at, completed_at "
        "FROM mission_tasks WHERE mission_id=%s ORDER BY task_order",
        (mission_id,)
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    for r in rows:
        r["created_at"]   = str(r["created_at"])
        r["completed_at"] = str(r["completed_at"]) if r["completed_at"] else None
        if r.get("result"):
            try:
                r["result"] = json.loads(r["result"])
            except Exception:
                pass
    return rows


def _get_risk(mission_id: int) -> str:
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT risk_level FROM mission_tasks WHERE mission_id=%s AND status='done'",
        (mission_id,)
    )
    levels = [r[0] for r in cursor.fetchall() if r[0]]
    cursor.close()
    conn.close()
    p = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    return max(levels, key=lambda l: p.get(l, 0)) if levels else "UNKNOWN"
