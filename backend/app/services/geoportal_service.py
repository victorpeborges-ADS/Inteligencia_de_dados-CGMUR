"""Geoportal municipal — publicação CTM (upload / API local) — Fase 16d.5."""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from sqlalchemy.orm import Session

from app.data_connectors.ctm_collector import (
    catalog_ctm_targets,
    collect_ctm_municipality,
    fetch_arcgis_geojson,
    fetch_geojson_url,
    import_ctm_mesh,
)
from app.data_connectors.ctm_registry import CTM_BY_CODE, CtmSource
from app.models import Bairro, Municipio, MunicipioGeoportalPublicacao, MunicipioSeed

logger = logging.getLogger(__name__)

GEOPORTAL_TIPOS = frozenset({"arcgis_rest", "geojson_url", "upload_geojson", "upload_shapefile"})
MAX_SNAPSHOT_FEATURES = 800
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def _normalize_codigo(codigo_ibge: str) -> str:
    return str(codigo_ibge).strip().zfill(7)[:7]


def _deactivate_previous(db: Session, codigo_ibge: str) -> None:
    db.query(MunicipioGeoportalPublicacao).filter(
        MunicipioGeoportalPublicacao.codigo_ibge == codigo_ibge,
        MunicipioGeoportalPublicacao.ativo.is_(True),
    ).update({"ativo": False}, synchronize_session=False)


def _publication_dict(row: MunicipioGeoportalPublicacao | None) -> dict[str, Any] | None:
    if not row:
        return None
    return {
        "id": row.id,
        "tipo": row.tipo,
        "titulo": row.titulo,
        "url": row.url,
        "arquivo_nome": row.arquivo_nome,
        "feature_count": row.feature_count,
        "status": row.status,
        "mensagem": row.mensagem,
        "ativo": row.ativo,
        "publicado_em": row.publicado_em.isoformat() if row.publicado_em else None,
        "importado_em": row.importado_em.isoformat() if row.importado_em else None,
    }


def parse_upload_to_geojson(content: bytes, filename: str) -> dict[str, Any]:
    """Converte upload GeoJSON ou ZIP shapefile em FeatureCollection."""
    name = (filename or "").lower()
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError(f"Arquivo excede {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")

    if name.endswith(".geojson") or name.endswith(".json"):
        data = json.loads(content.decode("utf-8"))
        if data.get("type") != "FeatureCollection":
            raise ValueError("Arquivo JSON deve ser FeatureCollection GeoJSON.")
        return data

    if name.endswith(".zip"):
        return _shapefile_zip_to_geojson(content)

    raise ValueError("Formato não suportado. Envie .geojson, .json ou .zip (shapefile).")


def _shapefile_zip_to_geojson(content: bytes) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        zip_path = root / "upload.zip"
        zip_path.write_bytes(content)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(root)
        shp_files = list(root.rglob("*.shp"))
        if not shp_files:
            raise ValueError("ZIP não contém arquivo .shp.")
        out_path = root / "malha.geojson"
        try:
            subprocess.run(
                [
                    "ogr2ogr",
                    "-f",
                    "GeoJSON",
                    str(out_path),
                    str(shp_files[0]),
                    "-t_srs",
                    "EPSG:4326",
                ],
                check=True,
                capture_output=True,
                timeout=120,
            )
        except FileNotFoundError as exc:
            raise ValueError("Conversão shapefile indisponível (ogr2ogr não instalado).") from exc
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or b"").decode("utf-8", errors="replace")[:300]
            raise ValueError(f"Falha ao converter shapefile: {stderr}") from exc
        data = json.loads(out_path.read_text(encoding="utf-8"))
        if data.get("type") != "FeatureCollection":
            raise ValueError("Conversão shapefile não gerou FeatureCollection.")
        return data


