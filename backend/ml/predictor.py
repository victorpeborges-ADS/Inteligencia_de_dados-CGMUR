from __future__ import annotations

import json
import logging
import pickle
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.services.analytical_engine import AnalyticalEngine
from ml.constants import (
    FEATURE_COLUMNS,
    FEATURE_DEFAULTS,
    MODEL_VERSION,
    MUNICIPALITY_SLUGS,
    SLUG_BY_IBGE,
)
from ml.model_policy import (
    SYNTHETIC_MODEL_KIND,
    bairro_production_model_ready,
    is_bairro_production_model,
    is_production_model,
    public_auc,
)
from ml.paths import bairro_model_path, model_path, terrain_parquet

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
    if not is_production_model(meta):
        return "nao_producao"
    auc = meta.get("auc_roc_cv")
    n_pos = meta.get("n_positive", 0)
    if auc is None or (isinstance(auc, float) and np.isnan(auc)):
        return "baixa"
    if auc >= 0.75 and n_pos >= 3:
        return "alta"
    if auc >= 0.65 or n_pos >= 1:
        return "média"
    return "baixa"


def _resolve_precip_7d(precip_72h: float, precip_7d: float | None) -> float:
    """Alinha feature precip_7d com o treino (rolling 7d). Sem proxy * 1.15."""
    if precip_7d is not None:
        return max(0.0, float(precip_7d))
    # Sem série de 7 dias: usa 72h como piso (conservador e explícito), nunca 72h*1.15.
    logger.warning("precip_7d ausente na inferência — usando precip_72h como piso (sem proxy).")
    return max(0.0, float(precip_72h))


