"""Ranking de municípios por critério comum (17h.2e).

Reaproveita `executive_snapshot` do analytics e CAPAG fiscal.
"""

from __future__ import annotations

from typing import Any, Literal

from sqlalchemy.orm import Session

from app.models import Municipio, MunicipioFiscal

Criterio = Literal["score_sinidu", "media_ivc", "media_iri", "media_adaptacao", "nota_capag", "populacao"]

CRITERIO_META: dict[str, dict[str, Any]] = {
    "score_sinidu": {"label": "Score Sinidu+Clima", "higher_is_worse": True, "format": "number"},
    "media_ivc": {"label": "IVC médio", "higher_is_worse": True, "format": "percent"},
    "media_iri": {"label": "IRI médio", "higher_is_worse": True, "format": "percent"},
    "media_adaptacao": {"label": "Capacidade de adaptação", "higher_is_worse": False, "format": "percent"},
    "nota_capag": {"label": "CAPAG", "higher_is_worse": False, "format": "text"},
    "populacao": {"label": "População", "higher_is_worse": False, "format": "number"},
}

CAPAG_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4}


def _capag_sort_key(nota: str | None, *, higher_is_worse: bool) -> float:
    if not nota:
        return 99.0
    rank = CAPAG_ORDER.get(str(nota).upper()[:1], 50)
    # A=0…D=3; higher_is_worse → D primeiro (−rank); senão A primeiro (+rank)
    return float(-rank if higher_is_worse else rank)


def rank_municipalities(
    db: Session,
    *,
    criterio: str = "score_sinidu",
    codigos: list[str] | None = None,
    uf: str | None = None,
    limit: int = 20,
    snapshot_fn=None,
) -> dict[str, Any]:
    """Ordena municípios pelo critério. `snapshot_fn` injetável p/ testes."""
    from app.api.analytics import executive_snapshot as default_snapshot

    snap_fn = snapshot_fn or default_snapshot
    crit = (criterio or "score_sinidu").strip().lower()
    if crit not in CRITERIO_META:
        raise ValueError(f"Critério inválido. Use: {', '.join(CRITERIO_META)}")

    meta = CRITERIO_META[crit]
    q = db.query(Municipio)
    if uf:
        q = q.filter(Municipio.uf == uf.upper()[:2])
    if codigos:
        codes = [str(c).zfill(7)[:7] for c in codigos if c]
        q = q.filter(Municipio.codigo_ibge.in_(codes))
    munis = q.order_by(Municipio.nome.asc()).limit(min(max(limit, 2), 60)).all()
    if len(munis) < 2 and not codigos and not uf:
        # fallback: top populados
        munis = (
            db.query(Municipio)
            .order_by(Municipio.populacao.desc())
            .limit(min(max(limit, 2), 30))
            .all()
        )

    rows: list[dict[str, Any]] = []
    for muni in munis:
        try:
            snap = dict(snap_fn(db, muni))
        except Exception:
            continue
        fiscal = (
            db.query(MunicipioFiscal)
            .filter(MunicipioFiscal.codigo_ibge == muni.codigo_ibge)
            .first()
        )
        snap["nota_capag"] = fiscal.nota_capag if fiscal else None
        valor = snap.get(crit)
        rows.append({
            "codigo_ibge": muni.codigo_ibge,
            "nome": muni.nome,
            "uf": muni.uf,
            "valor": valor,
            "score_sinidu": snap.get("score_sinidu"),
            "media_ivc": snap.get("media_ivc"),
            "media_iri": snap.get("media_iri"),
            "media_adaptacao": snap.get("media_adaptacao"),
            "nota_capag": snap.get("nota_capag"),
            "populacao": snap.get("populacao"),
        })

    higher_worse = bool(meta["higher_is_worse"])

    def sort_key(row: dict[str, Any]):
        v = row.get("valor")
        if crit == "nota_capag":
            return _capag_sort_key(v if isinstance(v, str) else None, higher_is_worse=higher_worse)
        if v is None:
            return 1e18 if higher_worse else -1e18
        try:
            fv = float(v)
        except (TypeError, ValueError):
            return 1e18 if higher_worse else -1e18
        return fv if higher_worse else -fv

    rows.sort(key=sort_key)
    for i, row in enumerate(rows, start=1):
        row["posicao"] = i

    return {
        "criterio": crit,
        "criterio_label": meta["label"],
        "higher_is_worse": higher_worse,
        "format": meta["format"],
        "total": len(rows),
        "uf": uf.upper()[:2] if uf else None,
        "items": rows,
        "nota": (
            "Ranking demonstrativo para consórcios/UF — mesmos critérios do painel Sinidu+Clima. "
            "CAPAG vem do Tesouro/SICONFI quando disponível."
        ),
    }
