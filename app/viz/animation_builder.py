"""Animazione temporale: sequenza di frame -> GIF o MP4.

Via matplotlib.animation o Plotly con frames. Mostra l'espansione
dell'acqua nel tempo per il candidato migliore (o tutti in griglia
comparativa).
"""
from app.core.types import DEMGrid, FloodTimeSeries


def build_animation(
    dem: DEMGrid,
    simulation: FloodTimeSeries,
    output_path: str,
    frame_stride: int = 1,
) -> str:
    """Costruisce e salva l'animazione GIF/MP4 per una singola simulazione."""
    raise NotImplementedError
