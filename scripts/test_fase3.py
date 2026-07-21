"""Test Fase 3: simula l'allagamento per tutti i candidati trovati e
confronta l'andamento dell'area nel tempo.

Uso:
    python -m scripts.test_fase3
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt

from app.core.naming import timestamped_filename
from app.hydrology.candidate_detection import detect_candidates
from app.hydrology.cellular_automata import simulate_flood
from app.hydrology.priority_flood import fill_depressions
from app.ingestion.public_dem import load_dem_from_geotiff

dem = load_dem_from_geotiff("data/dem/copernicus_glo30_test.tif")
dem_filled = fill_depressions(dem)
print(f"DEM: {dem.elevation.shape}, cell_size_m={dem.cell_size_m:.2f}")

candidates = detect_candidates(dem_filled)
print(f"Candidati trovati: {len(candidates)}\n")

results = {}
for c in candidates:
    print(f"Simulo {c.id} (quota {c.elevation:.1f}m)...")
    result = simulate_flood(dem_filled, c)
    results[c.id] = result
    print(
        f"  -> stabilizzato={result.stabilized}  "
        f"step={len(result.time_steps_s)}  "
        f"area_finale={result.area_flooded_m2[-1]:.0f}m2  "
        f"depth_max={result.max_depth_m[-1]:.2f}m"
    )

# Grafico comparativo Area(t)
fig, ax = plt.subplots(figsize=(9, 6))
for cand_id, result in results.items():
    hours = [t / 3600 for t in result.time_steps_s]
    ax.plot(hours, result.area_flooded_m2, label=cand_id, linewidth=2)

ax.set_xlabel("Tempo (ore)")
ax.set_ylabel("Area allagata (m²)")
ax.set_title("Confronto candidati — area allagata nel tempo")
ax.legend()
ax.grid(alpha=0.3)

out_path = Path("output/maps") / timestamped_filename("fase3_comparison", "png")
out_path.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(out_path, dpi=150, bbox_inches="tight")
print(f"\nGrafico salvato: {out_path.resolve()}")

# Classifica finale per area
ranking = sorted(results.items(), key=lambda kv: kv[1].area_flooded_m2[-1], reverse=True)
print("\nClassifica finale (per area allagata):")
for i, (cand_id, result) in enumerate(ranking, start=1):
    print(f"  {i}. {cand_id}: {result.area_flooded_m2[-1]:.0f} m2")
