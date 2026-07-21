"""1a. Mappa topografica scansionata -> DEM.

Pipeline CV classica (no deep learning, a meno che la qualità delle
scansioni non lo richieda):

1. Preprocessing immagine: binarizzazione, rimozione rumore
   (morphological opening/closing), eventuale deskew
2. Estrazione linee di livello: thinning/skeletonization
   (cv2.ximgproc.thinning, o segmentazione per colore)
3. Vettorizzazione: da pixel a polilinee (contour tracing)
4. Attribuzione quota per linea: OCR (Tesseract) o equidistanza fornita
   dall'utente (es. "linee ogni 10m")
5. Interpolazione a griglia: TIN o kriging (scipy.interpolate.griddata,
   pykrige)

Nota di robustezza: linee che si intersecano, quote illeggibili, scansioni
a bassa risoluzione sono le fonti di errore principali — marcare sempre il
DEM con quality_flags se la confidenza dell'estrazione è bassa.
"""
from app.core.types import DEMGrid


def extract_dem_from_scanned_map(image_path: str, contour_interval_m: float | None = None) -> DEMGrid:
    """Estrae un DEM da una mappa topografica scansionata.

    Args:
        image_path: path all'immagine scansionata.
        contour_interval_m: equidistanza tra le curve di livello, se nota
            (altrimenti si tenta l'OCR sui numeri di quota).
    """
    raise NotImplementedError
