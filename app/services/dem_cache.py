"""Cache Redis per DEM pesanti (opzionale).

Utile quando lo stesso DEM (es. area geografica ricorrente) viene
riutilizzato tra run diverse, evitando di rileggere/riprocessare i file
raw ogni volta.
"""
from app.core.types import DEMGrid


class DemCache:
    def __init__(self, redis_url: str) -> None:
        self.redis_url = redis_url
        raise NotImplementedError

    def get(self, key: str) -> DEMGrid | None:
        raise NotImplementedError

    def set(self, key: str, dem: DEMGrid, ttl_s: int | None = None) -> None:
        raise NotImplementedError
