"""Esporta l'espansione dell'acqua nel tempo come GIF/MP4, con la foto
satellitare come sfondo (invece del semplice terreno colorato) e l'acqua
in overlay semi-trasparente sopra.

Uso:
    python -m scripts.export_flood_animation_satellite
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
import requests
from matplotlib.animation import FuncAnimation, PillowWriter
from PIL import Image

from app.agents.ranking_agent import RankingAgent
from app.core.naming import timestamped_filename
from app.hydrology.candidate_detection import detect_candidates
from app.hydrology.cellular_automata import FLOOD_SIM_PARAMS, simulate_flood_with_snapshots
from app.hydrology.priority_flood import fill_depressions
from app.ingestion.public_dem import load_dem_from_geotiff

DEM_PATH = "data/dem/copernicus_glo30_test.tif"
OUTPUT_DIR = Path("output/animations")
N_FRAMES = 20
FPS = 4
DPI = 110
SCALE = 4  # risoluzione satellite: n_cols*SCALE x n_rows*SCALE
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

    print(f"Simulo con {N_FRAMES} frame per l'animazione...")
    result, frames = simulate_flood_with_snapshots(dem_filled, winner, n_snapshots=N_FRAMES)
    if not frames:
        print("ERRORE: nessuno snapshot catturato. Interrotto.")
        return

    with rasterio.open(DEM_PATH) as src:
        bbox = tuple(src.bounds)
    print(f"Bounding box: {bbox}")

    print("Scarico immagine satellitare...")
    try:
        satellite_arr = fetch_satellite_array(bbox, n_cols * SCALE, n_rows * SCALE)
    except requests.RequestException as exc:
        print(f"ERRORE nel download del satellite: {exc}")
        return

    fig, ax = plt.subplots(figsize=(9, 7))
    ax.imshow(satellite_arr, extent=[-0.5, n_cols - 0.5, n_rows - 0.5, -0.5])
    ax.plot(winner.col, winner.row, "*", color="gold", markersize=20, markeredgecolor="black", zorder=5)
    ax.set_xlabel("colonna")
    ax.set_ylabel("riga")
    title = ax.set_title("")

    max_depth = max(float(np.nanmax(h)) for _, h in frames)
    water_im = ax.imshow(
        np.ma.masked_all_like(elevation),
        cmap="Blues", alpha=0.8, origin="upper", vmin=0, vmax=max_depth,
        extent=[-0.5, n_cols - 0.5, n_rows - 0.5, -0.5],
    )

    def update(frame_idx):
        t_s, h_grid = frames[frame_idx]
        water_mask = np.ma.masked_where(h_grid < FLOOD_SIM_PARAMS["min_depth_threshold_m"], h_grid)
        water_im.set_data(water_mask)
        hours = t_s / 3600
        area = result.area_flooded_m2[
            min(range(len(result.time_steps_s)), key=lambda i: abs(result.time_steps_s[i] - t_s))
        ]
        title.set_text(f"{winner_id} — t = {hours:.2f} h — area {area:.0f} m²")
        return water_im, title

    anim = FuncAnimation(fig, update, frames=len(frames), blit=False, repeat=True)

    out_path = OUTPUT_DIR / timestamped_filename("flood_animation_satellite", "gif")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print("Salvo il GIF (può richiedere qualche secondo)...")
    anim.save(str(out_path), writer=PillowWriter(fps=FPS), dpi=DPI)
    plt.close(fig)
    print(f"\nSalvato: {out_path.resolve()}")

    try:
        from matplotlib.animation import FFMpegWriter
        mp4_path = out_path.with_suffix(".mp4")
        fig2, ax2 = plt.subplots(figsize=(9, 7))
        ax2.imshow(satellite_arr, extent=[-0.5, n_cols - 0.5, n_rows - 0.5, -0.5])
        ax2.plot(winner.col, winner.row, "*", color="gold", markersize=20, markeredgecolor="black", zorder=5)
        water_im2 = ax2.imshow(
            np.ma.masked_all_like(elevation), cmap="Blues", alpha=0.8, origin="upper",
            vmin=0, vmax=max_depth, extent=[-0.5, n_cols - 0.5, n_rows - 0.5, -0.5],
        )
        title2 = ax2.set_title("")

        def update2(frame_idx):
            t_s, h_grid = frames[frame_idx]
            water_mask = np.ma.masked_where(h_grid < FLOOD_SIM_PARAMS["min_depth_threshold_m"], h_grid)
            water_im2.set_data(water_mask)
            title2.set_text(f"{winner_id} — t = {t_s/3600:.2f} h")
            return water_im2, title2

        anim2 = FuncAnimation(fig2, update2, frames=len(frames), blit=False, repeat=True)
        anim2.save(str(mp4_path), writer=FFMpegWriter(fps=FPS))
        plt.close(fig2)
        print(f"Salvato anche: {mp4_path.resolve()} (mp4)")
    except (FileNotFoundError, RuntimeError):
        print("\n(mp4 non generato: ffmpeg non trovato — il GIF sopra funziona comunque ovunque)")


if __name__ == "__main__":
    main()
