"""Assembla il report finale (markdown/PDF): mappa, grafici, classifica motivata.

L'eventuale LLM interviene solo qui, per generare l'executive summary in
linguaggio naturale a partire dal ranking numerico già calcolato — non
tocca mai i calcoli idrologici (vedi note metodologiche nello spec:
determinismo vs LLM).
"""
from app.core.types import PipelineResult


def build_report(result: PipelineResult, output_path: str, use_llm_narrative: bool = False) -> str:
    """Genera il report finale e lo salva in output_path (.md o .pdf)."""
    raise NotImplementedError
