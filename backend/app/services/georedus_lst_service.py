"""Configuração da camada LST observada (GeoReDUS / TiTiler) — delega ao registry 16d.4."""

from __future__ import annotations

import json
import logging
import ssl
import urllib.request

from app.services.external_raster_service import (
    EXTERNAL_RASTER_SOURCES,
    build_mosaicjson_point_url,
    get_external_raster_config,
)

logger = logging.getLogger(__name__)

LST_DEFAULT_MIN_C = EXTERNAL_RASTER_SOURCES["lst_observada"].default_rescale[0]
LST_DEFAULT_MAX_C = EXTERNAL_RASTER_SOURCES["lst_observada"].default_rescale[1]
LST_MIN_ZOOM = EXTERNAL_RASTER_SOURCES["lst_observada"].min_zoom
LST_MAX_ZOOM = EXTERNAL_RASTER_SOURCES["lst_observada"].max_zoom
LST_PERIODO_LABEL = EXTERNAL_RASTER_SOURCES["lst_observada"].periodo_label
LST_FONTE_LABEL = EXTERNAL_RASTER_SOURCES["lst_observada"].source


def build_lst_tile_url(
    rescale_min: float = LST_DEFAULT_MIN_C,
    rescale_max: float = LST_DEFAULT_MAX_C,
    colormap_name: str = "turbo",
) -> str:
    cfg = get_external_raster_config(
        "lst_observada",
        rescale_min=rescale_min,
        rescale_max=rescale_max,
    )
    if colormap_name != "turbo":
        from app.services.external_raster_service import build_mosaicjson_tile_url

        source = EXTERNAL_RASTER_SOURCES["lst_observada"]
        return build_mosaicjson_tile_url(
            source,
            rescale_min=cfg["rescale_min"],
            rescale_max=cfg["rescale_max"],
            colormap_name=colormap_name,
        )
    return cfg["tile_url_template"]


def get_lst_observada_config(
    rescale_min: float | None = None,
    rescale_max: float | None = None,
    ano: int | None = None,
) -> dict:
    return get_external_raster_config(
        "lst_observada",
        rescale_min=rescale_min,
        rescale_max=rescale_max,
        ano=ano,
    )


def _parse_lst_point_payload(data: dict) -> float | None:
    for row in data.get("values") or []:
        if not row or len(row) < 2:
            continue
        vals = row[1]
        if isinstance(vals, list) and vals and vals[0] is not None:
            return round(float(vals[0]), 1)
    return None


def fetch_lst_point(lon: float, lat: float, *, timeout: float = 12.0) -> float | None:
    """Consulta LST observada (°C) em um ponto via TiTiler GeoReDUS."""
    source = EXTERNAL_RASTER_SOURCES["lst_observada"]
    url = build_mosaicjson_point_url(source, lon, lat)
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(url, timeout=timeout, context=ctx) as resp:
            payload = json.loads(resp.read().decode())
        return _parse_lst_point_payload(payload)
    except Exception as exc:
        logger.debug("LST point fetch failed lon=%s lat=%s: %s", lon, lat, exc)
        return None
