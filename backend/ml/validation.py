"""Protocolo de validação preditiva (Fase 21e).

Hold-out temporal, Brier, calibração e baselines obrigatórios.
O modelo final NÃO é retreinado no conjunto de teste.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss, roc_auc_score

from ml.constants import (
    FEATURE_COLUMNS,
    HOLDOUT_TEST_START_YEAR,
    HOLDOUT_TRAIN_END_YEAR,
    ML_ALGORITHM,
)
from ml.model_factory import attach_permutation_importances, fit_classifier, make_classifier

logger = logging.getLogger(__name__)


def temporal_split(
    df: pd.DataFrame,
    *,
    train_end_year: int = HOLDOUT_TRAIN_END_YEAR,
    test_start_year: int = HOLDOUT_TEST_START_YEAR,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separa treino (até train_end_year) e teste (a partir de test_start_year)."""
    work = df.copy()
    if "date" not in work.columns:
        raise ValueError("Dataset precisa da coluna date para hold-out temporal.")
    work["date"] = pd.to_datetime(work["date"])
    train = work[work["date"].dt.year <= train_end_year].copy()
    test = work[work["date"].dt.year >= test_start_year].copy()
    return train, test


def _xy(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    cols = [c for c in FEATURE_COLUMNS if c in df.columns]
    return df[cols].astype(float), df["label"].astype(int)


def rain_threshold_baseline(y_true: pd.Series, precip: pd.Series, threshold_mm: float) -> np.ndarray:
    """Baseline ‘chuva > X mm’ como probabilidade 0/1."""
    return (precip.astype(float) >= float(threshold_mm)).astype(float).to_numpy()


def seasonal_climatology_baseline(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
) -> np.ndarray:
    """Probabilidade = taxa histórica de eventos no mesmo mês (treino)."""
    if train_df.empty or "mes_do_ano" not in train_df.columns:
        return np.full(len(test_df), float(train_df["label"].mean()) if len(train_df) else 0.05)
    rates = train_df.groupby(train_df["mes_do_ano"].astype(int))["label"].mean()
    global_rate = float(train_df["label"].mean())
    months = test_df["mes_do_ano"].astype(int)
    return months.map(lambda m: float(rates.get(m, global_rate))).to_numpy(dtype=float)


def reliability_curve(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    *,
    n_bins: int = 8,
) -> list[dict[str, float]]:
    """Pontos da curva de confiabilidade (binning uniforme)."""
    y_true = np.asarray(y_true).astype(int)
    y_prob = np.clip(np.asarray(y_prob).astype(float), 0.0, 1.0)
    if len(y_true) == 0:
        return []
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    out: list[dict[str, float]] = []
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        mask = (y_prob >= lo) & (y_prob < hi if i < n_bins - 1 else y_prob <= hi)
        if not mask.any():
            continue
        out.append({
            "bin_left": round(float(lo), 3),
            "bin_right": round(float(hi), 3),
            "mean_predicted": round(float(y_prob[mask].mean()), 4),
            "fraction_positive": round(float(y_true[mask].mean()), 4),
            "count": int(mask.sum()),
        })
    return out


def _safe_auc(y_true: np.ndarray, y_prob: np.ndarray) -> float | None:
    if len(np.unique(y_true)) < 2:
        return None
    try:
        return round(float(roc_auc_score(y_true, y_prob)), 4)
    except ValueError:
        return None


def _safe_brier(y_true: np.ndarray, y_prob: np.ndarray) -> float | None:
    if len(y_true) == 0:
        return None
    try:
        return round(float(brier_score_loss(y_true, y_prob)), 4)
    except ValueError:
        return None


def evaluate_protocol(
    df: pd.DataFrame,
    *,
    rain_threshold_mm: float = 50.0,
    calibrate: bool = True,
) -> dict[str, Any]:
    """Roda 21e.1–21e.4: hold-out, métricas, baselines, calibração isotônica."""
    train_df, test_df = temporal_split(df)
    result: dict[str, Any] = {
        "protocol": "21e_temporal_holdout",
        "train_end_year": HOLDOUT_TRAIN_END_YEAR,
        "test_start_year": HOLDOUT_TEST_START_YEAR,
        "n_train": len(train_df),
        "n_test": len(test_df),
        "n_pos_train": int(train_df["label"].sum()) if len(train_df) else 0,
        "n_pos_test": int(test_df["label"].sum()) if len(test_df) else 0,
        "beats_rain_baseline": None,
        "beats_climatology": None,
        "discard_model": False,
        "calibrated": False,
    }

    if len(train_df) < 40 or result["n_pos_train"] < 1:
        result["ok"] = False
        result["reason"] = "treino_insuficiente_para_holdout"
        return result
    if len(test_df) < 10:
        result["ok"] = False
        result["reason"] = "teste_insuficiente_para_holdout"
        return result

    x_train, y_train = _xy(train_df)
    x_test, y_test = _xy(test_df)

    from sklearn.utils.class_weight import compute_sample_weight

    base_model, algo_name = make_classifier(ML_ALGORITHM)
    try:
        fit_classifier(base_model, x_train, y_train, algorithm=algo_name)
    except Exception as exc:
        logger.warning("HGB falhou (%s) — fallback RF", exc)
        base_model, algo_name = make_classifier("random_forest")
        fit_classifier(base_model, x_train, y_train, algorithm=algo_name)

    proba_raw = base_model.predict_proba(x_test)[:, 1]
    attach_permutation_importances(base_model, x_train, y_train)

    model_for_export = base_model
    proba = proba_raw
    if calibrate and result["n_pos_train"] >= 2 and y_train.nunique() > 1:
        try:
            fresh, _ = make_classifier(algo_name)
            calib = CalibratedClassifierCV(fresh, method="isotonic", cv=3)
            sw = compute_sample_weight("balanced", y_train)
            calib.fit(x_train, y_train, sample_weight=sw)
            proba = calib.predict_proba(x_test)[:, 1]
            model_for_export = calib
            imp = getattr(base_model, "_sinidu_feature_importances_", None)
            if imp is not None:
                setattr(model_for_export, "_sinidu_feature_importances_", imp)
            result["calibrated"] = True
            result["calibration_method"] = "isotonic_cv3"
        except Exception as exc:
            logger.info("Calibração indisponível: %s — usa proba bruta", exc)

    y_np = y_test.to_numpy()
    rain_proba = rain_threshold_baseline(y_test, test_df["precip_24h"], rain_threshold_mm)
    clim_proba = seasonal_climatology_baseline(train_df, test_df)

    model_brier = _safe_brier(y_np, proba)
    rain_brier = _safe_brier(y_np, rain_proba)
    clim_brier = _safe_brier(y_np, clim_proba)

    result.update({
        "ok": True,
        "algorithm": algo_name,
        "auc_roc_holdout": _safe_auc(y_np, proba),
        "brier_model": model_brier,
        "brier_rain_baseline": rain_brier,
        "brier_climatology": clim_brier,
        "auc_rain_baseline": _safe_auc(y_np, rain_proba),
        "auc_climatology": _safe_auc(y_np, clim_proba),
        "reliability_curve": reliability_curve(y_np, proba),
        "rain_threshold_mm": rain_threshold_mm,
        "model": model_for_export,
        "train_df": train_df,
        "test_df": test_df,
    })    # Menor Brier = melhor. Modelo deve bater ambos os baselines.
    if model_brier is not None and rain_brier is not None:
        result["beats_rain_baseline"] = model_brier < rain_brier
    if model_brier is not None and clim_brier is not None:
        result["beats_climatology"] = model_brier < clim_brier

    beats_rain = result["beats_rain_baseline"]
    beats_clim = result["beats_climatology"]
    if beats_rain is False and beats_clim is False:
        result["discard_model"] = True
        result["discard_reason"] = "modelo_nao_bate_baselines_brier"
    elif beats_rain is False:
        result["warning"] = "modelo_nao_bate_baseline_chuva_mm"

    return result


def write_model_card(
    path,
    *,
    codigo_ibge: str,
    meta: dict[str, Any],
    validation: dict[str, Any],
) -> None:
    """Card de modelo versionado (21e.6) — markdown curto."""
    spatial = validation.get("spatial") or meta.get("spatial_validation") or {}
    lines = [
        f"# Model card — IBGE {codigo_ibge}",
        "",
        f"- **model_version**: {meta.get('model_version')}",
        f"- **model_kind**: {meta.get('model_kind')}",
        f"- **algorithm**: {meta.get('algorithm') or (validation.get('algorithm') if validation else None) or '—'}",
        f"- **trained_at**: {meta.get('trained_at')}",
        f"- **features**: {', '.join(meta.get('feature_columns') or FEATURE_COLUMNS)}",
        f"- **n_positive (train fit)**: {meta.get('n_positive')}",
        f"- **label_policy**: {meta.get('label_policy')}",
        "",
        "## Hold-out temporal (21e)",
        f"- Treino ≤ {validation.get('train_end_year')} / Teste ≥ {validation.get('test_start_year')}",
        f"- n_train={validation.get('n_train')} (pos={validation.get('n_pos_train')})",
        f"- n_test={validation.get('n_test')} (pos={validation.get('n_pos_test')})",
        f"- AUC hold-out: {validation.get('auc_roc_holdout')}",
        f"- Brier modelo: {validation.get('brier_model')}",
        f"- Brier chuva>{validation.get('rain_threshold_mm')}mm: {validation.get('brier_rain_baseline')}",
        f"- Brier climatologia: {validation.get('brier_climatology')}",
        f"- Calibrado: {validation.get('calibrated')} ({validation.get('calibration_method', '—')})",
        f"- Bate baseline chuva: {validation.get('beats_rain_baseline')}",
        f"- Bate climatologia: {validation.get('beats_climatology')}",
        f"- Descartar modelo: {validation.get('discard_model')}",
        "",
        "## Validação espacial (21e.5)",
        f"- Disponível: {spatial.get('disponivel')}",
        f"- Fonte: {spatial.get('fonte', '—')}",
        f"- Eventos com geometria: {spatial.get('eventos_com_geometria')}",
        f"- Hit-rate (pontos na zona de risco): {spatial.get('hit_rate')}",
        f"- Jaccard bairros: {spatial.get('jaccard_bairros')}",
        f"- Acordo: {spatial.get('acordo')}",
        f"- Método da zona: {spatial.get('zona_metodo')}",
        f"- Narrativa: {spatial.get('narrativa', '—')}",
        "",
        "## Limitações",
        "- Não substitui alerta CEMADEN nem hidrodinâmica 2D.",
        "- IDF e grupo hidrológico ainda são proxies (qualidade Estimado).",
        "- Poucos rótulos oficiais: métricas instáveis com n_pos baixo.",
        "- Hit-rate espacial usa pontos S2ID/eventos (±50 m), não polígonos oficiais de área afetada.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


# Buffer ~50 m em graus (mesmo critério da simulação física)
_POINT_BUFFER_DEG = 0.00045


def _union_from_geojson(geometry: dict[str, Any] | None):
    from shapely.geometry import shape
    from shapely.ops import unary_union

    if not geometry:
        return None
    feats = geometry.get("features") if geometry.get("type") == "FeatureCollection" else None
    if feats is not None:
        shapes = []
        for f in feats:
            try:
                g = shape(f["geometry"])
                if not g.is_empty:
                    shapes.append(g)
            except Exception:
                continue
        if not shapes:
            return None
        return unary_union(shapes)
    try:
        g = shape(geometry if "coordinates" in geometry else geometry.get("geometry") or geometry)
        return g if not g.is_empty else None
    except Exception:
        return None


def _load_official_event_points(db: Session, codigo_ibge: str) -> list[dict[str, Any]]:
    """Pontos georreferenciados oficiais (evento_alagamento → S2ID oficial)."""
    import json

    from shapely.geometry import shape

    from app.models import EventoAlagamentoObservado, HistoricoDesastreS2ID, Municipio
    from ml.features import ML_LABEL_QUALITIES

    code = str(codigo_ibge).zfill(7)[:7]
    points: list[dict[str, Any]] = []

    observed = (
        db.query(EventoAlagamentoObservado)
        .filter(
            EventoAlagamentoObservado.codigo_ibge == code,
            EventoAlagamentoObservado.data_quality.in_(tuple(ML_LABEL_QUALITIES)),
            EventoAlagamentoObservado.geom.isnot(None),
        )
        .all()
    )
    for ev in observed:
        try:
            geojson = db.scalar(ev.geom.ST_AsGeoJSON())
            if not geojson:
                continue
            pt = shape(json.loads(geojson))
            if pt.is_empty:
                continue
            points.append({"id": ev.id, "fonte": "evento_alagamento_observado", "geom": pt})
        except Exception:
            continue

    if points:
        return points

    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        return []
    rows = (
        db.query(HistoricoDesastreS2ID)
        .filter(
            HistoricoDesastreS2ID.municipio_id == muni.id,
            HistoricoDesastreS2ID.data_quality.in_(tuple(ML_LABEL_QUALITIES)),
            HistoricoDesastreS2ID.geom.isnot(None),
        )
        .all()
    )
    from ml.constants import FLOOD_EVENT_TYPES

    for row in rows:
        tipo = row.tipo_desastre or ""
        if tipo not in FLOOD_EVENT_TYPES and not any(
            k in tipo for k in ("Inunda", "Alag", "Enxurr")
        ):
            continue
        try:
            geojson = db.scalar(row.geom.ST_AsGeoJSON())
            if not geojson:
                continue
            pt = shape(json.loads(geojson))
            if pt.is_empty:
                continue
            points.append({"id": row.id, "fonte": "s2id_oficial", "geom": pt})
        except Exception:
            continue
    return points


def _risk_zone_from_terrain(
    db: Session,
    codigo_ibge: str,
    *,
    top_frac: float = 0.25,
) -> tuple[dict[str, Any] | None, list[str], str]:
    """Zona de risco preditiva = top bairros por suscetibilidade_local (ou impermeab.)."""
    import json

    import pandas as pd
    from sqlalchemy import func

    from app.models import Bairro, Municipio
    from ml.paths import terrain_parquet

    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        return None, [], "municipio_ausente"

    path = terrain_parquet(code)
    if path.exists():
        df = pd.read_parquet(path)
        score_col = (
            "suscetibilidade_local"
            if "suscetibilidade_local" in df.columns
            else "impermeabilizacao_pct"
        )
        df = df.sort_values(score_col, ascending=False)
        n_keep = max(1, int(round(len(df) * float(top_frac))))
        top = df.head(n_keep)
        metodo = f"top_{int(top_frac * 100)}pct_{score_col}"
    else:
        bairros = db.query(Bairro).filter(Bairro.municipio_id == muni.id).all()
        if not bairros:
            return None, [], "sem_bairros"
        n_keep = max(1, int(round(len(bairros) * float(top_frac))))
        top = pd.DataFrame([{"bairro_id": b.id, "bairro_nome": b.nome} for b in bairros[:n_keep]])
        metodo = f"top_{int(top_frac * 100)}pct_ordem_cadastro"

    features = []
    nomes: list[str] = []
    for _, row in top.iterrows():
        b = (
            db.query(Bairro)
            .filter(Bairro.id == int(row["bairro_id"]), Bairro.municipio_id == muni.id)
            .first()
        )
        if not b or b.geom is None:
            continue
        try:
            geom = json.loads(db.scalar(func.ST_AsGeoJSON(b.geom)))
        except Exception:
            continue
        nomes.append(str(row.get("bairro_nome") or b.nome))
        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "name": b.nome,
                "bairro_id": b.id,
                "layer_type": "ml_risk_zone",
            },
        })

    if not features:
        return None, [], "sem_geometria_bairro"
    return {"type": "FeatureCollection", "features": features}, nomes, metodo


