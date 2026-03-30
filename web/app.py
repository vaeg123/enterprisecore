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
from core.agents.specialized_legal_agent import SpecializedLegalAgent, AGENT_PERSONAS
from core.agents.service_agent import ServiceAgent
from core.agents.services_config import SERVICES, list_services
from web.pdf_generator import generate_mission_pdf
from web.flask_auth import (
    login_required, admin_required, service_required,
    check_password, get_user, get_user_by_id, get_all_users,
    create_user, update_user, toggle_user_active, delete_user,
    has_service_access, ALL_SERVICES, ROLES, SERVICE_LABELS,
)
from api.auth import generate_api_key, save_key, get_all_keys, deactivate_key

# Mapping slug URL → clé de rôle interne
AGENT_SLUGS = {
    "douala":   "jurist",
    "yaounde":  "lawyer",
    "parme":    "compliance",
    "yabassi":  "risk",
}

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(32))

# ── État des missions en cours ────────────────────────────────
_missions_state: dict = {}   # run_id → {"status", "mission_id", "queue"}
_state_lock = threading.Lock()


# ── Rafraîchissement automatique de la session ────────────────
@app.before_request
def refresh_session():
    """
    Recharge role/permissions depuis la DB si la session est stale
    (connexion antérieure aux changements RBAC, ou restart app).
    """
    uid = session.get("user_id")
    if not uid:
        return
    if session.get("role") is None:
        user = get_user_by_id(uid)
        if not user or user.get("is_active") == 0:
            session.clear()
            return
        session["role"]        = user.get("role") or "user"
        session["permissions"] = user.get("permissions") or []
        session["username"]    = user.get("username", session.get("username", ""))


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
            if user.get("is_active") == 0:
                error = "Ce compte est désactivé. Contactez l'administrateur."
            else:
                session["user_id"]     = user["id"]
                session["username"]    = user["username"]
                session["role"]        = user.get("role") or "user"
                session["permissions"] = user.get("permissions") or []
                return redirect(next_url)
        else:
            error = "Identifiant ou mot de passe incorrect."

    return render_template("login.html", error=error, username=username, next=next_url)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ─────────────────────────────────────────────────────────────
# Admin — Gestion des utilisateurs
# ─────────────────────────────────────────────────────────────

@app.route("/admin")
@admin_required
def admin():
    users = get_all_users()
    return render_template("admin.html", users=users,
                           roles=ROLES, all_services=ALL_SERVICES,
                           service_labels=SERVICE_LABELS)


@app.route("/api/admin/users/create", methods=["POST"])
@admin_required
def api_admin_create_user():
    data     = request.get_json()
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    role     = (data.get("role") or "user").strip()
    perms    = data.get("permissions") or []

    if not username or not password:
        return jsonify({"error": "username et password requis"}), 400
    if role not in ROLES:
        return jsonify({"error": "rôle invalide"}), 400
    if get_user(username):
        return jsonify({"error": "Ce nom d'utilisateur existe déjà"}), 409
    try:
        uid = create_user(username, password, role, perms)
        return jsonify({"ok": True, "id": uid})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/users/<int:user_id>/update", methods=["POST"])
@admin_required
def api_admin_update_user(user_id):
    data  = request.get_json()
    role  = data.get("role")
    perms = data.get("permissions")
    pwd   = (data.get("password") or "").strip() or None

    if role and role not in ROLES:
        return jsonify({"error": "rôle invalide"}), 400
    try:
        update_user(user_id, role=role, permissions=perms, password=pwd)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/users/<int:user_id>/toggle", methods=["POST"])
@admin_required
def api_admin_toggle_user(user_id):
    if user_id == session.get("user_id"):
        return jsonify({"error": "Vous ne pouvez pas désactiver votre propre compte"}), 400
    toggle_user_active(user_id)
    user = get_user_by_id(user_id)
    return jsonify({"ok": True, "is_active": user["is_active"]})


@app.route("/api/admin/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def api_admin_delete_user(user_id):
    if user_id == session.get("user_id"):
        return jsonify({"error": "Vous ne pouvez pas supprimer votre propre compte"}), 400
    delete_user(user_id)
    return jsonify({"ok": True})


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


# ─────────────────────────────────────────────────────────────
# Services métier génériques (Commercial, Financier, Projets, R&D)
# ─────────────────────────────────────────────────────────────

@app.route("/services/<service_key>")
@login_required
def service_hub(service_key):
    if not has_service_access(service_key):
        return render_template("403.html"), 403
    service = SERVICES.get(service_key)
    if not service:
        return redirect(url_for("index"))
    agents_info = []
    for slug, cfg in service["agents"].items():
        count = _count_service_queries(service_key, slug)
        agents_info.append({
            "slug":     slug,
            "name":     cfg["name"],
            "icon":     cfg["icon"],
            "subtitle": cfg["subtitle"],
            "count":    count,
        })
    return render_template("service_hub.html",
                           service=service, service_key=service_key, agents=agents_info)


@app.route("/services/<service_key>/<agent_slug>")
@login_required
def service_agent_espace(service_key, agent_slug):
    if not has_service_access(service_key):
        return render_template("403.html"), 403
    service = SERVICES.get(service_key)
    if not service or agent_slug == "reunion":
        return redirect(url_for("service_hub", service_key=service_key))
    agent_cfg = service["agents"].get(agent_slug)
    if not agent_cfg:
        return redirect(url_for("service_hub", service_key=service_key))
    analyses = _get_service_queries(service_key, agent_slug)
    return render_template("service_agent_espace.html",
                           service=service, service_key=service_key,
                           agent=agent_cfg, agent_slug=agent_slug,
                           analyses=analyses)


@app.route("/services/<service_key>/reunion")
@login_required
def service_reunion(service_key):
    if not has_service_access(service_key):
        return render_template("403.html"), 403
    service = SERVICES.get(service_key)
    if not service:
        return redirect(url_for("index"))
    agents_info = []
    for slug, cfg in service["agents"].items():
        recent = _get_service_queries(service_key, slug, limit=5)
        agents_info.append({
            "slug":   slug,
            "name":   cfg["name"],
            "icon":   cfg["icon"],
            "count":  _count_service_queries(service_key, slug),
            "recent": recent,
        })
    return render_template("service_salle_reunion.html",
                           service=service, service_key=service_key, agents=agents_info)


@app.route("/api/services/<service_key>/<agent_slug>/ask", methods=["POST"])
@login_required
def api_service_ask(service_key, agent_slug):
    service = SERVICES.get(service_key)
    if not service or not service["agents"].get(agent_slug):
        return jsonify({"error": "Agent inconnu"}), 404

    data     = request.get_json()
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "question requise"}), 400

    try:
        agent    = ServiceAgent(service_key, agent_slug)
        response = agent.analyze(question)

        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```", 2)[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.rsplit("```", 1)[0].strip()

        parsed         = json.loads(content)
        priority_level = parsed.get("priority_level")
        confidence     = float(parsed.get("confidence", 0))

        _save_service_query(service_key, agent_slug, question, parsed, priority_level, confidence)
        return jsonify({"ok": True, "result": parsed})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/service-juridique")
