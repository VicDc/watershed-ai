"""Test Fase 4: pipeline completa Fase1->2->3->4, con classifica finale e
mappa statica con overlay acqua del candidato vincitore.

Uso:
    python -m scripts.test_fase4
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.ranking_agent import RankingAgent
from app.core.naming import timestamped_filename
from app.hydrology.candidate_detection import detect_candidates
from app.hydrology.cellular_automata import simulate_flood
from app.hydrology.priority_flood import fill_depressions
from app.ingestion.public_dem import load_dem_from_geotiff
from app.viz.raster_render import render_static_map

dem = load_dem_from_geotiff("data/dem/copernicus_glo30_test.tif")
dem_filled = fill_depressions(dem)
print(f"DEM: {dem.elevation.shape}, cell_size_m={dem.cell_size_m:.2f}")

candidates = detect_candidates(dem_filled)
print(f"Candidati trovati: {len(candidates)}\n")

print("Simulo l'allagamento per ciascun candidato...")
simulations = {}
for c in candidates:
    result = simulate_flood(dem_filled, c)
    simulations[c.id] = result
    print(f"  {c.id}: area_finale={result.area_flooded_m2[-1]:.0f}m2  stabilizzato={result.stabilized}")

ranking_agent = RankingAgent()
ranking = ranking_agent.process(simulations)

print("\n=== CLASSIFICA FINALE ===")
for note in ranking.comparison_notes:
    print(note)

out_path = Path("output/maps") / timestamped_filename("fase4_final_map", "png")
render_static_map(
    dem_filled, candidates, simulations, ranking.scores, ranking.ranked_candidates, str(out_path)
)
print(f"\nMappa finale salvata: {out_path.resolve()}")
print(f"\nCandidato vincitore: {ranking.ranked_candidates[0]}")
