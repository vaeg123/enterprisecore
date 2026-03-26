from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class LLMResponse:
    """
    Réponse standardisée d’un modèle.
    """
    content: str
    confidence: float
    metadata: Dict[str, Any]


class BaseProvider(ABC):
    """
    Contrat commun pour tous les fournisseurs LLM.
    """

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str = "") -> LLMResponse:
        """
        Doit retourner une réponse structurée.
        """
        pass
