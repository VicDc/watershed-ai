"""Vista 3D interattiva con la FOTO SATELLITARE VERA drappeggiata sul
terreno (PyVista/VTK, non Plotly — Plotly non supporta il texture
mapping su superfici 3D arbitrarie).

Uso:
    python -m scripts.visualize_terrain_satellite_3d
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pyvista as pv
import rasterio
import requests
from PIL import Image

from app.agents.ranking_agent import RankingAgent
from app.core.naming import timestamped_filename
from app.hydrology.candidate_detection import detect_candidates
from app.hydrology.cellular_automata import simulate_flood_with_snapshots
from app.hydrology.priority_flood import fill_depressions
from app.ingestion.public_dem import load_dem_from_geotiff

DEM_PATH = "data/dem/copernicus_glo30_test.tif"
OUTPUT_DIR = Path("output/maps")
SATELLITE_SCALE = 4  # risoluzione texture: n_cols*SCALE x n_rows*SCALE
N_SNAPSHOTS = 10
_TARGET_VISUAL_FRACTION = 0.12  # stessa esagerazione usata nella vista Plotly

# Esagerazione verticale dell'INTERA scena (terreno + acqua), applicata a
# scala 1:1 reale (ora che X/Y sono in metri come Z) — a scala vera un DEM
# con dislivelli modesti rispetto all'estensione orizzontale risulta
# spesso troppo "piatto" da leggere visivamente. 1.0 = nessuna esagerazione
# (scala fisicamente corretta), valori più alti accentuano il rilievo.
TERRAIN_Z_EXAGGERATION = 2.0
ESRI_EXPORT_URL = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/"
    "World_Imagery/MapServer/export"
)


def fetch_satellite_array(bbox: tuple[float, float, float, float], width: int, height: int) -> np.ndarray:
    params = {
        "bbox": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}",
        "bboxSR": "4326", "imageSR": "4326",
        "size": f"{width},{height}", "format": "png32", "f": "image",
    }
    resp = requests.get(ESRI_EXPORT_URL, params=params, timeout=30)
    resp.raise_for_status()
    img = Image.open(io.BytesIO(resp.content)).convert("RGB")
    return np.array(img)


def _compute_depth_exaggeration(elevation: np.ndarray, max_depth_observed: float) -> float:
    if max_depth_observed <= 1e-9:
        return 1.0
    elevation_range = float(elevation.max() - elevation.min())
    return max(1.0, elevation_range * _TARGET_VISUAL_FRACTION / max_depth_observed)


def main() -> None:
    dem = load_dem_from_geotiff(DEM_PATH)
    dem_filled = fill_depressions(dem)
    elevation = dem_filled.elevation
    n_rows, n_cols = elevation.shape

    print("Rilevo candidati e trovo il vincitore...")
    candidates = detect_candidates(dem_filled)
    simulations = {c.id: simulate_flood_with_snapshots(dem_filled, c, n_snapshots=1)[0] for c in candidates}
    ranking = RankingAgent().process(simulations)
    winner_id = ranking.ranked_candidates[0]
    winner = next(c for c in candidates if c.id == winner_id)
    print(f"Vincitore: {winner_id}")

    print(f"Simulo con {N_SNAPSHOTS} snapshot temporali...")
    result, frames = simulate_flood_with_snapshots(dem_filled, winner, n_snapshots=N_SNAPSHOTS)
    if not frames:
        print("ERRORE: nessuno snapshot catturato. Interrotto.")
        return
    t_final, h_final = frames[-1]
    max_depth = max(float(np.nanmax(h)) for _, h in frames)
    exaggeration = _compute_depth_exaggeration(elevation, max_depth)
    print(f"Fattore di esagerazione acqua: {exaggeration:.1f}x (stato finale, t={t_final/3600:.1f}h)")

    with rasterio.open(DEM_PATH) as src:
        bbox = tuple(src.bounds)
    print(f"Bounding box: {bbox}")

    print("Scarico immagine satellitare...")
    try:
        satellite_arr = fetch_satellite_array(bbox, n_cols * SATELLITE_SCALE, n_rows * SATELLITE_SCALE)
    except requests.RequestException as exc:
        print(f"ERRORE nel download del satellite: {exc}")
        return

    # --- Costruzione della mesh del terreno, con la foto satellitare vera
    # drappeggiata sopra (texture_map_to_plane + Texture) ---
    # IMPORTANTE: X/Y devono essere nella STESSA unità fisica di Z (metri),
    # non indici di griglia grezzi (0..n_cols) — altrimenti PyVista tratta
    # 1 "cella" e 1 "metro di quota" come la stessa unità, deformando
    # verticalmente tutta la scena (e con essa la texture).
    col_idx, row_idx = np.meshgrid(np.arange(n_cols), np.arange(n_rows))
    x_m = col_idx.astype(float) * dem.cell_size_m
    y_m = row_idx.astype(float) * dem.cell_size_m

    terrain_grid = pv.StructuredGrid(x_m, y_m, elevation)
    terrain_grid.texture_map_to_plane(inplace=True)
    satellite_texture = pv.Texture(satellite_arr)

    # --- Mesh dell'acqua: stessa griglia, ma quota esagerata e "ritagliata"
    # solo sulle celle bagnate (altrimenti sembrerebbe un lago ovunque) ---
    wet = h_final >= 0.01
    water_z = elevation + h_final * exaggeration
    water_grid = pv.StructuredGrid(x_m, y_m, water_z)
    water_grid["wet"] = wet.astype(float).ravel(order="F")
    water_grid["depth"] = h_final.ravel(order="F")

    # La colormap "Blues" di default parte da un bianco quasi puro per le
    # profondita' basse — con molte celle poco profonde il risultato
    # appare "lavato"/quasi invisibile (stesso problema gia' risolto
    # nell'overlay 2D). Uso una colormap custom che parte gia' da un
    # azzurro riconoscibile (mai bianco) e una scala a radice quadrata
    # per dare contrasto anche alle zone poco profonde.
    from matplotlib.colors import LinearSegmentedColormap
    water_cmap = LinearSegmentedColormap.from_list(
        "water_visible", ["#7fb8d8", "#003366"]
    )
    max_depth_final = max(float(h_final.max()), 1e-6)
    depth_flat = h_final.ravel(order="F")
    water_grid["depth_display"] = np.sqrt(np.clip(depth_flat, 0, None) / max_depth_final) * max_depth_final

    water_grid = water_grid.threshold(0.5, scalars="wet")

    plotter = pv.Plotter(off_screen=False, window_size=(1000, 800))
    plotter.add_mesh(terrain_grid, texture=satellite_texture)
    plotter.add_mesh(
        water_grid, scalars="depth_display", cmap=water_cmap, opacity=0.85,
        show_scalar_bar=True, scalar_bar_args={"title": "Profondità acqua (m)"},
    )

    for c in candidates:
        is_winner = c.id == winner_id
        radius_m = (3.0 if is_winner else 2.0) * dem.cell_size_m
        center = (c.col * dem.cell_size_m, c.row * dem.cell_size_m, c.elevation + elevation.max() * 0.02)
        sphere = pv.Sphere(radius=radius_m, center=center)
        plotter.add_mesh(sphere, color="gold" if is_winner else "mediumseagreen")

    plotter.add_text(f"Vincitore: {winner_id} (acqua esagerata {exaggeration:.1f}x, rilievo esagerato {TERRAIN_Z_EXAGGERATION:.1f}x)", font_size=10)
    plotter.set_scale(zscale=TERRAIN_Z_EXAGGERATION)
    plotter.camera_position = "iso"
    plotter.set_background("black")

    out_path = OUTPUT_DIR / timestamped_filename("terrain_satellite_3d", "html")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plotter.export_html(str(out_path))
    print(f"\nSalvato: {out_path.resolve()}")
    print("Apri il file: trascina per ruotare, rotella per zoom.")


if __name__ == "__main__":
    main()
