"""Gráficos matplotlib e mapas estáticos para relatório PDF enriquecido — Step 8."""

from __future__ import annotations

import base64
import io
import logging
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import HistoricoDesastreS2ID, Municipio, MunicipioFiscal
from app.services.maturity_engine import compute_maturity

logger = logging.getLogger(__name__)

MESES_PT = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

_NATIONAL_AVG_CACHE: dict[str, float] | None = None


def _fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _get_muni(db: Session, codigo: str) -> Municipio | None:
    return db.query(Municipio).filter(Municipio.codigo_ibge == codigo).first()


def _capag_score(nota: str | None) -> float:
    return {"A": 95, "B": 75, "C": 50, "D": 25, "E": 10}.get((nota or "").upper()[:1], 40)


_NATIONAL_BENCHMARK: dict[str, float] = {
    "IVC": 41.5,
    "IRI": 37.2,
    "Fiscal": 68.0,
    "Dados": 52.0,
    "Adaptação": 46.8,
}


def _national_averages(db: Session) -> dict[str, float]:
    global _NATIONAL_AVG_CACHE
    if _NATIONAL_AVG_CACHE is not None:
        return _NATIONAL_AVG_CACHE
    _NATIONAL_AVG_CACHE = dict(_NATIONAL_BENCHMARK)
    return _NATIONAL_AVG_CACHE


def gerar_grafico_desastres(municipio_codigo: str) -> str:
    """PNG base64 — barras horizontais eventos S2ID por ano (10 anos)."""
    db = SessionLocal()
    try:
        muni = _get_muni(db, municipio_codigo)
        if not muni:
            return _empty_chart("Histórico S2ID — sem dados")

        cutoff = date.today() - timedelta(days=365 * 10)
        rows = (
            db.query(HistoricoDesastreS2ID)
            .filter(
                HistoricoDesastreS2ID.municipio_id == muni.id,
                HistoricoDesastreS2ID.data_ocorrencia >= cutoff,
            )
            .all()
        )
        by_year: dict[int, dict[str, float]] = defaultdict(lambda: {"count": 0, "danos": 0.0})
        for row in rows:
            yr = row.data_ocorrencia.year
            by_year[yr]["count"] += 1
            by_year[yr]["danos"] += float(row.danos_materiais or 0)

        years = sorted(by_year.keys())[-10:]
        if not years:
            return _empty_chart("Histórico S2ID — sem eventos no período")

        counts = [by_year[y]["count"] for y in years]
        colors = ["#f97316" if by_year[y]["danos"] > 1_000_000 else "#fbbf24" for y in years]

        fig, ax = plt.subplots(figsize=(8, 4.5), facecolor="#ffffff")
        ax.barh([str(y) for y in years], counts, color=colors, edgecolor="#334155", height=0.65)
        ax.set_xlabel("Nº de eventos", fontsize=9)
        ax.set_title("Histórico S2ID — eventos por ano", fontsize=11, fontweight="bold", color="#0f172a")
        ax.grid(axis="x", alpha=0.25)
        ax.tick_params(labelsize=8)
        fig.tight_layout()
        return _fig_to_b64(fig)
    finally:
        db.close()


def gerar_grafico_precipitacao(municipio_codigo: str) -> str:
    """PNG base64 — precipitação mensal média (12 meses)."""
    db = SessionLocal()
    try:
        muni = _get_muni(db, municipio_codigo)
        if not muni:
            return _empty_chart("Precipitação — sem dados")

        from shapely.geometry import shape
        import json
        import httpx

        geojson = json.loads(db.scalar(muni.geom.ST_AsGeoJSON()))
        centroid = shape(geojson).centroid
        end = date.today()
        start = end - timedelta(days=365 * 3)
        url = "https://archive-api.open-meteo.com/v1/archive"
        params = {
            "latitude": centroid.y,
            "longitude": centroid.x,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "daily": "precipitation_sum",
            "timezone": "America/Sao_Paulo",
        }
        series: list[dict] = []
        try:
            response = httpx.get(url, params=params, timeout=25.0)
            response.raise_for_status()
            payload = response.json()
            dates = payload.get("daily", {}).get("time") or []
            values = payload.get("daily", {}).get("precipitation_sum") or []
            monthly: dict[int, list[float]] = {i: [] for i in range(1, 13)}
            for day, value in zip(dates, values):
                if value is None:
                    continue
                _y, mm, _d = day.split("-")
                monthly[int(mm)].append(float(value))
            for mm in range(1, 13):
                if monthly[mm]:
                    series.append({"periodo": f"{mm:02d}", "precipitacao_mm": sum(monthly[mm]) / len(monthly[mm])})
        except Exception as exc:
            logger.warning("Open-Meteo precipitação (chart): %s", exc)
            series = []
        monthly: dict[int, list[float]] = {i: [] for i in range(1, 13)}
        for item in series:
            try:
                mm = int(item["periodo"])
                monthly[mm].append(float(item["precipitacao_mm"]))
            except (ValueError, KeyError):
                continue

        values = [sum(monthly[i]) / len(monthly[i]) if monthly[i] else 0 for i in range(1, 13)]
        if not any(values):
            return _empty_chart("Precipitação — Open-Meteo indisponível")

        media = sum(values) / 12
        colors = ["#ef4444" if v > media else "#3b82f6" for v in values]

        fig, ax = plt.subplots(figsize=(8, 4.5), facecolor="#ffffff")
        ax.plot(MESES_PT, values, color="#64748b", linewidth=1.2, marker="o", markersize=4, zorder=2)
        ax.bar(MESES_PT, values, color=colors, alpha=0.75, edgecolor="#334155", linewidth=0.5, zorder=1)
        ax.axhline(media, color="#94a3b8", linestyle="--", linewidth=1, label=f"Média {media:.0f} mm")
        ax.set_ylabel("mm/mês", fontsize=9)
        ax.set_title("Precipitação Mensal Média", fontsize=11, fontweight="bold", color="#0f172a")
        ax.legend(fontsize=7, loc="upper right")
        ax.tick_params(labelsize=8)
        ax.grid(axis="y", alpha=0.25)
        fig.tight_layout()
        return _fig_to_b64(fig)
    finally:
        db.close()


