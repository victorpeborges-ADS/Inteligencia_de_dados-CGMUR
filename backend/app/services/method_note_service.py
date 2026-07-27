"""Nota metodológica publicável das simulações (17g.2g).

Agrega método, dados de entrada, selo de confiança, validação e limitações
em um documento legível (JSON + Markdown) para homologação/academia.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


REFERENCIAS = [
    {
        "id": "srtm",
        "label": "NASA/USGS SRTM — Modelo Digital de Elevação ~30 m",
        "url": "https://www.earthdata.nasa.gov/sensors/srtm",
    },
    {
        "id": "s2id",
        "label": "S2ID — Sistema Integrado de Informações sobre Desastres (MDR)",
        "url": "https://s2id.mi.gov.br/",
    },
    {
        "id": "cemaden",
        "label": "CEMADEN — Centro Nacional de Monitoramento e Alertas",
        "url": "https://www.gov.br/cemaden/",
    },
    {
        "id": "mapbiomas",
        "label": "MapBiomas — Cobertura e uso do solo",
        "url": "https://brasil.mapbiomas.org/",
    },
]

# Painel único de limites (20h.2) — espelhado na UI de Simulações
LIMITES_METODOLOGICOS_PAINEL = {
    "titulo": "Limites metodológicos das simulações",
    "o_que_e": [
        "Triagem territorial para priorizar bairros e ensaiar contingência",
        "Estimativa com DEM, chuva/cenário e proxies de uso do solo",
        "Selo de qualidade (Oficial | Observado | Estimado | Derivado) por camada/resultado",
    ],
    "o_que_nao_e": [
        "Laudo de engenharia, perícia judicial ou projeto executivo",
        "Modelagem hidrodinâmica 2D (HEC-RAS / SWMM) nem inventário completo de galerias",
        "Alerta oficial CEMADEN / Defesa Civil / SMS público",
        "Metodologia oficial ANA, CPRM ou IDF municipal homologada (salvo selo Oficial explícito)",
    ],
}


def _tipo_label(tipo: str) -> str:
    t = (tipo or "chuva").lower()
    if t in {"chuva", "extreme_rainfall", "extremrainfall", "pluvial"}:
        return "Simulação pluvial (inundação / alagamento)"
    if t in {"calor", "heat", "heat_island", "ilha_calor"}:
        return "Simulação de ilha de calor urbana"
    if t in {"deslizamento", "landslide", "encosta"}:
        return "Simulação de deslizamento / instabilidade de encosta"
    return f"Simulação ({tipo})"


def build_method_note(
    simulation_meta: dict[str, Any] | None,
    *,
    tipo: str = "chuva",
    municipio: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Monta nota metodológica a partir do simulation_meta já enriquecido."""
    meta = simulation_meta or {}
    seal = meta.get("selo_confianca") or {}
    s2id = meta.get("validacao_s2id") or {}
    bands = meta.get("uncertainty_bands") or {}
    idf = meta.get("idf") or {}
    nivel_mar = meta.get("nivel_mar") or {}
    drenagem = meta.get("drenagem_urbana") or {}

    muni_txt = ""
    if municipio:
        nome = municipio.get("nome") or ""
        uf = municipio.get("uf") or ""
        ibge = municipio.get("codigo_ibge") or ""
        muni_txt = f"{nome}/{uf} (IBGE {ibge})".strip()

    metodo = meta.get("method") or ("dem" if meta.get("dem_available") else "heuristic")
    model_version = meta.get("model_version") or "n/d"
    dem_source = meta.get("dem_source") or "indisponível"
    precip = meta.get("precipitation_mm")

    secoes: list[dict[str, Any]] = [
        {
            "id": "objetivo",
            "titulo": "Objetivo",
            "corpo": (
                f"Estimativa territorial de {_tipo_label(tipo).lower()} "
                "para apoiar priorização e contingência municipal — "
                "não substitui projeto de engenharia ou laudo oficial."
            ),
        },
        {
            "id": "metodo",
            "titulo": "Método",
            "corpo": (
                f"Motor: `{metodo}` (versão {model_version}). "
                f"Base topográfica: {dem_source}"
                + (
                    f" (~{meta.get('dem_resolution_m')} m)"
                    if meta.get("dem_resolution_m") is not None
                    else ""
                )
                + (
                    f"; incerteza vertical ±{meta.get('vertical_accuracy_m')} m"
                    if meta.get("vertical_accuracy_m") is not None
                    else ""
                )
                + ". "
                + (
                    "Acumulação de fluxo D8, TWI e proxy de impermeabilização "
                    "quando o DEM está disponível; caso contrário, heurística territorial."
                    if meta.get("dem_available")
                    else "Modo heurístico — use apenas para sensibilização."
                )
                + (
                    " DEM hidro-corrigido (preenchimento de depressões / Priority-Flood) antes do D8."
                    if meta.get("dem_hydro_conditioned")
                    else ""
                )
            ),
        },
    ]

    entradas = []
    if precip is not None:
        entradas.append(f"Precipitação do evento: {precip} mm")
    if idf:
        entradas.append(
            f"IDF/TR: {idf.get('periodo_retorno_anos')} anos · "
            f"{idf.get('duracao_min')} min · fonte {idf.get('fonte') or 'catálogo Sinidu'}"
        )
    if meta.get("chuva_antecedente_mm"):
        entradas.append(f"Chuva antecedente: {meta.get('chuva_antecedente_mm')} mm")
    if meta.get("nivel_mar_m"):
        entradas.append(
            f"Nível do mar / storm surge: +{meta.get('nivel_mar_m')} m"
            + (f" ({nivel_mar.get('cenario')})" if nivel_mar.get("cenario") else "")
        )
    if drenagem.get("aplicado"):
        entradas.append(
            f"Drenagem urbana (proxy): capacidade {drenagem.get('capacidade_mm_h')} mm/h · "
            f"removidos {drenagem.get('removido_mm')} mm"
            + (" · rede saturada" if drenagem.get("saturada") else "")
            + (f" · fonte {drenagem.get('fonte')}" if drenagem.get("fonte") else "")
        )
    if meta.get("max_depth_m") is not None:
        entradas.append(f"Profundidade máxima estimada: {meta.get('max_depth_m')} m")
    if entradas:
        secoes.append(
            {
                "id": "entradas",
                "titulo": "Entradas e resultados-chave",
                "corpo": "; ".join(entradas) + ".",
                "itens": entradas,
            }
        )

    if meta.get("flood_timeline"):
        tl = meta["flood_timeline"]
        secoes.append(
            {
                "id": "temporal",
                "titulo": "Evolução temporal (hidrograma)",
                "corpo": (
                    f"Animação em {tl.get('n_steps')} passos ao longo de {tl.get('duration_h')} h "
                    f"por escala do raster de profundidade de pico ({tl.get('method')}). "
                    "Não é simulação hidrodinâmica unsteady."
                ),
            }
        )

    if seal:
        secoes.append(
            {
                "id": "confianca",
                "titulo": "Selo de confiança",
                "corpo": (
                    f"{seal.get('selo_qualidade')} · confiança {seal.get('nivel_confianca')}. "
                    f"{seal.get('interpretacao') or ''}"
                ),
                "itens": seal.get("fatores") or [],
            }
        )

    if s2id.get("disponivel"):
        secoes.append(
            {
                "id": "validacao",
                "titulo": "Validação contra S2ID",
                "corpo": s2id.get("narrativa") or "",
                "itens": [
                    f"Acordo: {s2id.get('acordo')}",
                    f"Hit rate: {s2id.get('hit_rate')}",
                    s2id.get("limitacao") or "",
                ],
            }
        )

    if bands:
        secoes.append(
            {
                "id": "incerteza",
                "titulo": "Bandas de incerteza",
                "corpo": (
                    f"Envelope ±{bands.get('precip_delta_pct', 15)}% na precipitação "
                    "(cenários chuva menor / atual / chuva maior) para comunicar "
                    "sensibilidade do modelo, não intervalo estatístico formal."
                ),
            }
        )

    secoes.append(
        {
            "id": "limitacoes",
            "titulo": "Limitações",
            "corpo": (
                "O modelo não representa redes de drenagem subterrâneas detalhadas, "
                "obras hidráulicas locais nem dinâmica 2D completa. "
                "S2ID valida por pontos históricos, não por polígonos oficiais de área afetada. "
                "Resultados servem a priorização territorial e exercício de contingência."
            ),
            "itens": [
                meta.get("precision_note") or "",
                "Não usar como laudo de engenharia ou perícia judicial.",
            ],
        }
    )

    nota = {
        "titulo": f"Nota metodológica — {_tipo_label(tipo)}",
        "tipo": tipo,
        "municipio": muni_txt or None,
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "padrao_qualidade": "Oficial | Observado | Estimado | Derivado",
        "selo_confianca": seal or None,
        "secoes": secoes,
        "referencias": REFERENCIAS,
        "disclaimer": (
            "Documento gerado automaticamente pelo Sinidu+Clima para transparência "
            "metodológica. Revisar fontes e contexto local antes de uso em decisão "
            "operacional ou comunicação pública. Não habilita uso como laudo oficial "
            "nem como alerta CEMADEN/Defesa Civil."
        ),
    }
    nota["markdown"] = render_method_note_markdown(nota)
    return nota


def render_method_note_markdown(nota: dict[str, Any]) -> str:
    lines = [
        f"# {nota.get('titulo')}",
        "",
    ]
    if nota.get("municipio"):
        lines.append(f"**Município:** {nota['municipio']}")
    lines.append(f"**Gerado em:** {nota.get('gerado_em')}")
    lines.append("")
    for sec in nota.get("secoes") or []:
        lines.append(f"## {sec.get('titulo')}")
        lines.append("")
        if sec.get("corpo"):
            lines.append(str(sec["corpo"]))
            lines.append("")
        for item in sec.get("itens") or []:
            if item:
                lines.append(f"- {item}")
        if sec.get("itens"):
            lines.append("")
    lines.append("## Referências")
    lines.append("")
    for ref in nota.get("referencias") or []:
        lines.append(f"- [{ref.get('label')}]({ref.get('url')})")
    lines.append("")
    lines.append(f"> {nota.get('disclaimer')}")
    lines.append("")
    return "\n".join(lines)


def attach_method_note(
    simulation_meta: dict[str, Any] | None,
    *,
    tipo: str = "chuva",
    municipio: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta = dict(simulation_meta or {})
    meta["nota_metodologica"] = build_method_note(meta, tipo=tipo, municipio=municipio)
    return meta
