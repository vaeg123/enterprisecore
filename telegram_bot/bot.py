"""
EnterpriseCore — Bot Telegram
==============================
Commandes disponibles :

  /start                              Bienvenue
  /aide                               Aide complète
  /services                           Lister tous les services et agents

  /mission Titre | Objectif           Lancer une analyse juridique complète (multi-agents)
  /juridique <agent> <question>       Interroger un agent juridique directement
  /commercial <agent> <question>      Interroger un agent du service Commercial
  /financier  <agent> <question>      Interroger un agent du service Financier
  /projets    <agent> <question>      Interroger un agent du service Projets
  /rd         <agent> <question>      Interroger un agent du service R&D

Agents juridiques : douala · yaounde · parme · yabassi
"""

import os
import sys
import json
import asyncio
import logging
import threading
from pathlib import Path

# ── Ajouter la racine du projet au path ──────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode

from database.db_config import get_connection
from core.planning.mission_orchestrator import MissionOrchestrator
from core.agents.specialized_legal_agent import SpecializedLegalAgent, AGENT_PERSONAS
from core.agents.service_agent import ServiceAgent
from core.agents.services_config import SERVICES, list_services
from web.flask_auth import check_password, get_user

logging.basicConfig(
    format="%(asctime)s [BOT] %(levelname)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")

# ── Slugs pour les agents juridiques ─────────────────────────────────────────
LEGAL_SLUGS = {
    "douala":  "jurist",
    "yaounde": "lawyer",
    "parme":   "compliance",
    "yabassi": "risk",
}

# ── Slugs URL → clé interne pour les services métier ─────────────────────────
SERVICE_ALIASES = {
    "rd":        "rd",
    "r&d":       "rd",
    "projets":   "projets",
    "financier": "financier",
    "commercial": "commercial",
}

# ── Icônes par niveau de risque ───────────────────────────────────────────────
RISK_ICONS = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}

MAX_MSG = 4000   # limite Telegram : 4096 — marge de sécurité

# ── Application globale (pour notify_user) ────────────────────
_bot_app = None


# ─────────────────────────────────────────────────────────────
# ÉVOLUTION 2 — Notifications Telegram pro-actives
# ─────────────────────────────────────────────────────────────

def _get_user_chat_id(user_id: int):
    """Retourne le telegram_chat_id de l'utilisateur s'il est lié."""
    try:
        conn   = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT telegram_chat_id FROM users WHERE id=%s", (user_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return row["telegram_chat_id"] if row else None
    except Exception:
        return None


def notify_user(user_id: int, message: str) -> None:
    """Envoie un message Telegram à l'utilisateur si son compte est lié."""
    chat_id = _get_user_chat_id(user_id)
    if not chat_id or not _bot_app:
        return
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_bot_app.bot.send_message(chat_id=chat_id, text=message))
        loop.close()
    except Exception as e:
        log.warning(f"notify_user({user_id}): {e}")


# ─────────────────────────────────────────────────────────────
# ÉVOLUTION 5 — Sauvegarde des requêtes Telegram
# ─────────────────────────────────────────────────────────────

