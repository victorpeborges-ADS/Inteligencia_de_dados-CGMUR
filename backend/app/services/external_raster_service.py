"""Registry de tiles raster externos (mosaicjson / TiTiler) — Fase 16d.4.

Padrão GeoReDUS: raster-server ORI:ORO + mosaic.json em S3, sem replicar pipeline nacional.
Novas coberturas pesadas entram como entradas no registry — não como ingestão PostGIS.
"""

from __future__ import annotations

import json
import logging
import ssl
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

GEOREDUS_RASTER_BASE = "https://georedus-prod-raster-server.orioro.design"
GEOREDUS_PORTAL_URL = "https://www.redus.org.br/georedus"
TILE_MATRIX = "WebMercatorQuad"


@dataclass(frozen=True)
class ExternalRasterSource:
    layer_id: str
    label: str
    mosaic_url: str
    quality: str
    source: str
    description: str
    attribution: str
    default_rescale: tuple[float, float]
    rescale_bounds: tuple[float, float]
    min_zoom: int = 8
    max_zoom: int = 14
    colormap_name: str = "turbo"
    unit: str = ""
    periodo_label: str = ""
    status: str = "ativo"
    supports_point_query: bool = False
    provider: str = "georedus_mosaicjson"
    georedus_url: str = GEOREDUS_PORTAL_URL
    extra_tile_params: dict[str, str] = field(default_factory=dict)


LST_MOSAIC_URL = (
    "s3://georedus-prod-private-us-east-1/raster-server/cem/"
    "temperatura_superficie_2021_2025_v2/mosaic.json"
)

EXTERNAL_RASTER_SOURCES: dict[str, ExternalRasterSource] = {
    "lst_observada": ExternalRasterSource(
        layer_id="lst_observada",
        label="Temperatura de superfície (LST)",
        mosaic_url=LST_MOSAIC_URL,
        quality="Observado",
        source="GeoReDUS / Landsat 8-9",
        description=(
            "Média máxima de temperatura de superfície terrestre (LST) "
            "derivada de Landsat 8/9, agregada em mosaico nacional."
        ),
        attribution="GeoReDUS / CEM-USP / ReDUS",
        default_rescale=(20.0, 60.0),
        rescale_bounds=(0.0, 70.0),
        min_zoom=8,
        max_zoom=14,
        colormap_name="turbo",
        unit="°C",
        periodo_label="2021–2025",
        status="ativo",
        supports_point_query=True,
    ),
    # Coberturas pesadas futuras (MapBiomas raster, relevo DSM) entram aqui com status em_avaliacao.
}


def list_external_raster_ids() -> list[str]:
    return list(EXTERNAL_RASTER_SOURCES.keys())


def get_external_raster_source(layer_id: str) -> ExternalRasterSource | None:
    return EXTERNAL_RASTER_SOURCES.get(layer_id)


def _clamp_rescale(
    source: ExternalRasterSource,
    rescale_min: float | None,
    rescale_max: float | None,
) -> tuple[float, float]:
    lo_default, hi_default = source.default_rescale
    lo = lo_default if rescale_min is None else float(rescale_min)
    hi = hi_default if rescale_max is None else float(rescale_max)
    if lo >= hi:
        lo, hi = lo_default, hi_default
    bound_lo, bound_hi = source.rescale_bounds
    lo = max(bound_lo, min(lo, bound_hi - 1.0))
    hi = max(lo + 1.0, min(hi, bound_hi))
    return lo, hi


def build_mosaicjson_tile_url(
    source: ExternalRasterSource,
    *,
    rescale_min: float,
    rescale_max: float,
    colormap_name: str | None = None,
) -> str:
    def _fmt(value: float) -> str:
        return str(int(value)) if float(value).is_integer() else str(value)

    params: dict[str, str] = {
        "url": source.mosaic_url,
        "rescale": f"{_fmt(rescale_min)},{_fmt(rescale_max)}",
        "colormap_name": colormap_name or source.colormap_name,
    }
    params.update(source.extra_tile_params)
    query = urllib.parse.urlencode(params)
    return (
        f"{GEOREDUS_RASTER_BASE}/mosaicjson/tiles/{TILE_MATRIX}/"
        f"{{z}}/{{x}}/{{y}}.png?{query}"
    )


