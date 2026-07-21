"""App 3D interattiva (server locale via trame): terreno con foto
satellitare vera drappeggiata, slider temporale, slider di trasparenza
acqua, e radio button per la forma del marker del vincitore.

A differenza degli script visualize_*.py (che generano un file HTML
statico da aprire con doppio click), questo e' un VERO SERVER: lo lanci
da terminale e resta in esecuzione, poi apri il browser sull'indirizzo
che stampa (di solito http://localhost:8080).

Uso:
    python -m scripts.app_terrain_satellite_3d_interactive
    (poi apri http://localhost:8080 nel browser, Ctrl+C nel terminale per fermare il server)
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
from pyvista.trame.ui import plotter_ui
from trame.app import get_server
from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import vuetify3

from app.agents.ranking_agent import RankingAgent
from app.hydrology.candidate_detection import detect_candidates
from app.hydrology.cellular_automata import simulate_flood_with_snapshots
from app.hydrology.priority_flood import fill_depressions
from app.ingestion.public_dem import load_dem_from_geotiff

DEM_PATH = "data/dem/copernicus_glo30_test.tif"
SATELLITE_SCALE = 4
N_SNAPSHOTS = 10
_TARGET_VISUAL_FRACTION = 0.12
TERRAIN_Z_EXAGGERATION = 2.0
ESRI_EXPORT_URL = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/"
    "World_Imagery/MapServer/export"
)

SHAPE_OPTIONS = [
    {"text": "Sfera", "value": "sphere"},
    {"text": "Picco/cono", "value": "cone"},
    {"text": "Pin", "value": "pin"},
    {"text": "Diamante", "value": "diamond"},
]


def fetch_satellite_array(bbox, width, height) -> np.ndarray:
    params = {
        "bbox": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}",
        "bboxSR": "4326", "imageSR": "4326",
        "size": f"{width},{height}", "format": "png32", "f": "image",
    }
    resp = requests.get(ESRI_EXPORT_URL, params=params, timeout=30)
    resp.raise_for_status()
    return np.array(Image.open(io.BytesIO(resp.content)).convert("RGB"))


def compute_depth_exaggeration(elevation, max_depth_observed) -> float:
    if max_depth_observed <= 1e-9:
        return 1.0
    elevation_range = float(elevation.max() - elevation.min())
    return max(1.0, elevation_range * _TARGET_VISUAL_FRACTION / max_depth_observed)


def build_winner_shape(kind: str, center: tuple, size: float) -> pv.PolyData:
    """Costruisce la mesh 3D per la forma scelta del marker del vincitore,
    centrata su `center` con dimensione approssimativa `size`."""
    if kind == "sphere":
        return pv.Sphere(radius=size, center=center)

    if kind == "cone":
        mesh = pv.Cone(direction=(0, 0, 1), height=size * 3, radius=size * 1.3, resolution=24)
        mesh.translate(center, inplace=True)
        return mesh

    if kind == "pin":
        head = pv.Sphere(radius=size * 1.1, center=(0, 0, size * 1.6))
        tip = pv.Cone(direction=(0, 0, -1), height=size * 1.6, radius=size * 0.8, resolution=24)
        mesh = head + tip
        mesh.translate(center, inplace=True)
        return mesh

    if kind == "diamond":
        mesh = pv.PlatonicSolid(kind="icosahedron")
        mesh.scale(size, inplace=True)
        mesh.translate(center, inplace=True)
        return mesh

    raise ValueError(f"Forma sconosciuta: {kind}")


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
        print("ERRORE: nessuno snapshot catturato.")
        return

    max_depth = max(float(np.nanmax(h)) for _, h in frames)
    exaggeration = compute_depth_exaggeration(elevation, max_depth)
    frame_labels = [f"t = {t_s/3600:.2f} h" for t_s, _ in frames]

    with rasterio.open(DEM_PATH) as src:
        bbox = tuple(src.bounds)
    print("Scarico immagine satellitare...")
    try:
        satellite_arr = fetch_satellite_array(bbox, n_cols * SATELLITE_SCALE, n_rows * SATELLITE_SCALE)
    except requests.RequestException as exc:
        print(f"ERRORE nel download del satellite: {exc}")
        return

    col_idx, row_idx = np.meshgrid(np.arange(n_cols), np.arange(n_rows))
    x_m = col_idx.astype(float) * dem.cell_size_m
    y_m = row_idx.astype(float) * dem.cell_size_m

    terrain_grid = pv.StructuredGrid(x_m, y_m, elevation)
    terrain_grid.texture_map_to_plane(inplace=True)
    satellite_texture = pv.Texture(satellite_arr)

    def build_water_mesh(frame_idx: int) -> pv.DataSet:
        _, h_grid = frames[frame_idx]
        wet = h_grid >= 0.01
        water_z = elevation + h_grid * exaggeration
        grid = pv.StructuredGrid(x_m, y_m, water_z)
        grid["wet"] = wet.astype(float).ravel(order="F")
        grid["depth"] = h_grid.ravel(order="F")
        return grid.threshold(0.5, scalars="wet")

    # --- Setup PyVista + trame ---
    plotter = pv.Plotter(off_screen=True)
    plotter.add_mesh(terrain_grid, texture=satellite_texture)

    winner_center = (winner.col * dem.cell_size_m, winner.row * dem.cell_size_m, winner.elevation + elevation.max() * 0.02)
    marker_size = dem.cell_size_m * 2.5

    water_actor = plotter.add_mesh(
        build_water_mesh(0), scalars="depth", cmap="Blues", opacity=0.75,
        show_scalar_bar=True, scalar_bar_args={"title": "Profondità (m)"},
    )
    winner_actor = plotter.add_mesh(build_winner_shape("pin", winner_center, marker_size), color="gold")

    for c in candidates:
        if c.id != winner_id:
            plotter.add_mesh(
                pv.Sphere(radius=marker_size * 0.6, center=(c.col * dem.cell_size_m, c.row * dem.cell_size_m, c.elevation + elevation.max() * 0.02)),
                color="mediumseagreen",
            )

    plotter.set_scale(zscale=TERRAIN_Z_EXAGGERATION)
    plotter.camera_position = "iso"
    plotter.set_background("black")

    server = get_server("terrain_satellite_3d", client_type="vue3")
    state, ctrl = server.state, server.controller

    state.time_index = 0
    state.time_label = frame_labels[0]
    state.water_opacity = 0.75
    state.winner_shape = "pin"

    # Riferimenti mutabili agli attori correnti, per poterli rimuovere e
    # ricreare quando cambiano tempo/forma (PyVista non permette di
    # "rigenerare" la selezione delle celle di un threshold in-place)
    actors = {"water": water_actor, "winner": winner_actor}

    @state.change("time_index")
    def on_time_change(time_index, **kwargs):
        idx = int(time_index)
        plotter.remove_actor(actors["water"])
        actors["water"] = plotter.add_mesh(
            build_water_mesh(idx), scalars="depth", cmap="Blues", opacity=state.water_opacity,
            show_scalar_bar=True, scalar_bar_args={"title": "Profondità (m)"},
        )
        state.time_label = frame_labels[idx]
        ctrl.view_update()

    @state.change("water_opacity")
    def on_opacity_change(water_opacity, **kwargs):
        actors["water"].GetProperty().SetOpacity(water_opacity)
        ctrl.view_update()

    @state.change("winner_shape")
    def on_shape_change(winner_shape, **kwargs):
        plotter.remove_actor(actors["winner"])
        actors["winner"] = plotter.add_mesh(build_winner_shape(winner_shape, winner_center, marker_size), color="gold")
        ctrl.view_update()

    with SinglePageLayout(server) as layout:
        layout.title.set_text(f"Terreno 3D + satellite — vincitore {winner_id}")
        with layout.content:
            with vuetify3.VContainer(fluid=True, classes="pa-2 fill-height d-flex flex-column"):
                with vuetify3.VRow(classes="flex-grow-0", dense=True):
                    with vuetify3.VCol(cols=4):
                        vuetify3.VLabel("Tempo: {{ time_label }}")
                        vuetify3.VSlider(
                            v_model=("time_index", 0), min=0, max=len(frames) - 1, step=1,
                            hide_details=True, density="compact",
                        )
                    with vuetify3.VCol(cols=4):
                        vuetify3.VLabel("Trasparenza acqua")
                        vuetify3.VSlider(
                            v_model=("water_opacity", 0.75), min=0, max=1, step=0.05,
                            hide_details=True, density="compact",
                        )
                    with vuetify3.VCol(cols=4):
                        vuetify3.VLabel("Forma vincitore")
                        # IMPORTANTE: i figli vanno creati DENTRO il blocco
                        # "with" del gruppo, non passati come lista via
                        # children=[...] — quest'ultimo pattern li registra
                        # DUE VOLTE (una nidificati nel gruppo, una come
                        # fratelli diretti del contenitore) causando la
                        # duplicazione vista nello screenshot.
                        with vuetify3.VRadioGroup(
                            v_model=("winner_shape", "pin"), inline=True,
                            hide_details=True, density="compact",
                        ):
                            for opt in SHAPE_OPTIONS:
                                vuetify3.VRadio(label=opt["text"], value=opt["value"])
                with vuetify3.VRow(classes="flex-grow-1", style="min-height: 500px;"):
                    # mode="server": il rendering avviene lato Python (lo
                    # stesso meccanismo off-screen già verificato in questa
                    # conversazione) e vengono inviate immagini al browser,
                    # invece di sincronizzare geometria WebGL lato client —
                    # più lento a ridisegnare ma molto più affidabile,
                    # soprattutto per una prima verifica.
                    view = plotter_ui(plotter, mode="server")
                    ctrl.view_update = view.update

    # Forza un primo render non appena un client si connette: senza
    # questo, la vista può restare vuota finché non arriva la prima
    # interazione (bug noto di "schermata bianca al primo caricamento").
    @ctrl.on_server_ready.add
    def _initial_render(**kwargs):
        ctrl.view_update()

    print("\nServer pronto. Apri il browser su http://localhost:8080")
    print("(Ctrl+C nel terminale per fermare il server)")
    server.start(open_browser=True)


if __name__ == "__main__":
    main()
