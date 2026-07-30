"""Equipamentos urbanos Recife — escolas, creches, faculdades, hospitais, UPAs.

Fonte primária: inventário offline (OSM cache classificado + seed + INEP).
Fallback: Overpass ao vivo. Seed curado completa lacunas e corrige dependência.
Classifica dependência: federal | estadual | municipal | privada.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import requests
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy.orm import Session

from app.models import EscolaInep, EstabelecimentoSaude, InfraestruturaUrbana, Municipio

logger = logging.getLogger(__name__)

RECIFE_IBGE = "2611606"
# bbox um pouco ampliada (norte Olinda/Jaboatão borda)
RECIFE_BBOX = "-8.20,-35.02,-7.90,-34.82"
OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
)
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
SEED_PATH = DATA_DIR / "equipamentos_recife_seed.json"
INVENTARIO_PATH = DATA_DIR / "equipamentos_recife_inventario.json"
# Inventário completo (~900+ pontos); abaixo disso força re-sync
MIN_EQUIPAMENTOS = 400

DEPENDENCIAS = frozenset({"federal", "estadual", "municipal", "privada"})

TIPOS_EDUCACAO = frozenset({"escola", "creche", "faculdade"})
TIPOS_SAUDE = frozenset({"hospital", "upa", "ubs", "caps", "samu"})
TIPOS_KEEP = TIPOS_EDUCACAO | TIPOS_SAUDE


def _norm_name(nome: str) -> str:
    n = (nome or "").upper()
    n = re.sub(r"[^A-Z0-9À-Ü\s]", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def classify_dependencia(nome: str, tags: dict[str, Any] | None = None) -> str:
    """Infere esfera administrativa a partir de tags OSM e do nome."""
    tags = tags or {}
    op_type = str(tags.get("operator:type") or tags.get("ownership") or "").lower()
    gov = str(tags.get("government") or "").lower()
    operator = str(tags.get("operator") or "").lower()
    name_u = _norm_name(nome)

    if gov in {"federal"} or "federal" in op_type or any(
        k in name_u for k in ("UFPE", "UFRPE", "IFPE", "HOSPITAL DAS CLINICAS", "HC UFPE", "MEC ")
    ):
        return "federal"
    if gov in {"state"} or "state" in op_type or any(
        k in name_u
        for k in (
            "ESTADUAL",
            " EE ",
            "E.E.",
            "SECRETARIA DE EDUCACAO DE PERNAMBUCO",
            "SES PE",
            "HOSPITAL AGAMENON",
            "HOSPITAL DA RESTAURACAO",
            "HOSPITAL GETULIO VARGAS",
            "BARAO DE LUCENA",
        )
    ):
        return "estadual"
    if gov in {"municipal"} or "municipal" in op_type or any(
        k in name_u
        for k in (
            "MUNICIPAL",
            "EMEF",
            "EMEI",
            "CMEI",
            "CRECHE MUNICIPAL",
            "UBS ",
            "UPA ",
            "PREF ",
            "PREFEITURA",
            "SMS RECIFE",
        )
    ):
        return "municipal"
    if (
        "private" in op_type
        or "private" in str(tags.get("fee") or "").lower()
        or any(
            k in name_u
            for k in (
                "PARTICULAR",
                "PRIVAD",
                "COLEGIO",
                "COLÉGIO",
                "REAL HOSPITAL PORTUGUES",
                "ESPERANCA",
                "JAYME DA FONTE",
                "UNICAP",
                "FACULDADE SENAC",
                "UNINASSAU",
                "UNIFBV",
                "MAURICIO DE NASSAU",
            )
        )
    ):
        return "privada"
    if "public" in op_type or operator.startswith("prefeitura"):
        return "municipal"
    # default: escolas sem marcador costumam ser privadas no OSM BR; UPA/UBS municipais
    if "UPA" in name_u or "UBS" in name_u or "USF" in name_u:
        return "municipal"
    if "HOSPITAL" in name_u and any(k in name_u for k in ("IMIP", "FILANTROP")):
        return "privada"  # filantrópico tratado como privado na classificação pedida
    return "privada"


def classify_tipo(amenity: str, nome: str, tags: dict[str, Any] | None = None) -> str:
    tags = tags or {}
    name_u = _norm_name(nome)
    healthcare = str(tags.get("healthcare") or "").lower()
    amenity = (amenity or tags.get("amenity") or "").lower()

    if "UPA" in name_u or "PRONTO ATENDIMENTO" in name_u or "PRONTO-ATENDIMENTO" in name_u:
        return "upa"
    if "UBS" in name_u or "USF" in name_u or "UNIDADE BASICA" in name_u:
        return "ubs"
    if "CAPS" in name_u:
        return "caps"
    if "SAMU" in name_u:
        return "samu"
    if amenity in {"hospital"} or healthcare == "hospital" or "HOSPITAL" in name_u:
        return "hospital"
    if amenity in {"clinic"} or healthcare in {"clinic", "centre", "center"}:
        if "UPA" in name_u:
            return "upa"
        return "ubs"
    if amenity in {"university", "college"} or any(
        k in name_u for k in ("UNIVERSIDADE", "FACULDADE", "CENTRO UNIVERSITARIO", "IFPE", "UFPE", "UFRPE")
    ):
        return "faculdade"
    if amenity == "kindergarten" or any(
        k in name_u for k in ("CRECHE", "EMEI", "CMEI", "BERCARIO", "EDUCACAO INFANTIL")
    ):
        return "creche"
    if amenity == "school" or "ESCOLA" in name_u or "COLEGIO" in name_u or "COLÉGIO" in name_u:
        return "escola"
    return "escola"


def _element_point(el: dict[str, Any]) -> tuple[float, float] | None:
    if "lat" in el and "lon" in el:
        return float(el["lat"]), float(el["lon"])
    center = el.get("center") or {}
    if "lat" in center and "lon" in center:
        return float(center["lat"]), float(center["lon"])
    geom = el.get("geometry") or []
    if geom:
        lat = sum(float(g["lat"]) for g in geom) / len(geom)
        lon = sum(float(g["lon"]) for g in geom) / len(geom)
        return lat, lon
    return None


def _parse_equipamento_row(row: dict[str, Any], *, fonte_default: str) -> dict[str, Any] | None:
    nome = str(row.get("nome") or "").strip()
    if not nome:
        return None
    tipo = str(row.get("tipo") or classify_tipo("", nome)).lower()
    if tipo not in TIPOS_KEEP:
        return None
    dep = str(row.get("dependencia") or classify_dependencia(nome)).lower()
    if dep not in DEPENDENCIAS:
        dep = classify_dependencia(nome)
    try:
        lat = float(row["lat"])
        lng = float(row["lng"])
    except (KeyError, TypeError, ValueError):
        return None
    return {
        "nome": nome[:148],
        "tipo": tipo,
        "dependencia": dep,
        "lat": lat,
        "lng": lng,
        "fonte": str(row.get("fonte") or fonte_default),
        "osm_id": row.get("osm_id") or row.get("id") or f"EQ:{_norm_name(nome)[:40]}",
        "data_quality": str(row.get("data_quality") or ("oficial_curado" if fonte_default == "seed_curado" else "derivado")),
    }


def load_inventario_equipamentos() -> list[dict[str, Any]]:
    """Inventário offline completo (preferencial — não depende do Overpass)."""
    if not INVENTARIO_PATH.exists():
        return []
    try:
        raw = json.loads(INVENTARIO_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Inventário equipamentos inválido: %s", exc)
        return []
    rows = raw if isinstance(raw, list) else raw.get("equipamentos") or []
    out: list[dict[str, Any]] = []
    for row in rows:
        parsed = _parse_equipamento_row(row, fonte_default="inventario")
        if parsed:
            out.append(parsed)
    logger.info("Inventário equipamentos Recife: %d pontos", len(out))
    return out


def fetch_osm_equipamentos(*, timeout: float = 90.0) -> list[dict[str, Any]]:
    query = f"""
    [out:json][timeout:{int(timeout)}];
    (
      node["amenity"="school"]({RECIFE_BBOX});
      way["amenity"="school"]({RECIFE_BBOX});
      node["amenity"="kindergarten"]({RECIFE_BBOX});
      way["amenity"="kindergarten"]({RECIFE_BBOX});
      node["amenity"="university"]({RECIFE_BBOX});
      way["amenity"="university"]({RECIFE_BBOX});
      node["amenity"="college"]({RECIFE_BBOX});
      way["amenity"="college"]({RECIFE_BBOX});
      node["amenity"="hospital"]({RECIFE_BBOX});
      way["amenity"="hospital"]({RECIFE_BBOX});
      node["amenity"="clinic"]({RECIFE_BBOX});
      way["amenity"="clinic"]({RECIFE_BBOX});
      node["healthcare"="hospital"]({RECIFE_BBOX});
      way["healthcare"="hospital"]({RECIFE_BBOX});
      node["healthcare"="clinic"]({RECIFE_BBOX});
      way["healthcare"="clinic"]({RECIFE_BBOX});
    );
    out center tags;
    """
    elements: list[dict[str, Any]] = []
    for url in OVERPASS_URLS:
        try:
            resp = requests.post(url, data={"data": query}, timeout=timeout)
            if resp.status_code != 200:
                logger.warning("Overpass %s HTTP %s", url, resp.status_code)
                continue
            elements = resp.json().get("elements") or []
            if elements:
                break
        except Exception as exc:
            logger.warning("Overpass %s falhou: %s", url, exc)

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for el in elements:
        tags = el.get("tags") or {}
        nome = (tags.get("name") or tags.get("official_name") or "").strip()
        if not nome:
            continue
        pt = _element_point(el)
        if not pt:
            continue
        lat, lon = pt
        tipo = classify_tipo(str(tags.get("amenity") or ""), nome, tags)
        if tipo not in TIPOS_KEEP:
            continue
        name_u = _norm_name(nome)
        if tipo == "ubs" and not any(
            k in name_u for k in ("UBS", "USF", "UNIDADE BASICA", "POSTO DE SAUDE", "PSF ", "ESF ")
        ):
            continue
        dep = classify_dependencia(nome, tags)
        key = f"{tipo}|{_norm_name(nome)}"
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "nome": nome[:148],
            "tipo": tipo,
            "dependencia": dep,
            "lat": lat,
            "lng": lon,
            "fonte": "osm",
            "osm_id": f"{el.get('type')}/{el.get('id')}",
            "data_quality": "derivado",
        })
    logger.info("OSM equipamentos Recife: %d pontos", len(out))
    return out


def load_seed_equipamentos() -> list[dict[str, Any]]:
    if not SEED_PATH.exists():
        return []
    try:
        raw = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Seed equipamentos inválido: %s", exc)
        return []
    rows = raw if isinstance(raw, list) else raw.get("equipamentos") or []
    out: list[dict[str, Any]] = []
    for row in rows:
        parsed = _parse_equipamento_row(
            {**row, "osm_id": row.get("id") or f"SEED:{_norm_name(str(row.get('nome') or ''))[:40]}"},
            fonte_default="seed_curado",
        )
        if parsed:
            parsed["data_quality"] = "oficial_curado"
            out.append(parsed)
    return out


def merge_equipamentos(*sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Une fontes; seed/INEP curados sobrescrevem dependência genérica do OSM."""
    by_key: dict[str, dict[str, Any]] = {}
    for source in sources:
        for row in source:
            key = f"{row['tipo']}|{_norm_name(row['nome'])}"
            if key not in by_key:
                by_key[key] = row
                continue
            cur = by_key[key]
            # dependência curada prevalece sobre default privada do OSM
            if (
                row.get("dependencia") in DEPENDENCIAS
                and row["dependencia"] != "privada"
                and cur.get("dependencia") == "privada"
            ):
                cur["dependencia"] = row["dependencia"]
                cur["data_quality"] = row.get("data_quality") or "oficial_curado"
            elif row.get("fonte") in {"seed_curado", "inep_seed"} and row.get("dependencia") in DEPENDENCIAS:
                cur["dependencia"] = row["dependencia"]
                cur["data_quality"] = "oficial_curado"
    return list(by_key.values())


