from __future__ import annotations

import json
import logging
import pickle
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.services.analytical_engine import AnalyticalEngine
from ml.constants import FEATURE_COLUMNS, MODEL_VERSION, MUNICIPALITY_SLUGS, SLUG_BY_IBGE
from ml.paths import model_meta_path, model_path, terrain_parquet

logger = logging.getLogger(__name__)


def resolve_codigo_ibge(municipio_id: str) -> str:
    key = municipio_id.strip().lower().replace("-", "_").replace(" ", "_")
    if key in MUNICIPALITY_SLUGS:
        return MUNICIPALITY_SLUGS[key]
    digits = "".join(ch for ch in key if ch.isdigit())
    if len(digits) == 7:
        return digits
    raise ValueError(f"Município '{municipio_id}' inválido — informe código IBGE de 7 dígitos.")


def _risk_level(probability: float) -> str:
    if probability >= 0.75:
        return "MUITO_ALTO"
    if probability >= 0.55:
        return "ALTO"
    if probability >= 0.35:
        return "MEDIO"
    return "BAIXO"


def _confidence(meta: dict[str, Any]) -> str:
    auc = meta.get("auc_roc_cv")
    n_pos = meta.get("n_positive", 0)
    if auc is None or (isinstance(auc, float) and np.isnan(auc)):
        return "baixa"
    if auc >= 0.75 and n_pos >= 3:
        return "alta"
    if auc >= 0.65 or n_pos >= 1:
        return "média"
    return "baixa"


