import os
from dotenv import load_dotenv
import anthropic

from providers.base_provider import BaseProvider, LLMResponse


load_dotenv()


class AnthropicProvider(BaseProvider):
    """
    Provider Claude (Anthropic API)
    Conforme au contrat BaseProvider.
    """

    def __init__(self):

        self.api_key = os.getenv("ANTHROPIC_API_KEY")

        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not found in environment variables."
            )

        self.client = anthropic.Anthropic(api_key=self.api_key)

        # Modèle recommandé actuel
        self.model = "claude-3-5-sonnet-latest"


    def generate(self, prompt: str, system_prompt: str = "") -> LLMResponse:
        """
        Génère une réponse via Claude.
        Retourne un objet LLMResponse standardisé.
        """

        try:

            response = self.client.messages.create(
                model=self.model,
                max_tokens=800,
                temperature=0.3,
                system=system_prompt if system_prompt else "",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Sécurité : vérifier que Claude a bien répondu
            if not response.content:
                return LLMResponse(
                    content="",
                    confidence=0.0,
                    metadata={
                        "provider": "anthropic",
                        "model": self.model,
                        "error": "Empty response"
                    }
                )

            return LLMResponse(
                content=response.content[0].text,
                confidence=0.9,
                metadata={
                    "provider": "anthropic",
                    "model": self.model
                }
            )

        except Exception as e:

            return LLMResponse(
                content=f"Generation failed: {str(e)}",
                confidence=0.0,
                metadata={
                    "provider": "anthropic",
                    "model": self.model,
                    "error": True
                }
            )
