"""FASE 4b — Output: mappa statica, animazione, grafico comparativo, report.

Delega a app/viz/{raster_render,animation_builder,comparison_charts}.py e
app/services/report_builder.py.
"""
from app.agents.base import BaseAgent
from app.core.types import CandidatePoint, DEMGrid, FloodTimeSeries, RankingResult


class VisualizationAgent(BaseAgent):
    name = "visualization_agent"

    def process(
        self,
        dem: DEMGrid,
        candidates: list[CandidatePoint],
        simulations: dict[str, FloodTimeSeries],
        ranking: RankingResult,
    ) -> dict[str, str]:
        """Genera gli artefatti di output e ritorna i path prodotti.

        Ritorna un dict tipo:
            {"map": "output/maps/...png", "animation": "output/animations/...mp4",
             "comparison_chart": "output/maps/...png", "report": "output/reports/...md"}
        """
        raise NotImplementedError
