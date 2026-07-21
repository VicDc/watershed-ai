"""Test scheletro — da completare quando gli agenti avranno implementazione reale.

Suggerimento: usare un DEM sintetico piccolo (es. cono/piramide numpy) per
i primi test di candidate_detection e cellular_automata, senza dipendere
da dati reali scaricati.
"""
import pytest


def test_orchestrator_raises_on_invalid_source(monkeypatch):
    """La pipeline deve sollevare PipelineError se il DEM risulta vuoto."""
    pytest.skip("TODO: implementare dopo DemIngestAgent.process()")