def build_mosaicjson_point_url(source: ExternalRasterSource, lon: float, lat: float) -> str:
    params = urllib.parse.urlencode({"url": source.mosaic_url})
    return f"{GEOREDUS_RASTER_BASE}/mosaicjson/point/{lon},{lat}?{params}"


def build_mosaicjson_info_url(source: ExternalRasterSource) -> str:
    params = urllib.parse.urlencode({"url": source.mosaic_url})
    return f"{GEOREDUS_RASTER_BASE}/mosaicjson/info?{params}"


def list_external_rasters(*, include_inactive: bool = False) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in EXTERNAL_RASTER_SOURCES.values():
        if source.status != "ativo" and not include_inactive:
            continue
        rows.append(
            {
                "layer_id": source.layer_id,
                "label": source.label,
                "quality": source.quality,
                "source": source.source,
                "description": source.description,
                "status": source.status,
                "provider": source.provider,
                "tile_matrix": TILE_MATRIX,
                "min_zoom": source.min_zoom,
                "max_zoom": source.max_zoom,
                "unit": source.unit,
                "periodo_label": source.periodo_label,
                "supports_point_query": source.supports_point_query,
                "georedus_url": source.georedus_url,
                "default_rescale": {
                    "min": source.default_rescale[0],
                    "max": source.default_rescale[1],
                },
                "rescale_bounds": {
                    "min": source.rescale_bounds[0],
                    "max": source.rescale_bounds[1],
                },
                "colormap": source.colormap_name,
            }
        )
    return rows


def get_external_raster_config(
    layer_id: str,
    *,
    rescale_min: float | None = None,
    rescale_max: float | None = None,
    ano: int | None = None,
) -> dict[str, Any]:
    source = get_external_raster_source(layer_id)
    if not source:
        return {"error": f"Camada raster externa desconhecida: {layer_id}"}
    if source.status != "ativo":
        return {"error": f"Camada {layer_id} ainda em avaliação — tiles não disponíveis."}

    lo, hi = _clamp_rescale(source, rescale_min, rescale_max)
    ano_label = f"{ano}" if ano else source.periodo_label
    source_label = f"{source.source} ({ano_label})" if ano_label else source.source

    return {
        "layer_id": source.layer_id,
        "label": source.label,
        "quality": source.quality,
        "source": source_label,
        "ano_referencia": ano,
        "periodo_mosaico": source.periodo_label,
        "description": source.description,
        "tile_url_template": build_mosaicjson_tile_url(source, rescale_min=lo, rescale_max=hi),
        "min_zoom": source.min_zoom,
        "max_zoom": source.max_zoom,
        "rescale_min": lo,
        "rescale_max": hi,
        "rescale_min_c": lo,
        "rescale_max_c": hi,
        "unit": source.unit,
        "colormap": source.colormap_name,
        "attribution": source.attribution,
        "georedus_url": source.georedus_url,
        "provider": source.provider,
        "mosaic_url": source.mosaic_url,
        "tile_server_base": GEOREDUS_RASTER_BASE,
        "supports_point_query": source.supports_point_query,
    }


def probe_external_raster_server(
    layer_id: str,
    *,
    timeout: float = 8.0,
) -> dict[str, Any]:
    """Verifica disponibilidade do mosaicjson no raster-server (sem baixar tiles)."""
    source = get_external_raster_source(layer_id)
    if not source:
        return {"layer_id": layer_id, "ok": False, "error": "Camada desconhecida"}
    url = build_mosaicjson_info_url(source)
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(url, timeout=timeout, context=ctx) as resp:
            payload = json.loads(resp.read().decode())
        bounds = payload.get("bounds")
        return {
            "layer_id": layer_id,
            "ok": True,
            "tile_server_base": GEOREDUS_RASTER_BASE,
            "bounds": bounds,
            "minzoom": payload.get("minzoom"),
            "maxzoom": payload.get("maxzoom"),
        }
    except Exception as exc:
        logger.debug("Raster probe failed layer=%s: %s", layer_id, exc)
        return {
            "layer_id": layer_id,
            "ok": False,
            "tile_server_base": GEOREDUS_RASTER_BASE,
            "error": str(exc)[:200],
        }
