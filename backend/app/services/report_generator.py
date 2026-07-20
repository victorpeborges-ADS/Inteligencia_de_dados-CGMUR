from __future__ import annotations

import base64
import io
import json
import logging
import subprocess
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from shapely.geometry import shape
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.analytics import executive_snapshot
from app.api.data_catalog import coverage_for_code
from app.config import settings
from app.models import (
    AlertaCemaden,
    Bairro,
    CoberturaVegetalMapBiomas,
    HistoricoDesastreS2ID,
    Municipio,
    MunicipioFiscal,
    MunicipioIbge,
    RelatorioMunicipal,
)
from app.services.analytical_engine import AnalyticalEngine
from app.services.federal_financing_catalog import suggest_programs
from app.services.maturity_engine import compute_maturity
from app.services.mitigation_planner import MitigationPlanner
from app.data_connectors.orchestrator import IntegrationOrchestrator
from app.data_connectors.capag_collector import collect_capag_municipality

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "reports" / "templates"


def _format_currency(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"R$ {value:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _format_number(value: Optional[float], decimals: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fetch_google_satellite_map(lat: float, lon: float, api_key: str) -> bytes | None:
    import httpx

    params = {
        "center": f"{lat},{lon}",
        "zoom": "12",
        "size": "900x520",
        "maptype": "satellite",
        "scale": "2",
        "key": api_key,
    }
    try:
        resp = httpx.get("https://maps.googleapis.com/maps/api/staticmap", params=params, timeout=30.0)
        resp.raise_for_status()
        if resp.headers.get("content-type", "").startswith("image/"):
            return resp.content
    except Exception as exc:
        logger.warning("Google Static Maps indisponível: %s", exc)
    return None


def _google_maps_urls(lat: float, lon: float, nome: str, uf: str) -> dict[str, str]:
    return {
        "satellite": f"https://www.google.com/maps/@{lat:.6f},{lon:.6f},13z/data=!3m1!1e3",
        "search": f"https://www.google.com/maps/search/?api=1&query={lat:.6f},{lon:.6f}",
        "label": f"{nome}/{uf}",
    }


def _fmt_capag_valor(valor: float | None) -> str:
    if valor is None:
        return "—"
    if -5 <= valor <= 5:
        return f"{valor * 100:.1f}%"
    return f"{valor:.4f}"


def _capag_indicador_interpretation(nota: str | None) -> str:
    mapping = {
        "A": "Situação favorável.",
        "B": "Situação adequada, com monitoramento.",
        "C": "Atenção — exige acompanhamento fiscal.",
        "D": "Situação crítica.",
        "E": "Situação muito crítica.",
    }
    if not nota:
        return "Nota não disponível."
    return mapping.get(nota.upper()[:1], "Consultar metodologia CAPAG/STN.")


def _capag_indicadores_enriched(indicadores: list[dict] | None) -> list[dict]:
    enriched = []
    for item in indicadores or []:
        nota = item.get("nota")
        enriched.append(
            {
                **item,
                "valor_fmt": _fmt_capag_valor(item.get("valor")),
                "interpretacao": _capag_indicador_interpretation(nota),
            }
        )
    return enriched


def _load_stored_capag_indicators(fiscal: MunicipioFiscal | None) -> list[dict] | None:
    if not fiscal or not fiscal.raw_payload:
        return None
    try:
        payload = json.loads(fiscal.raw_payload)
        indicadores = payload.get("indicadores")
        return indicadores if indicadores else None
    except (json.JSONDecodeError, TypeError):
        return None


def _ensure_capag_fresh(db: Session, muni: Municipio) -> tuple[MunicipioFiscal | None, dict]:
    fiscal = db.query(MunicipioFiscal).filter(MunicipioFiscal.codigo_ibge == muni.codigo_ibge).first()
    stored_indicators = _load_stored_capag_indicators(fiscal)
    meta: dict[str, Any] = {
        "status": "ok" if fiscal and fiscal.nota_capag else "ausente",
        "fonte": "banco_local",
        "indicadores": stored_indicators or [],
    }

    needs_fetch = not fiscal or not fiscal.nota_capag or not stored_indicators
    if fiscal and fiscal.nota_capag and not needs_fetch:
        meta["nota"] = fiscal.nota_capag
        meta["fonte"] = fiscal.fonte or "CAPAG / Tesouro Transparente"
        try:
            payload = json.loads(fiscal.raw_payload or "{}")
            meta["nota_capag_raw"] = payload.get("nota_capag_raw")
            meta["origem_nota"] = payload.get("origem_nota")
        except (json.JSONDecodeError, TypeError):
            pass
        meta["indicadores"] = _capag_indicadores_enriched(stored_indicators)
        return fiscal, meta

    try:
        capag = collect_capag_municipality(muni.codigo_ibge)
        IntegrationOrchestrator(db)._upsert_fiscal_capag(muni.codigo_ibge, capag)
        db.commit()
        fiscal = db.query(MunicipioFiscal).filter(MunicipioFiscal.codigo_ibge == muni.codigo_ibge).first()
        indicadores = capag.get("indicadores") or []
        if capag.get("nota_capag"):
            meta = {
                "status": "consultado_agora",
                "nota": capag["nota_capag"],
                "nota_capag_raw": capag.get("nota_capag_raw"),
                "origem_nota": capag.get("origem_nota"),
                "fonte": capag.get("fonte"),
                "indicadores": _capag_indicadores_enriched(indicadores),
                "mensagem": "CAPAG obtida do CKAN oficial do Tesouro Transparente na geração do relatório.",
            }
        else:
            meta = {
                "status": "nao_encontrado",
                "indicadores": _capag_indicadores_enriched(indicadores),
                "mensagem": (
                    "Município não localizado na planilha CAPAG mais recente ou nota não publicada. "
                    "Consulte https://www.tesourotransparente.gov.br/ckan/dataset/capag-municipios"
                ),
            }
    except Exception as exc:
        logger.warning("CAPAG live fetch falhou para %s: %s", muni.codigo_ibge, exc)
        meta = {
            "status": "erro",
            "indicadores": _capag_indicadores_enriched(stored_indicators),
            "mensagem": f"Não foi possível consultar CAPAG online: {exc}",
        }
    return fiscal, meta


def _score_methodology() -> dict[str, Any]:
    return {
        "titulo": "Score Sinidu+Clima — Prioridade Territorial",
        "formula_municipal": "Score = 45% × IVC médio + 35% × IRI médio + 20% × (1 − capacidade de adaptação média)",
        "escala": "0 a 100 — quanto maior, maior a prioridade de intervenção territorial.",
        "ivc": {
            "nome": "Índice de Vulnerabilidade Climática (IVC)",
            "formula": "IVC = média(exposição, sensibilidade) × (1 − 0,3 × capacidade de adaptação)",
            "exposicao": "40% histórico S2ID no bairro + 60% alertas CEMADEN ativos (ponderados por nível).",
            "sensibilidade": "50% densidade demográfica + 50% inverso da renda média dos setores censitários.",
            "adaptacao": "60% cobertura vegetal + 40% infraestrutura de saúde (hospitais/UBS).",
            "fontes": "IBGE setores censitários, S2ID, CEMADEN, MapBiomas, infraestrutura urbana local.",
        },
        "iri": {
            "nome": "Índice de Risco de Inundação (IRI)",
            "formula": "IRI = 40% histórico S2ID (inundação) + 40% impermeabilização + 20% proximidade de corpos d'água.",
            "fontes": "S2ID, MapBiomas (área urbana), hidrografia/OSM local.",
        },
        "interpretacao": [
            "66–100: prioridade crítica — intervenção imediata e monitoramento reforçado.",
            "33–65: prioridade elevada — ações de curto prazo e preparação operacional.",
            "0–32: prioridade moderada — manutenção preventiva e acompanhamento.",
        ],
        "limitacoes": (
            "Índices derivados dos dados disponíveis no Sinidu+Clima no momento da geração. "
            "Não substituem estudos hidrológicos, geológicos ou planos municipais oficiais."
        ),
    }


def _capag_interpretation(nota: str | None) -> str:
    mapping = {
        "A": "Capacidade de pagamento robusta — elegível a garantia da União sem restrições adicionais.",
        "B": "Capacidade adequada — elegível a operações de crédito com garantia da União, com monitoramento.",
        "C": "Atenção — restrições para garantia da União; exige plano de equacionamento fiscal.",
        "D": "Capacidade limitada — alto risco fiscal; priorizar fontes não reembolsáveis e apoio técnico.",
    }
    if not nota:
        return "Nota não disponível na base integrada. Recomenda-se consultar o Tesouro Transparente."
    return mapping.get(nota.upper()[:1], "Classificação não reconhecida — verificar fonte oficial.")


def _matplotlib_map_fallback(muni_geojson: dict, bairros: List[dict]) -> bytes:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 6), facecolor="#0f172a")
    ax.set_facecolor("#0f172a")

    def plot_geom(geom_dict, **kwargs):
        geom = shape(geom_dict)
        if geom.geom_type == "Polygon":
            xs, ys = geom.exterior.xy
            ax.fill(xs, ys, **kwargs)
            ax.plot(xs, ys, color=kwargs.get("edgecolor", "#818cf8"), linewidth=1)
        elif geom.geom_type == "MultiPolygon":
            for poly in geom.geoms:
                xs, ys = poly.exterior.xy
                ax.fill(xs, ys, **kwargs)
                ax.plot(xs, ys, color=kwargs.get("edgecolor", "#818cf8"), linewidth=0.8)

    plot_geom(muni_geojson, facecolor="#312e81", edgecolor="#818cf8", alpha=0.25)
    for item in bairros[:20]:
        if item.get("geom"):
            plot_geom(item["geom"], facecolor=item.get("color", "#6366f1"), edgecolor="#c7d2fe", alpha=0.45)

    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Malha territorial municipal", color="#e2e8f0", fontsize=11, pad=8)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return buf.getvalue()


