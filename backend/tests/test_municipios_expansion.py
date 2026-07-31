"""Testes do catálogo piloto (6 municípios)."""
from __future__ import annotations

from pathlib import Path

import yaml

from app.data_connectors.constants import TARGET_IBGE_CODES


def _load_manifest():
    path = Path(__file__).resolve().parents[1] / "seeds" / "municipios_seed_50.yaml"
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh).get("municipios", [])


def test_seed_manifest_piloto_6_municipios():
    rows = _load_manifest()
    assert len(rows) == 6
    codes = {r["codigo_ibge"] for r in rows}
    assert codes == set(TARGET_IBGE_CODES)
    assert "2611606" in codes  # Recife
    assert "2800308" in codes  # Aracaju
    assert "2927408" in codes  # Salvador
    assert "3550308" in codes  # São Paulo
    assert "3304557" in codes  # Rio de Janeiro
    assert "5300108" in codes  # Brasília


def test_seed_criterios_piloto():
    rows = _load_manifest()
    assert all(r["criterio"] == "capital" for r in rows)
    assert rows[0]["codigo_ibge"] == "2611606"
    assert rows[1]["codigo_ibge"] == "2800308"
