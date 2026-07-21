"""Genera una pagina HTML con overlay satellite + acqua, con uno slider
TEMPORALE (non di trasparenza) per vedere come l'acqua si espande nel
tempo sul terreno reale, per il candidato vincitore della classifica.

Uso:
    python -m scripts.visualize_flood_timelapse
"""
import base64
import sys
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib

matplotlib.use("Agg")
import numpy as np
import rasterio
import requests
from PIL import Image

from app.agents.ranking_agent import RankingAgent
from app.core.naming import timestamped_filename
from app.hydrology.candidate_detection import detect_candidates
from app.hydrology.cellular_automata import FLOOD_SIM_PARAMS, simulate_flood_with_snapshots
from app.hydrology.priority_flood import fill_depressions
from app.ingestion.public_dem import load_dem_from_geotiff

DEM_PATH = "data/dem/copernicus_glo30_test.tif"
OUTPUT_DIR = Path("output/maps")
SCALE = 6
N_SNAPSHOTS = 12
ESRI_EXPORT_URL = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/"
    "World_Imagery/MapServer/export"
)

# Gradiente colore acqua: poca profondita' -> azzurro chiaro, molta
# profondita' -> blu scuro. L'alpha ha un PAVIMENTO minimo (ALPHA_FLOOR):
# senza di esso, la profondita' massima (vicino al punto sorgente) domina
# la normalizzazione e la maggior parte dell'area allagata, molto più
# sottile, diventa quasi invisibile (bug riscontrato: mediana ~12% di
# opacita', un terzo delle celle bagnate sotto l'8% -> sembravano "pochi
# punti" invece di un'area allagata continua). La scala a radice quadrata
# (invece che lineare) inoltre comprime meno i valori bassi, dando più
# contrasto visivo alle zone poco profonde.
_WATER_LIGHT = np.array([173, 216, 230])
_WATER_DARK = np.array([0, 51, 102])
_WATER_ALPHA_FLOOR = 90    # su 255: opacita' minima per QUALSIASI cella bagnata
_WATER_ALPHA_MAX = 230     # su 255: opacita' massima (celle piu' profonde)


