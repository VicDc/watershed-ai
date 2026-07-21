"""Config centralizzata, letta da .env tramite pydantic-settings.

Nessun parametro va hardcoded negli agenti: tutto passa da qui.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Sorgente dati default
    default_source_type: str = "public_dem"

    # DEM pubblici
    opentopography_api_key: str = ""

    # Simulazione (Fase 3 — vedi hydrology/cellular_automata.py)
    flow_rate_m3_s: float = 5.0
    time_step_s: float = 60.0
    max_simulation_time_s: float = 21600.0

    # Candidate detection (Fase 2 — vedi hydrology/candidate_detection.py)
    min_prominence_m: float = 10.0
    local_max_window_cells: int = 15
    min_watershed_area_cells: int = 100

    # Output
    output_dir: str = "output"
    redis_url: str = "redis://localhost:6379/0"

    # LLM (opzionale — solo narrativa, mai calcoli idrologici)
    llm_base_url: str = "http://localhost:1234/v1"
    llm_model: str = "gemma-4-26b"


settings = Settings()
