"""Mapa de risco consolidado (17h.1c) — síntese espacial IVC + IRI + alerta vivo."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Bairro, Municipio
from app.services.live_alert_level import live_alert_snapshot, max_alert_level, normalize_nivel
from app.services.report_generator import build_bairro_ranking
from app.services.risk_traffic_light_service import NIVEL_LABEL, _nivel_from_score


def build_risco_consolidado_geojson(db: Session, codigo_ibge: str) -> dict[str, Any]:
    """GeoJSON por bairro: score Sinidu × alerta vivo → nível semáforo."""
    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        raise ValueError(f"Município {code} não encontrado")

    ranking, _snapshot = build_bairro_ranking(db, muni)
    alerta = live_alert_snapshot(db, code)
    nivel_alerta = normalize_nivel(alerta.get("nivel_alerta"))

    geom_rows = (
        db.query(Bairro.id, func.ST_AsGeoJSON(Bairro.geom).label("geojson"))
        .filter(Bairro.municipio_id == muni.id, Bairro.geom.isnot(None))
        .all()
    )
    geom_by_id = {row.id: row.geojson for row in geom_rows}

    features: list[dict[str, Any]] = []
    for row in ranking:
        bid = row.get("bairro_id")
        raw_geom = geom_by_id.get(bid) if bid is not None else None
        if not raw_geom:
            continue
        try:
            geometry = json.loads(raw_geom) if isinstance(raw_geom, str) else raw_geom
        except (TypeError, json.JSONDecodeError):
            continue

        score = int(row.get("score_sinidu") or 0)
        nivel_score = _nivel_from_score(score)
        # Alerta vivo eleva o piso municipal — “risco agora”
        nivel = max_alert_level([nivel_score, nivel_alerta])

        features.append(
            {
                "type": "Feature",
                "geometry": geometry,
                "properties": {
                    "layer": "risco_consolidado",
                    "nome": row.get("bairro"),
                    "bairro_id": bid,
                    "codigo_bairro": None,
                    "score_sinidu": score,
                    "indice_vulnerabilidade": row.get("ivc"),
                    "indice_risco_inundacao": row.get("iri"),
                    "deficit_adaptacao": row.get("deficit_adaptacao"),
                    "nivel": nivel,
                    "nivel_score": nivel_score,
                    "alerta_vivo": nivel_alerta,
                    "label": NIVEL_LABEL.get(nivel, nivel),
                    "score_componentes": row.get("componentes") or {},
                    "fatores_principais": row.get("fatores_principais") or [],
                    "populacao": row.get("populacao"),
                    "explicacao": (
                        "Síntese = max(nível do Score Sinidu 45% IVC + 35% IRI + 20% déficit "
                        f"adaptação, alerta vivo {nivel_alerta})."
                    ),
                    "fonte_referencia": "Score Sinidu+Clima + CEMADEN/alertas vivos",
                    "qualidade_dado": "Derivado Sinidu+Clima",
                },
            }
        )

    return {
        "type": "FeatureCollection",
        "features": features,
        "meta": {
            "codigo_ibge": code,
            "alerta_vivo": nivel_alerta,
            "n_bairros": len(features),
            "formula": "max(nivel(score_sinidu), nivel_alerta_vivo)",
        },
    }
