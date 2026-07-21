"""FASE 3 — Flood Simulation: cellular automata shallow-water semplificato.

Modello a "diffusione proporzionale al gradiente": ad ogni step temporale,
una frazione dell'acqua presente in ogni cella (`outflow_fraction`) viene
ridistribuita verso i vicini più bassi, proporzionalmente al dislivello di
superficie (quota + acqua). E' un compromesso deliberato tra realismo
fisico e semplicità/stabilità numerica — non risolve le equazioni di
Saint-Venant, ma è sufficiente per confrontare candidati tra loro.

Confini del dominio: chiusi (nessun deflusso oltre il bordo del raster).
Semplificazione accettabile per un prototipo; se in futuro serve un
confine aperto (l'acqua può "uscire" dal ritaglio), va gestito
esplicitamente sui bordi.

Connettività: 4 (N/S/E/W). Niente diagonali, per evitare artefatti di
canale lungo le diagonali tipici di schemi CA più semplici.
"""
import numpy as np

from app.core.types import CandidatePoint, DEMGrid, FloodTimeSeries

FLOOD_SIM_PARAMS = {
    "flow_rate_m3_s": 5.0,               # portata ipotetica immessa
    "time_step_s": 60.0,                 # granularità temporale
    "max_simulation_time_s": 3600 * 6,   # tetto massimo (6 ore simulate)
    "min_depth_threshold_m": 0.01,
    "stabilization_window_steps": 10,
    "stabilization_tolerance_pct": 0.5,
    "outflow_fraction": 0.5,             # frazione di acqua ridistribuita per step
}


def _redistribute_step(elevation: np.ndarray, h: np.ndarray, outflow_fraction: float) -> np.ndarray:
    """Un singolo step di ridistribuzione dell'acqua verso i vicini più bassi.

    Usa padding "edge" per i bordi: un bordo replica il valore della cella
    stessa, quindi il dislivello verso un "vicino" oltre il bordo è sempre
    zero -> nessun deflusso attraverso il confine del dominio (bordo chiuso).
    """
    n_rows, n_cols = elevation.shape
    surface = elevation + h
    padded = np.pad(surface, 1, mode="edge")

    north = padded[0:n_rows, 1:n_cols + 1]
    south = padded[2:n_rows + 2, 1:n_cols + 1]
    west = padded[1:n_rows + 1, 0:n_cols]
    east = padded[1:n_rows + 1, 2:n_cols + 2]

    drop_n = np.maximum(surface - north, 0.0)
    drop_s = np.maximum(surface - south, 0.0)
    drop_w = np.maximum(surface - west, 0.0)
    drop_e = np.maximum(surface - east, 0.0)

    total_drop = drop_n + drop_s + drop_w + drop_e
    total_drop_safe = np.where(total_drop > 0, total_drop, 1.0)

    movable = h * outflow_fraction

    flow_n = movable * (drop_n / total_drop_safe)
    flow_s = movable * (drop_s / total_drop_safe)
    flow_w = movable * (drop_w / total_drop_safe)
    flow_e = movable * (drop_e / total_drop_safe)

    outflow_total = flow_n + flow_s + flow_w + flow_e

    inflow_total = np.zeros_like(h)
    # flow_n[r,c] esce dalla cella (r,c) verso (r-1,c): arriva come inflow lì
    inflow_total[0:n_rows - 1, :] += flow_n[1:n_rows, :]
    inflow_total[1:n_rows, :] += flow_s[0:n_rows - 1, :]
    inflow_total[:, 0:n_cols - 1] += flow_w[:, 1:n_cols]
    inflow_total[:, 1:n_cols] += flow_e[:, 0:n_cols - 1]

    h_new = h - outflow_total + inflow_total
    return np.maximum(h_new, 0.0)


