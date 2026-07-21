> Nota: questo è lo spec originale che ha dato il via al progetto, poi rinominato in Watershed-AI. Contenuto storico, non aggiornato.

# WatershedFlood AI — Multi-Source Terrain Analysis & Flood Simulation
> Spec file per scaffolding agentico (Antigravity IDE / Claude Code)
> Autore: Vicio Di Cara | Progetto esplorativo — possibile estensione capstone OPIT
> Versione: 1.0

---

## PROJECT OVERVIEW

Applicativo che, a partire da una sorgente di dati altimetrici (mappa
topografica scansionata, point cloud LiDAR, o ricostruzione fotogrammetrica
da drone), produce un DEM (Digital Elevation Model), individua i punti
candidati più promettenti per l'immissione di acqua, simula nel tempo
la superficie allagata per ciascun candidato, e restituisce un confronto
grafico + temporale per identificare quale punto copre la maggiore
superficie d'acqua.

**Differenza chiave rispetto a un semplice "trova il punto più alto":**
il punto di quota massima non è necessariamente quello che allaga più
superficie. Il sistema deve valutare N candidati (creste, massimi locali
con prominenza) e confrontarli tramite simulazione volumetrica nel tempo,
non tramite un solo calcolo statico di direzione di flusso.

**Stack:** Python, FastAPI (opzionale se serve API/UI), NumPy, `richdem` /
`pysheds` / `whitebox-tools` (idrologia raster), `laspy` + `PDAL` (LiDAR),
OpenDroneMap/COLMAP (fotogrammetria drone, opzionale fase futura),
Plotly / Matplotlib (grafici e animazioni), Redis (opzionale, cache DEM
pesanti), Docker Compose.

**Architettura:** Pipeline multi-agente sequenziale, stesso pattern
BaseAgent / Orchestrator già usato in OrgTransform AI e business-plan-ai —
qui l'Orchestrator valida la qualità/coerenza del DEM e dei risultati
idrologici piuttosto che il ragionamento LLM (il grosso del lavoro è
calcolo numerico, non generazione testuale).

---

## PROBLEMA IN 4 FASI

```
FASE 1 — INGESTION           sorgente dati → DEM pulito (griglia elevazione)
FASE 2 — CANDIDATE SELECTION  DEM → N punti candidati (non solo argmax)
FASE 3 — FLOOD SIMULATION     per ogni candidato → curva Area(t) / Area(Volume)
FASE 4 — RANKING & OUTPUT     confronto, mappa, animazione, report
```

---

## REPOSITORY STRUCTURE

```
watershed-flood-ai/
├── app/
│   ├── main.py                       # Entry point (CLI o FastAPI, vedi sezione API)
│   │
│   ├── agents/
│   │   ├── base.py                   # BaseAgent ABC (stesso pattern di OrgTransform)
│   │   ├── orchestrator.py           # Coordinamento pipeline + quality gate
│   │   ├── dem_ingest_agent.py       # Fase 1
│   │   ├── candidate_point_agent.py  # Fase 2
│   │   ├── flood_simulation_agent.py # Fase 3
│   │   ├── ranking_agent.py          # Fase 4a
│   │   └── visualization_agent.py    # Fase 4b
│   │
│   ├── core/
│   │   ├── types.py                  # Dataclass di dominio
│   │   ├── exceptions.py
│   │   └── config.py                 # pydantic-settings da .env
│   │
│   ├── ingestion/
│   │   ├── contour_extraction.py     # Mappa scansionata → curve di livello → DEM
│   │   ├── lidar_processing.py       # Point cloud (.las/.laz) → DTM
│   │   └── drone_photogrammetry.py   # Placeholder fase futura (SfM)
│   │
│   ├── hydrology/
│   │   ├── flow_routing.py           # D8 / D-infinity / MFD
│   │   ├── candidate_detection.py    # Massimi locali + prominenza + spartiacque
│   │   ├── priority_flood.py         # Riempimento depressioni, base per flood-fill
│   │   └── cellular_automata.py      # Simulazione temporale shallow-water semplificata
│   │
│   ├── viz/
│   │   ├── raster_render.py          # Mappa statica ipsometrica + overlay acqua
│   │   ├── animation_builder.py      # Sequenza frame → GIF/MP4
│   │   └── comparison_charts.py      # Area(t) sovrapposte per candidato
│   │
│   └── services/
│       ├── dem_cache.py              # Redis cache per DEM pesanti (opzionale)
│       └── report_builder.py         # Assembla report finale (md/pdf)
│
├── data/
│   ├── raw/                          # Mappe scansionate, .las/.laz, foto drone
│   ├── dem/                          # DEM processati (GeoTIFF)
│   └── public_dem_cache/             # DEM pubblici scaricati (Copernicus GLO-30, SRTM)
│
├── output/
│   ├── maps/
│   ├── animations/
│   └── reports/
│
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── requirements.txt
└── README.md
```

