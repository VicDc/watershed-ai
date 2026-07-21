"""Mappa statica ipsometrica + overlay acqua per il candidato vincitore.

DEM in scala colori (terrain), overlay semi-trasparente blu per l'acqua
al tempo finale del candidato in prima posizione in classifica, marker
per tutti i candidati colorati/etichettati per punteggio (posizione in
classifica).
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from app.core.types import CandidatePoint, DEMGrid, FloodTimeSeries
from app.hydrology.cellular_automata import FLOOD_SIM_PARAMS, _redistribute_step


def _recompute_final_water_depth(
    dem: DEMGrid,
    candidate: CandidatePoint,
    simulation: FloodTimeSeries,
) -> np.ndarray:
    """Rigioca la simulazione fino all'ultimo step per ottenere la griglia
    2D di profondità acqua finale (FloodTimeSeries salva solo le metriche
    aggregate per step, non la griglia intera per ogni istante — la
    ricalcoliamo una sola volta, per il solo candidato vincitore).
    """
    elevation = dem.elevation
    cell_area_m2 = dem.cell_size_m ** 2
    flow_rate = FLOOD_SIM_PARAMS["flow_rate_m3_s"]
    dt = FLOOD_SIM_PARAMS["time_step_s"]
    outflow_fraction = FLOOD_SIM_PARAMS["outflow_fraction"]

    h = np.zeros_like(elevation, dtype=np.float64)
    n_steps = len(simulation.time_steps_s)

    for _ in range(n_steps):
        h[candidate.row, candidate.col] += flow_rate * dt / cell_area_m2
        h = _redistribute_step(elevation, h, outflow_fraction)

    return h


def render_static_map(
    dem: DEMGrid,
    candidates: list[CandidatePoint],
    simulations: dict[str, FloodTimeSeries],
    scores: dict[str, float],
    ranked_candidates: list[str],
    output_path: str,
) -> str:
    """Renderizza e salva la mappa statica ipsometrica con overlay acqua
    del candidato in prima posizione, e marker per tutti i candidati.
    """
    elevation = dem.elevation
    winner_id = ranked_candidates[0]
    winner = next(c for c in candidates if c.id == winner_id)
    winner_sim = simulations[winner_id]

    h_final = _recompute_final_water_depth(dem, winner, winner_sim)

    fig, ax = plt.subplots(figsize=(11, 8))
    ax.imshow(elevation, cmap="terrain", origin="upper")

    water_mask = np.ma.masked_where(h_final < FLOOD_SIM_PARAMS["min_depth_threshold_m"], h_final)
    ax.imshow(water_mask, cmap="Blues", alpha=0.75, origin="upper", vmin=0)

    for c in candidates:
        rank = ranked_candidates.index(c.id) + 1
        is_winner = c.id == winner_id
        color = "gold" if is_winner else "white"
        marker = "*" if is_winner else "o"
        size = 22 if is_winner else 10

        ax.plot(c.col, c.row, marker, color=color, markersize=size, markeredgecolor="black", zorder=5)
        ax.annotate(
            f"#{rank} {c.elevation:.0f}m\n{scores[c.id]:.0f}m²",
            (c.col, c.row),
            textcoords="offset points",
            xytext=(8, 8),
            fontsize=8,
            color="white",
            bbox=dict(boxstyle="round,pad=0.2", fc="black", alpha=0.7),
            zorder=6,
        )

    ax.set_title(
        f"Miglior candidato: {winner_id} — area allagata finale "
        f"{scores[winner_id]:.0f}m² (stella dorata = vincitore)"
    )
    ax.set_xlabel("colonna")
    ax.set_ylabel("riga")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(out)
