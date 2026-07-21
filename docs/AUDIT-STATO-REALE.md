# Audit dello stato reale — Watershed-AI

Data audit: 2026-07-21
Metodo: ispezione riga per riga di ogni file `.py` in `app/` e `scripts/`, più esecuzione reale di ogni script con l'interprete `.venv/Scripts/python.exe` (Windows), usando `data/dem/copernicus_glo30_test.tif` come DEM di test. Nessuna valutazione è basata sul nome del file o su supposizioni: ogni riga "completo"/"parziale"/"stub" discende da lettura del corpo delle funzioni e/o da un'esecuzione reale con verifica su disco dei file di output.

---

## 1. Modulo `app/agents`

| File | Funzione/Classe principale | Stato reale | Note (NotImplementedError/TODO/FIXME con riga) |
|---|---|---|---|
| `app/agents/base.py` | `BaseAgent` (ABC) | Completo | `process()` astratto, `raise NotImplementedError` a riga 19 — corretto per un'ABC, non è uno stub applicativo. |
| `app/agents/candidate_point_agent.py` | `CandidatePointAgent.process()` | Presente ma mai testato (come classe) | Nessun TODO/stub nel corpo: è un thin wrapper che delega a `detect_candidates()`. La funzione delegata è ampiamente testata (vedi `app/hydrology/candidate_detection.py`), ma la classe `CandidatePointAgent` stessa non viene mai istanziata in nessuno script né in `tests/`: solo `Orchestrator` la usa, e `Orchestrator.run()` non arriva mai a chiamarla (fallisce prima, vedi riga sotto). |
| `app/agents/dem_ingest_agent.py` | `DemIngestAgent.process()` / `.apply_priority_flood()` | Parziale (stub + completo nello stesso file) | `process()`: `raise NotImplementedError` a riga 24, con blocco `TODO` a riga 16 che elenca il dispatch mai scritto (SCANNED_MAP/LIDAR/DRONE/PUBLIC_DEM). `apply_priority_flood()` invece è completo e delega a `fill_depressions()`, che è testato e funzionante. |
| `app/agents/flood_simulation_agent.py` | `FloodSimulationAgent.process()` | Presente ma mai testato (come classe) | Nessuno stub nel corpo, thin wrapper su `simulate_flood()` (funzione ampiamente testata). La classe stessa non è mai istanziata da nessuno script; solo l'orchestrator la referenzia, senza mai arrivarci in esecuzione. |
| `app/agents/orchestrator.py` | `Orchestrator.run()` | Parziale — logica corretta ma pipeline NON eseguibile | Nessuno stub nel file stesso, ma l'esecuzione reale fallisce sempre al primo step: `python -m app.main --source data/dem/copernicus_glo30_test.tif --source-type public_dem` solleva `NotImplementedError` da `dem_ingest_agent.py:24` (traceback completo in fondo, sezione script). L'intera catena Orchestrator→Agenti non è mai stata eseguita con successo end-to-end. |
| `app/agents/ranking_agent.py` | `RankingAgent.process()` | Completo e testato ripetutamente | Nessuno stub. Usato con successo (istanziato ed eseguito) in 8 script diversi (`test_fase4.py`, `export_flood_animation*.py`, `visualize_flood_3d.py`, `visualize_flood_timelapse.py`, `visualize_terrain_satellite_3d.py`, `app_terrain_satellite_3d_interactive.py`), tutti eseguiti con successo durante questo audit. |
| `app/agents/visualization_agent.py` | `VisualizationAgent.process()` | Stub totale | `raise NotImplementedError` a riga 26, corpo della funzione vuoto oltre alla docstring. Mai testato, mai chiamato con successo. |

---

## 2. Modulo `app/hydrology`

