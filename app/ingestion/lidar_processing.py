"""1b. LiDAR (.las/.laz) -> DTM.

1. Lettura point cloud: laspy
2. Classificazione ground/non-ground: Cloth Simulation Filter (CSF, via
   PDAL o binding Python CSF) -> produce DTM invece di DSM
3. Interpolazione a griglia raster: IDW o TIN sui soli punti "ground"
4. Output: GeoTIFF con stessa struttura di DEMGrid

Fonti dati pubbliche (Italia): Geoportale Nazionale, portali LiDAR
regionali (Regione Lombardia, Regione Toscana) — utile per prototipare
senza drone.
"""
from app.core.types import DEMGrid


def extract_dem_from_lidar(las_path: str) -> DEMGrid:
    """Estrae un DTM da una point cloud LiDAR .las/.laz."""
    raise NotImplementedError
