"""Priority-flood: riempimento depressioni (algoritmo di Barnes et al., 2014).

Implementazione in NumPy/SciPy puro, senza richdem — evita i problemi di
build su Windows (richiederebbe Visual Studio Build Tools). Per DEM
piccoli/medi (fino a qualche centinaio di migliaia di celle) le prestazioni
sono più che sufficienti per un prototipo.

Algoritmo (versione classica a coda di priorità):
1. Inserisci tutte le celle del bordo del raster in una coda di priorità
   (min-heap), ordinata per quota.
2. Estrai sempre la cella a quota più bassa dalla coda.
3. Per ogni vicino non ancora processato: se la sua quota è inferiore a
   quella della cella corrente, alzala fino al livello della cella
   corrente (riempie la depressione). Poi inseriscilo in coda.
4. Ripeti finché la coda è vuota.

Il risultato è un DEM "idrologicamente corretto": ogni cella ha sempre un
percorso di deflusso verso il bordo, senza buche artificiali dove l'acqua
si accumulerebbe senza motivo fisico.
"""
import heapq

import numpy as np

from app.core.types import DEMGrid

# Offset degli 8 vicini (connettività queen/8-connected)
_NEIGHBORS_8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def fill_depressions(dem: DEMGrid, epsilon: bool = False) -> DEMGrid:
    """Ritorna una nuova DEMGrid con i sink spuri riempiti.

    Rimuove "sink_artifacts_detected" da dem.quality_flags una volta
    applicato con successo.

    epsilon=True (Priority-Flood+Epsilon, Barnes 2014): ogni cella raggiunta
    non più alta della cella da cui arriva viene alzata al float successivo
    (np.nextafter, ~1e-13 m) invece che alla stessa quota. Laghi riempiti e
    piane diventano leggermente inclinati verso l'uscita: ogni cella interna
    ha un vicino strettamente più basso. Serve al flow routing D8; la
    simulazione usa il riempimento normale.
    """
    elevation = dem.elevation.astype(np.float64).copy()
    n_rows, n_cols = elevation.shape

    filled = elevation.copy()
    visited = np.zeros((n_rows, n_cols), dtype=bool)

    heap: list[tuple[float, int, int]] = []

    for r in range(n_rows):
        for c in (0, n_cols - 1):
            heapq.heappush(heap, (float(filled[r, c]), r, c))
            visited[r, c] = True
    for c in range(n_cols):
        for r in (0, n_rows - 1):
            if not visited[r, c]:
                heapq.heappush(heap, (float(filled[r, c]), r, c))
                visited[r, c] = True

    n_cells_raised = 0

    while heap:
        elev, r, c = heapq.heappop(heap)

        for dr, dc in _NEIGHBORS_8:
            nr, nc = r + dr, c + dc
            if nr < 0 or nr >= n_rows or nc < 0 or nc >= n_cols:
                continue
            if visited[nr, nc]:
                continue

            visited[nr, nc] = True
            if epsilon and filled[nr, nc] <= elev:
                filled[nr, nc] = np.nextafter(elev, np.inf)
                n_cells_raised += 1
            elif filled[nr, nc] < elev:
                filled[nr, nc] = elev
                n_cells_raised += 1

            heapq.heappush(heap, (float(filled[nr, nc]), nr, nc))

    quality_flags = [f for f in dem.quality_flags if f != "sink_artifacts_detected"]
    if n_cells_raised > 0:
        quality_flags.append(f"depressions_filled:{n_cells_raised}_cells")

    return DEMGrid(
        elevation=filled,
        cell_size_m=dem.cell_size_m,
        origin=dem.origin,
        nodata_value=dem.nodata_value,
        source=dem.source,
        quality_flags=quality_flags,
    )
