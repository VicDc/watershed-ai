"""BaseAgent ABC — stesso pattern usato in OrgTransform AI / business-plan-ai.

A differenza di quei progetti, qui il "lavoro" di ogni agente è per lo più
calcolo numerico deterministico: l'LLM è opzionale e confinato alla
generazione di testo narrativo (rationale, note comparative).
"""
from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """Interfaccia comune a tutti gli agenti della pipeline."""

    name: str = "base_agent"

    @abstractmethod
    def process(self, *args: Any, **kwargs: Any) -> Any:
        """Esegue la fase e ritorna il risultato tipizzato (vedi core/types.py)."""
        raise NotImplementedError
