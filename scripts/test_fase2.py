"""Test Fase 1 (priority-flood) + Fase 2 (candidate detection) sul DEM reale.

Uso:
    python -m scripts.test_fase2
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.hydrology.candidate_detection import detect_candidates
from app.hydrology.priority_flood import fill_depressions
from app.ingestion.public_dem import load_dem_from_geotiff

dem = load_dem_from_geotiff("data/dem/copernicus_glo30_test.tif")
print(f"DEM caricato: {dem.elevation.shape}, quota {dem.elevation.min():.1f}-{dem.elevation.max():.1f}m")

dem_filled = fill_depressions(dem)
print(f"Priority-flood applicato. Quality flags: {dem_filled.quality_flags}")

candidates = detect_candidates(dem_filled)
print(f"\nCandidati trovati: {len(candidates)}")
for c in candidates:
    print(f"  {c.id}: elev={c.elevation:.1f}m  prominenza={c.prominence:.1f}m  bacino={c.watershed_area_cells} celle")
    print(f"    -> {c.rationale}")
