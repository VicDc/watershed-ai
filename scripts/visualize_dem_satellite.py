"""Genera una pagina HTML con overlay DEM colorato + immagine satellitare,
con uno slider di trasparenza regolabile in tempo reale nel browser.

Il satellite viene scaricato da Esri World Imagery (servizio pubblico,
nessuna API key richiesta) per il bounding box esatto del DEM caricato.

Uso:
    python -m scripts.visualize_dem_satellite
"""
import base64
import sys
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
import requests

from app.core.naming import timestamped_filename
from app.hydrology.candidate_detection import (
    CANDIDATE_DETECTION_PARAMS,
    _compute_watershed_area,
    _estimate_prominence,
    _find_local_maxima,
)
from app.hydrology.flow_routing import compute_flow_direction, trace_flow_path
from app.hydrology.priority_flood import fill_depressions
from app.ingestion.public_dem import load_dem_from_geotiff

DEM_PATH = "data/dem/copernicus_glo30_test.tif"
OUTPUT_DIR = Path("output/maps")
SCALE = 6  # fattore di upscaling per la risoluzione delle immagini (n_cols*SCALE px)
ESRI_EXPORT_URL = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/"
    "World_Imagery/MapServer/export"
)


def fetch_satellite_image(bbox: tuple[float, float, float, float], width: int, height: int) -> bytes:
    """Scarica un'immagine satellitare PNG per il bbox dato (minx, miny, maxx, maxy)."""
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


def render_elevation_png(elevation: np.ndarray, width: int, height: int) -> bytes:
    """Renderizza il DEM colorato come PNG, senza assi/margini, alla risoluzione data."""
    dpi = 100
    fig = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.imshow(elevation, cmap="terrain", aspect="auto")
    ax.axis("off")

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=dpi)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def to_data_uri(png_bytes: bytes) -> str:
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"


def main() -> None:
    dem = load_dem_from_geotiff(DEM_PATH)
    dem_filled = fill_depressions(dem)
    elevation = dem_filled.elevation
    n_rows, n_cols = elevation.shape

    # Bbox geografico letto DIRETTAMENTE dal GeoTIFF via rasterio, non
    # ricostruito da dem.cell_size_m: quel campo ora rappresenta metri
    # veri (fix Fase 3 per la simulazione), non piu' gradi, quindi
    # moltiplicarlo per n_cols/n_rows darebbe un bbox completamente
    # sbagliato (bug reale riscontrato: bbox di migliaia di gradi).
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
        print("Verifica la connessione internet, o riprova piu' tardi (il servizio e' pubblico e gratuito ma puo' avere rate limit).")
        return

    print("Renderizzo il DEM colorato...")
    dem_png = render_elevation_png(elevation, width, height)

    # Candidati per i marker sempre visibili
    maxima = _find_local_maxima(elevation, CANDIDATE_DETECTION_PARAMS["local_max_window_cells"])
    markers_html = []
    direction = compute_flow_direction(dem_filled)
    path_polylines = []
    for row, col in maxima:
        prom, border_limited = _estimate_prominence(elevation, row, col)
        area = _compute_watershed_area(elevation, row, col)
        passes_prominence = border_limited or prom >= CANDIDATE_DETECTION_PARAMS["min_prominence_m"]
        passes_area = area >= CANDIDATE_DETECTION_PARAMS["min_watershed_area_cells"]
        passes = passes_prominence and passes_area

        # Ogni categoria ha un colore E una forma distinti (non solo
        # colore), cosi' resta leggibile anche per chi ha una qualche
        # forma di daltonismo (WCAG: non affidarsi al solo colore).
        if not passes:
            css_class = "discarded"   # rosso, triangolo
        elif border_limited:
            css_class = "border-limited"  # arancione, rombo
        else:
            css_class = "valid"       # verde, cerchio

        if passes:  # percorso di deflusso D8, coordinate = centro cella (colonna, riga)
            points = " ".join(f"{c + 0.5},{r + 0.5}" for r, c in trace_flow_path(direction, row, col))
            path_polylines.append(f'<polyline points="{points}" />')

        left_pct = (col + 0.5) / n_cols * 100
        top_pct = (row + 0.5) / n_rows * 100
        prom_label = f">= {prom:.1f}" if border_limited else f"{prom:.1f}"
        title = f"quota {elevation[row, col]:.1f}m | prominenza {prom_label}m | bacino {area} celle"

        markers_html.append(
            f'<div class="marker {css_class}" style="left:{left_pct:.3f}%; top:{top_pct:.3f}%;" '
            f'title="{title}"></div>'
        )

    html = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<title>DEM + Satellite overlay</title>
