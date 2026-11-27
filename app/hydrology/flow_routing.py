"""Flow routing D8 sul DEM: direzione di deflusso, accumulo, percorsi.

D8: ogni cella scarica tutta l'acqua verso il vicino (8-connesso) con la
pendenza massima, misurata come dislivello / distanza (sqrt(2) in diagonale).
Le direzioni si calcolano su un DEM condizionato con Priority-Flood+Epsilon:
depressioni e piane (anche i laghi già riempiti) ottengono una pendenza
infinitesima verso l'uscita, quindi i percorsi le attraversano. Il DEM
passato dal chiamante non viene modificato.

Bordo chiuso, come in cellular_automata.py: l'acqua non esce dal raster, le
celle di bordo senza vicini interni più bassi sono pozzi.

Usato per la heatmap di accumulo e per disegnare i percorsi di deflusso dai
candidati sopra le mappe. D-infinity e MFD non sono implementati.
"""
import numpy as np

from app.core.types import DEMGrid, FlowAlgorithm
from app.hydrology.priority_flood import fill_depressions

NO_FLOW = -1
# Indice della direzione = posizione in questa lista
D8_OFFSETS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def _require_d8(algorithm: FlowAlgorithm) -> None:
    if algorithm != FlowAlgorithm.D8:
        raise NotImplementedError(f"Flow routing {algorithm.value} non implementato: usare D8")


def _routing_surface(dem: DEMGrid) -> np.ndarray:
    """DEM condizionato per il routing: depressioni e piane riempite con
    epsilon, così ogni cella non di bordo ha un vicino strettamente più basso
    e i percorsi attraversano i laghi fino all'uscita invece di fermarsi.
    """
    return fill_depressions(dem, epsilon=True).elevation


def _direction_from_surface(z: np.ndarray) -> np.ndarray:
    n_rows, n_cols = z.shape
    padded = np.pad(z, 1, mode="constant", constant_values=np.inf)  # bordo chiuso

    best_slope = np.zeros_like(z)
    direction = np.full(z.shape, NO_FLOW, dtype=np.int8)
    for k, (dr, dc) in enumerate(D8_OFFSETS):
        neighbor = padded[1 + dr:1 + dr + n_rows, 1 + dc:1 + dc + n_cols]
        slope = (z - neighbor) / np.hypot(dr, dc)
        steeper = slope > best_slope
        best_slope[steeper] = slope[steeper]
        direction[steeper] = k
    return direction


def compute_flow_direction(dem: DEMGrid, algorithm: FlowAlgorithm = FlowAlgorithm.D8) -> np.ndarray:
    """Direzione di flusso per ogni cella: indice in D8_OFFSETS, o NO_FLOW.

    NO_FLOW resta solo sulle celle di bordo che sono uscite (bordo chiuso).
    """
    _require_d8(algorithm)
    return _direction_from_surface(_routing_surface(dem))


def compute_flow_accumulation(dem: DEMGrid, algorithm: FlowAlgorithm = FlowAlgorithm.D8) -> np.ndarray:
    """Numero di celle che drenano in ogni cella, inclusa la cella stessa."""
    _require_d8(algorithm)
    surface = _routing_surface(dem)
    direction = _direction_from_surface(surface)
    n_cols = direction.shape[1]
    flat_offsets = [dr * n_cols + dc for dr, dc in D8_OFFSETS]
    flat_direction = direction.ravel()
    accumulation = np.ones(direction.size, dtype=np.int64)

    # Dall'alto verso il basso: D8 punta sempre a una cella strettamente più
    # bassa, quindi ogni cella è completa prima di passare il suo totale a valle.
    for i in np.argsort(surface, axis=None, kind="stable")[::-1]:
        d = flat_direction[i]
        if d != NO_FLOW:
            accumulation[i + flat_offsets[d]] += accumulation[i]
    return accumulation.reshape(direction.shape)


def trace_flow_path(direction: np.ndarray, row: int, col: int) -> list[tuple[int, int]]:
    """Percorso (riga, colonna) da una cella fino al pozzo in cui si ferma."""
    path = [(row, col)]
    while (d := direction[row, col]) != NO_FLOW:
        dr, dc = D8_OFFSETS[d]
        row, col = row + dr, col + dc
        path.append((row, col))
    return path
