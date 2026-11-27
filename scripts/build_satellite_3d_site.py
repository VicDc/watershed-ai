"""Pagina web 3D interattiva: terreno con la foto satellitare drappeggiata,
acqua del candidato vincitore con slider del tempo, e lettura live
dell'angolo della camera. Pensata per essere pubblicata (Cloudflare Pages).

Orientamento geografico corretto: x = est, y = nord. Le altre viste 3D
usano y = riga del raster, che mette il nord a y=0 e specchia la scena.

L'angolo mostrato e' l'azimut della camera in gradi, antiorario da est,
nella stessa convenzione di CAMERA_START_DEGREES in
scripts/export_flood_animation_3d.py (ma su assi nord-in-alto).
Il link della pagina si aggiorna con #az=..&el=.. per condividere la vista.

Uso:
    python -m scripts.build_satellite_3d_site
    git add site/index.html && git commit && git push   (Cloudflare Pages ripubblica dal repo)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import plotly.graph_objects as go
import rasterio
from PIL import Image
from scipy import ndimage

from app.agents.ranking_agent import RankingAgent
from app.hydrology.candidate_detection import detect_candidates
from app.hydrology.cellular_automata import FLOOD_SIM_PARAMS, simulate_flood_with_snapshots
from app.hydrology.priority_flood import fill_depressions
from app.ingestion.public_dem import load_dem_from_geotiff
from scripts.export_flood_animation_3d import _compute_depth_exaggeration
from scripts.export_flood_animation_satellite import fetch_satellite_array

DEM_PATH = "data/dem/copernicus_glo30_test.tif"
OUT_PATH = Path("site/index.html")  # versionato: Cloudflare Pages pubblica questa cartella dal repo
SATELLITE_SCALE = 3          # texture e griglia del terreno: 3x la risoluzione del DEM
N_SNAPSHOTS = 10
TERRAIN_Z_EXAGGERATION = 2.0  # come visualize_terrain_satellite_3d.py
DEFAULT_AZIMUTH_DEG = 45      # camera a nord-est: vista scelta per leggere il pendio
DEFAULT_ELEVATION_DEG = 16
CAMERA_RADIUS = 1.5


def _satellite_surface_colors(rgb: np.ndarray) -> tuple[np.ndarray, list]:
    """Plotly non applica texture: quantizzo la foto a 256 colori e uso
    l'indice come surfacecolor, con una colorscale fatta della palette."""
    quantized = Image.fromarray(rgb).quantize(colors=256, method=Image.Quantize.MEDIANCUT)
    palette = np.array(quantized.getpalette()[:256 * 3]).reshape(-1, 3)
    colorscale = [[i / 255, f"rgb({r},{g},{b})"] for i, (r, g, b) in enumerate(palette)]
    return np.array(quantized), colorscale