def evaluate_spatial_hit_rate(
    db: Session,
    codigo_ibge: str,
    *,
    flood_geojson: dict[str, Any] | None = None,
    affected_bairros: list[str] | None = None,
    top_frac: float = 0.25,
) -> dict[str, Any]:
    """21e.5 — hit-rate da zona de risco ML contra eventos oficiais georreferenciados.

    Sem mancha explícita, usa top bairros por suscetibilidade (proxy da zona preditiva).
    """
    code = str(codigo_ibge).zfill(7)[:7]
    points = _load_official_event_points(db, code)

    zona_metodo = "flood_geojson_fornecido"
    nomes = list(affected_bairros or [])
    geo = flood_geojson
    if geo is None:
        geo, nomes_auto, zona_metodo = _risk_zone_from_terrain(db, code, top_frac=top_frac)
        if not nomes:
            nomes = nomes_auto

    flood_union = _union_from_geojson(geo)
    hits = 0
    for pt in points:
        if flood_union is None:
            break
        try:
            if flood_union.buffer(_POINT_BUFFER_DEG).intersects(pt["geom"]):
                hits += 1
        except Exception:
            continue

    n_geom = len(points)
    hit_rate = round(hits / n_geom, 3) if n_geom else None

    # Jaccard: bairros da zona × bairros que contêm eventos oficiais
    import json

    from shapely.geometry import shape as shp

    from app.models import Bairro, Municipio
    from sqlalchemy import func

    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    historicos: set[str] = set()
    if muni and points:
        for b in db.query(Bairro).filter(Bairro.municipio_id == muni.id).all():
            if b.geom is None:
                continue
            try:
                bgeo = db.scalar(func.ST_AsGeoJSON(b.geom))
                if not bgeo:
                    continue
                poly = shp(json.loads(bgeo))
            except Exception:
                continue
            for pt in points:
                try:
                    if poly.intersects(pt["geom"]):
                        historicos.add(b.nome)
                        break
                except Exception:
                    continue

    simulados = {str(x) for x in nomes if x}
    inter = historicos & simulados
    union = historicos | simulados
    jaccard = round(len(inter) / len(union), 3) if union else None

    if n_geom == 0 and not historicos:
        acordo = "insuficiente"
        narrativa = (
            "Sem eventos oficiais georreferenciados para validar a zona de risco ML."
        )
    elif hit_rate is not None and hit_rate >= 0.6:
        acordo = "alta"
        narrativa = f"{hits}/{n_geom} eventos oficiais caem na zona preditiva (hit-rate {hit_rate:.0%})."
    elif hit_rate is not None and hit_rate >= 0.3:
        acordo = "media"
        narrativa = (
            f"{hits}/{n_geom} eventos na zona (hit-rate {hit_rate:.0%}) — alinhamento parcial."
        )
    elif hit_rate is not None:
        acordo = "baixa"
        narrativa = f"Poucos eventos na zona preditiva ({hits}/{n_geom})."
    elif jaccard is not None and jaccard >= 0.4:
        acordo = "media"
        narrativa = f"Sobreposição de bairros histórico×preditivo (Jaccard {jaccard:.0%})."
    else:
        acordo = "baixa"
        narrativa = "Validação espacial limitada."

    fonte = points[0]["fonte"] if points else "nenhuma"
    return {
        "disponivel": n_geom > 0 or bool(historicos),
        "protocol": "21e5_spatial_hit_rate",
        "fonte": fonte,
        "qualidade": "Oficial" if n_geom else "Lacuna",
        "eventos_com_geometria": n_geom,
        "eventos_na_zona": hits,
        "hit_rate": hit_rate,
        "bairros_historicos": sorted(historicos)[:20],
        "bairros_preditivos": sorted(simulados)[:20],
        "bairros_em_comum": sorted(inter)[:20],
        "jaccard_bairros": jaccard,
        "acordo": acordo,
        "narrativa": narrativa,
        "zona_metodo": zona_metodo,
        "limitacao": (
            "Eventos S2ID/observados são pontos, não polígonos oficiais. "
            "Hit-rate mede se o histórico cai na zona preditiva (±50 m)."
        ),
    }