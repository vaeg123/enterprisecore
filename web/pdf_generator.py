"""
Génère un rapport PDF professionnel pour une mission EnterpriseCore.
"""
import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

# ── Palette ──────────────────────────────────────────────────
C_DARK    = colors.HexColor("#0f1117")
C_SURFACE = colors.HexColor("#1a1d27")
C_ACCENT  = colors.HexColor("#5b6af5")
C_HIGH    = colors.HexColor("#ef4444")
C_MEDIUM  = colors.HexColor("#f59e0b")
C_LOW     = colors.HexColor("#22c55e")
C_UNKNOWN = colors.HexColor("#64748b")
C_TEXT    = colors.HexColor("#1e293b")
C_MUTED   = colors.HexColor("#64748b")
C_BORDER  = colors.HexColor("#e2e8f0")

RISK_COLORS = {"HIGH": C_HIGH, "MEDIUM": C_MEDIUM, "LOW": C_LOW}


def _risk_color(level: str):
    return RISK_COLORS.get(level, C_UNKNOWN)


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=22,
                                 textColor=C_TEXT, spaceAfter=4),
        "subtitle": ParagraphStyle("subtitle", fontName="Helvetica", fontSize=10,
                                    textColor=C_MUTED, spaceAfter=12),
        "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=13,
                               textColor=C_TEXT, spaceBefore=14, spaceAfter=6),
        "h3": ParagraphStyle("h3", fontName="Helvetica-Bold", fontSize=10,
                               textColor=C_TEXT, spaceBefore=8, spaceAfter=4),
        "body": ParagraphStyle("body", fontName="Helvetica", fontSize=9,
                                textColor=C_TEXT, leading=14, spaceAfter=4),
        "muted": ParagraphStyle("muted", fontName="Helvetica", fontSize=8,
                                 textColor=C_MUTED, leading=12),
        "action": ParagraphStyle("action", fontName="Helvetica", fontSize=9,
                                  textColor=C_TEXT, leading=13, leftIndent=12,
                                  spaceAfter=3),
        "footer": ParagraphStyle("footer", fontName="Helvetica", fontSize=7,
                                  textColor=C_MUTED, alignment=TA_CENTER),
    }


