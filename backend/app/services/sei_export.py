"""Pacote de exportação institucional (SEI) — metadados + hash SHA-256."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings
from app.models import Municipio, RelatorioMunicipal


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_municipal_sei_package(
    record: RelatorioMunicipal,
    muni: Municipio | None,
    *,
    base_url: str = "",
) -> dict[str, Any]:
    path = Path(record.caminho_arquivo)
    file_hash = record.sha256_hash
    if not file_hash and path.exists():
        file_hash = sha256_file(path)
    elif not file_hash:
        file_hash = ""

    download_path = f"/api/v1/reports/{record.id}/download"
    download_url = f"{base_url.rstrip('/')}{download_path}" if base_url else download_path
    sei_export_path = f"/api/v1/reports/{record.id}/sei-export"
    sei_export_url = f"{base_url.rstrip('/')}{sei_export_path}" if base_url else sei_export_path

    gerado_em = record.gerado_em
    if gerado_em.tzinfo is None:
        gerado_em = gerado_em.replace(tzinfo=timezone.utc)

    municipio_meta: dict[str, Any] = {
        "codigo_ibge": record.codigo_ibge,
    }
    if muni:
        municipio_meta.update({"nome": muni.nome, "uf": muni.uf})

    return {
        "documento_tipo": "relatorio_territorial_sinidu",
        "sistema_origem": "Sinidu+Clima",
        "versao_sistema": "1.1.0",
        "municipio": municipio_meta,
        "relatorio": {
            "id": record.id,
            "nome_arquivo": record.nome_arquivo,
            "tamanho_bytes": record.tamanho_bytes,
            "status": record.status,
            "gerado_em": gerado_em.isoformat(),
        },
        "integridade": {
            "algoritmo": "SHA-256",
            "hash": file_hash,
        },
        "urls": {
            "download_pdf": download_url,
            "metadados_json": sei_export_url,
        },
        "observacao": (
            "Pacote gerado pelo Sinidu+Clima para protocolo manual no SEI. "
            "Não substitui assinatura eletrônica nem tramitação automática."
        ),
    }