class FloodRiskPredictor:
    def __init__(self):
        self._cache: dict[str, dict[str, Any]] = {}

    def _load(self, codigo_ibge: str) -> dict[str, Any]:
        if codigo_ibge in self._cache:
            return self._cache[codigo_ibge]
        path = model_path(codigo_ibge)
        if not path.exists():
            from ml.bootstrap import ensure_model_for
            if not ensure_model_for(codigo_ibge):
                raise FileNotFoundError(
                    f"Modelo não treinado para IBGE {codigo_ibge}. Execute etl/etl_flood_ml.py."
                )
        with path.open("rb") as fh:
            payload = pickle.load(fh)
        self._cache[codigo_ibge] = payload
        return payload

    def predict(
        self,
        db: Session,
        municipio_slug: str,
        precip_24h: float,
        precip_48h: float,
        precip_72h: float,
        mes_do_ano: int | None = None,
    ) -> dict[str, Any]:
        from datetime import datetime

        codigo_ibge = resolve_codigo_ibge(municipio_slug)
        payload = self._load(codigo_ibge)
        model = payload["model"]
        meta = payload["meta"]
        terrain = meta.get("terrain", {})

        month = mes_do_ano or datetime.now().month
        precip_7d = precip_72h * 1.15

        row = {
            "precip_24h": precip_24h,
            "precip_48h": precip_48h,
            "precip_72h": precip_72h,
            "precip_7d": precip_7d,
            "mes_do_ano": float(month),
            **terrain,
        }
        vec = np.array([[row[c] for c in FEATURE_COLUMNS]])
        probability = float(model.predict_proba(vec)[0][1])

        bairros = self._critical_neighborhoods(db, codigo_ibge, probability, row)
        geojson = self._flood_patch_geojson(db, codigo_ibge, bairros, probability)

        threshold = float(meta.get("threshold_mm_24h", 65.0))
        mm_acima = round(float(precip_24h) - threshold, 1)
        top_features: list[dict[str, Any]] = []
        importances = getattr(model, "feature_importances_", None)
        if importances is not None and len(importances) == len(FEATURE_COLUMNS):
            ranked = sorted(
                zip(FEATURE_COLUMNS, importances),
                key=lambda item: float(item[1]),
                reverse=True,
            )[:3]
            top_features = [
                {"feature": name, "importance": round(float(score), 3)}
                for name, score in ranked
            ]

        return {
            "codigo_ibge": codigo_ibge,
            "municipio_slug": SLUG_BY_IBGE.get(codigo_ibge, municipio_slug),
            "risk_probability": round(probability, 3),
            "risk_level": _risk_level(probability),
            "confidence": _confidence(meta),
            "threshold_mm_24h": threshold,
            "mm_acima_limiar": mm_acima,
            "top_features": top_features,
            "critical_neighborhoods": bairros,
            "flood_geojson": geojson,
            "model_version": meta.get("model_version", MODEL_VERSION),
            "model_kind": meta.get("model_kind", "full"),
            "data_quality": "estimado" if meta.get("model_kind") == "baseline_synthetic" else "derivado",
            "model_auc_roc": meta.get("auc_roc_cv"),
            "disclaimer": (
                "Modelo estatístico para apoio à decisão. Não substitui modelagem hidrodinâmica "
                "ou alerta oficial CEMADEN."
                + (
                    " Baseline sintético calibrado por terreno municipal — retreine com OpenMeteo+S2ID para produção."
                    if meta.get("model_kind") == "baseline_synthetic"
                    else ""
                )
            ),
        }

    def _critical_neighborhoods(
        self,
        db: Session,
        codigo_ibge: str,
        municipal_prob: float,
        feature_row: dict[str, float],
    ) -> list[dict[str, Any]]:
        from app.models import Bairro, Municipio
        from ml.baseline import TERRAIN_PRESETS

        muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
        if not muni:
            return []

        terrain_path = terrain_parquet(codigo_ibge)
        if terrain_path.exists():
            terrain_df = pd.read_parquet(terrain_path)
        else:
            # Evita OpenTopography na inferência — usa IRI + preset municipal
            floods = AnalyticalEngine.calculate_flood_risk(db, muni.id)
            preset = TERRAIN_PRESETS.get(codigo_ibge, TERRAIN_PRESETS["2611606"])
            rows = []
            flood_by_id = {item["id"]: item for item in floods}
            for b in db.query(Bairro).filter(Bairro.municipio_id == muni.id).all():
                flood = flood_by_id.get(b.id, {})
                iri = float(flood.get("indice_risco_inundacao", 0.5))
                bairro_prob = min(0.99, municipal_prob * 0.55 + iri * 0.45)
                rows.append({
                    "bairro_id": b.id,
                    "bairro_nome": b.nome,
                    "risk_probability": round(bairro_prob, 3),
                    "iri": round(iri, 3),
                    "impermeabilizacao_pct": preset["impermeabilizacao_pct"],
                })
            rows.sort(key=lambda item: item["risk_probability"], reverse=True)
            return rows[:8]

        floods = {item["id"]: item for item in AnalyticalEngine.calculate_flood_risk(db, muni.id)}
        rows = []
        for _, b in terrain_df.iterrows():
            flood = floods.get(int(b["bairro_id"]), {})
            iri = float(flood.get("indice_risco_inundacao", 0.5))
            bairro_prob = min(0.99, municipal_prob * 0.55 + iri * 0.45)
            rows.append({
                "bairro_id": int(b["bairro_id"]),
                "bairro_nome": b["bairro_nome"],
                "risk_probability": round(bairro_prob, 3),
                "iri": round(iri, 3),
                "impermeabilizacao_pct": float(b["impermeabilizacao_pct"]),
            })

        rows.sort(key=lambda item: item["risk_probability"], reverse=True)
        return rows[:8]

    def _flood_patch_geojson(
        self,
        db: Session,
        codigo_ibge: str,
        bairros: list[dict[str, Any]],
        probability: float,
    ) -> dict[str, Any]:
        import json
        from sqlalchemy import func

        from app.models import Bairro, Municipio

        if not bairros:
            return {"type": "FeatureCollection", "features": []}

        muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
        if not muni:
            return {"type": "FeatureCollection", "features": []}

        top_ids = {b["bairro_id"] for b in bairros[:5]}
        features = []
        for b_id in top_ids:
            row = db.query(Bairro).filter(Bairro.id == b_id, Bairro.municipio_id == muni.id).first()
            if not row:
                continue
            geom = json.loads(db.scalar(func.ST_AsGeoJSON(row.geom)))
            binfo = next((b for b in bairros if b["bairro_id"] == b_id), {})
            features.append({
                "type": "Feature",
                "geometry": geom,
                "properties": {
                    "name": row.nome,
                    "risk_probability": binfo.get("risk_probability", probability),
                    "precipitation_mm": None,
                    "description": "Mancha preditiva ML — risco estatístico de alagamento",
                },
            })

        return {"type": "FeatureCollection", "features": features}


predictor = FloodRiskPredictor()