def save_telegram_query(chat_id: int, agent_type: str, agent_slug: str,
                        question: str, result_json: dict,
                        risk_level: str, confidence: float) -> None:
    """Sauvegarde une requête Telegram dans agent_queries ou service_queries."""
    import json
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        if agent_type == "juridique":
            cursor.execute(
                "INSERT INTO agent_queries "
                "(agent_role, question, result, risk_level, confidence, source, telegram_chat_id) "
                "VALUES (%s, %s, %s, %s, %s, 'telegram', %s)",
                (agent_slug, question, json.dumps(result_json, ensure_ascii=False),
                 risk_level, confidence, chat_id)
            )
        else:
            cursor.execute(
                "INSERT INTO service_queries "
                "(service, agent_slug, question, result, priority_level, confidence, source, telegram_chat_id) "
                "VALUES (%s, %s, %s, %s, %s, %s, 'telegram', %s)",
                (agent_type, agent_slug, question,
                 json.dumps(result_json, ensure_ascii=False),
                 risk_level, confidence, chat_id)
            )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        log.warning(f"save_telegram_query: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Utilitaires
# ─────────────────────────────────────────────────────────────────────────────

def _escape(text: str) -> str:
    """Échappe les caractères MarkdownV2 sensibles."""
    for ch in r"\_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text


def _split_long(text: str, limit: int = MAX_MSG) -> list[str]:
    """Découpe un texte en morceaux ≤ limit caractères sur des sauts de ligne."""
    if len(text) <= limit:
        return [text]
    parts = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut == -1:
            cut = limit
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")
    if text:
        parts.append(text)
    return parts


async def _send(update: Update, text: str) -> None:
    """Envoie un message, découpé si trop long."""
    for chunk in _split_long(text):
        await update.effective_message.reply_text(chunk)


def _format_mission_report(report: dict) -> str:
    """Met en forme le rapport de mission pour Telegram."""
    risk = report.get("final_risk_level", "UNKNOWN")
    icon = RISK_ICONS.get(risk, "⚪")
    conf = int(report.get("average_confidence", 0) * 100)
    done = report.get("tasks_completed", 0)
    total = report.get("tasks_total", 0)

    lines = [
        f"✅ Mission terminée — {report.get('mission_title', '')}",
        "",
        f"{icon} Risque global : {risk}",
        f"📊 Confiance : {conf}%",
        f"📋 Tâches : {done}/{total} complétées",
        "",
    ]

    summary = report.get("executive_summary")
    if summary:
        lines += ["📝 Synthèse :", summary, ""]

    actions = report.get("key_actions", [])
    if actions:
        lines.append("🎯 Actions prioritaires :")
        for i, a in enumerate(actions[:5], 1):
            lines.append(f"  {i}. {a}")
        lines.append("")

    mid = report.get("mission_id")
    if mid:
        lines.append(f"🔗 Rapport complet : http://localhost:5050/missions/{mid}")

    return "\n".join(lines)


def _format_agent_response(agent_name: str, raw) -> str:
    """Met en forme la réponse JSON d'un agent."""
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return f"🤖 {agent_name}\n\n{raw}"
    else:
        data = raw

    risk = data.get("priority_level", "N/A")
    icon = RISK_ICONS.get(risk, "⚪")
    conf = int(float(data.get("confidence", 0)) * 100)

    lines = [
        f"🤖 {agent_name}",
        f"{icon} Niveau : {risk}  |  📊 Confiance : {conf}%",
        "",
        "📋 Analyse :",
        data.get("analysis", "—"),
        "",
    ]

    points = data.get("key_points", [])
    if points:
        lines.append("🔑 Points clés :")
        for p in points:
            lines.append(f"  • {p}")
        lines.append("")

    reco = data.get("recommendation")
    if reco:
        lines += ["💡 Recommandation :", reco, ""]

    note = data.get("expert_note")
    if note:
        lines += [f"🔍 Note experte : {note}"]

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Commandes
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "🏛️ Bienvenue sur EnterpriseCore AI\n\n"
        "Je suis votre assistant juridique et métier multi-agents.\n\n"
        "Tapez /aide pour voir toutes les commandes disponibles."
    )
    await _send(update, text)


async def cmd_aide(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "📖 Aide EnterpriseCore\n\n"
        "═══ MISSION COMPLÈTE ═══\n"
        "/mission Titre | Objectif détaillé\n"
        "→ Lance une analyse multi-agents (Douala, Yaoundé, Parme, Yabassi)\n"
        "→ Durée : 1 à 3 minutes\n\n"
        "═══ AGENTS JURIDIQUES ═══\n"
        "/juridique douala   <question>   — Juriste (cadre légal)\n"
        "/juridique yaounde  <question>   — Avocat (jurisprudence)\n"
        "/juridique parme    <question>   — DPO (RGPD)\n"
        "/juridique yabassi  <question>   — Risk Manager\n\n"
        "═══ SERVICES MÉTIER ═══\n"
        "/commercial bafoussam|kribi|limbe|maroua  <question>\n"
        "/financier  ngaoundere|bertoua|ebolowa|garoua  <question>\n"
        "/projets    bamenda|buea|edea|kumba  <question>\n"
        "/rd         nkongsamba|dschang|mbouda|foumban  <question>\n\n"
        "═══ DIVERS ═══\n"
        "/services  — Liste tous les agents disponibles\n"
        "/aide      — Ce message\n\n"
        "💡 Exemple :\n"
        "/mission Conformité RGPD | Notre site collecte des emails sans consentement explicite. Analyser les risques et les actions à mener."
    )
    await _send(update, text)


