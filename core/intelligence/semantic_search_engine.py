import numpy as np
from core.database.connection import get_connection
import json


class SemanticSearchEngine:

    def __init__(self):
        self.conn = get_connection()

    def cosine_similarity(self, vec1, vec2):
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)

        if np.linalg.norm(vec1) == 0 or np.linalg.norm(vec2) == 0:
            return 0.0

        return np.dot(vec1, vec2) / (
            np.linalg.norm(vec1) * np.linalg.norm(vec2)
        )

    def search(self, query_embedding):

        cursor = self.conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT 
                kc.id,
                kc.content,
                ke.embedding,
                kd.poids_strategique
            FROM knowledge_chunks kc
            JOIN knowledge_embeddings ke ON kc.id = ke.chunk_id
            JOIN knowledge_documents kdoc ON kc.document_id = kdoc.id
            JOIN knowledge_domains kd ON kdoc.domain_id = kd.id
            WHERE kdoc.actif = 1
        """)

        results = cursor.fetchall()

        best_match = None
        best_score = 0.0

        for row in results:

            # ✅ Correction ici
            stored_embedding = json.loads(row["embedding"])

            similarity = self.cosine_similarity(
                query_embedding,
                stored_embedding
            )

            weighted_score = similarity * float(row["poids_strategique"])

            if weighted_score > best_score:
                best_score = weighted_score
                best_match = row["content"]

        cursor.close()

        return best_match, best_score

