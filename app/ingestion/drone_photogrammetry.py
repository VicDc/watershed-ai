"""1c. Drone / fotogrammetria -> DSM (+ ortofoto RGB).

Placeholder per fase futura, quando sarà disponibile un drone:

1. Structure-from-Motion via OpenDroneMap (self-hosted, open source) o
   COLMAP
2. Output diretto: DSM + ortofoto RGB georeferenziata
3. Stessa classificazione ground/non-ground di lidar_processing.py se
   serve DTM puro
"""
from app.core.types import DEMGrid


def extract_dem_from_drone_images(images_dir: str) -> DEMGrid:
    """Ricostruisce un DSM da un set di foto drone (SfM).

    Non ancora implementato: attivare quando disponibile un drone
    (Fase 4 della roadmap).
    """
    raise NotImplementedError("Placeholder — vedi Fase 4 della roadmap implementativa")
