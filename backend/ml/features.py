from __future__ import annotations

import logging
import random as py_random
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Bairro, HistoricoDesastreS2ID, Municipio
from ml.constants import (
    FEATURE_COLUMNS,
    FEATURE_DEFAULTS,
    FLOOD_EVENT_TYPES,
    LABEL_LAG_AFTER_DAYS,
    LABEL_LAG_BEFORE_DAYS,
)
from ml.paths import bairro_features_parquet, features_parquet, terrain_parquet
from ml.precipitation import collect_precipitation
from ml.terrain import extract_bairro_features

logger = logging.getLogger(__name__)

# Só estes níveis entram como rótulo positivo no treino full (Fase 21c.2)
ML_LABEL_QUALITIES = frozenset({"oficial", "oficial_curado"})

_PRECIP_FEATURE_KEYS = {
    "precip_24h",
    "precip_48h",
    "precip_72h",
    "precip_7d",
    "precip_5d",
    "precip_10d",
    "precip_30d",
    "mes_do_ano",
    "duracao_chuva_h",
    "intensidade_media_mm_h",
    "intensidade_pico_proxy_mm_h",
    "razao_intensidade_idf_tr2",
    "sazonalidade_sin",
    "sazonalidade_cos",
}


def _load_municipal_terrain(codigo_ibge: str) -> dict[str, float]:
    import json

    meta_path = terrain_parquet(codigo_ibge).with_suffix(".municipal.json")
    if meta_path.exists():
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        for key, default in FEATURE_DEFAULTS.items():
            data.setdefault(key, default)
        return data
    df = pd.read_parquet(terrain_parquet(codigo_ibge))
    out = {
        "impermeabilizacao_pct": float(df["impermeabilizacao_pct"].mean()),
        "cobertura_vegetal_pct": float(df["cobertura_vegetal_pct"].mean()),
        "declividade_media": float(df["declividade_media"].mean()),
    }
    if "water_proximity" in df.columns:
        out["water_proximity"] = float(df["water_proximity"].mean())
    for key, default in FEATURE_DEFAULTS.items():
        out.setdefault(key, default)
    return out


def _is_flood_type(tipo: str) -> bool:
    t = tipo or ""
    return t in FLOOD_EVENT_TYPES or "Inunda" in t or "Alag" in t or "Enxurr" in t


def _event_dates(db: Session, municipio_id: int, codigo_ibge: str) -> set[date]:
    """Datas-rótulo: preferência evento_alagamento_observado; senão S2ID oficial apenas."""
    try:
        from app.services.evento_alagamento_service import observed_flood_dates

        observed = observed_flood_dates(db, codigo_ibge)
        if observed:
            return observed
    except Exception as exc:
        logger.info("evento_alagamento_observado indisponível %s: %s", codigo_ibge, exc)

    rows = (
        db.query(
            HistoricoDesastreS2ID.data_ocorrencia,
            HistoricoDesastreS2ID.tipo_desastre,
            HistoricoDesastreS2ID.data_quality,
        )
        .filter(HistoricoDesastreS2ID.municipio_id == municipio_id)
        .all()
    )
    dates: set[date] = set()
    skipped_estimado = 0
    for row in rows:
        quality = (row.data_quality or "estimado").lower()
        if quality not in ML_LABEL_QUALITIES:
            skipped_estimado += 1
            continue
        if _is_flood_type(row.tipo_desastre):
            dates.add(row.data_ocorrencia)
    if skipped_estimado:
        logger.info(
            "ML labels %s: ignorados %d eventos S2ID não-oficiais (estimado/sintético)",
            codigo_ibge,
            skipped_estimado,
        )
    return dates


def _expand_label_dates(event_dates: set[date]) -> set[date]:
    expanded = set(event_dates)
    for d in list(event_dates):
        for lag in range(-LABEL_LAG_BEFORE_DAYS, LABEL_LAG_AFTER_DAYS + 1):
            if lag == 0:
                continue
            expanded.add(d + timedelta(days=lag))
    return expanded