def generate_mission_pdf(mission: dict, tasks: list) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=18*mm, bottomMargin=18*mm,
        title=mission.get("title", "Rapport"),
    )

    S = _styles()
    story = []
    report = mission.get("final_report") or {}
    risk   = mission.get("final_risk_level", "UNKNOWN")

    # ── En-tête ──────────────────────────────────────────────
    header_data = [[
        Paragraph("EnterpriseCore AI", ParagraphStyle(
            "brand", fontName="Helvetica-Bold", fontSize=10, textColor=C_ACCENT)),
        Paragraph(f"Généré le {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                  ParagraphStyle("date", fontName="Helvetica", fontSize=8,
                                  textColor=C_MUTED, alignment=TA_RIGHT)),
    ]]
    header_tbl = Table(header_data, colWidths=["60%", "40%"])
    header_tbl.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LINEBELOW", (0,0), (-1,-1), 0.5, C_BORDER),
    ]))
    story.append(header_tbl)
    story.append(Spacer(1, 8*mm))

    # ── Titre + badge risque ─────────────────────────────────
    story.append(Paragraph(mission.get("title", "Mission"), S["title"]))
    story.append(Paragraph(mission.get("objective", ""), S["subtitle"]))

    # Badge risque
    risk_col = _risk_color(risk)
    badge_data = [[
        Paragraph(f"  Risque : {risk}  ",
                  ParagraphStyle("badge", fontName="Helvetica-Bold", fontSize=9,
                                  textColor=colors.white)),
        Paragraph(
            f"Mission #{mission.get('id','—')}  ·  "
            f"{mission.get('tasks_count',0)} tâches  ·  "
            f"Démarrée {(mission.get('created_at') or '')[:16]}",
            ParagraphStyle("meta", fontName="Helvetica", fontSize=8,
                            textColor=C_MUTED, alignment=TA_RIGHT)
        ),
    ]]
    badge_tbl = Table(badge_data, colWidths=["30%", "70%"])
    badge_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (0,0), risk_col),
        ("ROUNDEDCORNERS", (0,0), (0,0), [3,3,3,3]),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (0,0), 4),
        ("BOTTOMPADDING", (0,0), (0,0), 4),
        ("LEFTPADDING", (0,0), (0,0), 8),
    ]))
    story.append(badge_tbl)
    story.append(Spacer(1, 6*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=C_BORDER))
    story.append(Spacer(1, 4*mm))

    # ── KPIs ─────────────────────────────────────────────────
    conf = report.get("average_confidence", 0)
    kpi_data = [
        [
            _kpi_cell(str(mission.get("tasks_count", "—")), "Tâches planifiées", C_ACCENT),
            _kpi_cell(str(mission.get("completed_tasks", "—")), "Tâches complétées", C_LOW),
            _kpi_cell(f"{int(conf*100)}%" if conf else "—", "Confiance moyenne", C_ACCENT),
            _kpi_cell(risk, "Risque final", risk_col),
        ]
    ]
    kpi_tbl = Table(kpi_data, colWidths=["25%"]*4)
    kpi_tbl.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 0.5, C_BORDER),
        ("INNERGRID", (0,0), (-1,-1), 0.5, C_BORDER),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("TOPPADDING", (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
    ]))
    story.append(kpi_tbl)
    story.append(Spacer(1, 6*mm))

    # ── Synthèse exécutive ───────────────────────────────────
    exec_summary = report.get("executive_summary", "")
    if not exec_summary and isinstance(mission.get("final_report"), dict):
        exec_summary = mission["final_report"].get("executive_summary", "")

    if exec_summary:
        story.append(Paragraph("Synthèse exécutive", S["h2"]))
        story.append(Paragraph(exec_summary, S["body"]))
        story.append(Spacer(1, 3*mm))

    key_actions = report.get("key_actions", [])
    if key_actions:
        story.append(Paragraph("Actions prioritaires", S["h3"]))
        for i, action in enumerate(key_actions, 1):
            story.append(Paragraph(f"{i}.  {action}", S["action"]))
        story.append(Spacer(1, 4*mm))

    # ── Tableau des tâches ───────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=C_BORDER))
    story.append(Paragraph("Détail des tâches", S["h2"]))

    tbl_header = [
        Paragraph("#", S["muted"]),
        Paragraph("Tâche", S["muted"]),
        Paragraph("Agent", S["muted"]),
        Paragraph("Risque", S["muted"]),
        Paragraph("Confiance", S["muted"]),
    ]
    tbl_rows = [tbl_header]

    for task in tasks:
        t_risk  = task.get("risk_level", "—") or "—"
        t_conf  = task.get("confidence", 0) or 0
        t_color = _risk_color(t_risk) if t_risk != "—" else C_MUTED

        tbl_rows.append([
            Paragraph(str(task.get("task_order", "")), S["muted"]),
            Paragraph(f"<b>{task.get('task_title','')}</b>", S["body"]),
            Paragraph(str(task.get("agent_type","")).upper(), S["muted"]),
            Paragraph(t_risk, ParagraphStyle("risk_cell", fontName="Helvetica-Bold",
                                              fontSize=8, textColor=t_color)),
            Paragraph(f"{int(t_conf*100)}%" if t_conf else "—", S["muted"]),
        ])

    tasks_tbl = Table(tbl_rows, colWidths=["6%", "48%", "14%", "16%", "16%"])
    style_cmds = [
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#f8fafc")),
        ("LINEBELOW", (0,0), (-1,0), 0.8, C_BORDER),
        ("INNERGRID", (0,1), (-1,-1), 0.3, C_BORDER),
        ("BOX", (0,0), (-1,-1), 0.5, C_BORDER),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
    ]
    # Colorier les lignes HIGH
    for i, task in enumerate(tasks, 1):
        if task.get("risk_level") == "HIGH":
            style_cmds.append(("BACKGROUND", (0,i), (-1,i), colors.HexColor("#fff5f5")))

    tasks_tbl.setStyle(TableStyle(style_cmds))
    story.append(tasks_tbl)
    story.append(Spacer(1, 6*mm))

    # ── Détail des tâches (analyse complète) ─────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=C_BORDER))
    story.append(Paragraph("Analyses détaillées", S["h2"]))

    for task in tasks:
        result = task.get("result") or {}
        if not result:
            continue

        block = []
        t_risk  = task.get("risk_level", "UNKNOWN")
        t_color = _risk_color(t_risk)

        block.append(Paragraph(
            f"<b>{task.get('task_order','')}.  {task.get('task_title','')}</b>"
            f"  <font color='#{t_color.hexval()[2:]}' size='8'>[{t_risk}]</font>",
            S["h3"]
        ))

        if task.get("agent_type") == "debate":
            agents = result.get("agents_analysis", [])
            for a in agents:
                name = a.get("expert_name") or a.get("agent_role", "")
                analysis = a.get("analysis", {})
                lb = analysis.get("legal_basis", "")
                rec = analysis.get("recommendation", "")
                note = analysis.get("expert_note", "")
                if lb or rec:
                    block.append(Paragraph(f"<b>{name}</b>", S["muted"]))
                    if lb:
                        block.append(Paragraph(lb, S["body"]))
                    if rec:
                        block.append(Paragraph(f"→ {rec}", S["action"]))
                    if note:
                        block.append(Paragraph(f"Note : {note}", S["muted"]))
        elif result.get("executive_summary"):
            block.append(Paragraph(result["executive_summary"], S["body"]))
            for act in result.get("key_actions", []):
                block.append(Paragraph(f"→ {act}", S["action"]))
        else:
            if result.get("legal_basis"):
                block.append(Paragraph(f"<b>Base légale :</b> {result['legal_basis']}", S["body"]))
            if result.get("recommendation"):
                block.append(Paragraph(f"<b>Recommandation :</b> {result['recommendation']}", S["body"]))

        block.append(Spacer(1, 3*mm))
        story.append(KeepTogether(block))

    # ── Pied de page ─────────────────────────────────────────
    story.append(Spacer(1, 8*mm))
    story.append(HRFlowable(width="100%", thickness=0.3, color=C_BORDER))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        "EnterpriseCore AI Legal OS — Document confidentiel — Usage interne uniquement",
        S["footer"]
    ))

    doc.build(story)
    return buf.getvalue()


def _kpi_cell(value: str, label: str, color) -> Paragraph:
    return Paragraph(
        f"<font size='18' color='#{color.hexval()[2:]}'><b>{value}</b></font>"
        f"<br/><font size='7' color='#64748b'>{label}</font>",
        ParagraphStyle("kpi", alignment=TA_CENTER, leading=20)
    )
