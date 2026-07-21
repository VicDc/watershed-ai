"""Dataclass di dominio condivise da tutte le fasi della pipeline.

Fonte: sezione "DOMAIN TYPES" di docs/spec/watershed_ai_spec_ORIGINALE.md
"""
from dataclasses import dataclass, field
from enum import Enum

import numpy as np


class DataSource(str, Enum):
    SCANNED_MAP = "scanned_map"       # mappa topografica scansionata
    LIDAR = "lidar"                   # point cloud .las/.laz
    DRONE_PHOTOGRAMMETRY = "drone"    # SfM da foto drone
    PUBLIC_DEM = "public_dem"         # Copernicus GLO-30 / SRTM già pronto


class FlowAlgorithm(str, Enum):
    D8 = "d8"                         # singola direzione, il più semplice
    D_INFINITY = "d_infinity"         # direzione continua, più realistico
    MFD = "mfd"                       # multiple flow direction


@dataclass
class DEMGrid:
    """Rappresentazione della griglia di elevazione."""
    elevation: np.ndarray              # matrice 2D (righe=y, colonne=x)
    cell_size_m: float                 # risoluzione spaziale in metri/pixel
    origin: tuple[float, float]        # coordinate origine (georeferenziazione)
    nodata_value: float = -9999.0
    source: DataSource = DataSource.PUBLIC_DEM
    quality_flags: list[str] = field(default_factory=list)  # es. "sink_artifacts_detected"


@dataclass
class CandidatePoint:
    id: str
    row: int
    col: int
    elevation: float
    prominence: float                  # dislivello rispetto alla sella più vicina
    watershed_area_cells: int          # area del bacino potenziale (statica)
    rationale: str                     # perché è stato selezionato


@dataclass
class FloodTimeSeries:
    candidate_id: str
    time_steps_s: list[float]          # istanti temporali della simulazione
    area_flooded_m2: list[float]       # superficie allagata per ciascun istante
    volume_injected_m3: list[float]    # volume cumulativo immesso
    max_depth_m: list[float]           # profondità massima raggiunta per istante
    stabilized: bool                   # True se l'espansione si è arrestata prima di t_max


@dataclass
class RankingResult:
    ranked_candidates: list[str]       # candidate_id in ordine decrescente
    scores: dict[str, float]           # punteggio finale per candidato
    comparison_notes: list[str]        # osservazioni testuali


@dataclass
class PipelineResult:
    run_id: str
    dem: DEMGrid
    candidates: list[CandidatePoint]
    simulations: dict[str, FloodTimeSeries]
    ranking: RankingResult
    output_paths: dict[str, str]       # mappa statica, animazione, report
    warnings: list[str]