def fetch_satellite_image(bbox: tuple[float, float, float, float], width: int, height: int) -> bytes:
    params = {
        "bbox": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}",
        "bboxSR": "4326",
        "imageSR": "4326",
        "size": f"{width},{height}",
        "format": "png32",
        "f": "image",
    }
    resp = requests.get(ESRI_EXPORT_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.content


def render_water_overlay_png(h: np.ndarray, width: int, height: int, depth_norm: float) -> bytes:
    """Renderizza la griglia di profondita' acqua come PNG RGBA trasparente
    (trasparente dove non c'e' acqua, azzurro->blu scuro dove c'e').

    L'intensita' visiva (colore e alpha) usa sqrt(depth/depth_norm) invece
    di depth/depth_norm lineare, e l'alpha ha un pavimento minimo per le
    celle bagnate: senza questi due accorgimenti, la profondita' massima
    (quasi sempre vicino al punto sorgente) schiaccia il resto dell'area
    allagata a un'opacita' quasi nulla, rendendola invisibile sopra il
    satellite anche a slider di trasparenza al massimo.
    """
    depth_norm_safe = max(depth_norm, 1e-6)
    wet_mask = h >= FLOOD_SIM_PARAMS["min_depth_threshold_m"]

    t_linear = np.clip(h / depth_norm_safe, 0.0, 1.0)
    t_visual = np.sqrt(t_linear)  # boost percettivo delle profondita' basse

    rgb = (_WATER_LIGHT * (1 - t_visual[..., None]) + _WATER_DARK * t_visual[..., None]).astype(np.uint8)
    alpha_wet = _WATER_ALPHA_FLOOR + t_visual * (_WATER_ALPHA_MAX - _WATER_ALPHA_FLOOR)
    alpha = np.where(wet_mask, alpha_wet, 0).astype(np.uint8)

    rgba = np.dstack([rgb, alpha])
    img = Image.fromarray(rgba, mode="RGBA")
    img = img.resize((width, height), Image.BILINEAR)

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def to_data_uri(png_bytes: bytes) -> str:
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"


def main() -> None:
    dem = load_dem_from_geotiff(DEM_PATH)
    dem_filled = fill_depressions(dem)
    n_rows, n_cols = dem_filled.elevation.shape

    print("Rilevo candidati e simulo per trovare il vincitore...")
    candidates = detect_candidates(dem_filled)
    simulations = {c.id: simulate_flood_with_snapshots(dem_filled, c, n_snapshots=1)[0] for c in candidates}
    ranking = RankingAgent().process(simulations)
    winner_id = ranking.ranked_candidates[0]
    winner = next(c for c in candidates if c.id == winner_id)
    print(f"Vincitore: {winner_id} (area finale {ranking.scores[winner_id]:.0f}m2)")

    print(f"Simulo con {N_SNAPSHOTS} snapshot temporali per il vincitore...")
    result, frames = simulate_flood_with_snapshots(dem_filled, winner, n_snapshots=N_SNAPSHOTS)
    if not frames:
        print("ERRORE: nessuno snapshot catturato (simulazione troppo corta?). Interrotto.")
        return

    depth_norm = max(grid.max() for _, grid in frames)
    print(f"Profondita' massima osservata (per normalizzare il colore): {depth_norm:.2f}m")

    with rasterio.open(DEM_PATH) as src:
        minx, miny, maxx, maxy = src.bounds
    bbox = (minx, miny, maxx, maxy)
    print(f"Bounding box geografico: {bbox}")

    width, height = n_cols * SCALE, n_rows * SCALE

    print("Scarico immagine satellitare (Esri World Imagery)...")
    try:
        satellite_bytes = fetch_satellite_image(bbox, width, height)
    except requests.RequestException as exc:
        print(f"ERRORE nel download del satellite: {exc}")
        return

    print("Renderizzo i frame dell'acqua...")
    frame_data_uris = []
    frame_labels = []
    for t_s, grid in frames:
        png_bytes = render_water_overlay_png(grid, width, height, depth_norm)
        frame_data_uris.append(to_data_uri(png_bytes))
        hours = t_s / 3600
        area_at_t = None
        # trova l'area corrispondente nel FloodTimeSeries per questo istante
        for ts, area in zip(result.time_steps_s, result.area_flooded_m2):
            if abs(ts - t_s) < 1e-6:
                area_at_t = area
                break
        label = f"t = {hours:.2f} h" + (f" — area {area_at_t:.0f} m²" if area_at_t is not None else "")
        frame_labels.append(label)

    # Marker di tutti i candidati (goccia), vincitore evidenziato
    markers_html = []
    for c in candidates:
        is_winner = c.id == winner_id
        css_class = "winner shape-pin" if is_winner else "other"
        left_pct = (c.col + 0.5) / n_cols * 100
        top_pct = (c.row + 0.5) / n_rows * 100
        title = f"{c.id} | quota {c.elevation:.1f}m | area finale {ranking.scores[c.id]:.0f}m²"
        markers_html.append(
            f'<div class="marker {css_class}" style="left:{left_pct:.3f}%; top:{top_pct:.3f}%;" title="{title}"></div>'
        )

    frames_js_array = "[" + ",".join(f'"{uri}"' for uri in frame_data_uris) + "]"
    labels_js_array = "[" + ",".join(f'"{lbl}"' for lbl in frame_labels) + "]"

    html = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<title>Espansione acqua nel tempo — {winner_id}</title>
<style>
  :root {{
    --marker-size: 12px;
    --marker-border-width: 1.5px;
    --marker-border-color: #111;
    --color-winner: #ffd60a;
    --color-other: #2a9d8f;
  }}
  body {{ font-family: system-ui, sans-serif; background: #1a1a1a; color: #eee; margin: 0; padding: 20px; }}
  h1 {{ font-size: 18px; font-weight: 500; }}
  p.sub {{ color: #aaa; font-size: 13px; margin-top: -8px; }}

  .container {{
    position: relative;
    width: {width}px;
    height: {height}px;
    max-width: 100%;
    overflow: auto;
  }}
  .container img {{ position: absolute; top: 0; left: 0; width: {width}px; height: {height}px; display: block; }}
  #waterLayer {{ opacity: 0.85; }}

  .marker {{
    position: absolute;
    width: var(--marker-size);
    height: var(--marker-size);
    border: var(--marker-border-width) solid var(--marker-border-color);
    border-radius: 50% 50% 50% 0;
    transform: translate(-50%, -50%) rotate(-45deg);
    cursor: pointer;
    z-index: 10;
    box-sizing: border-box;
  }}
  .marker.other {{ background: var(--color-other); opacity: 0.85; }}

  /* Il vincitore ha una base comune (posizione/z-index), e la FORMA vera
     e propria è una classe aggiuntiva (.shape-pin / .shape-star /
     .shape-badge / .shape-mountain) attivata dai radio button in pagina —
     così si può cambiare aspetto senza toccare i dati o rigenerare nulla. */
  .marker.winner {{
    position: absolute;
    cursor: pointer;
    z-index: 10;
  }}

  /* Pin stile Google Maps: cerchio + punta, via pseudo-elementi (una
     punta dritta verso il basso non è ottenibile da una singola forma
     con border-radius/clip-path). Ancorato per la PUNTA: translate
     (-50%,-100%) porta il bordo inferiore del box — dove cade la punta —
     esattamente sulla coordinata del candidato. */
  .marker.winner.shape-pin {{
    width: 26px;
    height: 34px;
    transform: translate(-50%, -100%);
    filter: drop-shadow(0 0 1.5px #000) drop-shadow(0 0 1.5px #000);
  }}
  .marker.winner.shape-pin::before {{
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    width: 26px;
    height: 26px;
    background: var(--color-winner);
    border-radius: 50%;
  }}
  .marker.winner.shape-pin::after {{
    content: "";
    position: absolute;
    top: 20px;
    left: 50%;
    transform: translateX(-50%);
    width: 0;
    height: 0;
    border-left: 7px solid transparent;
    border-right: 7px solid transparent;
    border-top: 14px solid var(--color-winner);
  }}

  /* Stella: ancorata al centro (non ha una "punta" univoca). */
  .marker.winner.shape-star {{
    width: 24px;
    height: 24px;
    background: var(--color-winner);
    transform: translate(-50%, -50%);
    clip-path: polygon(
      50% 0%, 61% 35%, 98% 35%, 68% 57%, 79% 91%,
      50% 70%, 21% 91%, 32% 57%, 2% 35%, 39% 35%
    );
    filter: drop-shadow(0 0 1.5px #000) drop-shadow(0 0 1.5px #000);
  }}

  /* Badge numerato: cerchio pieno con "1" al centro (::after, così il div
     resta sempre vuoto e le altre forme non ereditano testo indesiderato). */
  .marker.winner.shape-badge {{
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: var(--color-winner);
    border: 1.5px solid #000;
    transform: translate(-50%, -50%);
    box-sizing: border-box;
  }}
  .marker.winner.shape-badge::after {{
    content: "1";
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    font-weight: bold;
    font-size: 13px;
    color: #000;
  }}

  /* Picco/montagna: coerente col fatto che i candidati sono vette del DEM. */
  .marker.winner.shape-mountain {{
    width: 26px;
    height: 22px;
    background: var(--color-winner);
    border: 1.5px solid #000;
    box-sizing: border-box;
    transform: translate(-50%, -50%);
    clip-path: polygon(50% 0%, 0% 100%, 100% 100%);
  }}

  .controls {{ margin: 16px 0; display: flex; align-items: center; gap: 12px; }}
  .shape-controls label {{ display: flex; align-items: center; gap: 4px; font-size: 13px; font-weight: normal; }}
  .shape-controls input[type="radio"] {{ width: auto; margin: 0; }}
  input[type="range"] {{ width: 400px; }}
  #timeLabel {{ font-variant-numeric: tabular-nums; min-width: 220px; display: inline-block; }}
  #opacityValue {{ min-width: 45px; display: inline-block; }}

  .legend {{ margin-top: 12px; font-size: 13px; display: flex; align-items: center; gap: 16px; }}
  .legend-item {{ display: flex; align-items: center; gap: 6px; }}
  .legend-swatch {{
    width: var(--marker-size); height: var(--marker-size);
    border: var(--marker-border-width) solid var(--marker-border-color);
    border-radius: 50% 50% 50% 0; transform: rotate(-45deg); box-sizing: border-box;
  }}
  .legend-swatch.winner {{
    background: var(--color-winner);
    border: var(--marker-border-width) solid var(--marker-border-color);
    border-radius: 50%; transform: none;
  }}
  .legend-swatch.other {{ background: var(--color-other); }}
  .legend-gradient {{
    width: 120px; height: 12px;
    background: linear-gradient(to right, rgba(173,216,230,0.3), rgba(0,51,102,0.85));
    border: 1px solid #555; display: inline-block; vertical-align: middle;
  }}
</style>
</head>
<body>
  <h1>Espansione dell'acqua nel tempo — candidato vincitore {winner_id}</h1>
  <p class="sub">Portata simulata {FLOOD_SIM_PARAMS['flow_rate_m3_s']} m³/s — profondità massima osservata {depth_norm:.2f} m</p>

  <div class="controls">
    <label for="timeSlider">Tempo:</label>
    <input type="range" id="timeSlider" min="0" max="{len(frame_data_uris) - 1}" value="0" step="1">
    <span id="timeLabel">{frame_labels[0]}</span>
  </div>
  <div class="controls">
    <label for="opacitySlider">Trasparenza acqua:</label>
    <input type="range" id="opacitySlider" min="0" max="100" value="85">
    <span id="opacityValue">85%</span>
  </div>
  <div class="controls shape-controls">
    <label>Forma vincitore:</label>
    <label><input type="radio" name="winnerShape" value="shape-pin" checked> Pin</label>
    <label><input type="radio" name="winnerShape" value="shape-star"> Stella</label>
    <label><input type="radio" name="winnerShape" value="shape-badge"> Badge</label>
    <label><input type="radio" name="winnerShape" value="shape-mountain"> Montagna</label>
  </div>

  <div class="container">
    <img id="satelliteLayer" src="{to_data_uri(satellite_bytes)}" alt="satellite">
    <img id="waterLayer" src="{frame_data_uris[0]}" alt="acqua">
    {''.join(markers_html)}
  </div>

  <div class="legend">
    <div class="legend-item"><span class="legend-swatch winner"></span> candidato vincitore</div>
    <div class="legend-item"><span class="legend-swatch other"></span> altri candidati</div>
    <div class="legend-item">profondità acqua: <span class="legend-gradient"></span> bassa &rarr; alta</div>
  </div>

<script>
  const frames = {frames_js_array};
  const labels = {labels_js_array};
  const timeSlider = document.getElementById('timeSlider');
  const opacitySlider = document.getElementById('opacitySlider');
  const waterLayer = document.getElementById('waterLayer');
  const timeLabel = document.getElementById('timeLabel');
  const opacityValue = document.getElementById('opacityValue');

  timeSlider.addEventListener('input', () => {{
    const i = parseInt(timeSlider.value, 10);
    waterLayer.src = frames[i];
    timeLabel.textContent = labels[i];
  }});

  opacitySlider.addEventListener('input', () => {{
    waterLayer.style.opacity = opacitySlider.value / 100;
    opacityValue.textContent = opacitySlider.value + '%';
  }});

  const winnerMarker = document.querySelector('.marker.winner');
  const shapeRadios = document.querySelectorAll('input[name="winnerShape"]');
  const allShapeClasses = ['shape-pin', 'shape-star', 'shape-badge', 'shape-mountain'];
  shapeRadios.forEach((radio) => {{
    radio.addEventListener('change', () => {{
      winnerMarker.classList.remove(...allShapeClasses);
      winnerMarker.classList.add(radio.value);
    }});
  }});
</script>
</body>
</html>
"""

    output_path = OUTPUT_DIR / timestamped_filename("flood_timelapse", "html")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"\nSalvato: {output_path.resolve()}")
    print("Apri il file nel browser e usa lo slider per vedere l'acqua espandersi nel tempo.")


if __name__ == "__main__":
    main()