def register_geoportal_api(
    db: Session,
    muni: Municipio,
    *,
    tipo: str,
    url: str,
    titulo: str = "Malha de bairros CTM",
    arcgis_where: str = "1=1",
    nome_campo_bairro: str | None = None,
) -> dict[str, Any]:
    if tipo not in {"arcgis_rest", "geojson_url"}:
        raise ValueError("tipo deve ser arcgis_rest ou geojson_url")
    if not url.strip():
        raise ValueError("URL obrigatória.")

    _deactivate_previous(db, muni.codigo_ibge)
    row = MunicipioGeoportalPublicacao(
        codigo_ibge=muni.codigo_ibge,
        municipio_id=muni.id,
        tipo=tipo,
        titulo=titulo,
        url=url.strip(),
        arcgis_where=arcgis_where or "1=1",
        nome_campo_bairro=nome_campo_bairro,
        status="registrado",
        mensagem="Fonte API registrada — execute importação para aplicar no mapa.",
        ativo=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"publicacao": _publication_dict(row)}


def register_geoportal_upload(
    db: Session,
    muni: Municipio,
    *,
    content: bytes,
    filename: str,
    titulo: str = "Malha de bairros CTM",
) -> dict[str, Any]:
    geojson = parse_upload_to_geojson(content, filename)
    features = geojson.get("features") or []
    tipo = "upload_shapefile" if filename.lower().endswith(".zip") else "upload_geojson"

    snapshot = geojson if len(features) <= MAX_SNAPSHOT_FEATURES else None
    _deactivate_previous(db, muni.codigo_ibge)
    row = MunicipioGeoportalPublicacao(
        codigo_ibge=muni.codigo_ibge,
        municipio_id=muni.id,
        tipo=tipo,
        titulo=titulo,
        arquivo_nome=filename,
        feature_count=len(features),
        status="registrado",
        mensagem=f"{len(features)} feições recebidas — execute importação para publicar no Sinidu.",
        geojson_snapshot=snapshot,
        ativo=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "publicacao": _publication_dict(row),
        "feature_count": len(features),
        "snapshot_stored": snapshot is not None,
    }


def _fetch_publication_geojson(pub: MunicipioGeoportalPublicacao) -> dict[str, Any]:
    if pub.tipo in {"upload_geojson", "upload_shapefile"}:
        if pub.geojson_snapshot:
            return pub.geojson_snapshot
        raise ValueError("Snapshot do upload indisponível — reenvie o arquivo.")

    if pub.tipo == "geojson_url":
        if not pub.url:
            raise ValueError("URL GeoJSON não configurada.")
        return fetch_geojson_url(pub.url)

    if pub.tipo == "arcgis_rest":
        if not pub.url:
            raise ValueError("URL ArcGIS REST não configurada.")
        source = CtmSource(
            codigo_ibge=pub.codigo_ibge,
            nome=pub.titulo,
            uf="",
            kind="arcgis",
            url=pub.url,
            name_fields=(pub.nome_campo_bairro or "nome", "NM_BAIRRO", "nome"),
            where=pub.arcgis_where or "1=1",
        )
        return fetch_arcgis_geojson(source)

    raise ValueError(f"Tipo de publicação não suportado: {pub.tipo}")


def import_geoportal_publication(
    db: Session,
    muni: Municipio,
    *,
    publicacao_id: int | None = None,
) -> dict[str, Any]:
    query = db.query(MunicipioGeoportalPublicacao).filter(
        MunicipioGeoportalPublicacao.codigo_ibge == muni.codigo_ibge,
        MunicipioGeoportalPublicacao.ativo.is_(True),
    )
    if publicacao_id:
        pub = query.filter(MunicipioGeoportalPublicacao.id == publicacao_id).first()
    else:
        pub = query.order_by(MunicipioGeoportalPublicacao.publicado_em.desc()).first()

    if not pub:
        return {
            "codigo_ibge": muni.codigo_ibge,
            "error": "Nenhuma publicação geoportal ativa. Registre API ou envie arquivo.",
            "skipped": True,
        }

    try:
        geojson = _fetch_publication_geojson(pub)
        result = import_ctm_mesh(db, muni, geojson, source_label="geoportal_municipal")
    except Exception as exc:
        pub.status = "erro"
        pub.mensagem = str(exc)[:500]
        db.commit()
        return {"codigo_ibge": muni.codigo_ibge, "error": str(exc), "publicacao_id": pub.id}

    if result.get("error"):
        pub.status = "erro"
        pub.mensagem = str(result.get("error"))[:500]
        db.commit()
        return {**result, "publicacao_id": pub.id}

    pub.status = "importado"
    pub.feature_count = result.get("bairros") or pub.feature_count
    pub.importado_em = datetime.utcnow()
    pub.mensagem = f"Malha importada — {result.get('bairros', 0)} bairros publicados."
    seed = db.query(MunicipioSeed).filter(MunicipioSeed.codigo_ibge == muni.codigo_ibge).first()
    if seed:
        seed.malha_fonte = "geoportal_municipal"
    db.commit()

    return {
        **result,
        "publicacao_id": pub.id,
        "fonte": "geoportal_municipal",
        "status": "importado",
    }


