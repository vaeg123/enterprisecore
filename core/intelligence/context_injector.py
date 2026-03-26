from core.intelligence.semantic_search_engine import SemanticSearchEngine
from providers.openai_provider import OpenAIProvider


class ContextInjector:
    """
    Injecte du contexte documentaire interne dans un prompt.
    """

    def __init__(self):
        self.search_engine = SemanticSearchEngine()
        self.embedding_provider = OpenAIProvider()

    def build_context(self, query: str):

        # 1️⃣ Générer embedding de la question
        query_embedding = self.embedding_provider.generate_embedding(query)

        # 2️⃣ Recherche sémantique
        best_match, score = self.search_engine.search(query_embedding)

        # 3️⃣ Seuil de pertinence
        if score < 0.70:
            return ""

        # 4️⃣ Construire le bloc contexte
        context_text = f"""
CONTEXTE INTERNE ENTREPRISE (à respecter en priorité) :

{best_match}

Fin du contexte interne.
"""

        return context_text