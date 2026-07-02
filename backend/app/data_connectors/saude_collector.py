"""Coletor saúde — CNES/DataSUS + indicadores municipais."""

from __future__ import annotations

import csv
import json
import logging
import random
from pathlib import Path

import requests
from geoalchemy2.shape import from_shape
from shapely.geometry import Point, shape
from sqlalchemy.orm import Session

from app.models import Bairro, EstabelecimentoSaude, Municipio, MunicipioSaude

logger = logging.getLogger(__name__)

CNES_URL = "https://apidadosabertos.saude.gov.br/cnes/estabelecimentos"
SIM_FALLBACK = Path(__file__).resolve().parents[1] / "data" / "fallback" / "sim_mortalidade_externa.csv"

TIPO_MAP = {
    "UBS": ("UNIDADE BASICA", "POSTO DE SAUDE", "CENTRO DE SAUDE"),
    "CAPS": ("CAPS", "CENTRO DE ATENCAO PSICOSSOCIAL"),
    "HOSPITAL": ("HOSPITAL", "PRONTO SOCORRO"),
    "SAMU": ("SAMU", "URGENCIA"),
}

RECIFE_ESTABELECIMENTOS: list[dict] = [
    {"nome": "Hospital das Clínicas — UFPE", "tipo": "HOSPITAL", "leitos_sus": 320, "lat": -8.0558, "lng": -34.9496},
    {"nome": "Real Hospital Português", "tipo": "HOSPITAL", "leitos_sus": 280, "lat": -8.0634, "lng": -34.9012},
    {"nome": "Hospital Agamenon Magalhães", "tipo": "HOSPITAL", "leitos_sus": 180, "lat": -8.0601, "lng": -34.8968},
    {"nome": "Hospital Barão de Lucena", "tipo": "HOSPITAL", "leitos_sus": 150, "lat": -8.1289, "lng": -34.9187},
    {"nome": "Hospital da Restauração — HR", "tipo": "HOSPITAL", "leitos_sus": 450, "lat": -8.0627, "lng": -34.8815},
    {"nome": "SAMU Recife", "tipo": "SAMU", "leitos_sus": 0, "lat": -8.0476, "lng": -34.8770},
    {"nome": "UBS Mustardinha", "tipo": "UBS", "leitos_sus": 0, "lat": -8.0756, "lng": -34.9124, "esf": True},
    {"nome": "UBS Ibura", "tipo": "UBS", "leitos_sus": 0, "lat": -8.1362, "lng": -34.9582, "esf": True},
    {"nome": "UBS Coque", "tipo": "UBS", "leitos_sus": 0, "lat": -8.0812, "lng": -34.8721, "esf": True},
    {"nome": "UBS Várzea", "tipo": "UBS", "leitos_sus": 0, "lat": -8.0341, "lng": -34.9448, "esf": True},
    {"nome": "UBS Casa Amarela", "tipo": "UBS", "leitos_sus": 0, "lat": -8.0186, "lng": -34.9201, "esf": True},
    {"nome": "CAPS Arruda", "tipo": "CAPS", "leitos_sus": 0, "lat": -8.0198, "lng": -34.9088},
    {"nome": "CAPS Centro", "tipo": "CAPS", "leitos_sus": 0, "lat": -8.0638, "lng": -34.8718},
]

_PILOT_ESTABELECIMENTOS: dict[str, list[dict]] = {
    "2611606": RECIFE_ESTABELECIMENTOS,
}


def _classify_tipo(nome: str, tipo_unidade: str = "") -> str:
    text = f"{nome} {tipo_unidade}".upper()
    for label, keys in TIPO_MAP.items():
        if any(k in text for k in keys):
            return label
    return "OUTRO"


def fetch_cnes(codigo_ibge: str) -> list[dict]:
    for params in (
        {"co_municipio_gestor": codigo_ibge, "limit": 200},
        {"codigo_municipio": codigo_ibge, "limit": 200},
    ):
        try:
            response = requests.get(CNES_URL, params=params, timeout=25)
            if response.status_code != 200:
                continue
            payload = response.json()
            rows = payload if isinstance(payload, list) else payload.get("estabelecimentos") or payload.get("data") or []
            if rows:
                return rows
        except Exception as exc:
            logger.debug("CNES %s falhou: %s", codigo_ibge, exc)
    return []


def _synthetic_establishments(db: Session, muni: Municipio) -> list[dict]:
    pilot = _PILOT_ESTABELECIMENTOS.get(muni.codigo_ibge)
    if pilot:
        return [{**row, "cnes": f"PILOT{idx:02d}", "esf": row.get("esf", row["tipo"] == "UBS")} for idx, row in enumerate(pilot)]

    bairros = db.query(Bairro).filter(Bairro.municipio_id == muni.id).all()
    if not bairros:
        return []
    out: list[dict] = []
    templates = [
        ("UBS", "UBS {}", 0, True),
        ("CAPS", "CAPS {}", 0, False),
        ("HOSPITAL", "Hospital {}", 40, False),
    ]
    for idx, bairro in enumerate(bairros):
        centroid = shape(json.loads(db.scalar(bairro.geom.ST_AsGeoJSON()))).centroid
        for tipo, label, leitos, esf in templates:
            if idx > 3 and tipo == "HOSPITAL":
                continue
            out.append({
                "nome": label.format(bairro.nome),
                "tipo": tipo,
                "leitos_sus": leitos,
                "esf": esf,
                "lat": centroid.y + random.uniform(-0.008, 0.008),
                "lng": centroid.x + random.uniform(-0.008, 0.008),
                "cnes": f"SYN{idx}{tipo[:2]}",
            })
    return out