@service_required("juridique")
def service_juridique():
    agents_info = []
    for slug, role in AGENT_SLUGS.items():
        persona = AGENT_PERSONAS[role]
        count   = _count_agent_queries(role)
        agents_info.append({"slug": slug, "role": role, "name": persona["name"], "count": count})
    return render_template("service_juridique.html", agents=agents_info)


@app.route("/service-juridique/<agent_slug>")
@service_required("juridique")
def agent_espace(agent_slug):
    role = AGENT_SLUGS.get(agent_slug)
    if not role:
        return redirect(url_for("service_juridique"))
    persona  = AGENT_PERSONAS[role]
    analyses = _get_agent_queries(role)
    return render_template("agent_espace.html",
                           slug=agent_slug,
                           role=role,
                           agent_name=persona["name"],
                           analyses=analyses)


@app.route("/service-juridique/salle-de-reunion")
@service_required("juridique")
def salle_reunion():
    missions = _search_missions()
    return render_template("salle_reunion.html", missions=missions, agents=AGENT_SLUGS)


# ─────────────────────────────────────────────────────────────
# API — Interrogation directe d'un agent
# ─────────────────────────────────────────────────────────────

@app.route("/api/service-juridique/<agent_slug>/ask", methods=["POST"])
@login_required
def api_agent_ask(agent_slug):
    role = AGENT_SLUGS.get(agent_slug)
    if not role:
        return jsonify({"error": "Agent inconnu"}), 404

    data     = request.get_json()
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "question requise"}), 400

    try:
        agent    = SpecializedLegalAgent(role)
        response = agent.analyze(question)

        # Parsing JSON
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```", 2)[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.rsplit("```", 1)[0].strip()

        parsed     = json.loads(content)
        risk_level = parsed.get("risk_level")
        confidence = float(parsed.get("confidence", 0))

        _save_agent_query(role, question, parsed, risk_level, confidence)
        return jsonify({"ok": True, "result": parsed})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


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


def _save_service_query(service: str, agent_slug: str, question: str,
                        result: dict, priority_level: str, confidence: float):
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO service_queries (service, agent_slug, question, result, priority_level, confidence) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (service, agent_slug, question, json.dumps(result, ensure_ascii=False), priority_level, confidence)
    )
    conn.commit()
    cursor.close()
    conn.close()


def _get_service_queries(service: str, agent_slug: str, limit: int = 50) -> list:
    conn   = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, question, result, priority_level, confidence, created_at "
        "FROM service_queries WHERE service=%s AND agent_slug=%s "
        "ORDER BY created_at DESC LIMIT %s",
        (service, agent_slug, limit)
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    for r in rows:
        r["created_at"] = str(r["created_at"])
        if r.get("result"):
            try:
                r["result"] = json.loads(r["result"])
            except Exception:
                pass
    return rows


def _count_service_queries(service: str, agent_slug: str) -> int:
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM service_queries WHERE service=%s AND agent_slug=%s",
        (service, agent_slug)
    )
    count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return count


def _save_agent_query(role: str, question: str, result: dict, risk_level: str, confidence: float):
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO agent_queries (agent_role, question, result, risk_level, confidence) "
        "VALUES (%s, %s, %s, %s, %s)",
        (role, question, json.dumps(result, ensure_ascii=False), risk_level, confidence)
    )
    conn.commit()
    cursor.close()
    conn.close()


def _get_agent_queries(role: str) -> list:
    conn   = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, question, result, risk_level, confidence, created_at "
        "FROM agent_queries WHERE agent_role=%s ORDER BY created_at DESC LIMIT 50",
        (role,)
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    for r in rows:
        r["created_at"] = str(r["created_at"])
        if r.get("result"):
            try:
                r["result"] = json.loads(r["result"])
            except Exception:
                pass
    return rows


def _count_agent_queries(role: str) -> int:
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM agent_queries WHERE agent_role=%s", (role,))
    count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return count


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
