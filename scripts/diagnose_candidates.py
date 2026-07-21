"""Diagnostica: mostra TUTTI i massimi locali trovati, prima dei filtri di
prominenza/area, per capire perche' il filtro sta scartando troppi candidati.

Uso:
    python -m scripts.diagnose_candidates
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from app.hydrology.candidate_detection import (
    _compute_watershed_area,
    _estimate_prominence,
    _find_local_maxima,
)
from app.hydrology.priority_flood import fill_depressions
from app.ingestion.public_dem import load_dem_from_geotiff

dem = load_dem_from_geotiff("data/dem/copernicus_glo30_test.tif")
dem_filled = fill_depressions(dem)
elev = dem_filled.elevation
n_rows, n_cols = elev.shape

idx = np.unravel_index(np.argmax(elev), elev.shape)
print(f"DEM: {n_rows}x{n_cols} celle")
print(f"Punto piu' alto assoluto: row={idx[0]} col={idx[1]}  quota={elev[idx]:.1f}m")
print(f"  Distanza dai bordi: top={idx[0]} bottom={n_rows-1-idx[0]} left={idx[1]} right={n_cols-1-idx[1]} celle\n")

maxima = _find_local_maxima(elev, 15)
print(f"Massimi locali trovati (window=15): {len(maxima)}\n")

print(f"{'row':>4} {'col':>4} {'elev':>7} {'prom':>8} {'bordo':>6} {'area':>6}  dist_bordo_min")
for row, col in sorted(maxima, key=lambda rc: -elev[rc]):
    prom, border_limited = _estimate_prominence(elev, row, col)
    area = _compute_watershed_area(elev, row, col)
    dist_border = min(row, n_rows - 1 - row, col, n_cols - 1 - col)
    flag = "SI" if border_limited else "no"
    print(f"{row:>4} {col:>4} {elev[row,col]:>7.1f} {prom:>8.2f} {flag:>6} {area:>6}  {dist_border}")
