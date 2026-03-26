from providers.openai_provider import OpenAIProvider
from providers.deepseek_provider import DeepSeekProvider
from providers.ollama_provider import OllamaProvider
from providers.anthropic_provider import AnthropicProvider


class RoleBasedRouter:

    def __init__(self):

        self.openai = OpenAIProvider()
        self.deepseek = DeepSeekProvider()
        self.ollama = OllamaProvider()

        try:
            self.anthropic = AnthropicProvider()
        except Exception:
            self.anthropic = None

    def route(self, role, prompt, system_prompt="", agent_id=None, domain_code=None):

        role = role.lower()

        # priorité juridique → Claude
        if role == "legal" and self.anthropic:

            response = self.anthropic.generate(prompt, system_prompt)

            # fallback si Claude échoue
            if response.metadata.get("error"):
                return self.openai.generate(prompt, system_prompt)

            return response

        elif role == "developer":
            return self.deepseek.generate(prompt, system_prompt)

        elif role == "finance":
            return self.openai.generate(prompt, system_prompt)

        else:
            return self.ollama.generate(prompt, system_prompt)