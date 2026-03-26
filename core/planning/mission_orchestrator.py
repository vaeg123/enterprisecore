import json
from datetime import datetime
from database.db_config import get_connection
from core.planning.mission_planner import MissionPlanner
from core.planning.task_executor import TaskExecutor
from core.memory.analysis_memory import AnalysisMemory


class MissionOrchestrator:
    """
    Orchestre une mission complète :
    1. Planification (décomposition en tâches)
    2. Exécution séquentielle par agents
    3. Rapport final consolidé
    4. Persistance en base
    5. Mémorisation automatique (mémoire évolutive)
    """

    def __init__(self):
        self.planner  = MissionPlanner()
        self.executor = TaskExecutor()
        self.memory   = AnalysisMemory()

    # ─────────────────────────────────────────────
    # Point d'entrée principal
    # ─────────────────────────────────────────────

    def run(self, title: str, objective: str, on_progress=None) -> dict:
        """
        on_progress : callback optionnel appelé après chaque tâche.
                      Signature : on_progress(event: dict)
        """
        started_at = datetime.now()

        def emit(event: dict):
            if on_progress:
                try:
                    on_progress(event)
                except Exception:
                    pass

        # 1. Planification
        tasks = self.planner.plan(objective)
        mission_id = self._save_mission(title, objective, len(tasks))
        emit({"type": "planned", "tasks_count": len(tasks),
              "tasks": [{"order": t.task_order, "title": t.title,
                         "agent_type": t.agent_type} for t in tasks]})

        # 2. Exécution tâche par tâche
        completed = 0
        for task in tasks:
            emit({"type": "task_start", "order": task.task_order,
                  "title": task.title, "agent_type": task.agent_type,
                  "total": len(tasks)})
            print(f"  [{task.task_order}/{len(tasks)}] {task.title} ({task.agent_type})...")
            self.executor.execute(task)
            self._save_task(mission_id, task)
            if task.status == "done":
                completed += 1
            emit({"type": "task_done", "order": task.task_order,
                  "title": task.title, "agent_type": task.agent_type,
                  "status": task.status, "risk_level": task.risk_level,
                  "confidence": task.confidence, "total": len(tasks)})

        # 3. Rapport final
        report = self._build_report(title, objective, tasks, started_at)

        # 4. Mise à jour mission en DB
        self._update_mission(mission_id, completed, report)

        # 5. Mémorisation automatique des conclusions
        try:
            chunks_created = self.memory.memorize_mission(mission_id, title, report)
            report["memory_chunks_created"] = chunks_created
            print(f"  [mémoire] {chunks_created} chunk(s) mémorisé(s) pour les prochaines missions.")
        except Exception as e:
            report["memory_chunks_created"] = 0
            print(f"  [mémoire] Avertissement : mémorisation ignorée ({e})")

        report["mission_id"] = mission_id
        return report

    # ─────────────────────────────────────────────
    # Construction du rapport
    # ─────────────────────────────────────────────

    def _build_report(self, title: str, objective: str, tasks: list, started_at: datetime) -> dict:
        risk_priority = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNKNOWN": 0}
        final_risk = max(
            (t.risk_level or "UNKNOWN" for t in tasks),
            key=lambda r: risk_priority.get(r, 0),
            default="UNKNOWN"
        )

        avg_confidence = (
            sum(t.confidence for t in tasks if t.status == "done") /
            max(1, sum(1 for t in tasks if t.status == "done"))
        )

        summary_task = next((t for t in reversed(tasks) if t.agent_type == "summary" and t.status == "done"), None)

        task_reports = []
        for t in tasks:
            task_reports.append({
                "order": t.task_order,
                "title": t.title,
                "agent_type": t.agent_type,
                "status": t.status,
                "risk_level": t.risk_level,
                "confidence": t.confidence,
                "result": t.result,
            })

        return {
            "mission_title": title,
            "objective": objective,
            "final_risk_level": final_risk,
            "average_confidence": round(avg_confidence, 2),
            "tasks_total": len(tasks),
            "tasks_completed": sum(1 for t in tasks if t.status == "done"),
            "executive_summary": summary_task.result.get("executive_summary") if summary_task else None,
            "key_actions": summary_task.result.get("key_actions", []) if summary_task else [],
            "task_reports": task_reports,
            "started_at": started_at.isoformat(),
            "completed_at": datetime.now().isoformat(),
        }

    # ─────────────────────────────────────────────
    # Persistance
    # ─────────────────────────────────────────────

    def _save_mission(self, title: str, objective: str, tasks_count: int) -> int:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO missions (title, objective, status, tasks_count) VALUES (%s, %s, %s, %s)",
            (title, objective, "running", tasks_count)
        )
        mission_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()
        return mission_id

    def _save_task(self, mission_id: int, task) -> None:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO mission_tasks
               (mission_id, task_order, task_title, task_description, agent_type,
                status, result, risk_level, confidence, completed_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                mission_id,
                task.task_order,
                task.title,
                task.description,
                task.agent_type,
                task.status,
                json.dumps(task.result, ensure_ascii=False),
                task.risk_level,
                task.confidence,
                task.completed_at,
            )
        )
        conn.commit()
        cursor.close()
        conn.close()

    def _update_mission(self, mission_id: int, completed: int, report: dict) -> None:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE missions
               SET status=%s, completed_tasks=%s, final_report=%s, completed_at=NOW()
               WHERE id=%s""",
            (
                "completed",
                completed,
                json.dumps(report, ensure_ascii=False, default=str),
                mission_id,
            )
        )
        conn.commit()
        cursor.close()
        conn.close()
