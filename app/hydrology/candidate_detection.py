"""FASE 2 — Candidate Selection: il punto di quota massima assoluta NON è
sufficiente.

Implementazione in NumPy/SciPy puro:

1. Local maxima detection: scipy.ndimage.maximum_filter su finestra mobile
2. Filtro di prominenza: dislivello tra il massimo locale e la quota
   minima lungo il percorso di discesa più semplice verso il bordo del
   raster (approssimazione via flood-fill a soglie crescenti, più
   economica di un vero algoritmo di prominenza topografica ma sufficiente
   per un prototipo)
3. Bacino potenziale statico: BFS/flood-fill dalla cella candidata verso
   il basso, contando le celle raggiungibili scendendo di quota — primo
   filtro economico prima delle simulazioni idrologiche vere e proprie
4. Filtro area minima bacino potenziale
5. Output: lista di CandidatePoint con rationale testuale generato dai
   numeri calcolati (nessun LLM necessario per questo)

Nota: la ridge detection descritta nello spec (creste larghe che
alimentano più bacini) non è implementata in questa prima versione —
rimandata a un affinamento successivo se il progetto lo richiede.
"""
import numpy as np
from scipy import ndimage

from app.core.types import CandidatePoint, DEMGrid

CANDIDATE_DETECTION_PARAMS = {
    "min_prominence_m": 10.0,
    "local_max_window_cells": 15,
    "min_watershed_area_cells": 20,
    "max_candidates": 15,
}

_NEIGHBORS_8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def _find_local_maxima(elevation: np.ndarray, window: int) -> list[tuple[int, int]]:
    """Trova le celle che sono il massimo nella finestra mobile attorno a sé.

    Le celle di massimo locale spesso non sono punti isolati ma piccoli
    plateau o creste intere (es. tutta una fila di bordo, se il terreno
    sale monotonicamente verso il bordo del ritaglio): senza
    deduplicazione produrrebbero decine di candidati quasi identici.
    Le celle "vincenti" adiacenti (8-connectivity) vengono quindi
    raggruppate in un unico blob, e per ciascun blob si ritorna un solo
    punto rappresentativo (quello più vicino al centroide del blob).
    """
    local_max = ndimage.maximum_filter(elevation, size=window, mode="nearest")
    mask = elevation == local_max

    labeled, n_blobs = ndimage.label(mask, structure=np.ones((3, 3)))

    representatives: list[tuple[int, int]] = []
    for blob_id in range(1, n_blobs + 1):
        coords = np.argwhere(labeled == blob_id)
        if len(coords) == 1:
            representatives.append((int(coords[0, 0]), int(coords[0, 1])))
            continue

        centroid = coords.mean(axis=0)
        dists = np.sum((coords - centroid) ** 2, axis=1)
        best = coords[np.argmin(dists)]
        representatives.append((int(best[0]), int(best[1])))

    return representatives


def _estimate_prominence(
    elevation: np.ndarray, row: int, col: int, n_steps: int = 100
) -> tuple[float, bool]:
    """Approssima la prominenza topografica via flood-fill a soglia decrescente.

    Parte dalla quota del picco e abbassa progressivamente una soglia,
    osservando la componente connessa (8-connectivity) che contiene il
    picco nella maschera "elevation >= soglia". Si ferma alla prima soglia
    in cui quella componente:
      - contiene una cella più alta del picco stesso (si è connessa al
        bacino di un rilievo più alto) -> prominenza REALE, sella trovata
        internamente al raster;
      - oppure tocca il bordo del raster senza aver incontrato un rilievo
        più alto -> il rilievo continua oltre il ritaglio: la prominenza
        calcolata è solo un LIMITE INFERIORE (border_limited=True), il
        vero valore potrebbe essere molto più alto.

    Ritorna (prominenza_stimata, border_limited). Quando border_limited è
    True, il chiamante non dovrebbe scartare il candidato solo perché il
    numero è basso: è un artefatto del ritaglio, non del terreno.
    """
    peak_elev = float(elevation[row, col])
    elev_min = float(elevation.min())
    thresholds = np.linspace(peak_elev, elev_min, n_steps)[1:]

    for threshold in thresholds:
        mask = elevation >= threshold
        labeled, _ = ndimage.label(mask, structure=np.ones((3, 3)))
        peak_label = labeled[row, col]
        component = labeled == peak_label

        touches_higher_peak = np.any(elevation[component] > peak_elev + 1e-6)
        if touches_higher_peak:
            return peak_elev - threshold, False

        touches_border = (
            component[0, :].any() or component[-1, :].any()
            or component[:, 0].any() or component[:, -1].any()
        )
        if touches_border:
            return peak_elev - threshold, True

    return peak_elev - elev_min, False


