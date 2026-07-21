"""Flow routing: D8 / D-infinity / MFD sul DEM.

Usato sia per il calcolo del bacino potenziale statico (Fase 2) sia come
possibile motore alternativo/di confronto alla simulazione cellular
automata (Fase 3). Implementabile con richdem / pysheds / whitebox.
"""
from app.core.types import DEMGrid, FlowAlgorithm

import numpy as np


def compute_flow_direction(dem: DEMGrid, algorithm: FlowAlgorithm = FlowAlgorithm.D8) -> np.ndarray:
    """Calcola la direzione di flusso per ogni cella del DEM."""
    raise NotImplementedError


def compute_flow_accumulation(dem: DEMGrid, algorithm: FlowAlgorithm = FlowAlgorithm.D8) -> np.ndarray:
    """Calcola l'accumulo di flusso (celle a monte) per ogni cella."""
    raise NotImplementedError
