"""Testes do catálogo piloto (8 municípios — capitais + PE LiDAR)."""
from __future__ import annotations

from pathlib import Path

import yaml

from app.data_connectors.constants import TARGET_IBGE_CODES


def _load_manifest():
    path = Path(__file__).resolve().parents[1] / "seeds" / "municipios_seed_50.yaml"
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh).get("municipios", [])


def test_seed_manifest_piloto_8_municipios():
    rows = _load_manifest()
    assert len(rows) == 8
    codes = {r["codigo_ibge"] for r in rows}
    assert codes == set(TARGET_IBGE_CODES)
    assert "2611606" in codes  # Recife
    assert "2800308" in codes  # Aracaju
    assert "2603603" in codes  # Camutanga
    assert "2607604" in codes  # Ilha de Itamaracá


def test_seed_criterios_piloto():
    rows = _load_manifest()
    by_code = {r["codigo_ibge"]: r for r in rows}
    assert by_code["2611606"]["criterio"] == "capital"
    assert by_code["2800308"]["criterio"] == "capital"
    assert by_code["2603603"]["criterio"] == "lidar_pe3d"
    assert by_code["2607604"]["criterio"] == "lidar_pe3d"
    assert rows[0]["codigo_ibge"] == "2611606"
    assert rows[1]["codigo_ibge"] == "2800308"