def _folium_to_png_bytes(m: Any) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        html_path = Path(tmp) / "map.html"
        png_path = Path(tmp) / "map.png"
        m.save(str(html_path))
        try:
            subprocess.run(
                ["wkhtmltoimage", "--quality", "90", "--width", "900", str(html_path), str(png_path)],
                check=True,
                capture_output=True,
                timeout=45,
            )
            return png_path.read_bytes()
        except Exception as exc:
            logger.warning("wkhtmltoimage indisponível (%s); usando fallback matplotlib.", exc)
            raise


def render_municipality_map(db: Session, muni: Municipio, ranking: List[dict]) -> str:
    import folium

    geojson = json.loads(db.scalar(muni.geom.ST_AsGeoJSON()))
    sh = shape(geojson)
    lat, lon = sh.centroid.y, sh.centroid.x

    score_by_name = {row["bairro"]: row["score_sinidu"] for row in ranking}

    bairros_rows = db.query(Bairro.id, Bairro.nome, func.ST_AsGeoJSON(Bairro.geom).label("geom")).filter(
        Bairro.municipio_id == muni.id
    ).all()

    bairro_payloads = []
    for row in bairros_rows:
        score = score_by_name.get(row.nome, 0)
        if score >= 66:
            color = "#ef4444"
        elif score >= 33:
            color = "#f97316"
        else:
            color = "#6366f1"
        bairro_payloads.append({"nome": row.nome, "geom": json.loads(row.geom), "color": color, "score": score})

    m = folium.Map(location=[lat, lon], zoom_start=11, tiles=None, width=900, height=520)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery",
        name="Satélite",
        overlay=False,
        control=False,
    ).add_to(m)
    folium.TileLayer("CartoDB dark_matter", name="Base escura", overlay=False, control=False).add_to(m)
    folium.GeoJson(
        geojson,
        name="Limite municipal",
        style_function=lambda _f: {
            "fillColor": "#000000",
            "color": "#fbbf24",
            "weight": 3,
            "fillOpacity": 0.05,
        },
    ).add_to(m)

    for item in bairro_payloads:
        folium.GeoJson(
            item["geom"],
            name=item["nome"],
            tooltip=f"{item['nome']} — Score {item['score']}",
            style_function=lambda _f, c=item["color"]: {
                "fillColor": c,
                "color": "#ffffff",
                "weight": 1.2,
                "fillOpacity": 0.62,
            },
        ).add_to(m)

    try:
        png_bytes = _folium_to_png_bytes(m)
    except Exception:
        png_bytes = _matplotlib_map_fallback(geojson, bairro_payloads)

    return base64.b64encode(png_bytes).decode("ascii")