def _compute_watershed_area(elevation: np.ndarray, row: int, col: int) -> int:
    """Bacino potenziale statico: BFS a partire dal candidato, seguendo solo
    celle vicine a quota decrescente o uguale (percorso di deflusso verso
    valle). Conta quante celle sono "a valle" del candidato.
    """
    n_rows, n_cols = elevation.shape
    visited = np.zeros((n_rows, n_cols), dtype=bool)
    stack = [(row, col)]
    visited[row, col] = True
    count = 0

    while stack:
        r, c = stack.pop()
        count += 1
        current_elev = elevation[r, c]

        for dr, dc in _NEIGHBORS_8:
            nr, nc = r + dr, c + dc
            if nr < 0 or nr >= n_rows or nc < 0 or nc >= n_cols:
                continue
            if visited[nr, nc]:
                continue
            if elevation[nr, nc] <= current_elev:
                visited[nr, nc] = True
                stack.append((nr, nc))

    return count


def detect_candidates(
    dem: DEMGrid,
    params: dict = CANDIDATE_DETECTION_PARAMS,
) -> list[CandidatePoint]:
    """Individua i punti candidati per l'immissione d'acqua."""
    elevation = dem.elevation
    maxima = _find_local_maxima(elevation, params["local_max_window_cells"])

    candidates: list[CandidatePoint] = []
    for row, col in maxima:
        prominence, border_limited = _estimate_prominence(elevation, row, col)

        # Scarta solo se la sella è reale (trovata internamente al raster)
        # ed è sotto soglia. Se il rilievo continua oltre il bordo del
        # ritaglio, la prominenza calcolata è solo un limite inferiore
        # inaffidabile: non è corretto scartare il picco solo per questo.
        if not border_limited and prominence < params["min_prominence_m"]:
            continue

        watershed_area = _compute_watershed_area(elevation, row, col)
        if watershed_area < params["min_watershed_area_cells"]:
            continue

        if border_limited:
            rationale = (
                f"Massimo locale a quota {elevation[row, col]:.1f}m, "
                f"prominenza >= {prominence:.1f}m (rilievo troncato dal bordo "
                f"del ritaglio — valore reale probabilmente più alto), "
                f"bacino potenziale di {watershed_area} celle."
            )
        else:
            rationale = (
                f"Massimo locale a quota {elevation[row, col]:.1f}m, "
                f"prominenza {prominence:.1f}m, "
                f"bacino potenziale di {watershed_area} celle."
            )

        candidates.append(
            CandidatePoint(
                id=f"cand_{row}_{col}",
                row=row,
                col=col,
                elevation=float(elevation[row, col]),
                prominence=float(prominence),
                watershed_area_cells=watershed_area,
                rationale=rationale,
            )
        )

    # Ordina per quota decrescente quando la prominenza è solo un limite
    # inferiore (poco confrontabile), altrimenti il bacino potenziale resta
    # il proxy migliore di "quanto allagherà"
    candidates.sort(key=lambda c: (c.watershed_area_cells, c.elevation), reverse=True)
    return candidates[: params["max_candidates"]]