def main() -> None:
    dem = load_dem_from_geotiff(DEM_PATH)
    dem_filled = fill_depressions(dem)
    elevation = dem_filled.elevation
    n_rows, n_cols = elevation.shape
    cell = dem.cell_size_m

    print("Rilevo candidati e trovo il vincitore...")
    candidates = detect_candidates(dem_filled)
    simulations = {c.id: simulate_flood_with_snapshots(dem_filled, c, n_snapshots=1)[0] for c in candidates}
    winner_id = RankingAgent().process(simulations).ranked_candidates[0]
    winner = next(c for c in candidates if c.id == winner_id)
    print(f"Vincitore: {winner_id}. Simulo {N_SNAPSHOTS} snapshot...")
    _, frames = simulate_flood_with_snapshots(dem_filled, winner, n_snapshots=N_SNAPSHOTS)
    max_depth = max(float(h.max()) for _, h in frames)
    exaggeration = _compute_depth_exaggeration(elevation, max_depth)

    print("Scarico immagine satellitare (Esri World Imagery)...")
    with rasterio.open(DEM_PATH) as src:
        bbox = tuple(src.bounds)
    satellite = fetch_satellite_array(bbox, n_cols * SATELLITE_SCALE, n_rows * SATELLITE_SCALE)
    colors, colorscale = _satellite_surface_colors(satellite)
    fine_z = ndimage.zoom(elevation, (colors.shape[0] / n_rows, colors.shape[1] / n_cols), order=1)

    # Assi in metri, nord in alto: la riga 0 del raster (nord) va a y massimo.
    # Le matrici si capovolgono (::-1) per avere y crescente.
    width_m, height_m = (n_cols - 1) * cell, (n_rows - 1) * cell
    fine_x = np.linspace(0, width_m, colors.shape[1])
    fine_y = np.linspace(0, height_m, colors.shape[0])
    x = np.arange(n_cols) * cell
    y = np.arange(n_rows) * cell

    terrain = go.Surface(
        x=fine_x, y=fine_y, z=np.round(fine_z[::-1], 1), surfacecolor=colors[::-1],
        colorscale=colorscale, cmin=0, cmax=255, showscale=False, hoverinfo="skip",
        lighting=dict(ambient=0.8, diffuse=0.35, specular=0.05, roughness=1.0), name="Terreno",
    )

    water_frames = []
    for _, h in frames:
        wet = h >= FLOOD_SIM_PARAMS["min_depth_threshold_m"]
        z = np.where(wet, elevation + h * exaggeration, np.nan)[::-1]
        c = np.where(wet, h, np.nan)[::-1]
        to_list = lambda a: [[None if np.isnan(v) else round(float(v), 2) for v in row] for row in a]
        water_frames.append({"z": to_list(z), "c": to_list(c)})
    frame_labels = [f"t = {t / 3600:.2f} h" for t, _ in frames]

    water = go.Surface(
        x=x, y=y, z=water_frames[-1]["z"], surfacecolor=water_frames[-1]["c"], cmin=0, cmax=max_depth,
        colorscale=[[0, "rgb(127,184,216)"], [1, "rgb(0,51,102)"]], opacity=0.9,
        colorbar=dict(title="Profondità acqua (m)", len=0.6), name="Acqua",
    )
    markers = go.Scatter3d(
        x=[c.col * cell for c in candidates], y=[(n_rows - 1 - c.row) * cell for c in candidates],
        z=[c.elevation + 25 for c in candidates], mode="markers",
        marker=dict(size=[8 if c.id == winner_id else 5 for c in candidates],
                    color=["gold" if c.id == winner_id else "mediumseagreen" for c in candidates],
                    line=dict(color="black", width=1)),
        text=[f"{c.id}{' (vincitore)' if c.id == winner_id else ''}" for c in candidates],
        hoverinfo="text", name="Candidati",
    )
    z_label = float(elevation.max()) + 60
    compass = go.Scatter3d(
        x=[width_m / 2, width_m / 2, width_m, 0], y=[height_m, 0, height_m / 2, height_m / 2],
        z=[z_label] * 4, mode="text", text=["<b>N</b>", "S", "E", "O"],
        textfont=dict(size=[26, 20, 20, 20], color=["red", "white", "white", "white"]),
        hoverinfo="skip", name="Punti cardinali",
    )

    z_ratio = (float(elevation.max() - elevation.min()) * TERRAIN_Z_EXAGGERATION) / width_m
    fig = go.Figure(data=[terrain, water, markers, compass])  # l'acqua e' la traccia 1 (usata dal JS)
    fig.update_layout(
        template="plotly_dark", margin=dict(l=0, r=0, t=0, b=0), showlegend=False,
        scene=dict(
            xaxis=dict(title="est (m)"), yaxis=dict(title="nord (m)"), zaxis=dict(title="quota (m)"),
            aspectmode="manual", aspectratio=dict(x=1, y=height_m / width_m, z=z_ratio),
        ),
    )
    div_id = "terrain3d"
    plot_html = fig.to_html(full_html=False, include_plotlyjs="cdn", div_id=div_id,
                            config={"responsive": True, "displaylogo": False})

    html = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Watershed-AI 3D</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ font-family: system-ui, sans-serif; background: #111; color: #eee; margin: 0; padding: 12px 16px; }}
  h1 {{ font-size: 18px; font-weight: 600; margin: 4px 0 8px; }}
  .bar {{ display: flex; flex-wrap: wrap; gap: 10px 22px; align-items: center; margin: 8px 0; font-size: 14px; }}
  .readout {{ font-variant-numeric: tabular-nums; background: #1e1e1e; border: 1px solid #333; border-radius: 8px; padding: 8px 12px; }}
  .readout b {{ color: #f4d35e; font-size: 16px; }}
  input[type=range] {{ width: min(320px, 70vw); }}
  button {{ background: #2a9d8f; color: #fff; border: 0; padding: 6px 12px; border-radius: 6px; cursor: pointer; }}
  #{div_id} {{ height: 72vh; touch-action: none; }}
  .note {{ font-size: 12px; color: #999; }}
</style>
</head>
<body>
  <h1>Watershed-AI: terreno satellitare 3D e allagamento del candidato {winner_id}</h1>
  <div class="bar">
    <div class="readout">Azimut camera: <b id="az">-</b> &middot; vista da <span id="from">-</span> &middot; elevazione <span id="el">-</span></div>
    <label>Rotazione <input type="range" id="azSlider" min="0" max="359" step="1"></label>
    <button id="copy">Copia link a questa vista</button>
    <button id="shot">Scarica screenshot PNG</button>
  </div>
  <div class="bar">
    <label>Tempo <input type="range" id="timeSlider" min="0" max="{len(frames) - 1}" value="{len(frames) - 1}" step="1"></label>
    <span id="timeLabel">{frame_labels[-1]}</span>
    <span class="note">Acqua esagerata {exaggeration:.1f}x, rilievo esagerato {TERRAIN_Z_EXAGGERATION:.1f}x. Trascina per ruotare, rotella per zoom.</span>
  </div>
  {plot_html}
  <p class="note">Azimut in gradi, antiorario da est (0 = da est, 90 = da nord, 180 = da ovest, 270 = da sud), assi con il nord in alto.
  Immagine satellitare: Esri World Imagery (Esri, Maxar, Earthstar Geographics). DEM: Copernicus GLO-30.</p>
<script>
  const waterFrames = {json.dumps(water_frames)};
  const frameLabels = {json.dumps(frame_labels)};
  const plot = document.getElementById('{div_id}');
  const deg = r => r * 180 / Math.PI, rad = d => d * Math.PI / 180;
  const norm = d => ((Math.round(d) % 360) + 360) % 360;
  const names = ['est', 'nord-est', 'nord', 'nord-ovest', 'ovest', 'sud-ovest', 'sud', 'sud-est'];
  const frameHours = {json.dumps([round(t / 3600, 2) for t, _ in frames])};
  let radius = {CAMERA_RADIUS};
  const view = {{ az: 0, el: 0, frame: frameHours.length - 1 }};  // stato corrente, per il nome dello screenshot

  function show(eye) {{
    const az = norm(deg(Math.atan2(eye.y, eye.x)));
    const el = Math.round(deg(Math.atan2(eye.z, Math.hypot(eye.x, eye.y))));
    radius = Math.hypot(eye.x, eye.y, eye.z);
    view.az = az;
    view.el = el;
    document.getElementById('az').textContent = az + '°';
    document.getElementById('from').textContent = names[Math.round(az / 45) % 8];
    document.getElementById('el').textContent = el + '°';
    document.getElementById('azSlider').value = az;
    history.replaceState(null, '', '#az=' + az + '&el=' + el);
  }}
  function setCamera(az, el) {{
    const eye = {{ x: radius * Math.cos(rad(el)) * Math.cos(rad(az)),
                  y: radius * Math.cos(rad(el)) * Math.sin(rad(az)),
                  z: radius * Math.sin(rad(el)) }};
    Plotly.relayout(plot, {{ 'scene.camera.eye': eye }});
    show(eye);
  }}
  function currentEl() {{
    const e = plot._fullLayout.scene.camera.eye;
    return deg(Math.atan2(e.z, Math.hypot(e.x, e.y)));
  }}

  const hash = new URLSearchParams(location.hash.slice(1));
  setCamera(Number(hash.get('az') ?? {DEFAULT_AZIMUTH_DEG}), Number(hash.get('el') ?? {DEFAULT_ELEVATION_DEG}));

  const onCamera = ev => {{ const eye = ev['scene.camera'] && ev['scene.camera'].eye; if (eye) show(eye); }};
  plot.on('plotly_relayout', onCamera);
  plot.on('plotly_relayouting', onCamera);
  document.getElementById('azSlider').addEventListener('input', e => setCamera(Number(e.target.value), currentEl()));
  document.getElementById('copy').addEventListener('click', async e => {{
    try {{ await navigator.clipboard.writeText(location.href); e.target.textContent = 'Link copiato'; }}
    catch {{ e.target.textContent = 'Copia il link dalla barra'; }}
    setTimeout(() => e.target.textContent = 'Copia link a questa vista', 1500);
  }});
  document.getElementById('timeSlider').addEventListener('input', e => {{
    view.frame = Number(e.target.value);
    const f = waterFrames[view.frame];
    Plotly.restyle(plot, {{ z: [f.z], surfacecolor: [f.c] }}, [1]);
    document.getElementById('timeLabel').textContent = frameLabels[view.frame];
  }});
  // Nome file: watershed-ai_<vincitore>_az45_el16_t4.52h_20261127-2210.png
  document.getElementById('shot').addEventListener('click', () => {{
    const d = new Date(), p = n => String(n).padStart(2, '0');
    const stamp = `${{d.getFullYear()}}${{p(d.getMonth() + 1)}}${{p(d.getDate())}}-${{p(d.getHours())}}${{p(d.getMinutes())}}`;
    const name = `watershed-ai_{winner_id}_az${{view.az}}_el${{view.el}}_t${{frameHours[view.frame]}}h_${{stamp}}`;
    Plotly.downloadImage(plot, {{ format: 'png', filename: name, width: plot.clientWidth, height: plot.clientHeight, scale: 2 }});
  }});
</script>
</body>
</html>
"""
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(html, encoding="utf-8")
    print(f"Salvato: {OUT_PATH.resolve()} ({OUT_PATH.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