def _clear_equipamento_points(db: Session, municipio_id: int) -> None:
    """Remove pontos de equipamentos (mantém vias)."""
    db.query(InfraestruturaUrbana).filter(
        InfraestruturaUrbana.municipio_id == municipio_id,
        InfraestruturaUrbana.tipo != "via",
    ).delete(synchronize_session=False)


def sync_equipamentos_recife(db: Session, *, force: bool = False, commit: bool = True) -> dict[str, Any]:
    """Ingere equipamentos Recife → infraestrutura + escolas + saúde."""
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == RECIFE_IBGE).first()
    if not muni:
        return {"codigo_ibge": RECIFE_IBGE, "error": "municipio_nao_encontrado"}

    existing = (
        db.query(InfraestruturaUrbana)
        .filter(
            InfraestruturaUrbana.municipio_id == muni.id,
            InfraestruturaUrbana.tipo != "via",
        )
        .count()
    )
    if existing >= MIN_EQUIPAMENTOS and not force:
        return {"codigo_ibge": RECIFE_IBGE, "skipped": True, "records": existing}

    inventario = load_inventario_equipamentos()
    seed = load_seed_equipamentos()
    # Inventário offline é suficiente; Overpass só se inventário estiver vazio/incompleto
    osm: list[dict[str, Any]] = []
    if len(inventario) < MIN_EQUIPAMENTOS:
        osm = fetch_osm_equipamentos()
    rows = merge_equipamentos(inventario, osm, seed)
    if not rows:
        return {
            "codigo_ibge": RECIFE_IBGE,
            "error": "sem_dados",
            "inventario": len(inventario),
            "osm": len(osm),
            "seed": len(seed),
        }

    _clear_equipamento_points(db, muni.id)

    # limpa tabelas oficiais para reescrever com classificação
    db.query(EscolaInep).filter(EscolaInep.municipio_id == muni.id).delete(synchronize_session=False)
    db.query(EstabelecimentoSaude).filter(EstabelecimentoSaude.municipio_id == muni.id).delete(
        synchronize_session=False
    )

    counts: dict[str, int] = {}
    dep_counts: dict[str, int] = {}

    for idx, row in enumerate(rows):
        tipo = row["tipo"]
        dep = row["dependencia"] if row["dependencia"] in DEPENDENCIAS else "privada"
        counts[tipo] = counts.get(tipo, 0) + 1
        dep_counts[dep] = dep_counts.get(dep, 0) + 1
        geom = from_shape(Point(row["lng"], row["lat"]), srid=4326)

        db.add(
            InfraestruturaUrbana(
                municipio_id=muni.id,
                tipo=tipo,
                nome=row["nome"],
                subgrupo=dep,  # dependência administrativa
                geom=geom,
            )
        )

        if tipo in TIPOS_EDUCACAO:
            mats = {
                "creche": {"matriculas_infantil": 80, "matriculas_fundamental": 0, "matriculas_medio": 0},
                "escola": {"matriculas_infantil": 40, "matriculas_fundamental": 200, "matriculas_medio": 80},
                "faculdade": {"matriculas_infantil": 0, "matriculas_fundamental": 0, "matriculas_medio": 0},
            }[tipo]
            total = sum(mats.values()) or (500 if tipo == "faculdade" else 100)
            db.add(
                EscolaInep(
                    municipio_id=muni.id,
                    codigo_inep=str(row.get("osm_id") or f"EQ{idx}")[:20],
                    nome=row["nome"][:250],
                    dependencia=dep,
                    localizacao=f"urbana|{tipo}",
                    ano=2024,
                    matriculas_total=total,
                    matriculas_infantil=mats["matriculas_infantil"],
                    matriculas_fundamental=mats["matriculas_fundamental"],
                    matriculas_medio=mats["matriculas_medio"],
                    geom=geom,
                    fonte=f"equipamentos_{row.get('fonte', 'osm')}",
                    data_quality=row.get("data_quality") or "derivado",
                )
            )

        if tipo in TIPOS_SAUDE:
            tipo_saude = {
                "hospital": "HOSPITAL",
                "upa": "UPA",
                "ubs": "UBS",
                "caps": "CAPS",
                "samu": "SAMU",
            }[tipo]
            db.add(
                EstabelecimentoSaude(
                    municipio_id=muni.id,
                    codigo_ibge=RECIFE_IBGE,
                    cnes_codigo=str(row.get("osm_id") or f"EQ{idx}")[:20],
                    nome=row["nome"][:250],
                    tipo=tipo_saude,
                    leitos_sus=40 if tipo == "hospital" else 0,
                    esf=tipo == "ubs",
                    dependencia=dep,
                    geom=geom,
                    fonte=f"equipamentos_{row.get('fonte', 'osm')}",
                )
            )

    if commit:
        db.commit()
    else:
        db.flush()
    total = sum(counts.values())
    logger.info("Equipamentos Recife sync: %d (%s)", total, counts)
    return {
        "codigo_ibge": RECIFE_IBGE,
        "skipped": False,
        "records": total,
        "por_tipo": counts,
        "por_dependencia": dep_counts,
        "fonte_inventario": len(inventario),
        "fonte_osm": len(osm),
        "fonte_seed": len(seed),
        "data_quality": "derivado" if (inventario or osm) else "oficial_curado",
    }
