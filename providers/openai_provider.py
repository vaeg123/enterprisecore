import os
from dotenv import load_dotenv
from openai import OpenAI

from providers.base_provider import BaseProvider, LLMResponse


load_dotenv()


class OpenAIProvider(BaseProvider):
    """
    Provider OpenAI sécurisé et standardisé.
    """

    def __init__(self, model: str = "gpt-4o-mini"):
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment.")

        self.client = OpenAI(api_key=api_key)
        self.model = model

    # -------------------------------------------------
    # Génération texte (Chat Completion)
    # -------------------------------------------------
    def generate(self, prompt: str, system_prompt: str = "") -> LLMResponse:

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
            )

            content = response.choices[0].message.content

            return LLMResponse(
                content=content,
                confidence=0.9,  # valeur provisoire
                metadata={
                    "provider": "openai",
                    "model": self.model
                }
            )

        except Exception as e:
            return LLMResponse(
                content=f"ERROR: {str(e)}",
                confidence=0.0,
                metadata={
                    "provider": "openai",
                    "error": True
                }
            )

    # -------------------------------------------------
    # Génération d'embedding (RAG / Recherche sémantique)
    # -------------------------------------------------
    def generate_embedding(self, text: str):
        """
        Génère un embedding vectoriel pour la recherche sémantique.
        Retourne une liste de floats.
        """

        try:
            response = self.client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )

            return response.data[0].embedding

        except Exception as e:
            raise RuntimeError(
                f"Embedding generation failed: {str(e)}"
            )