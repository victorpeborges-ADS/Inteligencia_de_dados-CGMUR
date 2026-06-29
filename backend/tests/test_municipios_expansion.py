"""Testes expansão 50 municípios + índice VM."""
from __future__ import annotations

from pathlib import Path

import yaml


def _load_manifest():
    path = Path(__file__).resolve().parents[1] / "seeds" / "municipios_seed_50.yaml"
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh).get("municipios", [])


def test_seed_manifest_has_61_municipios():
    rows = _load_manifest()
    assert len(rows) == 61
    codes = {r["codigo_ibge"] for r in rows}
    assert len(codes) == 61
    assert "2611606" in codes
    assert "3550308" in codes
    assert "5201108" in codes  # Anápolis — Cidades +Inteligentes


def test_seed_criterios():
    rows = _load_manifest()
    criterios = {r["criterio"] for r in rows}
    assert "capital" in criterios
    assert "s2id_emergencia" in criterios
    assert "cidades_mais_inteligentes" in criterios
    assert sum(1 for r in rows if r["criterio"] == "capital") == 27
    assert sum(1 for r in rows if r["criterio"] == "cidades_mais_inteligentes") == 19


def test_cidades_mais_inteligentes_edital_2026():
    """22 municípios do Edital SNDUM 1/2026 (3 já como capitais)."""
    rows = _load_manifest()
    codes = {r["codigo_ibge"] for r in rows}
    edital_22 = {
        "1702109", "1400233", "2604106", "2407104", "2924009", "2806701",
        "5201108", "5208905", "5218805", "4302105", "4304606", "4104907",
        "4305108", "3200607", "3509502", "3138203", "3548708", "3549904",
        "3305505", "1501402", "2408102", "4106902",  # Belém, Natal, Curitiba
    }
    assert edital_22.issubset(codes)
