"""Genera una vista 3D interattiva del terreno con l'acqua che sale nel
tempo, con uno SWITCH per alternare dal vivo (nel browser, senza
rigenerare nulla) tra:
  - vista ESAGERATA: profondita' acqua amplificata per essere visibile
    (necessario perche' pochi metri di profondita' sono invisibili su un
    terreno con centinaia di metri di dislivello)
  - vista REALE: scala 1:1 fisicamente corretta (quasi piatta, ma onesta)

Uso:
    python -m scripts.visualize_flood_3d
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import plotly.graph_objects as go

from app.agents.ranking_agent import RankingAgent
from app.core.naming import timestamped_filename
from app.hydrology.candidate_detection import detect_candidates
from app.hydrology.cellular_automata import simulate_flood_with_snapshots
from app.hydrology.flow_routing import compute_flow_direction, trace_flow_path
from app.hydrology.priority_flood import fill_depressions
from app.ingestion.public_dem import load_dem_from_geotiff

DEM_PATH = "data/dem/copernicus_glo30_test.tif"
OUTPUT_DIR = Path("output/maps")
N_SNAPSHOTS = 10
_TARGET_VISUAL_FRACTION = 0.12  # l'acqua esagerata occupa ~12% del range altimetrico
_ROUND_DECIMALS = 2             # arrotondamento per contenere la dimensione del file


def _compute_depth_exaggeration(elevation: np.ndarray, max_depth_observed: float) -> float:
    if max_depth_observed <= 1e-9:
        return 1.0
    elevation_range = float(elevation.max() - elevation.min())
    target_visual_height = elevation_range * _TARGET_VISUAL_FRACTION
    return max(1.0, target_visual_height / max_depth_observed)


def _grid_to_json_ready(arr: np.ndarray) -> list:
    """Converte una griglia NumPy (con eventuali NaN) in una lista di liste
    JSON-compatibile: NaN -> None (JSON non supporta NaN in modo standard,
    e JSON.parse in JS lo rifiuterebbe)."""
    rounded = np.round(arr, _ROUND_DECIMALS)
    return [[None if np.isnan(v) else float(v) for v in row] for row in rounded]


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

    max_depth_observed = max(float(np.nanmax(h)) if h.size else 0.0 for _, h in frames)
    exaggeration = _compute_depth_exaggeration(elevation, max_depth_observed)
    print(f"Profondita' massima osservata: {max_depth_observed:.2f}m")
    print(f"Fattore di esagerazione (vista esagerata): {exaggeration:.1f}x")

    n_wet_last = int(np.sum(frames[-1][1] >= 0.01))
    print(f"Celle bagnate nell'ultimo frame: {n_wet_last} (su {frames[-1][1].size} totali)")

    x = np.arange(n_cols)
    y = np.arange(n_rows)

    # Precalcolo, per OGNI frame temporale, sia la versione esagerata che
    # quella reale (scala 1:1) della superficie acqua, piu' il colore
    # (sempre la profondita' vera, indipendente dal fattore di esagerazione).
    frames_z_exagg, frames_z_standard, frames_color, frame_labels = [], [], [], []
    for t_s, h_grid in frames:
        wet = h_grid >= 0.01
        z_exagg = np.where(wet, elevation + h_grid * exaggeration, np.nan)
        z_standard = np.where(wet, elevation + h_grid, np.nan)
        color = np.where(wet, h_grid, np.nan)

        frames_z_exagg.append(_grid_to_json_ready(z_exagg))
        frames_z_standard.append(_grid_to_json_ready(z_standard))
        frames_color.append(_grid_to_json_ready(color))
        frame_labels.append(f"t = {t_s/3600:.2f} h")

    cmax = max(max_depth_observed, 0.01)

    terrain_surface = go.Surface(
        x=x, y=y, z=elevation,
        colorscale="earth",
        showscale=True,
        colorbar=dict(title="Quota terreno (m)", x=1.0),
        name="Terreno",
        opacity=1.0,
    )

    marker_colors = ["gold" if c.id == winner_id else "mediumseagreen" for c in candidates]
    marker_sizes = [8 if c.id == winner_id else 5 for c in candidates]
    candidate_markers = go.Scatter3d(
        x=[c.col for c in candidates],
        y=[c.row for c in candidates],
        z=[c.elevation + elevation.max() * 0.02 for c in candidates],
        mode="markers",
        marker=dict(size=marker_sizes, color=marker_colors, line=dict(color="black", width=1)),
        text=[f"{c.id} ({'vincitore' if c.id == winner_id else 'altro candidato'})" for c in candidates],
        hoverinfo="text",
        name="Candidati",
    )

    # Traccia acqua iniziale: frame 0, modalita' esagerata di default
    water_surface = go.Surface(
        x=x, y=y, z=frames_z_exagg[0],
        surfacecolor=frames_color[0],
        cmin=0.0, cmax=cmax,
        colorscale=[[0, "rgba(173,216,230,0.75)"], [1, "rgba(0,51,102,0.95)"]],
        showscale=True,
        colorbar=dict(title="Profondità acqua (m)", x=1.12),
        name="Acqua",
        opacity=0.9,
    )

    # Percorsi D8 dai candidati, una sola traccia con gap None tra un percorso e l'altro
    direction = compute_flow_direction(dem_filled)
    path_x, path_y, path_z = [], [], []
    for c in candidates:
        for r, col in trace_flow_path(direction, c.row, c.col):
            path_x.append(col)
            path_y.append(r)
            path_z.append(float(elevation[r, col]))
        path_x.append(None)
        path_y.append(None)
        path_z.append(None)
    flow_paths = go.Scatter3d(
        x=path_x, y=path_y, z=path_z, mode="lines",
        line=dict(color="cyan", width=4), hoverinfo="skip", name="Deflusso D8",
    )

    # L'ordine conta: lo script JS aggiorna l'acqua per indice (waterTraceIndex = 1)
    fig = go.Figure(data=[terrain_surface, water_surface, candidate_markers, flow_paths])
    fig.update_layout(
        title=f"Vista 3D — candidato vincitore {winner_id}",
        template="plotly_dark",
        scene=dict(
            xaxis_title="colonna",
            yaxis_title="riga",
            zaxis_title="quota (m)",
            aspectratio=dict(x=1, y=n_rows / n_cols, z=0.5),
            # camera di default Plotly (1.25, 1.25, 1.25) ruotata di -180°: l'acqua in primo piano
            camera=dict(eye=dict(x=-1.25, y=-1.25, z=1.25)),
        ),
        margin=dict(t=60, b=10),
        legend=dict(x=0.01, y=0.99),  # in alto a sinistra, lontano dalle colorbar a destra
    )

    div_id = "flood3dplot"
    plotly_config = {"responsive": True, "scrollZoom": True, "displaylogo": False}
    plot_html = fig.to_html(full_html=False, include_plotlyjs=True, div_id=div_id, config=plotly_config)

    html = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<title>Vista 3D — {winner_id}</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #111; color: #eee; margin: 0; padding: 20px; }}
  h1 {{ font-size: 18px; font-weight: 500; }}
  .controls {{ margin: 16px 0; display: flex; align-items: center; gap: 20px; flex-wrap: wrap; }}
  .mode-controls {{ display: flex; align-items: center; gap: 12px; padding: 8px 14px; background: #1e1e1e; border-radius: 8px; border: 1px solid #333; }}
  .mode-controls label {{ display: flex; align-items: center; gap: 5px; font-size: 13px; cursor: pointer; }}
  input[type="range"] {{ width: 350px; }}
  #frameLabel3d {{ font-variant-numeric: tabular-nums; min-width: 90px; display: inline-block; }}
  #modeNote {{ font-size: 12px; color: #f4a261; }}
  button {{ background: #2a9d8f; color: white; border: none; padding: 6px 14px; border-radius: 5px; cursor: pointer; font-size: 13px; }}
  button:hover {{ background: #238b7e; }}

  /* Su mobile, senza questa regola il browser intercetta il trascinamento
     con un dito come scroll della pagina invece di passarlo a Plotly per
     ruotare la vista 3D — bug comune di Plotly su touch screen. */
  #{div_id} {{ touch-action: none; }}
</style>
</head>
<body>
  <h1>Vista 3D — candidato vincitore {winner_id}</h1>

  <div class="controls">
    <div>
      <label for="timeSlider3d">Tempo:</label>
      <input type="range" id="timeSlider3d" min="0" max="{len(frames) - 1}" value="0" step="1">
      <span id="frameLabel3d">{frame_labels[0]}</span>
    </div>
    <button id="playBtn3d">▶ Play</button>
  </div>

  <div class="mode-controls">
    <strong>Vista acqua:</strong>
    <label><input type="radio" name="waterMode" value="exagg" checked> Esagerata ({exaggeration:.1f}x, visibile)</label>
    <label><input type="radio" name="waterMode" value="standard"> Reale (scala 1:1, fisicamente corretta)</label>
    <span id="modeNote"></span>
  </div>

  {plot_html}

<script>
  const framesZExagg = {json.dumps(frames_z_exagg)};
  const framesZStandard = {json.dumps(frames_z_standard)};
  const framesColor = {json.dumps(frames_color)};
  const frameLabels = {json.dumps(frame_labels)};
  const cmin3d = 0.0;
  const cmax3d = {cmax};
  const waterTraceIndex = 1;

  let currentFrame = 0;
  let currentMode = 'exagg';
  let playInterval = null;

  const plotDiv = document.getElementById('{div_id}');
  const timeSlider = document.getElementById('timeSlider3d');
  const frameLabelEl = document.getElementById('frameLabel3d');
  const playBtn = document.getElementById('playBtn3d');
  const modeNote = document.getElementById('modeNote');
  const modeRadios = document.querySelectorAll('input[name="waterMode"]');

  function updateWaterSurface() {{
    const zData = currentMode === 'exagg' ? framesZExagg[currentFrame] : framesZStandard[currentFrame];
    Plotly.restyle(plotDiv, {{
      z: [zData],
      surfacecolor: [framesColor[currentFrame]],
      cmin: [cmin3d],
      cmax: [cmax3d],
    }}, [waterTraceIndex]);
    frameLabelEl.textContent = frameLabels[currentFrame];
    modeNote.textContent = currentMode === 'standard'
      ? '(profondità reale: potrebbe risultare quasi piatta/invisibile)'
      : '';
  }}

  timeSlider.addEventListener('input', () => {{
    currentFrame = parseInt(timeSlider.value, 10);
    updateWaterSurface();
  }});

  modeRadios.forEach((radio) => {{
    radio.addEventListener('change', () => {{
      currentMode = radio.value;
      updateWaterSurface();
    }});
  }});

  playBtn.addEventListener('click', () => {{
    if (playInterval) {{
      clearInterval(playInterval);
      playInterval = null;
      playBtn.textContent = '▶ Play';
      return;
    }}
    playBtn.textContent = '⏸ Pausa';
    playInterval = setInterval(() => {{
      currentFrame = (currentFrame + 1) % framesZExagg.length;
      timeSlider.value = currentFrame;
      updateWaterSurface();
      if (currentFrame === framesZExagg.length - 1) {{
        clearInterval(playInterval);
        playInterval = null;
        playBtn.textContent = '▶ Play';
      }}
    }}, 700);
  }});
</script>
</body>
</html>
"""

    out_path = OUTPUT_DIR / timestamped_filename("flood_3d", "html")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"\nSalvato: {out_path.resolve()}")
    print("Apri il file: trascina per ruotare, rotella per zoom, radio button per Esagerata/Reale.")


if __name__ == "__main__":
    main()