class FloodRiskPredictor:
    def __init__(self):
        self._cache: dict[str, dict[str, Any]] = {}
        self._bairro_cache: dict[str, dict[str, Any]] = {}

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

    def _load_bairro_model(self, codigo_ibge: str) -> dict[str, Any] | None:
        """Carrega artefato grain=bairro se pronto para produção (21f.2)."""
        if codigo_ibge in self._bairro_cache:
            return self._bairro_cache[codigo_ibge]
        if not bairro_production_model_ready(codigo_ibge):
            return None
        path = bairro_model_path(codigo_ibge)
        if not path.exists():
            return None
        try:
            with path.open("rb") as fh:
                payload = pickle.load(fh)
            meta = payload.get("meta") or {}
            if not is_bairro_production_model(meta):
                return None
            self._bairro_cache[codigo_ibge] = payload
            return payload
        except Exception as exc:
            logger.info("Falha ao carregar modelo bairro %s: %s", codigo_ibge, exc)
            return None

    def clear_cache(self) -> None:
        self._cache.clear()
        self._bairro_cache.clear()

    def predict(
        self,
        db: Session,
        municipio_slug: str,
        precip_24h: float,
        precip_48h: float,
        precip_72h: float,
        mes_do_ano: int | None = None,
        precip_7d: float | None = None,
        duracao_chuva_h: float | None = None,
        precip_5d: float | None = None,
        precip_10d: float | None = None,
        precip_30d: float | None = None,
    ) -> dict[str, Any]:
        from datetime import datetime

        import numpy as np

        from ml.intensity import intensity_from_precip

        codigo_ibge = resolve_codigo_ibge(municipio_slug)
        payload = self._load(codigo_ibge)
        model = payload["model"]
        meta = payload["meta"]
        terrain = meta.get("terrain", {})
        kind = meta.get("model_kind") or "full"
        synthetic = kind == SYNTHETIC_MODEL_KIND or not is_production_model(meta)

        now = datetime.now()
        month = mes_do_ano or now.month
        precip_7d_val = _resolve_precip_7d(float(precip_72h), precip_7d)
        # Antecedente: se ausente, degrada graciosamente a partir de 7d / 72h
        p5 = float(precip_5d) if precip_5d is not None else min(precip_7d_val, float(precip_72h) * 1.6)
        p10 = float(precip_10d) if precip_10d is not None else max(precip_7d_val, p5)
        p30 = float(precip_30d) if precip_30d is not None else max(p10, precip_7d_val * 2.2)
        doy = float(now.timetuple().tm_yday)
        saz_sin = float(np.sin(2.0 * np.pi * doy / 365.25))
        saz_cos = float(np.cos(2.0 * np.pi * doy / 365.25))

        intensity = intensity_from_precip(
            float(precip_24h),
            duracao_h=duracao_chuva_h,
            codigo_ibge=codigo_ibge,
        )

        cols = list(meta.get("feature_columns") or FEATURE_COLUMNS)
        row = {
            "precip_24h": float(precip_24h),
            "precip_48h": float(precip_48h),
            "precip_72h": float(precip_72h),
            "precip_7d": precip_7d_val,
            "precip_5d": max(0.0, p5),
            "precip_10d": max(0.0, p10),
            "precip_30d": max(0.0, p30),
            "mes_do_ano": float(month),
            "sazonalidade_sin": round(saz_sin, 4),
            "sazonalidade_cos": round(saz_cos, 4),
            **FEATURE_DEFAULTS,
            **intensity,
            **terrain,
        }
        # Enriquecer terrain a partir do cache municipal se features 21d faltarem
        try:
            meta_path = terrain_parquet(codigo_ibge).with_suffix(".municipal.json")
            if meta_path.exists():
                cached = json.loads(meta_path.read_text(encoding="utf-8"))
                for k, v in cached.items():
                    if k in FEATURE_DEFAULTS or k in cols:
                        row.setdefault(k, float(v) if v is not None else FEATURE_DEFAULTS.get(k, 0.0))
        except Exception as exc:
            logger.debug("terrain municipal cache: %s", exc)

        # 21d.8 — proxies físicos SCS + rede (alinhados à simulação)
        from ml.physics_proxy import PHYSICS_PROXY_NOTE, apply_physics_proxies_to_row

        row.update(apply_physics_proxies_to_row(row))

        vec = np.array([[float(row.get(c, FEATURE_DEFAULTS.get(c, 0.0))) for c in cols]])

        from ml.horizon import build_horizon_forecasts, predict_proba_with_uncertainty

        unc = predict_proba_with_uncertainty(model, vec)
        probability = float(unc["probability"])
        horizons = build_horizon_forecasts(
            model,
            cols,
            row,
            precip_24h=float(precip_24h),
            precip_48h=float(precip_48h),
            precip_72h=float(precip_72h),
            codigo_ibge=codigo_ibge,
            duracao_chuva_h=duracao_chuva_h,
        )
        # D+1 alinha com a probabilidade principal
        if horizons:
            horizons[0]["risk_probability"] = round(probability, 3)
            horizons[0]["ci_low"] = unc["ci_low"]
            horizons[0]["ci_high"] = unc["ci_high"]
            horizons[0]["uncertainty_method"] = unc["method"]

        uncertainty = {
            "ci_low": unc["ci_low"],
            "ci_high": unc["ci_high"],
            "std": unc["std"],
            "method": unc["method"],
            "confidence_level": unc["confidence_level"],
            "nota": (
                "Intervalo ≈90% via dispersão entre árvores do RF "
                "(ou margem heurística se o modelo não expõe estimators_)."
            ),
        }

        bairros = self._critical_neighborhoods(db, codigo_ibge, probability, row)
        geojson = self._flood_patch_geojson(db, codigo_ibge, bairros, probability)
        ranking_mode = (
            "modelo_bairro"
            if bairros and all(b.get("score_source") == "modelo_bairro" for b in bairros)
            else (
                "modelo_bairro_parcial"
                if any(b.get("score_source") == "modelo_bairro" for b in bairros)
                else (bairros[0].get("score_source") if bairros else "blend_susc_iri")
            )
        )

        from app.services.flood_impact_service import build_flood_impact

        try:
            impact = build_flood_impact(
                db,
                codigo_ibge,
                municipal_prob=probability,
                critical_neighborhoods=bairros,
            )
        except Exception as exc:
            logger.info("impacto 21g.2 %s: %s", codigo_ibge, exc)
            impact = {"disponivel": False, "reason": str(exc), "protocol": "21g2_impacto"}

        threshold = float(meta.get("threshold_mm_24h", 65.0))
        mm_acima = round(float(precip_24h) - threshold, 1)

        from ml.explainability import domain_contributions

        explanation = domain_contributions(model, cols, row, top_n=5)
        top_features = explanation.get("top_features") or []
        # Compat: API antiga esperava só feature + importance
        top_features = [
            {"feature": f["feature"], "importance": float(f["importance"])}
            for f in top_features
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
            "explanation": explanation,
            "impact": impact,
            "horizons": horizons,
            "uncertainty": uncertainty,
            "critical_neighborhoods": bairros,
            "neighborhood_ranking_mode": ranking_mode,
            "flood_geojson": geojson,
            "model_version": meta.get("model_version", MODEL_VERSION),
            "model_kind": kind,
            "data_quality": "estimado" if synthetic else "derivado",
            "score_kind": "score_sintetico" if synthetic else "probabilidade_modelo",
            "production_ready": (not synthetic),
            "model_auc_roc": public_auc(meta),
            "features_used": {
                "precip_24h": round(float(precip_24h), 2),
                "precip_48h": round(float(precip_48h), 2),
                "precip_72h": round(float(precip_72h), 2),
                "precip_7d": round(precip_7d_val, 2),
                "precip_5d": round(max(0.0, p5), 2),
                "precip_10d": round(max(0.0, p10), 2),
                "precip_30d": round(max(0.0, p30), 2),
                "mes_do_ano": int(month),
            },
            "disclaimer": (
                "Não substitui modelagem hidrodinâmica nem alerta oficial CEMADEN. "
                + (
                    "ATENÇÃO: artefato baseline_synthetic — score experimental, NÃO é probabilidade "
                    "calibrada. O Monitor operacional usa curva heurística de chuva até existir "
                    "modelo full treinado com rótulos observados (Fase 21)."
                    if synthetic
                    else "Modelo estatístico com lastro observacional (model_kind=full). "
                )
                + " " + PHYSICS_PROXY_NOTE
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
        from ml.features import _bairro_terrain_row, _load_municipal_terrain

        muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
        if not muni:
            return []

        terrain_path = terrain_parquet(codigo_ibge)
        bairro_payload = self._load_bairro_model(codigo_ibge)

        # --- Fallback sem parquet de terreno ---
        if not terrain_path.exists():
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
                    "score_source": "blend_iri",
                })
            rows.sort(key=lambda item: item["risk_probability"], reverse=True)
            return rows[:8]

        terrain_df = pd.read_parquet(terrain_path)
        floods = {item["id"]: item for item in AnalyticalEngine.calculate_flood_risk(db, muni.id)}
        municipal_terrain = _load_municipal_terrain(codigo_ibge)

        # --- 21f.2: predizer com modelo por bairro ---
        if bairro_payload is not None:
            model = bairro_payload["model"]
            meta = bairro_payload.get("meta") or {}
            cols = list(meta.get("feature_columns") or FEATURE_COLUMNS)
            rows = []
            for _, b in terrain_df.iterrows():
                flood = floods.get(int(b["bairro_id"]), {})
                iri = float(flood.get("indice_risco_inundacao", 0.5))
                susc = float(b["suscetibilidade_local"]) if "suscetibilidade_local" in terrain_df.columns else iri
                local = _bairro_terrain_row(b, municipal_terrain)
                row = {**FEATURE_DEFAULTS, **feature_row, **local}
                from ml.physics_proxy import apply_physics_proxies_to_row

                row.update(apply_physics_proxies_to_row(row))
                vec = np.array([[float(row.get(c, FEATURE_DEFAULTS.get(c, 0.0))) for c in cols]])
                try:
                    proba = model.predict_proba(vec)[0]
                    bairro_prob = float(proba[1]) if len(proba) > 1 else float(proba[0])
                except Exception as exc:
                    logger.debug("predict bairro %s: %s — blend", b.get("bairro_nome"), exc)
                    bairro_prob = min(0.99, municipal_prob * 0.50 + susc * 0.35 + iri * 0.15)
                    source = "blend_susc_iri"
                else:
                    bairro_prob = min(0.99, max(0.0, bairro_prob))
                    source = "modelo_bairro"
                rows.append({
                    "bairro_id": int(b["bairro_id"]),
                    "bairro_nome": b["bairro_nome"],
                    "risk_probability": round(bairro_prob, 3),
                    "iri": round(iri, 3),
                    "suscetibilidade_local": round(susc, 3),
                    "impermeabilizacao_pct": float(b["impermeabilizacao_pct"]),
                    "score_source": source,
                    "curve_number": round(float(local.get("curve_number", 0)), 1),
                    "capacidade_drenagem_mm_h": round(float(local.get("capacidade_drenagem_mm_h", 0)), 1),
                })
            rows.sort(key=lambda item: item["risk_probability"], reverse=True)
            return rows[:8]

        # --- Blend heurístico (artefato bairro ausente) ---
        rows = []
        for _, b in terrain_df.iterrows():
            flood = floods.get(int(b["bairro_id"]), {})
            iri = float(flood.get("indice_risco_inundacao", 0.5))
            if "suscetibilidade_local" in terrain_df.columns:
                susc = float(b.get("suscetibilidade_local") or 0.4)
            else:
                susc = iri
            bairro_prob = min(0.99, municipal_prob * 0.50 + susc * 0.35 + iri * 0.15)
            rows.append({
                "bairro_id": int(b["bairro_id"]),
                "bairro_nome": b["bairro_nome"],
                "risk_probability": round(bairro_prob, 3),
                "iri": round(iri, 3),
                "suscetibilidade_local": round(susc, 3),
                "impermeabilizacao_pct": float(b["impermeabilizacao_pct"]),
                "score_source": "blend_susc_iri",
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
