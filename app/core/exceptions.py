"""Eccezioni custom della pipeline."""


class PipelineError(Exception):
    """Errore bloccante in una fase della pipeline (quality gate fallito)."""


class DEMIngestError(PipelineError):
    """Errore durante l'ingestion/costruzione del DEM (Fase 1)."""


class CandidateDetectionError(PipelineError):
    """Nessun candidato valido trovato (Fase 2)."""


class FloodSimulationError(PipelineError):
    """Errore durante la simulazione idrologica (Fase 3)."""