---

## DOMAIN TYPES — app/core/types.py

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
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
    elevation: np.ndarray             # matrice 2D (righe=y, colonne=x)
    cell_size_m: float                # risoluzione spaziale in metri/pixel
    origin: tuple[float, float]       # coordinate origine (georeferenziazione, opzionale)
    nodata_value: float = -9999.0
    source: DataSource = DataSource.PUBLIC_DEM
    quality_flags: list[str] = field(default_factory=list)  # es. "sink_artifacts_detected"


@dataclass
class CandidatePoint:
    id: str
    row: int
    col: int
    elevation: float
    prominence: float                 # dislivello rispetto alla sella più vicina
    watershed_area_cells: int         # area del bacino potenziale (statica, pre-simulazione)
    rationale: str                    # perché è stato selezionato


@dataclass
class FloodTimeSeries:
    candidate_id: str
    time_steps_s: list[float]         # istanti temporali della simulazione
    area_flooded_m2: list[float]      # superficie allagata per ciascun istante
    volume_injected_m3: list[float]   # volume cumulativo immesso
    max_depth_m: list[float]          # profondità massima raggiunta per istante
    stabilized: bool                  # True se l'espansione si è arrestata prima di t_max


@dataclass
class RankingResult:
    ranked_candidates: list[str]      # candidate_id in ordine decrescente di performance
    scores: dict[str, float]          # punteggio finale per candidato
    comparison_notes: list[str]       # osservazioni (es. "candidato B satura più lentamente")


@dataclass
class PipelineResult:
    run_id: str
    dem: DEMGrid
    candidates: list[CandidatePoint]
    simulations: dict[str, FloodTimeSeries]
    ranking: RankingResult
    output_paths: dict[str, str]      # mappa statica, animazione, report
    warnings: list[str]
