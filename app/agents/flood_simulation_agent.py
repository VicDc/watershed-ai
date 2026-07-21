"""FASE 3 — Flood Simulation: per ogni candidato -> Area(t) / Area(Volume).

Delega al modello cellular-automata shallow-water semplificato in
app/hydrology/cellular_automata.py.
"""
from app.agents.base import BaseAgent
from app.core.types import CandidatePoint, DEMGrid, FloodTimeSeries


class FloodSimulationAgent(BaseAgent):
    name = "flood_simulation_agent"

    def process(self, dem: DEMGrid, candidate: CandidatePoint) -> FloodTimeSeries:
        """Simula l'allagamento nel tempo per un singolo candidato.

        Vedi FLOOD_SIM_PARAMS in app/hydrology/cellular_automata.py per i
        parametri di default (flow_rate_m3_s, time_step_s,
        max_simulation_time_s, stabilization_*).
        """
        from app.hydrology.cellular_automata import simulate_flood
        return simulate_flood(dem, candidate)
