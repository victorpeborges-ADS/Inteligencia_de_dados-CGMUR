"""Explicabilidade por domínio de features (Fase 21g.3).

Agrupa importâncias do Random Forest em chuva / solo / drenagem / HAND /
sazonalidade — linguagem que o gestor entende, sem SHAP (CPU leve).
"""

from __future__ import annotations

from typing import Any

import numpy as np

# Domínio → features (ordem do FEATURE_COLUMNS)
FEATURE_DOMAINS: dict[str, tuple[str, ...]] = {
    "chuva": (
        "precip_24h",
        "precip_48h",
        "precip_72h",
        "precip_7d",
        "precip_5d",
        "precip_10d",
        "precip_30d",
        "duracao_chuva_h",
        "intensidade_media_mm_h",
        "intensidade_pico_proxy_mm_h",
        "razao_intensidade_idf_tr2",
    ),
    "solo_uso": (
        "impermeabilizacao_pct",
        "cobertura_vegetal_pct",
        "curve_number",
        "tendencia_impermeabilizacao_pp_a",
        "declividade_media",
    ),
    "drenagem": (
        "capacidade_drenagem_mm_h",
        "saturacao_drenagem_40mm",
    ),
    "hand_hidrografia": (
        "water_proximity",
        "hand_media_m",
        "pct_hand_lt_5m",
        "suscetibilidade_hand",
        "twi_media",
    ),
    "sazonalidade": (
        "mes_do_ano",
        "sazonalidade_sin",
        "sazonalidade_cos",
    ),
}

DOMAIN_LABELS_PT: dict[str, str] = {
    "chuva": "Chuva (volume/intensidade)",
    "solo_uso": "Solo e uso do solo",
    "drenagem": "Capacidade de drenagem",
    "hand_hidrografia": "HAND / hidrografia",
    "sazonalidade": "Sazonalidade",
}


def _unwrap_importances(model: Any) -> np.ndarray | None:
    """RF / HGB / CalibratedClassifierCV → vetor de importâncias."""
    custom = getattr(model, "_sinidu_feature_importances_", None)
    if custom is not None:
        return np.asarray(custom, dtype=float)
    imp = getattr(model, "feature_importances_", None)
    if imp is not None:
        return np.asarray(imp, dtype=float)
    # CalibratedClassifierCV (sklearn ≥1.x)
    cals = getattr(model, "calibrated_classifiers_", None)
    if cals:
        # Preferência: importâncias custom do primeiro calibrado
        for cal in cals:
            est = getattr(cal, "estimator", None) or getattr(cal, "base_estimator", None)
            if est is None:
                continue
            custom = getattr(est, "_sinidu_feature_importances_", None)
            if custom is not None:
                return np.asarray(custom, dtype=float)
        imps = []
        for cal in cals:
            est = getattr(cal, "estimator", None) or getattr(cal, "base_estimator", None)
            if est is not None and hasattr(est, "feature_importances_"):
                imps.append(np.asarray(est.feature_importances_, dtype=float))
        if imps:
            return np.mean(imps, axis=0)
    est = getattr(model, "estimator", None)
    if est is not None:
        custom = getattr(est, "_sinidu_feature_importances_", None)
        if custom is not None:
            return np.asarray(custom, dtype=float)
        if hasattr(est, "feature_importances_"):
            return np.asarray(est.feature_importances_, dtype=float)
    return None

def domain_contributions(
    model: Any,
    feature_columns: list[str],
    feature_row: dict[str, float] | None = None,
    *,
    top_n: int = 5,
) -> dict[str, Any]:
    """Importância agregada por domínio + top features individuais."""
    cols = list(feature_columns)
    importances = _unwrap_importances(model)
    if importances is None or len(importances) != len(cols):
        return {
            "disponivel": False,
            "method": "indisponivel",
            "domains": [],
            "top_features": [],
            "narrativa": "Modelo sem importâncias de feature (ex.: calibrador sem RF base).",
        }

    total = float(np.sum(importances)) or 1.0
    by_feat = {c: float(importances[i]) / total for i, c in enumerate(cols)}

    domains: list[dict[str, Any]] = []
    for dom_id, feats in FEATURE_DOMAINS.items():
        share = sum(by_feat.get(f, 0.0) for f in feats)
        # Contribuição contextual: importância × valor normalizado (quando há row)
        weighted = share
        if feature_row:
            vals = []
            for f in feats:
                if f not in by_feat or by_feat[f] <= 0:
                    continue
                v = float(feature_row.get(f, 0.0) or 0.0)
                # Escala grosseira por tipo
                if f.startswith("precip_") or "intensidade" in f:
                    norm = min(1.0, max(0.0, v / 100.0))
                elif f in ("hand_media_m",):
                    norm = min(1.0, max(0.0, 1.0 - v / 25.0))  # HAND baixo → mais risco
                elif f.endswith("_pct") or f == "curve_number":
                    norm = min(1.0, max(0.0, v / 100.0))
                else:
                    norm = min(1.0, max(0.0, abs(v)))
                vals.append(by_feat[f] * norm)
            if vals:
                weighted = float(sum(vals))
        domains.append({
            "id": dom_id,
            "label": DOMAIN_LABELS_PT[dom_id],
            "importance_share": round(share, 4),
            "contribution": round(weighted, 4),
        })

    # Normaliza contribution entre domínios para % legível
    w_sum = sum(d["contribution"] for d in domains) or 1.0
    for d in domains:
        d["contribution_pct"] = round(100.0 * d["contribution"] / w_sum, 1)
        d["importance_pct"] = round(100.0 * d["importance_share"], 1)
    domains.sort(key=lambda x: x["contribution_pct"], reverse=True)

    ranked = sorted(by_feat.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    top_features = [
        {"feature": name, "importance": round(score, 4), "domain": _domain_of(name)}
        for name, score in ranked
    ]

    lead = domains[0] if domains else None
    narrativa = (
        f"Maior contribuição neste cenário: {lead['label']} ({lead['contribution_pct']:.0f}%)."
        if lead
        else "Sem contribuição dominante."
    )

    return {
        "disponivel": True,
        "method": "rf_importance_by_domain",
        "domains": domains,
        "top_features": top_features,
        "narrativa": narrativa,
        "nota": (
            "Importância do Random Forest agregada por domínio — "
            "não é SHAP; indica quais famílias de variáveis o modelo mais usa."
        ),
    }


def _domain_of(feature: str) -> str | None:
    for dom_id, feats in FEATURE_DOMAINS.items():
        if feature in feats:
            return dom_id
    return None