def render_report_maps(db: Session, muni: Municipio, ranking: List[dict]) -> dict[str, Any]:
    geojson = json.loads(db.scalar(muni.geom.ST_AsGeoJSON()))
    centroid = shape(geojson).centroid
    lat, lon = centroid.y, centroid.x

    thematic_b64 = render_municipality_map(db, muni, ranking)
    satellite_b64 = None
    satellite_fonte = "Visão satélite Esri + camadas temáticas Sinidu+Clima."

    if settings.GOOGLE_MAPS_API_KEY:
        google_png = _fetch_google_satellite_map(lat, lon, settings.GOOGLE_MAPS_API_KEY)
        if google_png:
            satellite_b64 = base64.b64encode(google_png).decode("ascii")
            satellite_fonte = "Google Maps — Static Maps API (maptype=satellite). Requer chave GOOGLE_MAPS_API_KEY."

    google_maps = _google_maps_urls(lat, lon, muni.nome, muni.uf)

    return {
        "thematic_b64": thematic_b64,
        "satellite_b64": satellite_b64,
        "thematic_fonte": "Bairros coloridos por Score Sinidu+Clima: vermelho ≥66 · laranja ≥33 · azul <33.",
        "satellite_fonte": satellite_fonte,
        "google_maps": google_maps,
    }


