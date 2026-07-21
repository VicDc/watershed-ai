"""Esporta l'espansione dell'acqua nel tempo come file GIF autonomo
(nessuna dipendenza esterna tipo ffmpeg), mostrabile ovunque: presentazioni,
messaggistica, allegato email — a differenza degli HTML interattivi, non
richiede un browser per essere visto.

Uso:
    python -m scripts.export_flood_animation
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation, PillowWriter

from app.agents.ranking_agent import RankingAgent
from app.core.naming import timestamped_filename
from app.hydrology.candidate_detection import detect_candidates
from app.hydrology.cellular_automata import FLOOD_SIM_PARAMS, simulate_flood_with_snapshots
from app.hydrology.priority_flood import fill_depressions
from app.ingestion.public_dem import load_dem_from_geotiff

DEM_PATH = "data/dem/copernicus_glo30_test.tif"
OUTPUT_DIR = Path("output/animations")
N_FRAMES = 20        # più frame = animazione più fluida, ma file più pesante
FPS = 4              # velocità di riproduzione
DPI = 110


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

    print(f"Simulo con {N_FRAMES} frame per l'animazione...")
    result, frames = simulate_flood_with_snapshots(dem_filled, winner, n_snapshots=N_FRAMES)
    if not frames:
        print("ERRORE: nessuno snapshot catturato. Interrotto.")
        return

    fig, ax = plt.subplots(figsize=(9, 7))
    ax.imshow(elevation, cmap="terrain", origin="upper")
    ax.plot(winner.col, winner.row, "*", color="gold", markersize=20, markeredgecolor="black", zorder=5)
    ax.set_xlabel("colonna")
    ax.set_ylabel("riga")
    title = ax.set_title("")

    # Placeholder iniziale per l'overlay acqua, aggiornato ad ogni frame
    water_im = ax.imshow(
        np.ma.masked_all_like(elevation),
        cmap="Blues", alpha=0.8, origin="upper", vmin=0,
        vmax=max(float(np.nanmax(h)) for _, h in frames),
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

    out_path = OUTPUT_DIR / timestamped_filename("flood_animation", "gif")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print("Salvo il GIF (può richiedere qualche secondo)...")
    anim.save(str(out_path), writer=PillowWriter(fps=FPS), dpi=DPI)
    plt.close(fig)

    print(f"\nSalvato: {out_path.resolve()}")

    # Tentativo opzionale di MP4, solo se ffmpeg e' disponibile nel sistema
    try:
        from matplotlib.animation import FFMpegWriter
        mp4_path = out_path.with_suffix(".mp4")
        fig2, ax2 = plt.subplots(figsize=(9, 7))
        ax2.imshow(elevation, cmap="terrain", origin="upper")
        ax2.plot(winner.col, winner.row, "*", color="gold", markersize=20, markeredgecolor="black", zorder=5)
        water_im2 = ax2.imshow(
            np.ma.masked_all_like(elevation), cmap="Blues", alpha=0.8, origin="upper",
            vmin=0, vmax=max(float(np.nanmax(h)) for _, h in frames),
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
        print(f"Salvato anche: {mp4_path.resolve()} (mp4, più leggero del gif)")
    except (FileNotFoundError, RuntimeError):
        print("\n(mp4 non generato: ffmpeg non trovato sul sistema — il GIF sopra funziona comunque ovunque)")


if __name__ == "__main__":
    main()