<style>
  :root {{
    /* Variabili facilmente modificabili per personalizzare i marker */
    --marker-size: 12px;
    --marker-border-width: 1.5px;
    --marker-border-color: #111;
    --color-valid: #2a9d8f;
    --color-border-limited: #f4a261;
    --color-discarded: #e63946;
    --dem-default-opacity: 0.6;
  }}
  body {{ font-family: system-ui, sans-serif; background: #1a1a1a; color: #eee; margin: 0; padding: 20px; }}
  h1 {{ font-size: 18px; font-weight: 500; }}

  /* FIX: senza width+height espliciti in pixel, un container
     position:relative con soli figli position:absolute collassa ad
     altezza zero -> i marker con top:X% diventano invalidi e finiscono
     tutti ammassati in alto. Uso pixel fissi (non aspect-ratio) per
     eliminare qualunque ambiguita' di supporto/calcolo nel browser. */
  .container {{
    position: relative;
    width: {width}px;
    height: {height}px;
    max-width: 100%;
    overflow: auto;
  }}
  .container img {{ position: absolute; top: 0; left: 0; width: {width}px; height: {height}px; display: block; }}
  #demLayer {{ opacity: var(--dem-default-opacity); }}
  /* Percorsi D8 sopra le immagini, sotto i marker */
  .flow-paths {{ position: absolute; top: 0; left: 0; width: {width}px; height: {height}px; z-index: 5; pointer-events: none; }}
  .flow-paths polyline {{ fill: none; stroke: cyan; stroke-width: 2; stroke-opacity: 0.9; vector-effect: non-scaling-stroke; }}
  .legend-line {{ width: 22px; height: 0; border-top: 2px solid cyan; flex-shrink: 0; }}

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
  .marker.valid {{ background: var(--color-valid); border-style: solid; }}
  .marker.border-limited {{ background: var(--color-border-limited); border-style: dashed; }}
  .marker.discarded {{ background: var(--color-discarded); border-style: dotted; opacity: 0.85; }}

  .controls {{ margin: 16px 0; display: flex; align-items: center; gap: 12px; }}
  input[type="range"] {{ width: 300px; }}

  .legend {{ margin-top: 12px; font-size: 13px; display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }}
  .legend-item {{ display: flex; align-items: center; gap: 6px; }}
  .legend-swatch {{
    width: var(--marker-size); height: var(--marker-size);
    border: var(--marker-border-width) solid var(--marker-border-color);
    border-radius: 50% 50% 50% 0;
    transform: rotate(-45deg);
    box-sizing: border-box; flex-shrink: 0;
  }}
  .legend-swatch.valid {{ background: var(--color-valid); border-style: solid; }}
  .legend-swatch.border-limited {{ background: var(--color-border-limited); border-style: dashed; }}
  .legend-swatch.discarded {{ background: var(--color-discarded); border-style: dotted; opacity: 0.85; }}
</style>
</head>
<body>
  <h1>DEM {n_rows}x{n_cols} — overlay elevazione / satellite</h1>
  <div class="controls">
    <label for="opacitySlider">Trasparenza elevazione:</label>
    <input type="range" id="opacitySlider" min="0" max="100" value="60">
    <span id="opacityValue">60%</span>
  </div>
  <div class="container">
    <img id="satelliteLayer" src="{to_data_uri(satellite_bytes)}" alt="satellite">
    <img id="demLayer" src="{to_data_uri(dem_png)}" alt="dem">
    <svg class="flow-paths" viewBox="0 0 {n_cols} {n_rows}" preserveAspectRatio="none">{''.join(path_polylines)}</svg>
    {''.join(markers_html)}
  </div>
  <div class="legend">
    <div class="legend-item"><span class="legend-swatch valid"></span> candidato valido (sella reale)</div>
    <div class="legend-item"><span class="legend-swatch border-limited"></span> candidato valido (limite bordo)</div>
    <div class="legend-item"><span class="legend-swatch discarded"></span> scartato</div>
    <div class="legend-item"><span class="legend-line"></span> deflusso D8 dai candidati validi</div>
  </div>
<script>
  const slider = document.getElementById('opacitySlider');
  const demLayer = document.getElementById('demLayer');
  const label = document.getElementById('opacityValue');
  slider.addEventListener('input', () => {{
    demLayer.style.opacity = slider.value / 100;
    label.textContent = slider.value + '%';
  }});
</script>
</body>
</html>
"""

    output_path = OUTPUT_DIR / timestamped_filename("dem_satellite_overlay", "html")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"\nSalvato: {output_path.resolve()}")
    print("Apri il file nel browser (doppio click) e usa lo slider per regolare la trasparenza.")


if __name__ == "__main__":
    main()