def fetch_precipitation_series(lat: float, lon: float) -> List[dict]:
    import httpx

    end = date.today()
    start = end - timedelta(days=365 * 10)
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": "precipitation_sum",
        "timezone": "America/Sao_Paulo",
    }
    try:
        response = httpx.get(url, params=params, timeout=45.0)
        response.raise_for_status()
        payload = response.json()
        dates = payload.get("daily", {}).get("time") or []
        values = payload.get("daily", {}).get("precipitation_sum") or []
        monthly: Dict[str, List[float]] = {}
        for day, value in zip(dates, values):
            if value is None:
                continue
            year, month, _ = day.split("-")
            key = f"{year}-{month}"
            monthly.setdefault(key, []).append(float(value))
        series = []
        for key in sorted(monthly.keys())[-36:]:
            year, month = key.split("-")
            avg_mm = sum(monthly[key]) / max(len(monthly[key]), 1)
            series.append({"periodo": f"{month}/{year}", "precipitacao_mm": round(avg_mm, 1)})
        return series
    except Exception as exc:
        logger.warning("OpenMeteo indisponível: %s", exc)
        return []


def build_bairro_ranking(db: Session, muni: Municipio) -> tuple[List[dict], dict]:
    vulnerabilities = AnalyticalEngine.calculate_climate_vulnerability(db, muni.id)
    floods = AnalyticalEngine.calculate_flood_risk(db, muni.id)
    flood_by_id = {item["id"]: item for item in floods}

    ranking = []
    for item in vulnerabilities:
        flood = flood_by_id.get(item["id"], {})
        ivc = float(item.get("indice_vulnerabilidade", 0.0))
        iri = float(flood.get("indice_risco_inundacao", 0.0))
        adaptation_gap = 1.0 - float(item.get("capacidade_adaptacao", 0.0))
        score = round(((ivc * 0.45) + (iri * 0.35) + (adaptation_gap * 0.20)) * 100)
        ranking.append({
            "bairro": item["bairro_nome"],
            "score_sinidu": score,
            "ivc": round(ivc, 3),
            "iri": round(iri, 3),
            "deficit_adaptacao": round(adaptation_gap, 3),
            "componentes": {
                "vulnerabilidade_pct": round(ivc * 45, 1),
                "inundacao_pct": round(iri * 35, 1),
                "deficit_adaptacao_pct": round(adaptation_gap * 20, 1),
            },
        })
    ranking.sort(key=lambda row: row["score_sinidu"], reverse=True)

    snapshot = executive_snapshot(db, muni)
    return ranking, snapshot


