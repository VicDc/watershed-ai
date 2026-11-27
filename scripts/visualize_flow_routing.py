"""Heatmap dell'accumulo di flusso D8 e D-infinity, e terreno 3D con i
percorsi di deflusso D8.

Uso:
    python -m scripts.visualize_flow_routing
"""
import sys
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.naming import timestamped_filename
from app.core.types import FlowAlgorithm
from app.hydrology.priority_flood import fill_depressions
from app.ingestion.public_dem import load_dem_from_geotiff
from app.viz.raster_render import render_flow_accumulation_map, render_flow_paths_3d

OUTPUT_DIR = Path("output/maps")

dem_filled = fill_depressions(load_dem_from_geotiff("data/dem/copernicus_glo30_test.tif"))
renders = (
    ("flow_accumulation", render_flow_accumulation_map),
    ("flow_accumulation_dinf", partial(render_flow_accumulation_map, algorithm=FlowAlgorithm.D_INFINITY)),
    ("flow_paths_3d", render_flow_paths_3d),
)
for name, render in renders:
    out = render(dem_filled, str(OUTPUT_DIR / timestamped_filename(name, "png")))
    print(f"Salvato: {Path(out).resolve()}")