```

---

## FASE 1 — INGESTION

### 1a. Mappa topografica scansionata — app/ingestion/contour_extraction.py

Pipeline CV classica, non deep learning (a meno che la qualità delle
scansioni non lo richieda):

1. **Preprocessing immagine**: binarizzazione, rimozione rumore
   (morphological opening/closing), eventuale deskew
2. **Estrazione linee di livello**: thinning/skeletonization delle linee
   scure isolate dal background (OpenCV: `cv2.ximgproc.thinning`, oppure
   segmentazione per colore se le curve sono colorate)
3. **Vettorizzazione**: da pixel a polilinee (contour tracing)
4. **Attribuzione quota per linea**: OCR (Tesseract) sui numeri di quota
   stampati lungo le linee, o interpolazione manuale se l'utente fornisce
   l'equidistanza (es. "linee ogni 10m")
5. **Interpolazione a griglia**: da polilinee con quota nota a DEM continuo
   — TIN (triangulated irregular network) o kriging
   (`scipy.interpolate.griddata`, `pykrige` per kriging vero)

**Nota di robustezza**: linee che si intersecano, quote illeggibili, e
scansioni a bassa risoluzione sono le fonti di errore principali — il
DEM risultante va sempre marcato con `quality_flags` se la confidenza
dell'estrazione è bassa.

### 1b. LiDAR — app/ingestion/lidar_processing.py

Il LiDAR fornisce già dati 3D diretti (non serve ricostruzione da immagine):

1. **Lettura point cloud**: `laspy` per `.las`/`.laz`
2. **Classificazione ground/non-ground**: Cloth Simulation Filter (CSF,
   via `PDAL` o `CSF` python binding) per separare suolo nudo da
   vegetazione/edifici → produce DTM invece di DSM
3. **Interpolazione a griglia raster**: IDW o TIN sui soli punti "ground"
4. **Output**: GeoTIFF con stessa struttura di `DEMGrid`

**Fonti dati pubbliche (Italia)**: Geoportale Nazionale, portali LiDAR
regionali (es. Regione Lombardia, Regione Toscana hanno open data LiDAR
scaricabili gratuitamente) — utile per prototipare senza drone.

### 1c. Drone / fotogrammetria — app/ingestion/drone_photogrammetry.py

Placeholder per fase futura quando sarà disponibile un drone:

1. Structure-from-Motion via OpenDroneMap (self-hosted, open source) o
   COLMAP
2. Output diretto: DSM + ortofoto RGB georeferenziata
3. Stessa classificazione ground/non-ground di 1b se serve DTM puro

### 1d. DEM pubblici (per test immediati senza dati propri)

`app/ingestion/public_dem.py` (nuovo file, non ancora nella struttura
sopra — aggiungilo): download automatico Copernicus GLO-30 (30m risoluzione,
globale, gratuito) o SRTM per un'area di interesse data come bounding box.
Permette di validare tutta la pipeline a valle (fasi 2-4) senza aspettare
scansioni o lidar propri.

---

## FASE 2 — CANDIDATE SELECTION

### app/hydrology/candidate_detection.py

Il punto di quota massima assoluta NON è sufficiente. Algoritmo:

1. **Local maxima detection**: filtro di massimo locale su finestra
   mobile (`scipy.ndimage.maximum_filter`) per trovare tutti i picchi
2. **Filtro di prominenza**: scarta i massimi la cui prominenza (dislivello
   rispetto alla sella di connessione al terreno più alto vicino) è sotto
   una soglia — evita di segnalare decine di punti sullo stesso rilievo
   (algoritmo simile alla prominence topografica usata in alpinismo/GIS,
   implementabile con `richdem` o logica custom su watershed inverso)
3. **Analisi degli spartiacque (ridge detection)**: oltre ai massimi
   puntuali, identifica segmenti di cresta larga — un punto su una cresta
   ampia può alimentare più bacini contemporaneamente ed essere migliore
   di un picco isolato
4. **Bacino potenziale (pre-simulazione)**: per ciascun candidato, calcola
   il watershed statico a valle (area totale raggiungibile in teoria,
   ignorando volume/tempo) — serve come primo filtro per scartare
   candidati con bacino minuscolo prima di lanciare simulazioni costose
5. **Output**: lista di `CandidatePoint`, tipicamente 5-15 in un'area di
   medie dimensioni, ciascuno con `rationale` testuale (es. "cresta larga
   80m, bacino potenziale 12 km², prominenza 45m")

```python
CANDIDATE_DETECTION_PARAMS = {
    "min_prominence_m": 10.0,       # scarta massimi con dislivello < 10m
    "local_max_window_cells": 15,   # finestra per maximum_filter
    "min_watershed_area_cells": 100 # scarta bacini potenziali troppo piccoli
}
```

---

## FASE 3 — FLOOD SIMULATION (analisi temporale)

### app/hydrology/cellular_automata.py

Per ogni candidato, simulazione a step temporali (non solo flow direction
statica). Modello scelto: **cellular automata shallow-water semplificato**
— buon compromesso tra realismo e costo computazionale per un prototipo/tesi.

**Logica del modello:**

```
Stato: h[row, col] = livello d'acqua per cella, inizializzato a 0
Input: portata costante Q (m³/s) immessa nella cella del candidato

