"""Coordina le 4 fasi e applica quality gate numerici tra una fase e l'altra.

A differenza di OrgTransform AI, qui l'Orchestrator NON fa consistency-check
tra output LLM: valida la qualità/coerenza del DEM e dei risultati
idrologici. Non richiede necessariamente un LLM — può essere puro controllo
di flusso Python. Un LLM è utile solo per generare le `rationale` testuali
dei candidati e le note comparative del ranking in linguaggio naturale.
"""
import uuid

from app.agents.candidate_point_agent import CandidatePointAgent
from app.agents.dem_ingest_agent import DemIngestAgent
from app.agents.flood_simulation_agent import FloodSimulationAgent
from app.agents.ranking_agent import RankingAgent
from app.agents.visualization_agent import VisualizationAgent
from app.core.exceptions import PipelineError
from app.core.types import DataSource, PipelineResult


class Orchestrator:
    def __init__(self) -> None:
        self.dem_ingest_agent = DemIngestAgent()
        self.candidate_point_agent = CandidatePointAgent()
        self.flood_simulation_agent = FloodSimulationAgent()
        self.ranking_agent = RankingAgent()
        self.visualization_agent = VisualizationAgent()

    def run(self, source_path: str, source_type: DataSource) -> PipelineResult:
        run_id = uuid.uuid4().hex[:8]

        # FASE 1 — Ingestion
        dem = self.dem_ingest_agent.process(source_path, source_type)
        if "sink_artifacts_detected" in dem.quality_flags:
            dem = self.dem_ingest_agent.apply_priority_flood(dem)

        # QUALITY GATE 1: DEM valido?
        if dem.elevation is None or dem.elevation.size == 0:
            raise PipelineError("DEM ingestion fallita — verificare sorgente dati")

        # FASE 2 — Candidate selection
        candidates = self.candidate_point_agent.process(dem)
        if len(candidates) == 0:
            raise PipelineError("Nessun candidato trovato — abbassare soglia prominenza")

        # FASE 3 — Flood simulation (può girare in parallelo per candidato)
        simulations = {
            c.id: self.flood_simulation_agent.process(dem, c)
            for c in candidates
        }

        # FASE 4 — Ranking & output
        ranking = self.ranking_agent.process(simulations)
        output_paths = self.visualization_agent.process(dem, candidates, simulations, ranking)

        return PipelineResult(
            run_id=run_id,
            dem=dem,
            candidates=candidates,
            simulations=simulations,
            ranking=ranking,
            output_paths=output_paths,
            warnings=dem.quality_flags,
        )
