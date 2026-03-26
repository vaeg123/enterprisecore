import requests
from providers.base_provider import BaseProvider, LLMResponse


class OllamaProvider(BaseProvider):
    """
    Provider Ollama local.
    """

    def __init__(self, model: str = "mistral:7b"):
        self.model = model
        self.base_url = "http://localhost:11434/api/generate"

    def generate(self, prompt: str, system_prompt: str = "") -> LLMResponse:

        full_prompt = f"{system_prompt}\n\n{prompt}"

        try:
            response = requests.post(
                self.base_url,
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "stream": False
                }
            )

            response.raise_for_status()

            data = response.json()

            return LLMResponse(
                content=data.get("response", ""),
                confidence=0.75,  # Local confidence légèrement plus basse
                metadata={
                    "provider": "ollama",
                    "model": self.model
                }
            )

        except Exception as e:
            return LLMResponse(
                content=f"ERROR: {str(e)}",
                confidence=0.0,
                metadata={
                    "provider": "ollama",
                    "error": True
                }
            )
