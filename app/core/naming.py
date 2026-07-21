"""Utility di naming condivise, coerenti con docs/NAMING-CONVENTIONS.md.

Usate dagli script in scripts/ per non sovrascrivere mai un output
precedente: ogni run produce un file con timestamp UTC distinto,
confrontabile con i run precedenti.
"""
from datetime import datetime, timezone


def utc_stamp() -> str:
    """Timestamp UTC filesystem-safe: 2026-07-01T14-32-08Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def timestamped_filename(stem: str, ext: str) -> str:
    """Es. timestamped_filename('dem_candidates_debug', 'png')
    -> '2026-07-01T14-32-08Z__dem_candidates_debug.png'
    """
    return f"{utc_stamp()}__{stem}.{ext}"
