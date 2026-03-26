from providers.openai_provider import OpenAIProvider
from providers.ollama_provider import OllamaProvider
from providers.base_provider import LLMResponse


class LLMRouter:
    """
    Router hybride intelligent.
    """

    def __init__(self):
        self.cloud_provider = OpenAIProvider()
        self.local_provider = OllamaProvider()
        self.code_provider = OllamaProvider(model="deepseek-coder:6.7b")

    def generate(self, prompt: str, system_prompt: str = "", task_type: str = "general") -> LLMResponse:

        try:
            if task_type == "code":
                return self.code_provider.generate(prompt, system_prompt)

            if task_type == "critical":
                return self.cloud_provider.generate(prompt, system_prompt)

            # Default → local first
            response = self.local_provider.generate(prompt, system_prompt)

            if response.confidence == 0.0:
                # fallback cloud
                return self.cloud_provider.generate(prompt, system_prompt)

            return response

        except Exception:
            # Ultimate fallback
            return self.cloud_provider.generate(prompt, system_prompt)
