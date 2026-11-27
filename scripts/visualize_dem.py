"""Visualizza il DEM con tutti i massimi locali marcati (verde=candidato
valido, rosso=scartato dai filtri), per capire a colpo d'occhio dove si
trovano i picchi e perche' alcuni vengono esclusi.

Salva un PNG in output/maps/. Uso:
    python -m scripts.visualize_dem
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt
import numpy as np

from app.core.naming import timestamped_filename
from app.hydrology.candidate_detection import (
    CANDIDATE_DETECTION_PARAMS,
    _compute_watershed_area,
    _estimate_prominence,
    _find_local_maxima,
)
from app.hydrology.flow_routing import compute_flow_direction, trace_flow_path
from app.hydrology.priority_flood import fill_depressions
from app.ingestion.public_dem import load_dem_from_geotiff

dem = load_dem_from_geotiff("data/dem/copernicus_glo30_test.tif")
dem_filled = fill_depressions(dem)
elev = dem_filled.elevation

maxima = _find_local_maxima(elev, CANDIDATE_DETECTION_PARAMS["local_max_window_cells"])

fig, ax = plt.subplots(figsize=(10, 7))
im = ax.imshow(elev, cmap="terrain", origin="upper")
plt.colorbar(im, ax=ax, label="Quota (m)")

direction = compute_flow_direction(dem_filled)

for row, col in maxima:
    prom, border_limited = _estimate_prominence(elev, row, col)
    area = _compute_watershed_area(elev, row, col)
    passes_prominence = border_limited or prom >= CANDIDATE_DETECTION_PARAMS["min_prominence_m"]
    passes_area = area >= CANDIDATE_DETECTION_PARAMS["min_watershed_area_cells"]
    passes = passes_prominence and passes_area

    if not passes:
        color = "red"          # scartato (prominenza reale bassa o bacino troppo piccolo)
    elif border_limited:
        color = "orange"       # accettato, ma prominenza è solo un limite inferiore
    else:
        color = "lime"         # accettato, prominenza reale misurata internamente

    if passes:  # percorso di deflusso D8 dai candidati validi, come nella mappa finale
        path = np.array(trace_flow_path(direction, row, col))
        ax.plot(path[:, 1], path[:, 0], color="cyan", linewidth=1.2, alpha=0.9, zorder=3)
    ax.plot(col, row, "o", color=color, markersize=8, markeredgecolor="black", zorder=4)
    ax.annotate(
        f"{elev[row,col]:.0f}m\nprom={'>=' if border_limited else ''}{prom:.1f}",
        (col, row),
        textcoords="offset points",
        xytext=(6, 6),
        fontsize=7,
        color="white",
        bbox=dict(boxstyle="round,pad=0.2", fc="black", alpha=0.6),
    )

# punto piu' alto assoluto, evidenziato a parte
idx = np.unravel_index(np.argmax(elev), elev.shape)
ax.plot(idx[1], idx[0], "*", color="cyan", markersize=18, markeredgecolor="black", zorder=5)

ax.set_title(
    f"DEM {elev.shape[0]}x{elev.shape[1]} — verde=valido, arancione=valido (bordo tronca la sella),\n"
    f"rosso=scartato, stella ciano=quota massima assoluta,\n"
    f"linee ciano=deflusso D8 dai candidati validi"
)
ax.set_xlabel("colonna")
ax.set_ylabel("riga")

out_path = Path("output/maps") / timestamped_filename("dem_candidates_debug", "png")
out_path.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(out_path, dpi=150, bbox_inches="tight")
print(f"Salvato: {out_path.resolve()}")
