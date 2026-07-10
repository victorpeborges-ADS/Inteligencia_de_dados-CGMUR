"""Testes do serviço de importação CSV SINGED Lab."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from app.data_connectors.constants import TARGET_IBGE_CODES
from app.services.singedlab_import_service import (
    merge_into_seed,
    normalize_ibge_export_bytes,
    run_singedlab_csv_import,
)


def _csv_bytes(header: str, *rows: str) -> bytes:
    body = "\n".join([header, *rows])
    return body.encode("utf-8-sig")


def test_normalize_flexible_column_aliases():
    content = _csv_bytes(
        "cd_mun,pop_residente,total_domicilios",
        "4304606,160677,69196",
    )
    rows = normalize_ibge_export_bytes(content)
    assert len(rows) == 1
    assert rows[0]["codigo_ibge"] == "4304606"
    assert rows[0]["populacao_area_afetada"] == "160677"
    assert rows[0]["domicilios_area_afetada"] == "69196"
    assert rows[0]["data_quality"] == "oficial"


def test_merge_into_seed_preserves_priority_municipios(tmp_path: Path):
    target = tmp_path / "seed.csv"
    import_rows = [
        {
            "codigo_ibge": "4305108",
            "escopo": "aplicavel",
            "populacao_area_afetada": "42000",
            "domicilios_area_afetada": "18000",
            "estabelecimentos_area_afetada": "",
            "pct_populacao_municipio": "8.2",
            "pct_area_municipio": "",
            "data_quality": "oficial",
            "fonte_ref": "",
        }
    ]
    merged = merge_into_seed(import_rows, target, source_label="caxias.csv")
    assert merged == 1

    with target.open(encoding="utf-8", newline="") as handle:
        rows = {r["codigo_ibge"]: r for r in csv.DictReader(handle)}
    assert len(rows) == len(TARGET_IBGE_CODES)
    caxias = rows["4305108"]
    assert caxias["populacao_area_afetada"] == "42000"
    assert "caxias.csv" in caxias["fonte_ref"]
    assert rows["2611606"]["escopo"] == "nao_aplicavel"


def test_run_import_without_db(tmp_path: Path):
    target = tmp_path / "seed.csv"
    content = _csv_bytes(
        "codigo_ibge,populacao_area_afetada",
        "4316907,12500",
    )
    result = run_singedlab_csv_import(
        content,
        filename="sao_luiz.csv",
        target_csv=target,
        db=None,
    )
    assert result["imported_municipios"] == 1
    assert result["codigos_ibge"] == ["4316907"]
    assert "sync" not in result


def test_run_import_rejects_empty_csv():
    content = _csv_bytes("codigo_ibge,populacao", "")
    with pytest.raises(ValueError, match="Nenhuma linha reconhecida"):
        run_singedlab_csv_import(content, filename="vazio.csv", db=None)