async def cmd_services(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    lines = ["🗂️ Services et agents disponibles\n"]

    # Service Juridique
    lines.append("⚖️ Service Juridique")
    for slug, role in LEGAL_SLUGS.items():
        name = AGENT_PERSONAS[role]["name"]
        lines.append(f"  /juridique {slug} <question>  — {name}")
    lines.append("")

    # Services métier
    icons = {"commercial": "◉", "financier": "💰", "projets": "📋", "rd": "🔬"}
    for svc_key, svc in SERVICES.items():
        icon = icons.get(svc_key, "▸")
        cmd = svc_key
        lines.append(f"{icon} {svc['name']}")
        for agent_slug, agent_cfg in svc["agents"].items():
            lines.append(f"  /{cmd} {agent_slug} <question>  — {agent_cfg['name']}")
        lines.append("")

    await _send(update, "\n".join(lines))


async def cmd_mission(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Lance une mission juridique complète (asynchrone, avec progression)."""
    raw = " ".join(ctx.args) if ctx.args else ""
    if "|" not in raw:
        await _send(update,
            "❌ Format incorrect.\n\n"
            "Usage : /mission Titre | Objectif détaillé\n\n"
            "Exemple :\n"
            "/mission Clause non-concurrence | Notre contrat avec un commercial senior "
            "contient une clause de non-concurrence de 3 ans sur tout le territoire européen. "
            "Est-elle valide en droit français ?"
        )
        return

    sep = raw.index("|")
    title = raw[:sep].strip()
    objective = raw[sep + 1:].strip()

    if not title or not objective:
        await _send(update, "❌ Le titre et l'objectif ne peuvent pas être vides.")
        return

    msg = await update.effective_message.reply_text(
        f"🚀 Mission lancée : {title}\n\n⏳ Analyse en cours (1-3 min)…"
    )

    loop = asyncio.get_event_loop()

    def _run_mission():
        orchestrator = MissionOrchestrator()
        steps_done = []

        def on_progress(event):
            if event.get("type") == "task_start":
                agent = event.get("agent_type", "")
                label = event.get("title", agent)
                steps_done.append(f"  ⏳ {label}")
                progress_text = (
                    f"🔄 Mission : {title}\n\n"
                    + "\n".join(steps_done)
                )
                asyncio.run_coroutine_threadsafe(
                    msg.edit_text(progress_text[:MAX_MSG]),
                    loop,
                )
            elif event.get("type") == "task_done":
                if steps_done:
                    steps_done[-1] = steps_done[-1].replace("⏳", "✅")

        return orchestrator.run(title, objective, on_progress=on_progress)

    try:
        report = await loop.run_in_executor(None, _run_mission)
        result_text = _format_mission_report(report)
        await msg.edit_text(result_text[:MAX_MSG])
        # Si le rapport est long, envoyer la suite
        for chunk in _split_long(result_text)[1:]:
            await _send(update, chunk)
    except Exception as e:
        log.exception("Erreur mission Telegram")
        await msg.edit_text(f"❌ Erreur lors de l'analyse :\n{e}")


async def cmd_juridique(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Interroge un agent juridique directement."""
    if not ctx.args or len(ctx.args) < 2:
        await _send(update,
            "❌ Usage : /juridique <agent> <question>\n\n"
            "Agents : douala · yaounde · parme · yabassi\n\n"
            "Exemple :\n/juridique parme Sommes-nous obligés de réaliser une AIPD pour notre CRM ?"
        )
        return

    slug = ctx.args[0].lower()
    question = " ".join(ctx.args[1:])

    role = LEGAL_SLUGS.get(slug)
    if not role:
        await _send(update,
            f"❌ Agent inconnu : {slug}\n"
            "Agents disponibles : douala · yaounde · parme · yabassi"
        )
        return

    agent_name = AGENT_PERSONAS[role]["name"]
    wait_msg = await update.effective_message.reply_text(
        f"🔄 {agent_name} analyse votre question…"
    )

    chat_id = update.effective_chat.id
    loop = asyncio.get_event_loop()
    try:
        agent = SpecializedLegalAgent(role)
        raw = await loop.run_in_executor(None, agent.analyze, question)

        # ÉVOLUTION 5 — Sauvegarder dans agent_queries
        try:
            import json as _json
            content = raw.content.strip() if hasattr(raw, "content") else str(raw)
            if content.startswith("```"):
                content = content.split("```", 2)[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.rsplit("```", 1)[0].strip()
            parsed_result = _json.loads(content)
            save_telegram_query(
                chat_id=chat_id,
                agent_type="juridique",
                agent_slug=role,
                question=question,
                result_json=parsed_result,
                risk_level=parsed_result.get("risk_level", "UNKNOWN"),
                confidence=float(parsed_result.get("confidence", 0)),
            )
        except Exception:
            pass

        result = _format_agent_response(agent_name, raw)
        await wait_msg.edit_text(result[:MAX_MSG])
        for chunk in _split_long(result)[1:]:
            await _send(update, chunk)
    except Exception as e:
        log.exception("Erreur agent juridique")
        await wait_msg.edit_text(f"❌ Erreur : {e}")


async def _cmd_service(
    update: Update,
    ctx: ContextTypes.DEFAULT_TYPE,
    service_key: str,
) -> None:
    """Interroge un agent d'un service métier."""
    svc = SERVICES.get(service_key)
    if not svc:
        await _send(update, f"❌ Service inconnu : {service_key}")
        return

    agent_list = "  ".join(svc["agents"].keys())

    if not ctx.args or len(ctx.args) < 2:
        await _send(update,
            f"❌ Usage : /{service_key} <agent> <question>\n\n"
            f"Agents : {agent_list}\n\n"
            f"Exemple :\n/{service_key} {list(svc['agents'].keys())[0]} "
            "Comment améliorer notre taux de conversion ?"
        )
        return

    agent_slug = ctx.args[0].lower()
    question = " ".join(ctx.args[1:])

    if agent_slug not in svc["agents"]:
        await _send(update,
            f"❌ Agent inconnu : {agent_slug}\n"
            f"Agents disponibles : {agent_list}"
        )
        return

    agent_cfg = svc["agents"][agent_slug]
    agent_name = agent_cfg["name"]

    wait_msg = await update.effective_message.reply_text(
        f"🔄 {agent_name} analyse votre question…"
    )

    chat_id = update.effective_chat.id
    loop = asyncio.get_event_loop()
    try:
        agent = ServiceAgent(service_key, agent_slug)
        raw = await loop.run_in_executor(None, agent.analyze, question)

        # ÉVOLUTION 5 — Sauvegarder dans service_queries
        try:
            import json as _json
            content = raw.content.strip() if hasattr(raw, "content") else str(raw)
            if content.startswith("```"):
                content = content.split("```", 2)[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.rsplit("```", 1)[0].strip()
            parsed_result = _json.loads(content)
            save_telegram_query(
                chat_id=chat_id,
                agent_type=service_key,
                agent_slug=agent_slug,
                question=question,
                result_json=parsed_result,
                risk_level=parsed_result.get("priority_level", "UNKNOWN"),
                confidence=float(parsed_result.get("confidence", 0)),
            )
        except Exception:
            pass

        result = _format_agent_response(agent_name, raw)
        await wait_msg.edit_text(result[:MAX_MSG])
        for chunk in _split_long(result)[1:]:
            await _send(update, chunk)
    except Exception as e:
        log.exception("Erreur agent service")
        await wait_msg.edit_text(f"❌ Erreur : {e}")


# Handlers génériques pour chaque service métier
async def cmd_commercial(u, c): await _cmd_service(u, c, "commercial")
async def cmd_financier(u, c):  await _cmd_service(u, c, "financier")
async def cmd_projets(u, c):    await _cmd_service(u, c, "projets")
async def cmd_rd(u, c):         await _cmd_service(u, c, "rd")


async def cmd_connect(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """ÉVOLUTION 2 — Lie le compte Telegram à un compte EnterpriseCore."""
    if not ctx.args or len(ctx.args) < 2:
        await _send(update,
            "❌ Usage : /connect <username> <password>\n\n"
            "Exemple :\n/connect marie.dupont monMotDePasse123"
        )
        return

    username = ctx.args[0].strip()
    password = " ".join(ctx.args[1:]).strip()
    chat_id  = update.effective_chat.id

    user = get_user(username)
    if not user or not check_password(password, user["password_hash"]):
        await _send(update, "❌ Identifiants incorrects. Vérifiez votre nom d'utilisateur et mot de passe.")
        return

    if user.get("is_active") == 0:
        await _send(update, "❌ Ce compte est désactivé.")
        return

    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET telegram_chat_id=%s WHERE id=%s", (chat_id, user["id"]))
        conn.commit()
        cursor.close()
        conn.close()
        await _send(update,
            f"✅ Compte lié avec succès !\n\n"
            f"Bonjour {user['username']}, votre compte EnterpriseCore est maintenant connecté.\n"
            f"Vous recevrez des notifications pro-actives ici."
        )
    except Exception as e:
        log.exception("Erreur cmd_connect")
        await _send(update, f"❌ Erreur : {e}")


async def cmd_deconnect(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """ÉVOLUTION 2 — Délie le compte Telegram du compte EnterpriseCore."""
    chat_id = update.effective_chat.id
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET telegram_chat_id=NULL WHERE telegram_chat_id=%s", (chat_id,))
        affected = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        if affected > 0:
            await _send(update, "✅ Compte déconnecté. Vous ne recevrez plus de notifications.")
        else:
            await _send(update, "ℹ️ Aucun compte lié à ce chat.")
    except Exception as e:
        log.exception("Erreur cmd_deconnect")
        await _send(update, f"❌ Erreur : {e}")


async def cmd_unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await _send(update, "❓ Commande inconnue. Tapez /aide pour voir les commandes disponibles.")


# ─────────────────────────────────────────────────────────────────────────────
# Lancement
# ─────────────────────────────────────────────────────────────────────────────

def run_bot() -> None:
    global _bot_app
    if not TOKEN:
        log.error("TELEGRAM_TOKEN absent du .env — bot non démarré.")
        return

    app = (
        Application.builder()
        .token(TOKEN)
        .build()
    )
    _bot_app = app

    app.add_handler(CommandHandler("start",       cmd_start))
    app.add_handler(CommandHandler("aide",        cmd_aide))
    app.add_handler(CommandHandler("help",        cmd_aide))
    app.add_handler(CommandHandler("services",    cmd_services))
    app.add_handler(CommandHandler("mission",     cmd_mission))
    app.add_handler(CommandHandler("juridique",   cmd_juridique))
    app.add_handler(CommandHandler("commercial",  cmd_commercial))
    app.add_handler(CommandHandler("financier",   cmd_financier))
    app.add_handler(CommandHandler("projets",     cmd_projets))
    app.add_handler(CommandHandler("rd",          cmd_rd))
    app.add_handler(CommandHandler("connect",     cmd_connect))
    app.add_handler(CommandHandler("deconnect",   cmd_deconnect))
    app.add_handler(MessageHandler(filters.COMMAND, cmd_unknown))

    log.info("Bot Telegram démarré (polling)…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    run_bot()
