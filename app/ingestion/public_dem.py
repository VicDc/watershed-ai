"""1d. DEM pubblici — per test immediati senza dati propri.

Download automatico Copernicus GLO-30 (30m risoluzione, globale, gratuito)
o SRTM per un'area di interesse data come bounding box. Permette di
validare tutta la pipeline a valle (fasi 2-4) senza aspettare scansioni o
lidar propri.

Nota: file aggiunto rispetto alla struttura iniziale dello spec, come
indicato nella sezione FASE 1 punto 1d.
"""
import math

import numpy as np
import rasterio

from app.core.types import DataSource, DEMGrid

_METERS_PER_DEGREE_LAT = 111_320.0


def load_dem_from_geotiff(path: str) -> DEMGrid:
    """Carica un DEM già scaricato manualmente (es. da OpenTopography) da GeoTIFF.

    Utile per un primo test end-to-end senza dover implementare subito la
    chiamata API automatica (vedi download_public_dem sotto).

    Args:
        path: path al file .tif (es. "data/dem/copernicus_glo30_test.tif")
    """
    with rasterio.open(path) as src:
        elevation = src.read(1).astype(np.float64)
        nodata = src.nodata if src.nodata is not None else -9999.0

        n_rows, n_cols = elevation.shape
        cell_size_deg = abs(src.transform[0])
        origin = (src.transform[2], src.transform[5])  # (x, y) angolo alto-sx = (lon, lat)

        # Il GeoTIFF è in coordinate geografiche (EPSG:4326): la risoluzione
        # nativa è in gradi, non metri. Convertiamo in un cell_size_m
        # approssimato, isotropo, usando la latitudine media dell'area:
        #   1° di latitudine ≈ 111.32 km (costante)
        #   1° di longitudine ≈ 111.32 km * cos(latitudine) (si restringe
        #     avvicinandosi ai poli)
        # Approssimazione ragionevole per estensioni piccole (poche km);
        # non sostituisce una vera riproiezione (rasterio.warp) se serve
        # precisione metrica rigorosa su aree grandi.
        mean_lat_deg = origin[1] - (n_rows * cell_size_deg) / 2
        meters_per_deg_lon = _METERS_PER_DEGREE_LAT * math.cos(math.radians(mean_lat_deg))
        cell_size_m = cell_size_deg * (_METERS_PER_DEGREE_LAT + meters_per_deg_lon) / 2

        quality_flags: list[str] = ["cell_size_approximated_from_degrees"]
        if np.any(elevation == nodata):
            quality_flags.append("nodata_cells_present")

        return DEMGrid(
            elevation=elevation,
            cell_size_m=cell_size_m,
            origin=origin,
            nodata_value=nodata,
            source=DataSource.PUBLIC_DEM,
            quality_flags=quality_flags,
        )


def download_public_dem(
    bbox: tuple[float, float, float, float],
    source: str = "copernicus_glo30",
) -> DEMGrid:
    """Scarica/ritaglia un DEM pubblico per la bounding box data.

    Args:
        bbox: (min_lon, min_lat, max_lon, max_lat)
        source: "copernicus_glo30" | "srtm"

    Richiede OPENTOPOGRAPHY_API_KEY in .env (vedi app/core/config.py).
    """
    raise NotImplementedError
