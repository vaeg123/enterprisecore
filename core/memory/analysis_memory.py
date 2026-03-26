"""
Mémoire évolutive des analyses passées.

Après chaque mission complétée, les conclusions clés sont transformées
en knowledge_chunks avec embeddings et injectées dans la base de connaissance.
Elles seront automatiquement récupérées par le RAG lors des prochaines missions.
"""
import json
from datetime import datetime
from database.db_config import get_connection
from providers.openai_provider import OpenAIProvider


# ID du domaine "Mémoire des Analyses Passées" (créé en DB)
MEMORY_DOMAIN_CODE = "MEMOIRE_MISSIONS"


class AnalysisMemory:

    def __init__(self):
        self.embedding_provider = OpenAIProvider()
        self._domain_id = None
        self._doc_id = None

    # ─────────────────────────────────────────────────────────
    # Point d'entrée principal
    # ─────────────────────────────────────────────────────────

    def memorize_mission(self, mission_id: int, mission_title: str, report: dict) -> int:
        """
        Extrait les conclusions de la mission et les sauvegarde en mémoire.
        Retourne le nombre de chunks créés.
        """
        doc_id  = self._get_or_create_document(mission_id, mission_title)
        chunks  = self._extract_chunks(mission_title, report)
        created = 0

        for idx, chunk_text in enumerate(chunks):
            chunk_id = self._save_chunk(doc_id, chunk_text, idx)
            self._save_embedding(chunk_id, chunk_text)
            created += 1

        return created

    # ─────────────────────────────────────────────────────────
    # Extraction du contenu mémorisable
    # ─────────────────────────────────────────────────────────

    def _extract_chunks(self, title: str, report: dict) -> list[str]:
        chunks = []
        risk   = report.get("final_risk_level", "UNKNOWN")
        date   = datetime.now().strftime("%Y-%m-%d")

        # Chunk 1 : synthèse globale de la mission
        summary = report.get("executive_summary") or ""
        if not summary and isinstance(report.get("final_report"), dict):
            summary = report["final_report"].get("executive_summary", "")

        if summary:
            chunks.append(
                f"[Analyse passée — {date}] Mission : {title}\n"
                f"Risque final : {risk}\n"
                f"Synthèse : {summary}"
            )

        # Chunk 2 : actions recommandées
        key_actions = report.get("key_actions") or []
        if not key_actions and isinstance(report.get("final_report"), dict):
            key_actions = report["final_report"].get("key_actions", [])

        if key_actions:
            actions_text = "\n".join(f"- {a}" for a in key_actions)
            chunks.append(
                f"[Actions recommandées — {date}] Mission : {title}\n"
                f"Risque : {risk}\n"
                f"Actions :\n{actions_text}"
            )

        # Chunk 3 : conclusions par tâche (uniquement les HIGH)
        task_reports = report.get("task_reports", [])
        high_tasks = [t for t in task_reports if t.get("risk_level") == "HIGH" and t.get("result")]

        for task in high_tasks:
            result = task.get("result", {})
            legal_basis = result.get("legal_basis", "")
            recommendation = result.get("recommendation", "")

            if legal_basis:
                chunks.append(
                    f"[Analyse HIGH — {date}] {task.get('title', '')} (mission : {title})\n"
                    f"Base légale : {legal_basis}\n"
                    f"Recommandation : {recommendation}"
                )

        return [c for c in chunks if len(c.strip()) > 50]

    # ─────────────────────────────────────────────────────────
    # Persistance
    # ─────────────────────────────────────────────────────────

    def _get_domain_id(self) -> int:
        if self._domain_id:
            return self._domain_id
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM knowledge_domains WHERE code = %s", (MEMORY_DOMAIN_CODE,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if not row:
            raise RuntimeError(f"Domaine '{MEMORY_DOMAIN_CODE}' introuvable en base.")
        self._domain_id = row[0]
        return self._domain_id

    def _get_or_create_document(self, mission_id: int, mission_title: str) -> int:
        domain_id = self._get_domain_id()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO knowledge_documents
               (domain_id, title, source_type, version, actif)
               VALUES (%s, %s, %s, %s, 1)""",
            (domain_id, f"Mission #{mission_id} — {mission_title}", "auto_memory", "1.0")
        )
        doc_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()
        return doc_id

    def _save_chunk(self, doc_id: int, content: str, index: int) -> int:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO knowledge_chunks (document_id, content, chunk_index) VALUES (%s, %s, %s)",
            (doc_id, content, index)
        )
        chunk_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()
        return chunk_id

    def _save_embedding(self, chunk_id: int, text: str) -> None:
        embedding = self.embedding_provider.generate_embedding(text)
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO knowledge_embeddings (chunk_id, embedding) VALUES (%s, %s)",
            (chunk_id, json.dumps(embedding))
        )
        conn.commit()
        cursor.close()
        conn.close()
