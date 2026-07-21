"""FASE 2 — Candidate Selection: DEM -> N punti candidati (non solo argmax).

Delega la logica numerica a app/hydrology/candidate_detection.py e genera
(qui o via LLM opzionale) il campo `rationale` testuale di ogni candidato.
"""
from app.agents.base import BaseAgent
from app.core.types import CandidatePoint, DEMGrid


class CandidatePointAgent(BaseAgent):
    name = "candidate_point_agent"

    def process(self, dem: DEMGrid) -> list[CandidatePoint]:
        """Ritorna 5-15 CandidatePoint tipicamente, ordinati per bacino potenziale.

        Pipeline (vedi app/hydrology/candidate_detection.py):
        1. local maxima detection (scipy.ndimage.maximum_filter)
        2. filtro di prominenza (min_prominence_m)
        3. ridge detection (creste larghe)
        4. bacino potenziale statico pre-simulazione
        5. filtro min_watershed_area_cells
        """
        from app.hydrology.candidate_detection import detect_candidates
        return detect_candidates(dem)
