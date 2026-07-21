"""FASE 1 — Ingestion: sorgente dati -> DEM pulito (griglia elevazione).

Dispatcha verso app/ingestion/{contour_extraction,lidar_processing,
drone_photogrammetry,public_dem}.py in base a DataSource.
"""
from app.agents.base import BaseAgent
from app.core.types import DataSource, DEMGrid


class DemIngestAgent(BaseAgent):
    name = "dem_ingest_agent"

    def process(self, source_path: str, source_type: DataSource) -> DEMGrid:
        """Costruisce un DEMGrid dalla sorgente indicata.

        TODO:
        - SCANNED_MAP        -> app.ingestion.contour_extraction
        - LIDAR              -> app.ingestion.lidar_processing
        - DRONE_PHOTOGRAMMETRY -> app.ingestion.drone_photogrammetry (placeholder)
        - PUBLIC_DEM         -> app.ingestion.public_dem
        Marcare dem.quality_flags (es. "sink_artifacts_detected") se la
        confidenza dell'estrazione è bassa.
        """
        raise NotImplementedError

    def apply_priority_flood(self, dem: DEMGrid) -> DEMGrid:
        """Riempie i sink/depressioni spurie via richdem (Barnes et al.).

        Vedi app/hydrology/priority_flood.py — va sempre applicato prima di
        qualsiasi simulazione idrologica.
        """
        from app.hydrology.priority_flood import fill_depressions
        return fill_depressions(dem)
