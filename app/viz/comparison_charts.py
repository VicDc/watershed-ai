"""Grafico comparativo Area(t): curve sovrapposte, una per candidato.

Con legenda — permette di vedere a colpo d'occhio quale punto vince a ogni
istante, non solo al termine.

Widget interattivo (opzionale): artifact HTML/React con slider temporale
per esplorare l'animazione senza rigenerare file statici.
"""
from app.core.types import FloodTimeSeries


def build_comparison_chart(simulations: dict[str, FloodTimeSeries], output_path: str) -> str:
    """Costruisce e salva il grafico comparativo Area(t) per tutti i candidati."""
    raise NotImplementedError