class MunicipalReportGenerator:
    def __init__(self, db: Session):
        self.db = db
        self.reports_dir = Path(settings.REPORTS_DIR)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, municipio_id: int) -> RelatorioMunicipal:
        muni = self.db.query(Municipio).filter(Municipio.id == municipio_id).first()
        if not muni:
            raise ValueError(f"Município id={municipio_id} não encontrado.")

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{muni.codigo_ibge}_{stamp}.pdf"
        filepath = self.reports_dir / filename

        record = RelatorioMunicipal(
            municipio_id=muni.id,
            codigo_ibge=muni.codigo_ibge,
            nome_arquivo=filename,
            caminho_arquivo=str(filepath),
            status="gerando",
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)

        try:
            context = self._build_context(muni)
            html = self._render_html(context)
            from weasyprint import HTML

            HTML(string=html, base_url=str(TEMPLATE_DIR)).write_pdf(str(filepath))
            record.status = "concluido"
            record.tamanho_bytes = filepath.stat().st_size if filepath.exists() else 0
            if filepath.exists():
                from app.services.sei_export import sha256_file

                record.sha256_hash = sha256_file(filepath)
            record.erro_mensagem = None
        except Exception as exc:
            logger.exception("Falha ao gerar relatório para %s", muni.codigo_ibge)
            record.status = "falha"
            record.erro_mensagem = str(exc)
            if filepath.exists():
                filepath.unlink(missing_ok=True)
            raise
        finally:
            self.db.commit()
            self.db.refresh(record)

        return record

    def _build_context(self, muni: Municipio) -> Dict[str, Any]:
        ranking, snapshot = build_bairro_ranking(self.db, muni)
        ibge = self.db.query(MunicipioIbge).filter(MunicipioIbge.codigo_ibge == muni.codigo_ibge).first()
        fiscal, capag_meta = _ensure_capag_fresh(self.db, muni)
        maturidade, bases, gaps = coverage_for_code(muni.codigo_ibge, self.db)

        try:
            maturity = compute_maturity(self.db, muni.codigo_ibge)
        except Exception:
            maturity = None

        ten_years_ago = date.today() - timedelta(days=365 * 10)
        desastres = (
            self.db.query(HistoricoDesastreS2ID)
            .filter(
                HistoricoDesastreS2ID.municipio_id == muni.id,
                HistoricoDesastreS2ID.data_ocorrencia >= ten_years_ago,
            )
            .order_by(HistoricoDesastreS2ID.data_ocorrencia.desc())
            .limit(20)
            .all()
        )

        alertas = (
            self.db.query(AlertaCemaden)
            .filter(AlertaCemaden.municipio_id == muni.id)
            .order_by(AlertaCemaden.data_alerta.desc())
            .all()
        )

        total_area_deg = self.db.scalar(func.ST_Area(muni.geom))
        urban_area_deg = self.db.query(func.sum(func.ST_Area(CoberturaVegetalMapBiomas.geom))).filter(
            CoberturaVegetalMapBiomas.municipio_id == muni.id,
            CoberturaVegetalMapBiomas.classe_uso == "Área Urbana",
        ).scalar()
        impermeabilizacao_pct = round((float(urban_area_deg) / float(total_area_deg)) * 100, 2) if urban_area_deg and total_area_deg else None

        geojson = json.loads(self.db.scalar(muni.geom.ST_AsGeoJSON()))
        centroid = shape(geojson).centroid
        precip_series = fetch_precipitation_series(centroid.y, centroid.x)

        plan = MitigationPlanner.build_rainfall_plan(self.db, muni, 120.0)
        raw_actions = plan.get("acoes_tecnicas_padrao", [])
        actions = [
            a.model_dump() if hasattr(a, "model_dump") else (a.dict() if hasattr(a, "dict") else a)
            for a in raw_actions
        ]
        capacidade = plan.get("capacidade_investimento") or {}
        nota_capag = fiscal.nota_capag if fiscal else capag_meta.get("nota")
        programas = suggest_programs(
            severidade=plan.get("severidade", "Média"),
            nota_capag=nota_capag,
            media_ivc=float(capacidade.get("media_ivc") or snapshot.get("media_ivc") or 0),
        )

        def _horizonte(action: dict) -> str:
            return (action.get("horizonte") or "").lower()

        maps = render_report_maps(self.db, muni, ranking)
        methodology = _score_methodology()
        generated_at = datetime.now()

        experiencias = plan.get("experiencias_municipais") or []
        analogos = plan.get("municipios_analogos") or []
        restricoes = plan.get("restricoes_plano_diretor") or []

        return {
            "generated_at": generated_at.strftime("%d/%m/%Y %H:%M"),
            "footer_date": generated_at.strftime("%d/%m/%Y"),
            "municipio": {
                "nome": muni.nome,
                "uf": muni.uf,
                "codigo_ibge": muni.codigo_ibge,
                "populacao": ibge.populacao if ibge and ibge.populacao else muni.populacao,
                "populacao_fonte": (ibge.fonte if ibge else "Estimativa demonstrativa interna"),
                "area_km2": float(ibge.area_km2 if ibge and ibge.area_km2 else muni.area_km2),
                "densidade": snapshot.get("densidade_demografica"),
                "idh": float(ibge.idh) if ibge and ibge.idh else None,
                "idh_fonte": f"IBGE {ibge.idh_ano}" if ibge and ibge.idh_ano else "IBGE",
                "pib_per_capita": float(ibge.pib_per_capita) if ibge and ibge.pib_per_capita else None,
            },
            "map_image_b64": maps["thematic_b64"],
            "maps": maps,
            "fiscal": {
                "nota_capag": nota_capag,
                "nota_capag_raw": capag_meta.get("nota_capag_raw"),
                "capag_interpretacao": _capag_interpretation(nota_capag),
                "capag_meta": capag_meta,
                "capag_indicadores": capag_meta.get("indicadores") or [],
                "capag_origem_nota": capag_meta.get("origem_nota"),
                "receita_corrente_liquida": float(fiscal.receita_corrente_liquida) if fiscal and fiscal.receita_corrente_liquida else None,
                "despesa_pessoal_pct_rcl": float(fiscal.despesa_pessoal_pct_rcl) if fiscal and fiscal.despesa_pessoal_pct_rcl is not None else None,
                "divida_consolidada": float(fiscal.divida_consolidada) if fiscal and fiscal.divida_consolidada else None,
                "exec_saude": float(fiscal.exec_saude) if fiscal and fiscal.exec_saude else None,
                "exec_defesa_civil": float(fiscal.exec_defesa_civil) if fiscal and fiscal.exec_defesa_civil else None,
                "exec_saneamento": float(fiscal.exec_saneamento) if fiscal and fiscal.exec_saneamento else None,
                "exercicio": fiscal.exercicio if fiscal else None,
                "fonte": fiscal.fonte if fiscal else "SICONFI / Tesouro Transparente",
            },
            "score": {
                "valor": snapshot.get("score_sinidu"),
                "media_ivc": snapshot.get("media_ivc"),
                "media_iri": snapshot.get("media_iri"),
                "media_adaptacao": snapshot.get("media_adaptacao"),
                "formula": methodology["formula_municipal"],
                "metodologia": methodology,
            },
            "maturity": maturity,
            "ranking": ranking[:15],
            "desastres": [
                {
                    "tipo": row.tipo_desastre,
                    "data": row.data_ocorrencia.strftime("%d/%m/%Y"),
                    "populacao_afetada": row.populacao_afetada,
                    "danos_materiais": float(row.danos_materiais or 0),
                    "danos_fmt": _format_currency(float(row.danos_materiais or 0)),
                }
                for row in desastres
            ],
            "ambiental": {
                "cobertura_vegetal_percent": snapshot.get("cobertura_vegetal_percent"),
                "impermeabilizacao_pct": impermeabilizacao_pct,
                "alertas": [
                    {
                        "nivel": row.nivel_alerta,
                        "data": row.data_alerta.strftime("%d/%m/%Y %H:%M"),
                        "descricao": row.descricao or "—",
                    }
                    for row in alertas
                ],
                "precipitacao_serie": precip_series[-12:],
                "precipitacao_fonte": "Open-Meteo Archive API",
            },
            "capacidade": {
                "maturidade_percentual": maturity["score"] if maturity else maturidade,
                "classificacao": maturity["classificacao"] if maturity else ("Alta" if maturidade >= 75 else ("Média" if maturidade >= 50 else "Baixa")),
                "bases": bases,
                "lacunas": gaps,
                "capacidade_investimento": capacidade,
            },
            "plano": {
                "severidade": plan.get("severidade"),
                "acoes_imediatas": [a for a in actions if "imediata" in _horizonte(a)],
                "acoes_curto_prazo": [a for a in actions if "curto prazo" in _horizonte(a)],
                "acoes_estruturais": [a for a in actions if any(term in _horizonte(a) for term in ("estrutural", "planejamento", "adaptação"))],
                "fontes_financiamento": capacidade.get("fontes_financiamento_sugeridas") or [],
                "programas_federais": programas,
                "experiencias_municipais": [
                    e.model_dump() if hasattr(e, "model_dump") else (e.dict() if hasattr(e, "dict") else e)
                    for e in experiencias[:5]
                ],
                "municipios_analogos": [
                    a.model_dump() if hasattr(a, "model_dump") else (a.dict() if hasattr(a, "dict") else a)
                    for a in analogos[:5]
                ],
                "restricoes_plano_diretor": [
                    r.model_dump() if hasattr(r, "model_dump") else (r.dict() if hasattr(r, "dict") else r)
                    for r in restricoes[:4]
                ],
                "lacunas": plan.get("lacunas") or [],
            },
            "format_currency": _format_currency,
            "format_number": _format_number,
        }

    def _render_html(self, context: Dict[str, Any]) -> str:
        env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=select_autoescape(["html", "xml"]),
        )
        template = env.get_template("municipal_report.html")
        return template.render(**context)