| File | Funzione/Classe principale | Stato reale | Note |
|---|---|---|---|
| `app/hydrology/candidate_detection.py` | `detect_candidates()` | Completo e testato | Nessuno stub/TODO nel codice eseguibile. Eseguito con successo più volte (vedi sezione script): su `copernicus_glo30_test.tif` produce 6 candidati riproducibili. Nota dichiarata nel docstring (righe 19-21): la "ridge detection" descritta nello spec **non è implementata**, non è un TODO formale ma una funzionalità mancante dichiarata esplicitamente dall'autore. |
| `app/hydrology/cellular_automata.py` | `simulate_flood()` / `simulate_flood_with_snapshots()` | Completo e testato | Nessuno stub. Eseguito con successo in tutti gli script di fase 3+ (vedi sotto), con stabilizzazione raggiunta in tutti i 6 candidati testati. |
| `app/hydrology/flow_routing.py` | `compute_flow_direction()` / `compute_flow_accumulation()` | Stub totale, orphan | Entrambe le funzioni `raise NotImplementedError` (righe 14 e 19). Verificato via grep: **nessun file in `app/` o `scripts/` importa questo modulo** — è codice morto, mai richiamato da nessuna parte della pipeline attuale. |
| `app/hydrology/priority_flood.py` | `fill_depressions()` | Completo e testato | Nessuno stub. Eseguito con successo in ogni script che carica il DEM di test; sul DEM di test riempie 74 celle (`depressions_filled:74_cells`), verificato nell'output reale di `scripts/test_fase2.py`. |

---

## 3. Modulo `app/ingestion`

| File | Funzione/Classe principale | Stato reale | Note |
|---|---|---|---|
| `app/ingestion/contour_extraction.py` | `extract_dem_from_scanned_map()` | Stub totale | `raise NotImplementedError` a riga 31. Mai testato (nessun dato di scansione disponibile nel repo). |
| `app/ingestion/drone_photogrammetry.py` | `extract_dem_from_drone_images()` | Stub totale (placeholder dichiarato) | `raise NotImplementedError("Placeholder — vedi Fase 4 della roadmap implementativa")` a riga 20 — l'autore stesso lo marca come non ancora da implementare. |
| `app/ingestion/lidar_processing.py` | `extract_dem_from_lidar()` | Stub totale | `raise NotImplementedError` a riga 18. Nessun file `.las/.laz` di test presente nel repo. |
| `app/ingestion/public_dem.py` | `load_dem_from_geotiff()` / `download_public_dem()` | Parziale (un ramo completo, un ramo stub) | `load_dem_from_geotiff()`: completo e ampiamente testato — è la funzione più usata in assoluto in questo audit (15 script su 15 la richiamano con successo). `download_public_dem()` (download automatico via API): `raise NotImplementedError` a riga 77, mai testato. |

---

## 4. Modulo `app/viz`

| File | Funzione/Classe principale | Stato reale | Note |
|---|---|---|---|
| `app/viz/animation_builder.py` | `build_animation()` | Stub totale — MA funzionalità equivalente esiste altrove | `raise NotImplementedError` a riga 17. Attenzione: la funzionalità "animazione temporale GIF/MP4" **esiste ed è stata testata con successo** in questo audit, ma implementata come codice duplicato e indipendente dentro `scripts/export_flood_animation.py`, `export_flood_animation_3d.py`, `export_flood_animation_satellite.py` — nessuno di questi script importa o usa `app/viz/animation_builder.py`. Discrepanza architetturale: il modulo "ufficiale" previsto dallo spec è morto, la funzionalità reale vive fuori da `app/`. |
| `app/viz/comparison_charts.py` | `build_comparison_chart()` | Stub totale — MA funzionalità equivalente esiste altrove | `raise NotImplementedError` a riga 14. Stessa situazione: il grafico comparativo Area(t) è generato con successo da `scripts/test_fase3.py` (codice matplotlib inline), bypassando completamente questo modulo. |
| `app/viz/raster_render.py` | `render_static_map()` | Completo e testato | Nessuno stub. Eseguito con successo in `scripts/test_fase4.py`: produce la mappa statica ipsometrica con overlay acqua e marker candidati, file PNG verificato su disco. |