def gerar_grafico_score_radar(municipio_codigo: str) -> str:
    """PNG base64 — radar 5 eixos vs média nacional (400×400)."""
    from app.services.report_generator import build_bairro_ranking

    db = SessionLocal()
    try:
        muni = _get_muni(db, municipio_codigo)
        if not muni:
            return _empty_chart("Score radar — sem dados")

        _, snap = build_bairro_ranking(db, muni)
        fiscal = db.query(MunicipioFiscal).filter(MunicipioFiscal.codigo_ibge == municipio_codigo).first()
        try:
            mat = compute_maturity(db, municipio_codigo)
            dados = float(mat.get("score") or 0)
        except Exception:
            dados = 50.0

        local = {
            "IVC": round(float(snap.get("media_ivc") or 0) * 100, 1),
            "IRI": round(float(snap.get("media_iri") or 0) * 100, 1),
            "Fiscal": _capag_score(fiscal.nota_capag if fiscal else None),
            "Dados": round(dados, 1),
            "Adaptação": round(float(snap.get("media_adaptacao") or 0) * 100, 1),
        }
        national = _national_averages(db)
        labels = list(local.keys())
        angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
        angles += angles[:1]

        local_vals = [local[k] for k in labels] + [local[labels[0]]]
        nat_vals = [national[k] for k in labels] + [national[labels[0]]]

        fig, ax = plt.subplots(figsize=(4, 4), subplot_kw={"polar": True}, facecolor="#ffffff")
        ax.plot(angles, local_vals, "o-", linewidth=2, color="#059669", label=muni.nome)
        ax.fill(angles, local_vals, alpha=0.2, color="#059669")
        ax.plot(angles, nat_vals, "o--", linewidth=1.5, color="#6366f1", label="Média catálogo piloto")
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(labels, fontsize=8)
        ax.set_ylim(0, 100)
        ax.set_title("Perfil territorial vs rede", fontsize=10, fontweight="bold", pad=16)
        ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.1), fontsize=7)
        fig.tight_layout()
        return _fig_to_b64(fig)
    finally:
        db.close()


def gerar_mapa_estatico(municipio_codigo: str, layer: str = "vulnerabilidade") -> str:
    """PNG base64 1200×700 — mapa dark com bairros coloridos."""
    from app.services.map_screenshot_service import map_screenshot_base64

    db = SessionLocal()
    try:
        muni = _get_muni(db, municipio_codigo)
        if not muni:
            return _empty_chart("Mapa — município não encontrado", dark=True)
        return map_screenshot_base64(db, muni, layer=layer)
    finally:
        db.close()


def _empty_chart(title: str, *, dark: bool = False) -> str:
    bg = "#0f172a" if dark else "#ffffff"
    fg = "#e2e8f0" if dark else "#64748b"
    fig, ax = plt.subplots(figsize=(8, 4), facecolor=bg)
    ax.axis("off")
    ax.text(0.5, 0.5, title, ha="center", va="center", fontsize=11, color=fg, transform=ax.transAxes)
    return _fig_to_b64(fig)


def gerar_todos_graficos(
    municipio_codigo: str,
    *,
    on_step: Callable[[str, int], None] | None = None,
) -> dict[str, str]:
    steps = [
        ("desastres", gerar_grafico_desastres),
        ("precipitacao", gerar_grafico_precipitacao),
        ("radar", gerar_grafico_score_radar),
        ("mapa", lambda c: gerar_mapa_estatico(c, "vulnerabilidade")),
    ]
    out: dict[str, str] = {}
    for idx, (key, fn) in enumerate(steps, start=1):
        if on_step:
            on_step(key, idx)
        out[key] = fn(municipio_codigo)
    return out
