import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import queue
import threading
import secrets
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, Response, stream_with_context, session
from database.db_config import get_connection
from core.planning.mission_orchestrator import MissionOrchestrator
from web.pdf_generator import generate_mission_pdf
from web.flask_auth import login_required, check_password, get_user
from api.auth import generate_api_key, save_key, get_all_keys, deactivate_key

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(32))

# ── État des missions en cours ────────────────────────────────
_missions_state: dict = {}   # run_id → {"status", "mission_id", "queue"}
_state_lock = threading.Lock()


# ─────────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("index"))

    error    = None
    username = ""
    next_url = request.args.get("next") or request.form.get("next") or "/"

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user     = get_user(username)

        if user and check_password(password, user["password_hash"]):
            session["user_id"]   = user["id"]
            session["username"]  = user["username"]
            return redirect(next_url)
        else:
            error = "Identifiant ou mot de passe incorrect."

    return render_template("login.html", error=error, username=username, next=next_url)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ─────────────────────────────────────────────────────────────
# Pages HTML
# ─────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def index():
    q = (request.args.get("q") or "").strip()
    risk_filter = (request.args.get("risk") or "").strip().upper()
    missions = _search_missions(q, risk_filter)
    return render_template("index.html", missions=missions, q=q, risk_filter=risk_filter)


@app.route("/mission/<int:mission_id>")
@login_required
def mission_detail(mission_id):
    mission = _get_mission(mission_id)
    if not mission:
        return redirect(url_for("index"))
    tasks = _get_tasks(mission_id)
    return render_template("mission_detail.html", mission=mission, tasks=tasks)


@app.route("/settings")
@login_required
def settings():
    keys = get_all_keys()
    return render_template("settings.html", keys=keys)


@app.route("/api/keys/create", methods=["POST"])
@login_required
def api_create_key():
    data = request.get_json()
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "nom requis"}), 400
    full, prefix, hashed = generate_api_key()
    key_id = save_key(name, prefix, hashed)
    return jsonify({"id": key_id, "key": full, "prefix": prefix, "name": name})


@app.route("/api/keys/<int:key_id>/revoke", methods=["POST"])
@login_required
def api_revoke_key(key_id):
    deactivate_key(key_id)
    return jsonify({"ok": True})


# ─────────────────────────────────────────────────────────────
# API — Missions
# ─────────────────────────────────────────────────────────────

@app.route("/api/missions", methods=["GET"])
@login_required
def api_missions():
    q    = (request.args.get("q") or "").strip()
    risk = (request.args.get("risk") or "").strip().upper()
    return jsonify(_search_missions(q, risk))


@app.route("/api/mission/<int:mission_id>", methods=["GET"])
@login_required
def api_mission(mission_id):
    return jsonify({"mission": _get_mission(mission_id), "tasks": _get_tasks(mission_id)})


@app.route("/api/mission/create", methods=["POST"])
@login_required
def api_create_mission():
    data      = request.get_json()
    title     = (data.get("title") or "").strip()
    objective = (data.get("objective") or "").strip()

    if not title or not objective:
        return jsonify({"error": "title et objective requis"}), 400

    run_id = f"{title[:20]}_{datetime.now().strftime('%H%M%S')}"
    event_q: queue.Queue = queue.Queue()

    with _state_lock:
        _missions_state[run_id] = {"status": "running", "mission_id": None, "queue": event_q}

    def run():
        def on_progress(event: dict):
            event_q.put(event)

        try:
            orchestrator = MissionOrchestrator()
            result = orchestrator.run(title=title, objective=objective, on_progress=on_progress)
            event_q.put({"type": "mission_done", "mission_id": result["mission_id"]})
            with _state_lock:
                _missions_state[run_id]["status"]     = "done"
                _missions_state[run_id]["mission_id"] = result["mission_id"]
        except Exception as e:
            event_q.put({"type": "mission_error", "error": str(e)})
            with _state_lock:
                _missions_state[run_id]["status"] = "error"

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"run_id": run_id, "status": "running"})


@app.route("/api/mission/status/<run_id>", methods=["GET"])
@login_required
def api_mission_status(run_id):
    with _state_lock:
        info = _missions_state.get(run_id, {"status": "unknown"})
        return jsonify({"status": info["status"], "mission_id": info.get("mission_id")})


# ─────────────────────────────────────────────────────────────
# SSE — Progression live
# ─────────────────────────────────────────────────────────────

@app.route("/api/mission/events/<run_id>")
@login_required
def mission_events(run_id):
    """Server-Sent Events : envoie la progression tâche par tâche."""
    with _state_lock:
        state = _missions_state.get(run_id)

    if not state:
        return Response("data: {\"type\":\"error\"}\n\n", mimetype="text/event-stream")

    event_q: queue.Queue = state["queue"]

    @stream_with_context
    def generate():
        yield "data: {\"type\":\"connected\"}\n\n"
        while True:
            try:
                event = event_q.get(timeout=120)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event.get("type") in ("mission_done", "mission_error"):
                    break
            except queue.Empty:
                yield "data: {\"type\":\"heartbeat\"}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


# ─────────────────────────────────────────────────────────────
# PDF
# ─────────────────────────────────────────────────────────────

@app.route("/api/mission/<int:mission_id>/pdf")
@login_required
def mission_pdf(mission_id):
    mission = _get_mission(mission_id)
    if not mission:
        return jsonify({"error": "Mission introuvable"}), 404

    tasks = _get_tasks(mission_id)
    pdf_bytes = generate_mission_pdf(mission, tasks)

    filename = f"rapport_mission_{mission_id}.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ─────────────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────────────

def _search_missions(q: str = "", risk: str = "") -> list:
    conn   = get_connection()
    cursor = conn.cursor(dictionary=True)

    sql    = ("SELECT id, title, objective, status, tasks_count, completed_tasks, "
              "created_at, completed_at FROM missions WHERE 1=1")
    params = []

    if q:
        sql += " AND (title LIKE %s OR objective LIKE %s)"
        params += [f"%{q}%", f"%{q}%"]

    sql += " ORDER BY created_at DESC"
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    result = []
    for r in rows:
        r["created_at"]  = str(r["created_at"])
        r["completed_at"] = str(r["completed_at"]) if r["completed_at"] else None
        r["final_risk_level"] = _get_mission_risk(r["id"])
        if risk and r["final_risk_level"] != risk:
            continue
        result.append(r)

    return result


def _get_mission(mission_id: int) -> dict | None:
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

    row["created_at"]   = str(row["created_at"])
    row["completed_at"] = str(row["completed_at"]) if row["completed_at"] else None

    if row.get("final_report"):
        try:
            row["final_report"] = json.loads(row["final_report"])
        except Exception:
            pass

    row["final_risk_level"] = _get_mission_risk(mission_id)
    return row


def _get_tasks(mission_id: int) -> list:
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


def _get_mission_risk(mission_id: int) -> str:
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT risk_level FROM mission_tasks WHERE mission_id=%s AND status='done'",
        (mission_id,)
    )
    levels = [row[0] for row in cursor.fetchall() if row[0]]
    cursor.close()
    conn.close()
    priority = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    if not levels:
        return "UNKNOWN"
    return max(levels, key=lambda l: priority.get(l, 0))


if __name__ == "__main__":
    port  = int(os.getenv("PORT", 5050))
    debug = os.getenv("FLASK_ENV") != "production"
    app.run(debug=debug, port=port, host="0.0.0.0", use_reloader=False)