---

## 5. Modulo `app/core`

| File | Funzione/Classe principale | Stato reale | Note |
|---|---|---|---|
| `app/core/config.py` | `Settings` (pydantic-settings) | Completo | Nessuno stub. Semplice dataclass di configurazione, nessuna logica da testare oltre al caricamento da `.env`. |
| `app/core/exceptions.py` | `PipelineError` e sottoclassi | Completo | Solo definizioni di eccezioni, nessuna logica. |
| `app/core/naming.py` | `utc_stamp()` / `timestamped_filename()` | Completo e testato indirettamente | Usato con successo in praticamente tutti gli script eseguiti in questo audit (i nomi dei file di output generati durante l'audit — es. `2026-07-20T23-03-06Z__fase4_final_map.png` — sono prodotti da questa funzione). |
| `app/core/types.py` | `DEMGrid`, `CandidatePoint`, `FloodTimeSeries`, `RankingResult`, `PipelineResult`, `DataSource`, `FlowAlgorithm` | Completo | Solo dataclass/enum di dominio, nessuna logica applicativa da testare. |

---

## 6. Modulo `app/services`

| File | Funzione/Classe principale | Stato reale | Note |
|---|---|---|---|
| `app/services/dem_cache.py` | `DemCache` (cache Redis) | Stub totale, orphan | Tutti e 3 i metodi sollevano `NotImplementedError`: `__init__` riga 13, `get()` riga 16, `set()` riga 19 — persino il costruttore fallisce sempre. Verificato via grep: **mai istanziato da nessuna parte** di `app/` o `scripts/`. |
| `app/services/report_builder.py` | `build_report()` | Stub totale, orphan | `raise NotImplementedError` a riga 13. Verificato via grep: **mai chiamato da nessuna parte**. Nessuno script genera un report Markdown/PDF; questa funzionalità (prevista nello spec, Fase 3 della roadmap) non esiste in nessuna forma nel repo, nemmeno duplicata negli script (a differenza di animazioni e grafici comparativi).

---

## 7. `app/main.py` (entry point CLI)

| File | Funzione/Classe principale | Stato reale | Note |
|---|---|---|---|
| `app/main.py` | `main()` (CLI argparse → `Orchestrator.run()`) | Presente ma non funzionante end-to-end | Nessuno stub nel file stesso: il parsing argomenti è completo e corretto. Ma l'esecuzione reale fallisce **sempre**, in ogni caso d'uso, perché `Orchestrator.run()` chiama `DemIngestAgent.process()` che è uno stub. Comando eseguito ed esito verificato in questo audit: |

```
$ python -m app.main --source data/dem/copernicus_glo30_test.tif --source-type public_dem
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "C:\GitHub\watershed-flood-ai\app\main.py", line 33, in <module>
    main()
  File "C:\GitHub\watershed-flood-ai\app\main.py", line 24, in main
    result = orchestrator.run(args.source, DataSource(args.source_type))
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\GitHub\watershed-flood-ai\app\agents\orchestrator.py", line 32, in run
    dem = self.dem_ingest_agent.process(source_path, source_type)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\GitHub\watershed-flood-ai\app\agents\dem_ingest_agent.py", line 24, in process
    raise NotImplementedError
NotImplementedError
```

**Conclusione chiave**: l'unico punto di ingresso "ufficiale" della pipeline (`app/main.py` → `Orchestrator`) non ha mai funzionato nemmeno una volta con il DEM di test disponibile nel repo. Tutta la pipeline che funziona realmente (fasi 1→4, dal caricamento DEM alla mappa finale) esiste e gira solo attraverso gli script in `scripts/`, che chiamano direttamente le funzioni di `app/hydrology/` e `app/ingestion/public_dem.py`, bypassando completamente `Orchestrator` e 4 delle 5 classi Agent.

Anche `tests/test_orchestrator.py` conferma questo stato: l'unico test presente è marcato `pytest.skip("TODO: implementare dopo DemIngestAgent.process()")` — la suite di test (`pytest tests/ -q`) è stata eseguita in questo audit e risulta: `1 skipped in 0.03s`.

---

## 8. Esecuzione reale degli script in `scripts/`

Tutti gli script sono stati eseguiti realmente con `.venv/Scripts/python.exe` da riga di comando (`python -m scripts.<nome>`), usando `data/dem/copernicus_glo30_test.tif`. I tempi sono wall-clock reali misurati con timestamp prima/dopo l'esecuzione. Ogni "Output prodotto" è stato verificato con `ls -la` sul file reale, non dedotto dai print dello script.

| Script | Esito | Tempo approssimativo | Output prodotto (path verificato) | Errore |
|---|---|---|---|---|
| `test_load_dem.py` | OK | ~2s | Nessuno (solo stampa a console: shape, min/max quota, cell_size_m, quality_flags) | — |
| `test_fase2.py` | OK | ~3s | Nessuno (solo stampa: 6 candidati con rationale) | — |
| `test_fase3.py` | OK | ~7s | `output/maps/2026-07-20T23-02-51Z__fase3_comparison.png` (99 307 byte, verificato su disco) | — |
| `test_fase4.py` | OK | ~4s | `output/maps/2026-07-20T23-03-06Z__fase4_final_map.png` (verificato su disco) | — |
| `diagnose_candidates.py` | OK | ~1s | Nessuno (solo tabella diagnostica a console) | — |
| `diagnose_trame_minimal.py` | Interattivo — non testabile fino a interruzione manuale | ~15s (avviato, poi terminato via timeout) | `diagnose_screenshot.png` (17 949 byte, rigenerato e verificato su disco) | Nessun errore: server trame partito correttamente, client connesso, render iniziale eseguito con successo entro il timeout di 15s. |
| `export_flood_animation.py` | OK | ~12s | `output/animations/2026-07-20T23-03-48Z__flood_animation.gif` (432 674 byte) **e** `...flood_animation.mp4` (63 392 byte) — ffmpeg risulta disponibile nell'ambiente, entrambi i file verificati su disco | — |
| `export_flood_animation_3d.py` | OK | ~153s (2m33s) | `output/animations/2026-07-20T23-21-05Z__flood_animation_3d.gif` (3 908 994 byte) **e** `...flood_animation_3d.mp4` (70 832 byte), entrambi verificati su disco | — |
| `export_flood_animation_satellite.py` | OK | ~19s | `output/animations/2026-07-20T23-22-37Z__flood_animation_satellite.gif` (8 920 705 byte) **e** `...flood_animation_satellite.mp4` (204 409 byte), verificati su disco | — |
| `visualize_dem.py` | OK | ~2s | `output/maps/2026-07-20T23-03-35Z__dem_candidates_debug.png` (98 072 byte, verificato) | — |
| `visualize_dem_satellite.py` | OK (richiede internet — Esri World Imagery, verificato raggiungibile) | ~4s | `output/maps/2026-07-20T23-21-16Z__dem_satellite_overlay.html` (1 669 750 byte, verificato) | — |
| `visualize_flood_3d.py` | OK | ~5s | `output/maps/2026-07-20T23-21-39Z__flood_3d.html` (7 768 679 byte, verificato) | — |
| `visualize_flood_timelapse.py` | OK (richiede internet) | ~9s | `output/maps/2026-07-20T23-22-08Z__flood_timelapse.html` (2 382 227 byte, verificato) | — |
| `visualize_terrain_satellite_3d.py` | OK (richiede internet + pyvista/vtk) | ~12s | `output/maps/2026-07-20T23-23-09Z__terrain_satellite_3d.html` (2 506 970 byte, verificato) | — |
| `app_terrain_satellite_3d_interactive.py` | Interattivo — non testabile fino a interruzione manuale | ~30s (avviato, poi terminato via timeout) | Nessun file (serve pagine via server locale su `http://localhost:8080`) | Nessun errore: pipeline di rilevamento candidati + simulazione + download satellite + avvio server trame completata con successo entro il timeout di 30s. |

**Nota trasversale non bloccante**: diversi script (`test_fase2.py`, `test_fase3.py`, `test_fase4.py`, `export_flood_animation*.py`) stampano a console caratteri accentati/simboli (`m²`, `m³`, `è`) che appaiono come `�` nel terminale Windows usato per l'audit (mismatch tra encoding UTF-8 dei sorgenti e codepage della console, es. cp1252/850). Questo **non è un bug funzionale**: i file salvati su disco (PNG, HTML) sono corretti e non affetti — è solo un problema di visualizzazione a schermo dell'output di `print()`.

**Nota su rete**: 5 script (`visualize_dem_satellite.py`, `visualize_flood_timelapse.py`, `export_flood_animation_satellite.py`, `visualize_terrain_satellite_3d.py`, `app_terrain_satellite_3d_interactive.py`) dipendono da una chiamata HTTP reale al servizio pubblico Esri World Imagery (`server.arcgisonline.com`) senza API key. La raggiungibilità è stata verificata esplicitamente in questo audit (richiesta di test, HTTP 200). Se questo servizio non fosse raggiungibile (rete assente, rate limit, servizio down), questi script fallirebbero — è una dipendenza esterna non documentata esplicitamente come tale nel README.

---

## 9. Verifica `requirements.txt` vs ambiente reale

Comando eseguito: `.venv/Scripts/python.exe -m pip freeze` (156 pacchetti installati), confrontato riga per riga con `requirements.txt`.

### 9.1 Pacchetti in `requirements.txt` ma NON installati nel venv

Nessuno. Tutti i pacchetti elencati in `requirements.txt` risultano installati nel venv (incluse le righe duplicate/ridondanti `plotly` e `kaleido` a righe 19-20, che non aggiungono nulla rispetto alle righe 10 e 12 già presenti).

### 9.2 Pacchetti installati nel venv ma NON elencati in `requirements.txt`

Il gruppo più rilevante — usato realmente da 3 script eseguiti con successo in questo audit (`visualize_terrain_satellite_3d.py`, `app_terrain_satellite_3d_interactive.py`, `diagnose_trame_minimal.py`) — **non è tracciato in `requirements.txt`**:

- `pyvista==0.48.4`
- `vtk==9.6.2`
- `trame==3.13.2`, `trame-client==3.13.2`, `trame-common==1.2.4`, `trame-server==3.12.5`, `trame-vtk==2.11.8`, `trame-vuetify==3.2.2`
- `wslink==2.5.7`, `simpervisor==1.0.0`

Conseguenza pratica: un `pip install -r requirements.txt` da zero **non basterebbe** a far girare 3 dei 15 script di `scripts/` (quelli che usano la vista 3D con texture satellitare via PyVista/trame) — servirebbe installare questo stack manualmente, senza che sia documentato né in `requirements.txt` né nel README.

Altri pacchetti installati ma non elencati sono in gran parte dipendenze transitive attese (matplotlib/scikit-image/rasterio/uvicorn[standard]/redis[asyncio] portano con sé `contourpy`, `cycler`, `fonttools`, `kiwisolver`, `imageio`, `tifffile`, `networkx`, `pooch`, `affine`, `cligj`, `click`, `watchfiles`, `websockets`, `httptools`, `python-dotenv`, `PyYAML`, `aiohttp` e simili) e un ecosistema Jupyter/IPython completo (`ipython`, `ipywidgets`, `jupyter_client`, `jupyter_core`, `jupyter_server`, `nbconvert`, `nbformat`, `notebook`-adjacent, `jupyter_server_proxy`, ecc.) presumibilmente introdotto da `trame`/`pyvista` o da tool dell'editor — non necessari per il funzionamento della pipeline stessa, ma presenti nel venv. Non sono considerati un problema in sé (sono transitivi), ma confermano che il venv reale è più pesante e diverso da quanto `requirements.txt` lascia intendere.

### 9.3 Versioni disallineate (richiesta vs installata)

Tutte le versioni installate soddisfano il vincolo `>=` dichiarato in `requirements.txt` (nessun pacchetto è sotto la soglia minima), ma diversi hanno subito salti di versione major, con potenziale rischio di breaking change non verificato esplicitamente in questo audit oltre al fatto che gli script sopra hanno effettivamente funzionato:

| Pacchetto | Richiesto | Installato | Salto |
|---|---|---|---|
| `numpy` | `>=1.26.0` | `2.5.1` | major 1→2 |
| `opencv-python` | `>=4.10.0` | `5.0.0.93` | major 4→5 |
| `pandas` | `>=2.0.0` | `3.0.3` | major 2→3 |
| `kaleido` | `>=0.2.1` | `1.3.0` | major 0→1 (v1 ha cambiato architettura interna, vedi pacchetto aggiuntivo `choreographer` presente nel venv) |
| `redis[asyncio]` | `>=5.0.0` | `8.0.1` | major 5→8 |

Questi salti non hanno causato errori negli script eseguiti in questo audit (tutti gli script che usano `kaleido`, `pandas`-simili, `opencv` indirettamente via `scikit-image` hanno funzionato), ma il file `requirements.txt` non fissa un limite superiore (`<`) su nessun pacchetto, quindi una nuova installazione futura potrebbe scaricare versioni ancora più recenti senza alcuna garanzia di compatibilità testata.

---

## 10. Discrepanze trovate rispetto a INTEGRAZIONI.md

**Il file `INTEGRAZIONI.md` non esiste da nessuna parte nel repository.** È stata effettuata una ricerca ricorsiva in tutte le directory del progetto (incluse `docs/`, `app/`, `scripts/`, `tests/`, root) e il file non è presente in nessuna forma o posizione. Non è quindi stato possibile effettuare il confronto diretto richiesto tra questo audit e un ipotetico `INTEGRAZIONI.md`. Questa è di per sé una discrepanza/assenza documentale da segnalare esplicitamente.

In assenza di quel file, il confronto è stato fatto con la documentazione di stato/architettura effettivamente presente nel repo (`README.md`, `README.it.md`, `docs/spec/watershed_ai_spec_ORIGINALE.md`). Discrepanze rilevate:

1. **Il README è già onesto sullo stato "non-AI" e sul fatto che l'LLM non è implementato** (sezione "È realmente un sistema ad agenti AI?") — su questo punto non c'è discrepanza, anzi il README è più cauto del codice in un paio di punti. Nessuna azione richiesta qui.

2. **`docs/spec/watershed_ai_spec_ORIGINALE.md`, sezione "ROADMAP IMPLEMENTATIVA" (righe 510-546): tutte le checkbox sono `[ ]` (non completate)**, incluse quelle di "Fase 1 — Validazione pipeline core" che elencano esattamente: `candidate_detection.py`, `priority_flood.py`, `cellular_automata.py` e "prima mappa statica con overlay acqua". Questo audit dimostra con esecuzione reale che **tutti e quattro questi elementi sono in realtà completi, funzionanti e testati** (vedi sezioni 2 e 8 sopra). Non è una discrepanza nel senso "la doc dichiara completo ma non lo è" — è l'opposto: la roadmap è **disallineata per difetto** (sottostima lo stato reale, non lo sovrastima). Va comunque segnalata perché chiunque legga solo lo spec penserebbe che nulla di Fase 1 sia stato iniziato.

3. **Discrepanza architetturale più significativa**: lo spec e il README descrivono un'architettura a 5 "agent" (`app/agents/*.py`) orchestrati da `Orchestrator`, con output prodotti da `app/viz/animation_builder.py`, `app/viz/comparison_charts.py` e `app/services/report_builder.py`. Nella realtà verificata in questo audit:
   - Questi 3 moduli sono **stub vuoti** (`NotImplementedError`), mai completati.
   - La stessa funzionalità (animazioni GIF/MP4, grafico comparativo Area(t)) **esiste comunque ed è stata testata con successo**, ma è stata reimplementata da zero, duplicata, dentro gli script in `scripts/` — bypassando completamente l'architettura "ufficiale" `app/viz/`.
   - L'unico punto di ingresso ufficiale (`app/main.py` → `Orchestrator.run()`) **non ha mai funzionato nemmeno una volta** nei test di questo audit (fallisce immediatamente su `DemIngestAgent.process()`, stub).
   - Il report finale Markdown/PDF (`report_builder.build_report()`) non esiste in nessuna forma nel repo, nemmeno duplicato negli script: è l'unico output previsto dallo spec completamente assente ad oggi.

   In sintesi: **la pipeline "vera" che funziona oggi non è quella descritta come architettura in `app/agents/`+`Orchestrator`, ma un insieme di 15 script indipendenti in `scripts/` che richiamano direttamente le funzioni di `app/hydrology/` e `app/ingestion/public_dem.py`.** Chi legga lo spec o il README aspettandosi di poter lanciare `python -m app.main` e ottenere una pipeline completa (DEM → candidati → simulazione → ranking → mappa/animazione/report) troverebbe invece un crash immediato; per ottenere risultati reali bisogna sapere di dover usare gli script in `scripts/`, che non sono menzionati nello spec come il percorso operativo effettivo.

4. **Stack PyVista/trame/VTK usato da 3 script funzionanti non è documentato né in `requirements.txt` né nel README/spec** (vedi sezione 9.2) — chi seguisse la Quickstart del README (`pip install -r requirements.txt`) non riuscirebbe a far girare quegli script senza scoprirlo da un `ModuleNotFoundError` a runtime.

---

## Riepilogo numerico

- **Moduli `app/` ispezionati**: 25 file `.py` (agents: 7, hydrology: 4, ingestion: 4, viz: 3, core: 4, services: 2, main: 1 — nota: `__init__.py` esclusi dal conteggio funzionale).
- **Stato**: 10 completi e testati (`base.py`, `ranking_agent.py`, `candidate_detection.py`, `cellular_automata.py`, `priority_flood.py`, `raster_render.py`, `config.py`, `exceptions.py`, `naming.py`, `types.py`), 3 parziali — un ramo completo + uno stub nello stesso file (`dem_ingest_agent.py`, `orchestrator.py`, `public_dem.py`), 9 stub totali con `NotImplementedError` (`visualization_agent.py`, `flow_routing.py`, `contour_extraction.py`, `drone_photogrammetry.py`, `lidar_processing.py`, `animation_builder.py`, `comparison_charts.py`, `dem_cache.py`, `report_builder.py`), 2 "presenti ma mai testati come classe" — thin wrapper il cui unico stato verificabile è quello della funzione delegata (`candidate_point_agent.py`, `flood_simulation_agent.py`), 1 "presente ma non funzionante end-to-end" (`main.py`, fallisce sempre in esecuzione reale).
- **Script in `scripts/` eseguiti**: 15/15. Esito: 13 OK (con output verificato su disco dove previsto), 2 interattivi (server trame) avviati con successo entro un timeout breve e poi terminati manualmente — nessun fallimento reale riscontrato in nessuno dei 15 script.
- **`requirements.txt`**: 0 pacchetti mancanti, ~9 pacchetti installati e realmente usati ma non tracciati (stack PyVista/trame/VTK), 5 pacchetti con salto di versione major rispetto al minimo richiesto.
