"""Flow routing D8 e D-infinity sul DEM: direzione di deflusso, accumulo, percorsi.

D8: ogni cella scarica tutta l'acqua verso il vicino (8-connesso) con la
pendenza massima, misurata come dislivello / distanza (sqrt(2) in diagonale).

D-infinity (Tarboton 1997): la direzione è un angolo continuo. Attorno alla
cella si considerano 8 faccette triangolari (cella, vicino cardinale, vicino
diagonale adiacente); si sceglie la faccetta con la pendenza massima e l'acqua
si divide tra i suoi due vicini in proporzione all'angolo. Rende meglio i
versanti obliqui, dove D8 può scegliere solo multipli di 45°.

Le direzioni si calcolano su un DEM condizionato con Priority-Flood+Epsilon:
depressioni e piane (anche i laghi già riempiti) ottengono una pendenza
infinitesima verso l'uscita, quindi i percorsi le attraversano. Il DEM
passato dal chiamante non viene modificato.

Bordo chiuso, come in cellular_automata.py: l'acqua non esce dal raster, le
celle di bordo senza vicini interni più bassi sono pozzi.

Usato per la heatmap di accumulo e per disegnare i percorsi di deflusso dai
candidati sopra le mappe. MFD non è implementato.
"""
import numpy as np

from app.core.types import DEMGrid, FlowAlgorithm
from app.hydrology.priority_flood import fill_depressions

NO_FLOW = -1
# Indice della direzione = posizione in questa lista
D8_OFFSETS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

# Faccette D-infinity (Tarboton 1997, tabella 1): (vicino cardinale, vicino
# diagonale, ac, af) con i vicini come indici in D8_OFFSETS. Angolo di flusso
# = ac * pi/2 + af * r, in radianti, antiorario da est (pi/2 = nord = riga - 1).
_DINF_FACETS = [
    (4, 2, 0, 1),    # E, NE
    (1, 2, 1, -1),   # N, NE
    (1, 0, 1, 1),    # N, NW
    (3, 0, 2, -1),   # W, NW
    (3, 5, 2, 1),    # W, SW
    (6, 5, 3, -1),   # S, SW
    (6, 7, 3, 1),    # S, SE
    (4, 7, 4, -1),   # E, SE
]


def _require_implemented(algorithm: FlowAlgorithm) -> None:
    if algorithm not in (FlowAlgorithm.D8, FlowAlgorithm.D_INFINITY):
        raise NotImplementedError(f"Flow routing {algorithm.value} non implementato: usare D8 o D_INFINITY")


def _routing_surface(dem: DEMGrid) -> np.ndarray:
    """DEM condizionato per il routing: depressioni e piane riempite con
    epsilon, così ogni cella non di bordo ha un vicino strettamente più basso
    e i percorsi attraversano i laghi fino all'uscita invece di fermarsi.
    """
    return fill_depressions(dem, epsilon=True).elevation


def _shifted(padded: np.ndarray, k: int, shape: tuple[int, int]) -> np.ndarray:
    """Vista del vicino k di ogni cella, da un array con padding di 1."""
    dr, dc = D8_OFFSETS[k]
    return padded[1 + dr:1 + dr + shape[0], 1 + dc:1 + dc + shape[1]]


def _direction_from_surface(z: np.ndarray) -> np.ndarray:
    padded = np.pad(z, 1, mode="constant", constant_values=np.inf)  # bordo chiuso

    best_slope = np.zeros_like(z)
    direction = np.full(z.shape, NO_FLOW, dtype=np.int8)
    for k, (dr, dc) in enumerate(D8_OFFSETS):
        slope = (z - _shifted(padded, k, z.shape)) / np.hypot(dr, dc)
        steeper = slope > best_slope
        best_slope[steeper] = slope[steeper]
        direction[steeper] = k
    return direction


