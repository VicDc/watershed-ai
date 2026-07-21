"""Esporta la vista 3D come GIF/MP4: ogni fotogramma e' renderizzato
staticamente da Plotly (via kaleido) con una camera fissa, poi i
fotogrammi vengono uniti in un'animazione.

Richiede: pip install -U kaleido (include un browser headless proprio,
non serve installare Chrome separatamente).

Uso:
    python -m scripts.export_flood_animation_3d
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import plotly.graph_objects as go
from matplotlib.animation import FuncAnimation, PillowWriter
from PIL import Image

from app.agents.ranking_agent import RankingAgent
from app.core.naming import timestamped_filename
from app.hydrology.candidate_detection import detect_candidates
from app.hydrology.cellular_automata import simulate_flood_with_snapshots
from app.hydrology.priority_flood import fill_depressions
from app.ingestion.public_dem import load_dem_from_geotiff

DEM_PATH = "data/dem/copernicus_glo30_test.tif"
OUTPUT_DIR = Path("output/animations")
N_FRAMES = 24   # con la rotazione servono più frame per un giro fluido
FPS = 6
FRAME_WIDTH = 1600
FRAME_HEIGHT = 1300 
FRAME_SCALE = 1   # moltiplicatore risoluzione: 2 = doppia densità pixel
_TARGET_VISUAL_FRACTION = 0.12

# --- Rotazione della camera -------------------------------------------
# Invece di una camera fissa (che puo' nascondere l'acqua dietro una
# cresta a seconda dell'angolo), la camera ruota di ROTATE_DEGREES_TOTAL
# gradi nell'arco dell'intero video — cosi' ogni punto di vista viene
# mostrato automaticamente, senza dover indovinare l'angolo "giusto".
ROTATE_DEGREES_TOTAL = 0      # 360 = giro completo; 0 = camera fissa (comportamento precedente)
CAMERA_RADIUS = 1.4             # distanza della camera dal centro (più alto = più zoom out)
CAMERA_START_DEGREES = 230      # angolo di partenza
CAMERA_ELEVATION = 1.1          # quota della camera (più alto = vista più dall'alto)

# --- Colori --------------------------------------------------------------
# Terreno: qualunque colorscale Plotly valida. Alternative interessanti:
# "earth" (attuale, verde-marrone-bianco) | "Viridis" (blu-verde-giallo,
# alto contrasto) | "thermal" (nero-viola-arancione-bianco) | "turbo"
# (arcobaleno, molto leggibile per variazioni piccole) | "Greys"
TERRAIN_COLORSCALE = "earth"

# Acqua: gradiente a due colori, [profondita_minima, profondita_massima].
# Formato "rgba(R,G,B,A)". Esempio alternativo (acqua torbida/marrone):
# WATER_COLOR_LOW, WATER_COLOR_HIGH = "rgba(200,180,140,0.6)", "rgba(90,60,20,0.9)"
WATER_COLOR_LOW = "rgba(173,216,230,0.75)"
WATER_COLOR_HIGH = "rgba(0,51,102,0.95)"


def _compute_depth_exaggeration(elevation: np.ndarray, max_depth_observed: float) -> float:
    if max_depth_observed <= 1e-9:
        return 1.0
    elevation_range = float(elevation.max() - elevation.min())
    return max(1.0, elevation_range * _TARGET_VISUAL_FRACTION / max_depth_observed)


def _camera_for_frame(frame_idx: int, n_frames: int) -> dict:
    """Calcola la posizione della camera per il fotogramma frame_idx,
    ruotando attorno all'asse verticale di ROTATE_DEGREES_TOTAL gradi
    totali nell'arco di tutta l'animazione."""
    if n_frames <= 1:
        progress = 0.0
    else:
        progress = frame_idx / (n_frames - 1)
    angle_deg = CAMERA_START_DEGREES + progress * ROTATE_DEGREES_TOTAL
    angle_rad = np.radians(angle_deg)
    eye_x = CAMERA_RADIUS * np.cos(angle_rad)
    eye_y = CAMERA_RADIUS * np.sin(angle_rad)
    return dict(eye=dict(x=eye_x, y=eye_y, z=CAMERA_ELEVATION))


def _render_3d_frame_png(
    elevation: np.ndarray, h_grid: np.ndarray, exaggeration: float, cmax: float,
    candidates, winner_id: str, title_text: str, camera: dict,
) -> bytes:
    n_rows, n_cols = elevation.shape
    x, y = np.arange(n_cols), np.arange(n_rows)
    wet = h_grid >= 0.01
    z_water = np.where(wet, elevation + h_grid * exaggeration, np.nan)
    color_water = np.where(wet, h_grid, np.nan)

    terrain = go.Surface(x=x, y=y, z=elevation, colorscale=TERRAIN_COLORSCALE, showscale=False)
    water = go.Surface(
        x=x, y=y, z=z_water, surfacecolor=color_water, cmin=0.0, cmax=cmax,
        colorscale=[[0, WATER_COLOR_LOW], [1, WATER_COLOR_HIGH]],
        showscale=False, opacity=0.9,
    )
    markers = go.Scatter3d(
        x=[c.col for c in candidates], y=[c.row for c in candidates],
        z=[c.elevation + elevation.max() * 0.02 for c in candidates],
        mode="markers",
        marker=dict(
            size=[8 if c.id == winner_id else 5 for c in candidates],
            color=["gold" if c.id == winner_id else "mediumseagreen" for c in candidates],
            line=dict(color="black", width=1),
        ),
    )

    fig = go.Figure(data=[terrain, water, markers])
    fig.update_layout(
        title=title_text,
        template="plotly_dark",
        scene=dict(
            xaxis_title="colonna", yaxis_title="riga", zaxis_title="quota (m)",
            aspectratio=dict(x=1, y=n_rows / n_cols, z=0.5),
            camera=camera,
        ),
        margin=dict(t=50, b=10, l=10, r=10),
        width=FRAME_WIDTH, height=FRAME_HEIGHT,
    )
    return fig.to_image(format="png")


def main() -> None:
    dem = load_dem_from_geotiff(DEM_PATH)
    dem_filled = fill_depressions(dem)
    elevation = dem_filled.elevation

    print("Rilevo candidati e trovo il vincitore...")
    candidates = detect_candidates(dem_filled)
    simulations = {c.id: simulate_flood_with_snapshots(dem_filled, c, n_snapshots=1)[0] for c in candidates}
    ranking = RankingAgent().process(simulations)
    winner_id = ranking.ranked_candidates[0]
    winner = next(c for c in candidates if c.id == winner_id)
    print(f"Vincitore: {winner_id}")

    print(f"Simulo con {N_FRAMES} frame...")
    result, frames = simulate_flood_with_snapshots(dem_filled, winner, n_snapshots=N_FRAMES)
    if not frames:
        print("ERRORE: nessuno snapshot catturato. Interrotto.")
        return

    max_depth = max(float(np.nanmax(h)) for _, h in frames)
    exaggeration = _compute_depth_exaggeration(elevation, max_depth)
    print(f"Fattore di esagerazione: {exaggeration:.1f}x")

    print(f"Renderizzo {len(frames)} fotogrammi 3D (può richiedere qualche minuto)...")
    pil_frames = []
    try:
        for i, (t_s, h_grid) in enumerate(frames):
            title = f"{winner_id} — t = {t_s/3600:.2f}h (acqua esagerata {exaggeration:.1f}x)"
            camera = _camera_for_frame(i, len(frames))
            png_bytes = _render_3d_frame_png(
                elevation, h_grid, exaggeration, max_depth, candidates, winner_id, title, camera
            )
            pil_frames.append(Image.open(io.BytesIO(png_bytes)).convert("RGB"))
            print(f"  fotogramma {i+1}/{len(frames)} completato")
    except Exception as exc:
        print(f"\nERRORE nel rendering 3D via kaleido: {exc}")
        print("Verifica di avere kaleido aggiornato: pip install -U kaleido")
        return

    out_path = OUTPUT_DIR / timestamped_filename("flood_animation_3d", "gif")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print("Salvo il GIF...")
    pil_frames[0].save(
        str(out_path), save_all=True, append_images=pil_frames[1:],
        duration=int(1000 / FPS), loop=0,
    )
    print(f"\nSalvato: {out_path.resolve()}")

    # MP4 opzionale: ricicliamo i PNG gia' renderizzati dentro una
    # FuncAnimation di matplotlib, invece di richiamare Plotly di nuovo.
    try:
        from matplotlib.animation import FFMpegWriter
        mp4_path = out_path.with_suffix(".mp4")
        fig, ax = plt.subplots(figsize=(FRAME_WIDTH / 100, FRAME_HEIGHT / 100))
        ax.axis("off")
        im = ax.imshow(np.array(pil_frames[0]))

        def update(i):
            im.set_data(np.array(pil_frames[i]))
            return (im,)

        anim = FuncAnimation(fig, update, frames=len(pil_frames), blit=True)
        anim.save(str(mp4_path), writer=FFMpegWriter(fps=FPS))
        plt.close(fig)
        print(f"Salvato anche: {mp4_path.resolve()} (mp4)")
    except (FileNotFoundError, RuntimeError):
        print("\n(mp4 non generato: ffmpeg non trovato — il GIF sopra funziona comunque ovunque)")


if __name__ == "__main__":
    main()
