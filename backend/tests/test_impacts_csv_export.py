"""Export CSV de impactos operacionais."""

from __future__ import annotations

from types import SimpleNamespace

from app.services.simulation_export import build_impacts_csv_text


def test_impacts_csv_contains_sections():
    muni = SimpleNamespace(nome="Camutanga", codigo_ibge="2603603", uf="PE")
    simulation = {
        "scenario_type": "ExtremeRainfall",
        "input_value": 120,
        "simulation_meta": {
            "impacto_operacional": {
                "mobilidade": {"vias_comprometidas_km": 3.2, "vias_trechos": 4, "vias_fonte": "osm"},
            },
            "ativos_criticos": {"escolas": 2, "saude": 1, "abrigos": 0},
            "glofas_compare": {"ok": True, "overlap_pct": 12.5, "nota": "teste"},
        },
        "vias_intransitaveis": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": [[-35.3, -7.4], [-35.29, -7.41]]},
                    "properties": {"nome": "Rua A", "highway": "residential", "length_km": 0.4},
                }
            ],
        },
        "ativos_criticos_atingidos": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [-35.3, -7.43]},
                    "properties": {
                        "categoria": "escola",
                        "nome": "Escola X",
                        "depth_band": "moderada",
                        "matriculas_total": 120,
                    },
                }
            ],
        },
    }
    text = build_impacts_csv_text(simulation, muni)  # type: ignore[arg-type]
    assert "Vias intransitáveis" in text
    assert "Ativos críticos" in text
    assert "Rua A" in text
    assert "Escola X" in text
    assert "12.5" in text