def _dinf_from_surface(z: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """D-infinity: (angolo, vicino cardinale, vicino diagonale, frazione al diagonale).

    Celle quadrate: la distanza tra celle si semplifica nel rapporto delle
    pendenze, quindi si lavora in unità di cella.
    """
    padded = np.pad(z, 1, mode="edge")
    inside = np.pad(np.ones(z.shape, dtype=bool), 1, constant_values=False)  # bordo chiuso

    best_slope = np.zeros_like(z)
    angle = np.full(z.shape, np.nan)
    k1 = np.full(z.shape, NO_FLOW, dtype=np.int8)
    k2 = np.full(z.shape, NO_FLOW, dtype=np.int8)
    frac2 = np.zeros_like(z)
    for e1_k, e2_k, ac, af in _DINF_FACETS:
        e1 = _shifted(padded, e1_k, z.shape)
        e2 = _shifted(padded, e2_k, z.shape)
        s1, s2 = z - e1, e1 - e2
        r = np.arctan2(s2, s1)
        slope = np.hypot(s1, s2)
        # Direzione fuori dalla faccetta: si appoggia al lato più vicino
        below, above = r < 0, r > np.pi / 4
        r = np.clip(r, 0.0, np.pi / 4)
        slope = np.where(below, s1, np.where(above, (z - e2) / np.sqrt(2), slope))

        valid = _shifted(inside, e1_k, z.shape) & _shifted(inside, e2_k, z.shape)
        steeper = valid & (slope > best_slope)
        best_slope[steeper] = slope[steeper]
        angle[steeper] = (ac * np.pi / 2 + af * r)[steeper]
        k1[steeper] = e1_k
        k2[steeper] = e2_k
        frac2[steeper] = (r / (np.pi / 4))[steeper]
    return angle, k1, k2, frac2


def compute_flow_direction(dem: DEMGrid, algorithm: FlowAlgorithm = FlowAlgorithm.D8) -> np.ndarray:
    """Direzione di flusso per ogni cella.

    D8: indice in D8_OFFSETS (int8), o NO_FLOW.
    D_INFINITY: angolo in radianti in [0, 2*pi), antiorario da est
    (pi/2 = nord, verso la riga 0), NaN dove non c'è deflusso.

    Senza deflusso restano solo le celle di bordo che sono uscite (bordo chiuso).
    """
    _require_implemented(algorithm)
    surface = _routing_surface(dem)
    if algorithm == FlowAlgorithm.D8:
        return _direction_from_surface(surface)
    return _dinf_from_surface(surface)[0]


def compute_flow_accumulation(dem: DEMGrid, algorithm: FlowAlgorithm = FlowAlgorithm.D8) -> np.ndarray:
    """Numero di celle che drenano in ogni cella, inclusa la cella stessa.

    D8: intero. D_INFINITY: float, perché ogni cella divide la sua acqua tra
    due vicini.
    """
    _require_implemented(algorithm)
    surface = _routing_surface(dem)
    if algorithm == FlowAlgorithm.D8:
        receivers = [(_direction_from_surface(surface), np.ones(surface.shape, dtype=np.int64))]
        accumulation = np.ones(surface.size, dtype=np.int64)
    else:
        _, k1, k2, frac2 = _dinf_from_surface(surface)
        receivers = [(k1, 1.0 - frac2), (k2, frac2)]
        accumulation = np.ones(surface.size)

    n_cols = surface.shape[1]
    flat_offsets = [dr * n_cols + dc for dr, dc in D8_OFFSETS]
    flat_receivers = [(k.ravel().tolist(), w.ravel().tolist()) for k, w in receivers]

    # Dall'alto verso il basso: ogni vicino che riceve acqua è strettamente più
    # basso, quindi ogni cella è completa prima di passare il suo totale a valle.
    for i in np.argsort(surface, axis=None, kind="stable")[::-1]:
        for ks, ws in flat_receivers:
            if ks[i] != NO_FLOW and ws[i] > 0:
                accumulation[i + flat_offsets[ks[i]]] += accumulation[i] * ws[i]
    return accumulation.reshape(surface.shape)


def trace_flow_path(direction: np.ndarray, row: int, col: int) -> list[tuple[int, int]]:
    """Percorso (riga, colonna) da una cella fino al pozzo in cui si ferma.

    Solo per direzioni D8 (compute_flow_direction con l'algoritmo di default).
    """
    path = [(row, col)]
    while (d := direction[row, col]) != NO_FLOW:
        dr, dc = D8_OFFSETS[d]
        row, col = row + dr, col + dc
        path.append((row, col))
    return path