Per ogni step temporale dt:
    1. Aggiungi acqua nella cella sorgente: h[candidate] += Q * dt / cell_area
    2. Per ogni cella con acqua, calcola il differenziale di quota totale
       (elevation + h) verso le celle vicine più basse
    3. Ridistribuisci l'acqua in eccesso proporzionalmente al gradiente
       (regola tipo "weighted outflow", non serve risolvere Navier-Stokes)
    4. Applica una soglia minima di profondità per considerare una cella
       "allagata" (es. > 1cm) — evita di contare come coperte celle con
       tracce infinitesimali
    5. Registra: area_flooded_m2 (celle sopra soglia * cell_area),
       max_depth_m, volume_injected_m3 cumulativo
    6. Condizione di stop: se l'area allagata non cresce per N step
       consecutivi (< 0.5% variazione) → stabilized = True, interrompi
```

**Parametri di configurazione:**

```python
FLOOD_SIM_PARAMS = {
    "flow_rate_m3_s": 5.0,          # portata ipotetica immessa
    "time_step_s": 60.0,            # granularità temporale
    "max_simulation_time_s": 3600 * 6,  # tetto massimo (6 ore simulate)
    "min_depth_threshold_m": 0.01,
    "stabilization_window_steps": 10,
    "stabilization_tolerance_pct": 0.5
}
```

**Alternativa più rigorosa (fase avanzata, opzionale):**
Shallow Water Equations vere tramite `landlab` (libreria Python per
modellazione di superficie terrestre) o integrazione con `LISFLOOD-FP`
(open source, C++/Python bindings) — da considerare solo se il livello
di rigore richiesto lo giustifica, altrimenti overkill per un prototipo.

**Gestione dei sink/depressioni spurie:** prima di ogni simulazione,
applicare `priority_flood.py` (algoritmo di Barnes et al., disponibile
in `richdem` come `rd.FillDepressions`) per riempire le depressioni
artificiali dovute a rumore di interpolazione/lidar — altrimenti l'acqua
si accumula in buche false invece di scorrere realisticamente.

---

## FASE 4 — RANKING & OUTPUT

### 4a. app/agents/ranking_agent.py

Confronto tra tutte le `FloodTimeSeries`:

- **Metrica primaria**: area allagata al tempo di stabilizzazione (o al
  tempo massimo se nessun candidato si stabilizza)
- **Metriche secondarie**: velocità di crescita iniziale (area/tempo nei
  primi N step — utile se serve un allagamento rapido), area per m³
  immesso (efficienza volumetrica)
- **Output**: `RankingResult` con classifica motivata e note comparative
  testuali (es. "il candidato C2 copre il 18% di superficie in più di C1
  ma richiede il triplo del volume per stabilizzarsi")

### 4b. app/agents/visualization_agent.py

- **Mappa statica ipsometrica**: DEM in scala colori (verde→marrone→bianco
  per quota crescente) con overlay semi-trasparente blu per l'acqua al
  tempo finale, marker per ciascun candidato colorati per punteggio
- **Animazione temporale**: sequenza di frame (uno ogni N step) →
  GIF o MP4 via `matplotlib.animation` o `Plotly` con frames, mostra
  l'espansione dell'acqua nel tempo per il candidato migliore (o tutti
  in griglia comparativa)
- **Grafico comparativo Area(t)**: curve sovrapposte, una per candidato,
  con leggenda — permette di vedere a colpo d'occhio quale punto vince
  a ogni istante, non solo al termine
- **Widget interattivo (opzionale)**: artifact HTML/React con slider
  temporale per esplorare l'animazione senza rigenerare file statici

---

## ORCHESTRATOR — app/agents/orchestrator.py

A differenza di OrgTransform AI, qui l'Orchestrator non fa "consistency
check" tra output LLM ma un **quality gate numerico** sulla pipeline:

```python
class Orchestrator:
    """
    Coordina le 4 fasi e applica controlli di qualità tra una fase e l'altra.
    Non richiede necessariamente un LLM — può essere puro controllo di flusso
    Python. Un LLM è utile solo per generare le `rationale` testuali dei
    candidati e le note comparative del ranking in linguaggio naturale.
    """

    def run(self, source_path: str, source_type: DataSource) -> PipelineResult:
        # FASE 1
        dem = self.dem_ingest_agent.process(source_path, source_type)
        if "sink_artifacts_detected" in dem.quality_flags:
            dem = self.dem_ingest_agent.apply_priority_flood(dem)

        # QUALITY GATE 1: DEM valido?
        if dem.elevation is None or dem.elevation.size == 0:
            raise PipelineError("DEM ingestion fallita — verificare sorgente dati")

        # FASE 2
        candidates = self.candidate_point_agent.process(dem)
        if len(candidates) == 0:
            raise PipelineError("Nessun candidato trovato — abbassare soglia prominenza")

        # FASE 3 (può girare in parallelo per candidato)
        simulations = {
            c.id: self.flood_simulation_agent.process(dem, c)
            for c in candidates
        }

        # FASE 4
        ranking = self.ranking_agent.process(simulations)
        output_paths = self.visualization_agent.process(dem, candidates, simulations, ranking)

        return PipelineResult(
            run_id=..., dem=dem, candidates=candidates,
            simulations=simulations, ranking=ranking,
            output_paths=output_paths, warnings=dem.quality_flags
        )
