"""Entry point (CLI). Estendibile a FastAPI se serve API/UI.

Uso:
    python -m app.main --source data/raw/mia_mappa.las --source-type lidar
"""
import argparse

from app.agents.orchestrator import Orchestrator
from app.core.types import DataSource


def main() -> None:
    parser = argparse.ArgumentParser(description="Watershed-AI pipeline")
    parser.add_argument("--source", required=True, help="Path al file sorgente")
    parser.add_argument(
        "--source-type",
        required=True,
        choices=[s.value for s in DataSource],
        help="Tipo di sorgente dati",
    )
    args = parser.parse_args()

    orchestrator = Orchestrator()
    result = orchestrator.run(args.source, DataSource(args.source_type))

    print(f"Run {result.run_id} completata.")
    print(f"Candidati valutati: {len(result.candidates)}")
    print(f"Miglior candidato: {result.ranking.ranked_candidates[0]}")
    print(f"Output: {result.output_paths}")


if __name__ == "__main__":
    main()
