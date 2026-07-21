"""FASE 4a — Ranking: confronto tra tutte le FloodTimeSeries.

Metrica primaria: area allagata al tempo finale (o di stabilizzazione).
Metriche secondarie riportate nelle note: velocita' di crescita iniziale
ed efficienza volumetrica (area per m3 immesso) — utili per distinguere
un candidato che allaga "tanto ma lentamente" da uno "meno ma subito".

Nessun LLM richiesto: il punteggio resta interamente deterministico,
calcolato dai numeri della simulazione.
"""
from app.agents.base import BaseAgent
from app.core.types import FloodTimeSeries, RankingResult


class RankingAgent(BaseAgent):
    name = "ranking_agent"

    def process(self, simulations: dict[str, FloodTimeSeries]) -> RankingResult:
        """Produce una RankingResult con classifica motivata."""
        scores: dict[str, float] = {}
        notes: list[str] = []

        for cand_id, sim in simulations.items():
            final_area = sim.area_flooded_m2[-1] if sim.area_flooded_m2 else 0.0
            scores[cand_id] = final_area

        ranked = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)

        for i, cand_id in enumerate(ranked, start=1):
            sim = simulations[cand_id]
            final_area = sim.area_flooded_m2[-1] if sim.area_flooded_m2 else 0.0
            final_volume = sim.volume_injected_m3[-1] if sim.volume_injected_m3 else 0.0
            efficiency = final_area / final_volume if final_volume > 0 else 0.0

            # velocita' di crescita iniziale: area raggiunta al 10% del
            # tempo totale simulato, utile per distinguere "allaga subito"
            # da "allaga alla fine"
            n_steps = len(sim.area_flooded_m2)
            early_idx = max(0, n_steps // 10 - 1)
            early_area = sim.area_flooded_m2[early_idx] if n_steps > 0 else 0.0

            status = "stabilizzato" if sim.stabilized else "ancora in espansione a fine simulazione"
            notes.append(
                f"#{i} {cand_id}: area finale {final_area:.0f}m² ({status}), "
                f"efficienza {efficiency:.3f}m²/m³, "
                f"area al 10% del tempo simulato: {early_area:.0f}m²."
            )

        return RankingResult(
            ranked_candidates=ranked,
            scores=scores,
            comparison_notes=notes,
        )