def _run_simulation(
    dem: DEMGrid,
    candidate: CandidatePoint,
    params: dict,
    snapshot_step_indices: set[int] | None = None,
) -> tuple[FloodTimeSeries, dict[int, np.ndarray]]:
    """Loop di simulazione condiviso. Se snapshot_step_indices e' dato,
    salva una copia della griglia acqua 2D a quegli step (1-indexed),
    utile per costruire una visualizzazione dell'espansione nel tempo
    senza dover rieseguire la simulazione da capo.
    """
    elevation = dem.elevation
    n_rows, n_cols = elevation.shape
    cell_area_m2 = dem.cell_size_m ** 2

    flow_rate = params["flow_rate_m3_s"]
    dt = params["time_step_s"]
    max_time = params["max_simulation_time_s"]
    min_depth = params["min_depth_threshold_m"]
    stab_window = params["stabilization_window_steps"]
    stab_tol_pct = params["stabilization_tolerance_pct"]
    outflow_fraction = params["outflow_fraction"]

    h = np.zeros((n_rows, n_cols), dtype=np.float64)
    snapshot_step_indices = snapshot_step_indices or set()
    snapshots: dict[int, np.ndarray] = {}

    n_steps = int(max_time // dt)
    time_steps_s: list[float] = []
    area_flooded_m2: list[float] = []
    volume_injected_m3: list[float] = []
    max_depth_m: list[float] = []

    volume_cum = 0.0
    stabilized = False
    recent_areas: list[float] = []

    for step in range(1, n_steps + 1):
        h[candidate.row, candidate.col] += flow_rate * dt / cell_area_m2
        volume_cum += flow_rate * dt

        h = _redistribute_step(elevation, h, outflow_fraction)

        if step in snapshot_step_indices:
            snapshots[step] = h.copy()

        flooded_mask = h >= min_depth
        area = float(np.sum(flooded_mask) * cell_area_m2)
        depth_max = float(h.max())

        time_steps_s.append(step * dt)
        area_flooded_m2.append(area)
        volume_injected_m3.append(volume_cum)
        max_depth_m.append(depth_max)

        recent_areas.append(area)
        if len(recent_areas) > stab_window:
            recent_areas.pop(0)
        if len(recent_areas) == stab_window:
            a_min, a_max = min(recent_areas), max(recent_areas)
            if a_max > 0 and (a_max - a_min) / a_max * 100 <= stab_tol_pct:
                stabilized = True
                # cattura comunque uno snapshot finale se richiesto oltre
                # lo step di stabilizzazione (l'ultimo raggiunto)
                if snapshot_step_indices and step not in snapshots and max(snapshot_step_indices) >= step:
                    snapshots[step] = h.copy()
                break

    result = FloodTimeSeries(
        candidate_id=candidate.id,
        time_steps_s=time_steps_s,
        area_flooded_m2=area_flooded_m2,
        volume_injected_m3=volume_injected_m3,
        max_depth_m=max_depth_m,
        stabilized=stabilized,
    )
    return result, snapshots


def simulate_flood(
    dem: DEMGrid,
    candidate: CandidatePoint,
    params: dict = FLOOD_SIM_PARAMS,
) -> FloodTimeSeries:
    """Simula l'espansione dell'acqua nel tempo per un singolo candidato.

    Assicurarsi che il DEM sia già stato passato per priority_flood.py
    prima di chiamare questa funzione.
    """
    result, _ = _run_simulation(dem, candidate, params)
    return result


def simulate_flood_with_snapshots(
    dem: DEMGrid,
    candidate: CandidatePoint,
    params: dict = FLOOD_SIM_PARAMS,
    n_snapshots: int = 10,
) -> tuple[FloodTimeSeries, list[tuple[float, np.ndarray]]]:
    """Come simulate_flood, ma cattura anche n_snapshots griglie 2D della
    profondità dell'acqua, a istanti equispaziati nel tempo simulato
    (utile per un'animazione o uno slider temporale).

    Ritorna (FloodTimeSeries, lista di (tempo_s, griglia_profondita_m)).
    Il numero di step totali non è noto a priori (la simulazione può
    fermarsi prima per stabilizzazione), quindi si fa una prima passata
    "a vuoto" solo per contare gli step, poi una seconda con gli snapshot
    agli indici giusti. Per DEM di dimensioni tipiche di questo progetto
    (poche decine di migliaia di celle) il costo aggiuntivo è trascurabile.
    """
    dry_run_result, _ = _run_simulation(dem, candidate, params)
    total_steps = len(dry_run_result.time_steps_s)

    if total_steps == 0:
        return dry_run_result, []

    step_indices = sorted(
        {max(1, round(i * total_steps / n_snapshots)) for i in range(1, n_snapshots + 1)}
    )
    result, snapshots = _run_simulation(dem, candidate, params, snapshot_step_indices=set(step_indices))

    frames = [(step * params["time_step_s"], snapshots[step]) for step in sorted(snapshots.keys())]
    return result, frames