def _top_quartile_bairro_ids(terrain_df: pd.DataFrame) -> set[int]:
    """Bairros no quartil superior de suscetibilidade (fallback espacial)."""
    if terrain_df.empty:
        return set()
    col = "suscetibilidade_local" if "suscetibilidade_local" in terrain_df.columns else None
    if col is None:
        return {int(x) for x in terrain_df["bairro_id"].tolist()}
    q75 = float(terrain_df[col].quantile(0.75))
    ids = terrain_df.loc[terrain_df[col] >= q75, "bairro_id"]
    out = {int(x) for x in ids.tolist()}
    if not out:
        top = terrain_df.sort_values(col, ascending=False).head(max(1, len(terrain_df) // 4))
        out = {int(x) for x in top["bairro_id"].tolist()}
    return out


def _positive_bairro_by_date(
    db: Session,
    municipio_id: int,
    codigo_ibge: str,
    terrain_df: pd.DataFrame,
) -> dict[date, set[int]]:
    """
    Mapa data → bairros positivos (21f.2).

    Preferência: interseção geométrica do evento oficial com o polígono do bairro.
    Sem geometria: atribui ao quartil superior de suscetibilidade_local.
    """
    from app.models import EventoAlagamentoObservado

    result: dict[date, set[int]] = defaultdict(set)
    top_ids = _top_quartile_bairro_ids(terrain_df)
    all_ids = {int(x) for x in terrain_df["bairro_id"].tolist()} if not terrain_df.empty else set()

    try:
        obs = (
            db.query(EventoAlagamentoObservado)
            .filter(
                EventoAlagamentoObservado.codigo_ibge == codigo_ibge,
                EventoAlagamentoObservado.data_quality.in_(tuple(ML_LABEL_QUALITIES)),
            )
            .all()
        )
    except Exception as exc:
        logger.info("EventoAlagamentoObservado query %s: %s", codigo_ibge, exc)
        obs = []

    for ev in obs:
        if not _is_flood_type(ev.tipo or ""):
            continue
        d = ev.inicio_em.date() if hasattr(ev.inicio_em, "date") else ev.inicio_em
        hit_ids: set[int] = set()
        if ev.geom is not None:
            try:
                rows = (
                    db.query(Bairro.id)
                    .filter(
                        Bairro.municipio_id == municipio_id,
                        func.ST_Intersects(Bairro.geom, ev.geom),
                    )
                    .all()
                )
                hit_ids = {int(r.id) for r in rows}
            except Exception as exc:
                logger.debug("intersect evento×bairro: %s", exc)
        if hit_ids:
            result[d].update(hit_ids)
        else:
            result[d].update(top_ids or all_ids)

    if not result:
        s2id = (
            db.query(HistoricoDesastreS2ID)
            .filter(
                HistoricoDesastreS2ID.municipio_id == municipio_id,
                HistoricoDesastreS2ID.data_quality.in_(tuple(ML_LABEL_QUALITIES)),
            )
            .all()
        )
        for row in s2id:
            if not _is_flood_type(row.tipo_desastre or ""):
                continue
            d = row.data_ocorrencia
            hit_ids: set[int] = set()
            if row.geom is not None:
                try:
                    hits = (
                        db.query(Bairro.id)
                        .filter(
                            Bairro.municipio_id == municipio_id,
                            func.ST_Intersects(Bairro.geom, row.geom),
                        )
                        .all()
                    )
                    hit_ids = {int(r.id) for r in hits}
                except Exception:
                    hit_ids = set()
            if hit_ids:
                result[d].update(hit_ids)
            else:
                result[d].update(top_ids or all_ids)

    return dict(result)


def _bairro_terrain_row(
    bairro_row: Any,
    municipal: dict[str, float],
) -> dict[str, float]:
    """Monta vetor de terreno: features locais do bairro + HAND municipal."""
    def _get(key: str, default: float) -> float:
        val = None
        if isinstance(bairro_row, dict):
            val = bairro_row.get(key)
        elif isinstance(bairro_row, pd.Series):
            val = bairro_row[key] if key in bairro_row.index else None
        elif hasattr(bairro_row, key):
            val = getattr(bairro_row, key)
        if val is None or (isinstance(val, float) and val != val):
            return default
        try:
            return float(val)
        except (TypeError, ValueError):
            return default

    cap = _get("capacidade_drenagem_mm_h", float(municipal.get("capacidade_drenagem_mm_h", 18.0)))
    sat = min(1.0, 40.0 / max(cap, 1.0))
    susc_local = _get("suscetibilidade_local", float(municipal.get("suscetibilidade_hand", 0.35)))
    out = {**FEATURE_DEFAULTS, **municipal}
    out.update({
        "impermeabilizacao_pct": _get("impermeabilizacao_pct", 45.0),
        "cobertura_vegetal_pct": _get("cobertura_vegetal_pct", 15.0),
        "declividade_media": _get("declividade_media", 3.0),
        "water_proximity": _get("water_proximity", 0.1),
        "curve_number": _get("curve_number", float(municipal.get("curve_number", 85.0))),
        "capacidade_drenagem_mm_h": cap,
        "saturacao_drenagem_40mm": sat,
        # 21f.2 — suscetibilidade local ocupa o slot HAND no vetor ML
        "suscetibilidade_hand": susc_local,
    })
    return out


def build_labeled_dataset(db: Session, codigo_ibge: str, force: bool = False) -> pd.DataFrame:
    output = features_parquet(codigo_ibge)
    if output.exists() and not force:
        return pd.read_parquet(output)

    muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
    if not muni:
        raise ValueError(f"Município {codigo_ibge} não encontrado.")

    precip = collect_precipitation(db, codigo_ibge, force=force)
    extract_bairro_features(db, codigo_ibge, force=force)
    terrain = _load_municipal_terrain(codigo_ibge)
    event_dates = _event_dates(db, muni.id, codigo_ibge)

    precip["date_only"] = precip["date"].dt.date
    expanded_dates = _expand_label_dates(event_dates)
    precip["label"] = precip["date_only"].apply(lambda d: 1 if d in expanded_dates else 0)

    if "intensidade_media_mm_h" not in precip.columns:
        from ml.intensity import enrich_intensity_features

        precip = enrich_intensity_features(precip, codigo_ibge=codigo_ibge)

    positives = precip[precip["label"] == 1]
    negatives = precip[precip["label"] == 0]
    max_neg = max(len(positives) * 40, 400)
    if len(negatives) > max_neg:
        negatives = negatives.sample(n=max_neg, random_state=42)
    labeled = pd.concat([positives, negatives], ignore_index=True).sort_values("date")

    for key, value in terrain.items():
        labeled[key] = value

    from ml.physics_proxy import enrich_dataframe_physics_proxies

    labeled = enrich_dataframe_physics_proxies(labeled)

    try:
        from app.services.fluvio_series_service import cota_features_for_dates

        labeled = cota_features_for_dates(db, codigo_ibge, labeled)
    except Exception as exc:
        logger.warning("Features de cota ANA indisponíveis para %s: %s", codigo_ibge, exc)
        labeled["cota_rio_disponivel"] = 0.0
        labeled["cota_rio_anomalia"] = 0.0

    labeled["codigo_ibge"] = codigo_ibge
    labeled["label_source"] = "official_observed_or_s2id"
    output.parent.mkdir(parents=True, exist_ok=True)
    labeled.to_parquet(output, index=False)
    logger.info(
        "Dataset %s: %d positivos (só rótulo oficial), %d negativos, %d linhas",
        codigo_ibge,
        int(labeled["label"].sum()),
        int((labeled["label"] == 0).sum()),
        len(labeled),
    )
    return labeled


def build_labeled_dataset_bairro(db: Session, codigo_ibge: str, force: bool = False) -> pd.DataFrame:
    """
    Dataset grain=bairro (Fase 21f.2).

    Cada linha = (data, bairro) com precip do dia + terreno local.
    Rótulo positivo se o bairro está no mapa espacial do evento (ou quartil de susc.).
    """
    output = bairro_features_parquet(codigo_ibge)
    if output.exists() and not force:
        return pd.read_parquet(output)

    muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
    if not muni:
        raise ValueError(f"Município {codigo_ibge} não encontrado.")

    precip = collect_precipitation(db, codigo_ibge, force=force)
    terrain_df = extract_bairro_features(db, codigo_ibge, force=force)
    municipal = _load_municipal_terrain(codigo_ibge)
    pos_map = _positive_bairro_by_date(db, muni.id, codigo_ibge, terrain_df)

    if terrain_df.empty or not pos_map:
        logger.warning("Dataset bairro %s: sem terreno ou sem eventos oficiais.", codigo_ibge)
        empty = pd.DataFrame(columns=["date", "label", "bairro_id", *FEATURE_COLUMNS])
        output.parent.mkdir(parents=True, exist_ok=True)
        empty.to_parquet(output, index=False)
        return empty

    if "intensidade_media_mm_h" not in precip.columns:
        from ml.intensity import enrich_intensity_features

        precip = enrich_intensity_features(precip, codigo_ibge=codigo_ibge)

    precip = precip.copy()
    precip["date_only"] = precip["date"].dt.date

    expanded_pos: dict[date, set[int]] = defaultdict(set)
    for d, ids in pos_map.items():
        for lag in range(-LABEL_LAG_BEFORE_DAYS, LABEL_LAG_AFTER_DAYS + 1):
            expanded_pos[d + timedelta(days=lag)].update(ids)

    terrain_by_id = {int(r.bairro_id): r for r in terrain_df.itertuples()}
    bairro_ids = list(terrain_by_id.keys())
    rnd = py_random.Random(42)

    rows: list[dict[str, Any]] = []
    for _, prow in precip.iterrows():
        d = prow["date_only"]
        pos_ids = expanded_pos.get(d, set())
        precip_feats = {
            c: float(prow[c]) if c in prow.index and pd.notna(prow[c]) else FEATURE_DEFAULTS.get(c, 0.0)
            for c in _PRECIP_FEATURE_KEYS
        }
        if "mes_do_ano" not in precip_feats or precip_feats["mes_do_ano"] == 0.0:
            month = getattr(prow["date"], "month", None)
            precip_feats["mes_do_ano"] = float(month or 3)

        for bid in pos_ids:
            if bid not in terrain_by_id:
                continue
            terr = _bairro_terrain_row(terrain_by_id[bid], municipal)
            row = {**FEATURE_DEFAULTS, **terr, **precip_feats}
            row.update({
                "date": prow["date"],
                "bairro_id": bid,
                "bairro_nome": getattr(terrain_by_id[bid], "bairro_nome", ""),
                "label": 1,
                "codigo_ibge": codigo_ibge,
                "label_source": "official_spatial_or_susc_quartile",
            })
            rows.append(row)

        candidates = [b for b in bairro_ids if b not in pos_ids] if pos_ids else list(bairro_ids)
        k = min(len(candidates), 8 if pos_ids else 3)
        if k <= 0:
            continue
        for bid in rnd.sample(candidates, k=k):
            terr = _bairro_terrain_row(terrain_by_id[bid], municipal)
            row = {**FEATURE_DEFAULTS, **terr, **precip_feats}
            row.update({
                "date": prow["date"],
                "bairro_id": bid,
                "bairro_nome": getattr(terrain_by_id[bid], "bairro_nome", ""),
                "label": 0,
                "codigo_ibge": codigo_ibge,
                "label_source": "official_spatial_or_susc_quartile",
            })
            rows.append(row)

    labeled = pd.DataFrame(rows)
    if labeled.empty:
        output.parent.mkdir(parents=True, exist_ok=True)
        labeled.to_parquet(output, index=False)
        return labeled

    positives = labeled[labeled["label"] == 1]
    negatives = labeled[labeled["label"] == 0]
    max_neg = max(len(positives) * 25, 800)
    if len(negatives) > max_neg:
        negatives = negatives.sample(n=max_neg, random_state=42)
    labeled = pd.concat([positives, negatives], ignore_index=True).sort_values("date")

    for col in FEATURE_COLUMNS:
        if col not in labeled.columns:
            labeled[col] = FEATURE_DEFAULTS.get(col, 0.0)

    from ml.physics_proxy import enrich_dataframe_physics_proxies

    labeled = enrich_dataframe_physics_proxies(labeled)

    output.parent.mkdir(parents=True, exist_ok=True)
    labeled.to_parquet(output, index=False)
    logger.info(
        "Dataset bairro %s: %d positivos, %d negativos, %d linhas, %d bairros",
        codigo_ibge,
        int(labeled["label"].sum()),
        int((labeled["label"] == 0).sum()),
        len(labeled),
        labeled["bairro_id"].nunique() if "bairro_id" in labeled.columns else 0,
    )
    return labeled


def feature_matrix(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    x = df[FEATURE_COLUMNS].astype(float)
    y = df["label"].astype(int)
    return x, y