def get_geoportal_status(db: Session, muni: Municipio) -> dict[str, Any]:
    code = muni.codigo_ibge
    bairros = db.query(Bairro).filter(Bairro.municipio_id == muni.id).count()
    seed = db.query(MunicipioSeed).filter(MunicipioSeed.codigo_ibge == code).first()
    pub = (
        db.query(MunicipioGeoportalPublicacao)
        .filter(
            MunicipioGeoportalPublicacao.codigo_ibge == code,
            MunicipioGeoportalPublicacao.ativo.is_(True),
        )
        .order_by(MunicipioGeoportalPublicacao.publicado_em.desc())
        .first()
    )
    ctm_registry = CTM_BY_CODE.get(code)
    catalog_row = next((r for r in catalog_ctm_targets() if r.get("codigo_ibge") == code), None)

    acoes: list[str] = []
    if bairros < 4:
        acoes.append("Publicar malha de bairros via upload GeoJSON/shapefile ou API municipal.")
    if not pub and not ctm_registry:
        acoes.append("Registrar URL do geoportal (ArcGIS REST ou GeoJSON) na prefeitura.")
    if pub and pub.status == "registrado":
        acoes.append("Executar importação para aplicar a malha publicada no mapa Sinidu.")
    if ctm_registry and catalog_row and catalog_row.get("status") not in ("sem_ctm_cadastrada", "erro"):
        acoes.append("Alternativa: sincronizar CTM do catálogo nacional ReDUS/GeoReDUS.")

    return {
        "codigo_ibge": code,
        "municipio": {"nome": muni.nome, "uf": muni.uf},
        "bairros_count": bairros,
        "malha_fonte": seed.malha_fonte if seed else None,
        "publicacao_ativa": _publication_dict(pub),
        "ctm_registry": {
            "disponivel": ctm_registry is not None,
            "nome": ctm_registry.nome if ctm_registry else None,
            "tipo": ctm_registry.kind if ctm_registry else None,
            "url": ctm_registry.url if ctm_registry else None,
            "nota": ctm_registry.nota if ctm_registry else catalog_row.get("nota") if catalog_row else None,
        }
        if ctm_registry or catalog_row
        else {"disponivel": False},
        "catalog_status": catalog_row.get("status") if catalog_row else "sem_ctm_cadastrada",
        "acoes_sugeridas": acoes,
        "formatos_aceitos": [".geojson", ".json", ".zip (shapefile)"],
        "tipos_api": ["arcgis_rest", "geojson_url"],
    }


def probe_geoportal_url(tipo: str, url: str, *, arcgis_where: str = "1=1") -> dict[str, Any]:
    """Valida URL municipal sem importar."""
    try:
        if tipo == "geojson_url":
            fc = fetch_geojson_url(url)
        elif tipo == "arcgis_rest":
            source = CtmSource(
                codigo_ibge="0000000",
                nome="probe",
                uf="",
                kind="arcgis",
                url=url,
                name_fields=("nome",),
                where=arcgis_where,
            )
            fc = fetch_arcgis_geojson(source)
        else:
            return {"ok": False, "error": "tipo inválido para probe"}
        count = len(fc.get("features") or [])
        return {"ok": True, "feature_count": count, "tipo": tipo}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:300]}