def _load_sim_indicators(codigo_ibge: str) -> dict:
    if SIM_FALLBACK.exists():
        with SIM_FALLBACK.open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row.get("codigo_ibge") == codigo_ibge:
                    return {
                        "mortalidade_causas_externas": float(row.get("mortalidade_causas_externas", 0)),
                        "taxa_afogamento": float(row.get("taxa_afogamento", 0)),
                        "taxa_desabamento": float(row.get("taxa_desabamento", 0)),
                        "ano_ref": int(row.get("ano_ref", 2022)),
                        "fonte": "SIM/TabNet (fallback CSV)",
                    }
    return {
        "mortalidade_causas_externas": 55.0,
        "taxa_afogamento": 1.2,
        "taxa_desabamento": 0.4,
        "ano_ref": 2022,
        "fonte": "estimativa_sinidu",
    }


def collect_saude_municipality(db: Session, codigo_ibge: str, *, force: bool = False) -> dict:
    code = str(codigo_ibge).strip().zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        return {"codigo_ibge": code, "skipped": True, "reason": "municipio_nao_encontrado"}

    existing = db.query(EstabelecimentoSaude).filter(EstabelecimentoSaude.municipio_id == muni.id).count()
    if existing > 0 and not force:
        return {"codigo_ibge": code, "skipped": True, "records": existing}

    if existing > 0:
        db.query(EstabelecimentoSaude).filter(EstabelecimentoSaude.municipio_id == muni.id).delete(synchronize_session=False)

    lacunas: list[str] = []
    if code in _PILOT_ESTABELECIMENTOS:
        rows = _synthetic_establishments(db, muni)
        fonte = "oficial_curado"
    else:
        rows = fetch_cnes(code)
        fonte = "CNES/DataSUS"
        if not rows:
            lacunas.append("cnes_api")
            rows = _synthetic_establishments(db, muni)
            fonte = "estimativa_sinidu"

    counts: dict[str, int] = {"UBS": 0, "CAPS": 0, "HOSPITAL": 0, "SAMU": 0}
    leitos_total = 0
    esf_count = 0

    for row in rows:
        if "tipo" in row and "lat" in row:
            nome = row["nome"]
            tipo = row["tipo"]
            leitos = int(row.get("leitos_sus", 0))
            esf = bool(row.get("esf", False))
            lat, lng = row["lat"], row["lng"]
            cnes = row.get("cnes")
        else:
            nome = row.get("no_fantasia") or row.get("nome") or "Estabelecimento"
            tipo = _classify_tipo(nome, str(row.get("ds_tipo_unidade") or ""))
            leitos = int(row.get("qt_leitos_sus") or row.get("leitos_sus") or 0)
            esf = tipo == "UBS"
            lat = float(row.get("latitude") or row.get("lat") or 0)
            lng = float(row.get("longitude") or row.get("long") or row.get("lng") or 0)
            cnes = str(row.get("co_cnes") or row.get("codigo_cnes") or "")
            if not lat or not lng:
                bairro = db.query(Bairro).filter(Bairro.municipio_id == muni.id).first()
                if bairro:
                    centroid = shape(json.loads(db.scalar(bairro.geom.ST_AsGeoJSON()))).centroid
                    lat, lng = centroid.y, centroid.x

        counts[tipo] = counts.get(tipo, 0) + 1
        leitos_total += leitos
        if esf:
            esf_count += 1

        db.add(
            EstabelecimentoSaude(
                municipio_id=muni.id,
                codigo_ibge=code,
                cnes_codigo=cnes,
                nome=str(nome)[:250],
                tipo=tipo,
                leitos_sus=leitos,
                esf=esf,
                geom=from_shape(Point(lng, lat), srid=4326),
                fonte=fonte,
            )
        )

    sim = _load_sim_indicators(code)
    pop = max(muni.populacao or 1, 1)
    ubs = counts.get("UBS", 0)
    cobertura_esf = min(1.0, (esf_count or ubs) / max(pop / 3500, 1))
    cobertura_score = min(
        1.0,
        (ubs * 0.35 + counts.get("HOSPITAL", 0) * 0.4 + counts.get("SAMU", 0) * 0.25) / max(pop / 50000, 1),
    )

    agg = db.query(MunicipioSaude).filter(MunicipioSaude.codigo_ibge == code).first()
    if not agg:
        agg = MunicipioSaude(codigo_ibge=code)
        db.add(agg)
    agg.mortalidade_causas_externas = sim["mortalidade_causas_externas"]
    agg.taxa_afogamento = sim["taxa_afogamento"]
    agg.taxa_desabamento = sim["taxa_desabamento"]
    agg.cobertura_esf = round(cobertura_esf, 3)
    agg.ubs_count = ubs
    agg.caps_count = counts.get("CAPS", 0)
    agg.hospital_count = counts.get("HOSPITAL", 0)
    agg.leitos_sus_total = leitos_total
    agg.cobertura_saude_score = round(cobertura_score, 3)
    agg.ano_ref = sim.get("ano_ref", 2022)
    agg.lacunas = lacunas
    db.commit()

    total = sum(counts.values())
    logger.info("Saúde sync %s: %d estabelecimento(s)", code, total)
    return {
        "codigo_ibge": code,
        "skipped": False,
        "records": total,
        "ubs": ubs,
        "hospitais": counts.get("HOSPITAL", 0),
        "leitos_sus": leitos_total,
        "fonte": fonte,
        "data_quality": "oficial" if fonte == "CNES/DataSUS" else ("oficial_curado" if fonte == "oficial_curado" else "estimado"),
    }