```

**Se vuoi mantenere il pattern LLM-revision-loop coerente con OrgTransform**
(per riuso accademico / confronto metodologico nella tesi), puoi aggiungere
un LLM step opzionale che, dato il ranking numerico, genera solo la parte
narrativa del report (executive summary in linguaggio naturale) — non
tocca i calcoli, che restano deterministici e riproducibili.

---

## LIBRERIE CHIAVE — requirements.txt

```
numpy>=1.26.0
scipy>=1.13.0
richdem>=0.3.4              # priority-flood, flow accumulation, D8/D-infinity
pysheds>=0.3.5               # alternativa/complemento a richdem
whitebox>=2.3.0              # toolset idrologia raster, wrapper Python di WhiteboxTools
laspy>=2.5.0                  # lettura point cloud LiDAR .las/.laz
rasterio>=1.3.0               # I/O GeoTIFF, georeferenziazione
opencv-python>=4.10.0         # estrazione curve di livello da mappe scansionate
pytesseract>=0.3.10           # OCR per quote sulle curve di livello
scikit-image>=0.24.0          # skeletonization, morphological ops
plotly>=5.0.0
matplotlib>=3.7.0
kaleido>=0.2.1                 # export statico Plotly
pandas>=2.0.0
pydantic>=2.7.0
pydantic-settings>=2.3.0
fastapi>=0.115.0               # opzionale, se serve API/UI
uvicorn[standard]>=0.30.0
redis[asyncio]>=5.0.0          # opzionale, cache DEM
```

**Nota rete**: `richdem`, `pysheds`, `whitebox`, `laspy`, `rasterio` sono
installabili via `pip` da PyPI — nessuna dipendenza da servizi esterni per
il calcolo. `PDAL` (per classificazione LiDAR avanzata) è più comodo via
conda/apt se serve; in alternativa `CSF` ha un binding pip.

---

## DOCKER COMPOSE — docker-compose.yml

```yaml
version: "3.9"

services:
  watershed-app:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./data:/app/data
      - ./output:/app/output
    depends_on:
      redis:
        condition: service_healthy

  redis:
    image: redis:8.6-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
```

---

## ENV FILE — .env.example

```
# Sorgente dati default
DEFAULT_SOURCE_TYPE=public_dem

