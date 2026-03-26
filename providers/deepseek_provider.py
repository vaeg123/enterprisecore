import os
from dotenv import load_dotenv
from openai import OpenAI
from providers.base_provider import LLMResponse


load_dotenv()


class DeepSeekProvider:
    """
    Provider DeepSeek via API officielle.
    Compatible OpenAI API (endpoint spécifique).
    """

    def __init__(self):

        self.api_key = os.getenv("DEEPSEEK_API_KEY")

        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY not found in environment variables.")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com"
        )

        self.model = "deepseek-chat"

    def generate(self, prompt: str, system_prompt: str = None):

        messages = []

        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })

        messages.append({
            "role": "user",
            "content": prompt
        })

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.3
        )

        return LLMResponse(
        content=response.choices[0].message.content,
        confidence=0.8,
        metadata={
        "provider": "deepseek",
        "model": self.model
    }
)

