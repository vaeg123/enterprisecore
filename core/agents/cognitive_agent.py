import json
from providers.llm_router import LLMRouter
from core.identity.agent_identity import AgentIdentity


class CognitiveAgent(AgentIdentity):

    def __init__(self, name: str, role: str):
        super().__init__(name=name, role=role)
        self.router = LLMRouter()

    def analyze_topic(self, topic: str, options: list):

        options_text = "\n".join([f"- {opt}" for opt in options])

        system_prompt = f"""
You are the {self.role.upper()} of an enterprise.

You must choose ONE of the following strategic options:

{options_text}

Respond ONLY in valid JSON:

{{
  "decision": "EXACT_OPTION_NAME",
  "justification": "2-3 concise sentences",
  "confidence": 0.0
}}

Do not add any extra text.
"""

        response = self.router.generate(
            prompt=f"Topic: {topic}",
            system_prompt=system_prompt,
            task_type="general"
        )

        try:
            parsed = json.loads(response.content)

            return {
                "decision": parsed.get("decision", ""),
                "justification": parsed.get("justification", ""),
                "confidence": float(parsed.get("confidence", 0.5)),
                "provider_metadata": response.metadata
            }

        except Exception:
            return {
                "decision": "",
                "justification": response.content,
                "confidence": 0.3,
                "provider_metadata": response.metadata,
                "error": "Parsing failed"
            }