# DEM pubblici (Copernicus GLO-30 via OpenTopography API o AWS)
OPENTOPOGRAPHY_API_KEY=your_key_here

# Simulazione
FLOW_RATE_M3_S=5.0
TIME_STEP_S=60.0
MAX_SIMULATION_TIME_S=21600

# Candidate detection
MIN_PROMINENCE_M=10.0
LOCAL_MAX_WINDOW_CELLS=15

# Output
OUTPUT_DIR=output
REDIS_URL=redis://localhost:6379/0

# LLM (opzionale, solo per narrativa report)
LLM_BASE_URL=http://localhost:1234/v1
LLM_MODEL=gemma-4-26b
```

---

## ROADMAP IMPLEMENTATIVA

### Fase 1 — Validazione pipeline core (1-2 settimane)
- [ ] Scaricare un DEM pubblico di test (Copernicus GLO-30 o SRTM, area
      montuosa/collinare reale in Italia)
- [ ] Implementare `candidate_detection.py` (local maxima + prominenza)
- [ ] Implementare `priority_flood.py` (riempimento depressioni via richdem)
- [ ] Implementare `cellular_automata.py` per un solo candidato, validare
      visivamente che l'espansione abbia senso fisico
- [ ] Prima mappa statica con overlay acqua

### Fase 2 — Multi-candidato + ranking (1 settimana)
- [ ] Estendere a N candidati in parallelo (multiprocessing o async)
- [ ] Implementare `ranking_agent.py` con le metriche definite
- [ ] Grafico comparativo Area(t) per tutti i candidati

### Fase 3 — Animazione e report (1 settimana)
- [ ] Animazione temporale (GIF/MP4) per il candidato vincente
- [ ] Report markdown/PDF con mappa, grafici, classifica motivata
- [ ] (Opzionale) widget interattivo con slider temporale

### Fase 4 — Ingestion da sorgenti reali (quando disponibili)
- [ ] `contour_extraction.py`: pipeline OCR + vettorizzazione su una
      mappa topografica scansionata reale
- [ ] `lidar_processing.py`: test su un dataset LiDAR pubblico regionale
      italiano (verificare disponibilità su Geoportale Nazionale)
- [ ] `drone_photogrammetry.py`: placeholder, attivare quando disponibile
      un drone

### Fase 5 — Validazione ed eventuale collegamento accademico
- [ ] Confronto quantitativo tra risultati su DEM pubblico a bassa
      risoluzione (30m) vs LiDAR ad alta risoluzione (se disponibile) —
      possibile materiale per discussione metodologica
- [ ] Se utile per la tesi: ablation study tra D8 vs D-infinity vs MFD
      come motore di flow routing, per vedere quanto cambia il ranking
      finale dei candidati

---

## NOTE METODOLOGICHE

- **Il punto più alto non è il migliore**: la selezione dei candidati deve
  sempre passare da prominenza + bacino potenziale, mai da un semplice
  argmax sulla quota.
- **I sink/depressioni spurie sono la fonte di errore più comune**: vanno
  sempre riempite con priority-flood prima di qualsiasi simulazione,
  altrimenti l'acqua si accumula in buche artificiali da rumore del DEM.
- **Risoluzione del DEM conta più della sofisticazione dell'algoritmo**:
  un DEM a 30m (SRTM) può nascondere creste strette importanti che un
  LiDAR a 1m rileverebbe — utile flag di cautela quando si presentano
  risultati basati su DEM pubblici a bassa risoluzione.
- **Determinismo vs LLM**: a differenza di OrgTransform AI, qui il cuore
  del sistema è calcolo numerico deterministico; l'LLM (se incluso) va
  confinato alla generazione di testo narrativo, mai ai calcoli
  idrologici — questo mantiene i risultati riproducibili e verificabili,
  requisito importante se il progetto finisce in un contesto accademico.

---

*Fine spec — pronto per scaffolding agentico.*
