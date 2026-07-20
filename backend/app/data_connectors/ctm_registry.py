"""Catálogo de fontes CTM (Cartografia Territorial Municipal) abertas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SourceKind = Literal[
    "arcgis",
    "geojson_url",
    "geojson_file",
    "geoserver_wfs",
    "ibge_setores_agreg",
    "ibge_setores_individuais",
]


@dataclass(frozen=True)
class CtmSource:
    codigo_ibge: str
    nome: str
    uf: str
    kind: SourceKind
    url: str
    name_fields: tuple[str, ...]
    code_fields: tuple[str, ...] = ()
    where: str = "1=1"
    cql_filter: str = ""
    prioridade: int = 1
    nota: str = ""
    nivel_alvo: str = "BAIXA"  # BAIXA | MEDIA


# 24 municípios abaixo do patamar Salvador/Recife (19 BAIXA + 5 MEDIA).
# Fontes verificadas manualmente (ArcGIS REST com geoJSON).
RS_STATE_BAIRROS_URL = (
    "https://iede.rs.gov.br/server/rest/services/SEPLAG/"
    "Malha_de_Bairros___Censo_Demogr%C3%A1fico_2022/MapServer/0/query"
)
BA_STATE_BAIRROS_URL = (
    "https://maps.informs.conder.ba.gov.br/arcgis/rest/services/"
    "BAHIA/BAIRRO_GEO/MapServer/0/query"
)
IBGE_BAIRROS_WFS_URL = "https://geoservicos.ibge.gov.br/geoserver/wfs"
IBGE_BAIRROS_TYPE = "CGMAT:qg_2022_650_bairro_agreg"
CAMPINAS_UTB_GEOJSON = "data/cache/ctm/3509502_campinas_utb.geojson"

CTM_SOURCES: list[CtmSource] = [
    CtmSource(
        codigo_ibge="5208707",
        nome="Goiânia",
        uf="GO",
        kind="arcgis",
        url=(
            "https://portalmapa.goiania.go.gov.br/servicogyn/rest/services/"
            "MapaServer/Mapa_Basico3/MapServer/391/query"
        ),
        name_fields=("nm_bai", "nm2", "nm3", "nome"),
        code_fields=("id",),
        where="1=1",
        nota="MUBDG — divisas de bairros (prefeitura); filtra nm_bai vazio no import",
    ),
    # Campinas: CATI/Bairros é linha; UTB poligonal via cache DIDT (exporta_shp id=91).
    CtmSource(
        codigo_ibge="3509502",
        nome="Campinas",
        uf="SP",
        kind="geojson_file",
        url=CAMPINAS_UTB_GEOJSON,
        name_fields=("DENOMINACA", "UTB_SIGLA", "nome", "NM_BAIRRO"),
        code_fields=("UTB_SIGLA", "cd_bairro"),
        nota="DIDC/PD2018 — Unidades Territoriais Básicas (93 polígonos); dissolve por DENOMINACA",
    ),
    CtmSource(
        codigo_ibge="5300108",
        nome="Brasília",
        uf="DF",
        kind="arcgis",
        url=(
            "https://onda.ibram.df.gov.br/server/rest/services/Territorio/"
            "Regioes_Administrativas_DF_2025/FeatureServer/0/query"
        ),
        name_fields=("ra_nome", "nome"),
        code_fields=("ra_codigo",),
        nota="Regiões Administrativas DF (IBRAM) — 35 polígonos nomeados",
    ),
    CtmSource(
        codigo_ibge="4314902",
        nome="Porto Alegre",
        uf="RS",
        kind="arcgis",
        url=(
            "https://gis-smamus.portoalegre.rs.gov.br/server/rest/services/"
            "01_PUBLICACOES/bairros_2016/FeatureServer/0/query"
        ),
        name_fields=("nome", "NOME"),
        code_fields=("codigo", "id"),
        nota="Lei 12.112/2016 — backup CTM quando malha IBGE regredir",
        prioridade=2,
    ),
    CtmSource(
        codigo_ibge="1200401",
        nome="Rio Branco",
        uf="AC",
        kind="arcgis",
        url=(
            "https://rbgeo.riobranco.ac.gov.br/server/rest/services/"
            "Hosted/Bairros_2024/FeatureServer/0/query"
        ),
        name_fields=("bairro", "BAIRRO", "nome"),
        code_fields=("cod_bairro", "id"),
        nota="GeoPortal Rio Branco — Bairros 2024 (94 polígonos)",
    ),
    CtmSource(
        codigo_ibge="4304606",
        nome="Canoas",
        uf="RS",
        kind="arcgis",
        url=RS_STATE_BAIRROS_URL,
        name_fields=("nm_bairro", "NM_BAIRRO", "BAIRRO"),
        code_fields=("cd_bairro",),
        where="cd_mun='4304606'",
        nota="IDE-RS/SEPLAG — Malha bairros Censo 2022 (18 polígonos); geoportal municipal com dados versionados",
        nivel_alvo="MEDIA",
    ),
    CtmSource(
        codigo_ibge="4318903",
        nome="São Luiz Gonzaga",
        uf="RS",
        kind="arcgis",
        url=RS_STATE_BAIRROS_URL,
        name_fields=("nm_bairro", "NM_BAIRRO"),
        code_fields=("cd_bairro",),
        where="cd_mun='4318903'",
        nota="IDE-RS/SEPLAG — Malha bairros Censo 2022 (23 polígonos)",
        nivel_alvo="MEDIA",
    ),
    CtmSource(
        codigo_ibge="2913606",
        nome="Ilhéus",
        uf="BA",
        kind="arcgis",
        url=BA_STATE_BAIRROS_URL,
        name_fields=("NM_BAIRRO", "nm_bairro", "BAIRRO"),
        code_fields=("CD_BAIRRO",),
        where="CD_MUN='2913606'",
        nota="IDE Bahia/CONDER — serviço intermitente; tentar import quando online",
        nivel_alvo="MEDIA",
        prioridade=3,
    ),
    CtmSource(
        codigo_ibge="2924009",
        nome="Paulo Afonso",
        uf="BA",
        kind="arcgis",
        url=BA_STATE_BAIRROS_URL,
        name_fields=("NM_BAIRRO", "nm_bairro", "BAIRRO"),
        code_fields=("CD_BAIRRO",),
        where="CD_MUN='2924009'",
        nota="IDE Bahia/CONDER — serviço intermitente",
        prioridade=3,
    ),
    CtmSource(
        codigo_ibge="2800308",
        nome="Aracaju",
        uf="SE",
        kind="geoserver_wfs",
        url="https://fazenda.aracaju.se.gov.br/geoserver/wfs",
        name_fields=("bairro", "nome", "NM_BAIRRO"),
        where="Limites_Municipais:bairros_2023",
        nota="GeoServer SEFAZ Aracaju — malha oficial de bairros (Lei 873/1982, revisão 2023)",
        prioridade=2,
    ),
    CtmSource(
        codigo_ibge="2602902",
        nome="Cabo de Santo Agostinho",
        uf="PE",
        kind="geoserver_wfs",
        url=IBGE_BAIRROS_WFS_URL,
        name_fields=("nm_bairro", "NM_BAIRRO", "nome"),
        code_fields=("cd_bairro",),
        where=IBGE_BAIRROS_TYPE,
        cql_filter="cd_mun='2602902'",
        nota="IBGE CGM 2022 (bairro agregado) — 24 polígonos até geoportal municipal PE",
        prioridade=4,
    ),
    CtmSource(
        codigo_ibge="2806701",
        nome="São Cristóvão",
        uf="SE",
        kind="geoserver_wfs",
        url=IBGE_BAIRROS_WFS_URL,
        name_fields=("nm_bairro", "NM_BAIRRO", "nome"),
        code_fields=("cd_bairro",),
        where=IBGE_BAIRROS_TYPE,
        cql_filter="cd_mun='2806701'",
        nota="IBGE CGM 2022 (bairro agregado) — 14 polígonos até REST municipal SE",
        prioridade=4,
    ),
    # Fallback IBGE — agregação de setores censitários 2022 (prioridade 5, até CTM municipal).
    CtmSource(
        codigo_ibge="3143906",
        nome="Mariana",
        uf="MG",
        kind="ibge_setores_agreg",
        url="ibge://setores/2022",
        name_fields=("NM_BAIRRO", "nm_bairro", "nome"),
        code_fields=("CD_BAIRRO",),
        nota="IBGE Censo 2022 — 7 bairros por agregação de setores (sem REST municipal)",
        prioridade=5,
    ),
    CtmSource(
        codigo_ibge="5208905",
        nome="Goiás",
        uf="GO",
        kind="ibge_setores_agreg",
        url="ibge://setores/2022",
        name_fields=("NM_BAIRRO", "nm_bairro", "nome"),
        code_fields=("CD_BAIRRO",),
        nota="IBGE Censo 2022 — 6 bairros por agregação de setores",
        prioridade=5,
    ),
    CtmSource(
        codigo_ibge="5201108",
        nome="Anápolis",
        uf="GO",
        kind="ibge_setores_agreg",
        url="ibge://setores/2022",
        name_fields=("NM_BAIRRO", "nm_bairro", "nome"),
        code_fields=("CD_BAIRRO",),
        nota="IBGE Censo 2022 — 5 bairros por agregação de setores",
        prioridade=5,
    ),
    CtmSource(
        codigo_ibge="3109006",
        nome="Brumadinho",
        uf="MG",
        kind="ibge_setores_agreg",
        url="ibge://setores/2022",
        name_fields=("NM_BAIRRO", "nm_bairro", "nome"),
        code_fields=("CD_BAIRRO",),
        nota="IBGE Censo 2022 — 5 bairros por agregação de setores",
        prioridade=5,
    ),
    CtmSource(
        codigo_ibge="2407104",
        nome="Macaíba",
        uf="RN",
        kind="ibge_setores_agreg",
        url="ibge://setores/2022",
        name_fields=("NM_BAIRRO", "nm_bairro", "nome"),
        code_fields=("CD_BAIRRO",),
        nota="IBGE Censo 2022 — 5 bairros por agregação de setores",
        prioridade=5,
    ),
    CtmSource(
        codigo_ibge="3303906",
        nome="Petrópolis",
        uf="RJ",
        kind="ibge_setores_agreg",
        url="ibge://setores/2022",
        name_fields=("NM_BAIRRO", "nm_bairro", "nome"),
        code_fields=("CD_BAIRRO",),
        nota="IBGE Censo 2022 — 5 bairros por agregação de setores",
        prioridade=5,
    ),
    CtmSource(
        codigo_ibge="5218805",
        nome="Rio Verde",
        uf="GO",
        kind="ibge_setores_agreg",
        url="ibge://setores/2022",
        name_fields=("NM_BAIRRO", "nm_bairro", "nome"),
        code_fields=("CD_BAIRRO",),
        nota="IBGE Censo 2022 — 4 bairros por agregação de setores",
        prioridade=5,
    ),
    # Fallback setor a setor — quando agregação IBGE dá <4 bairros (sem REST municipal).
    CtmSource(
        codigo_ibge="4104907",
        nome="Castro",
        uf="PR",
        kind="ibge_setores_individuais",
        url="ibge://setores/2022",
        name_fields=("NM_BAIRRO", "NM_DIST", "nome"),
        code_fields=("CD_SETOR",),
        nota="IBGE Censo 2022 — setores censitários como malha operacional (CTM municipal pendente)",
        prioridade=6,
    ),
    CtmSource(
        codigo_ibge="1721000",
        nome="Palmas",
        uf="TO",
        kind="ibge_setores_individuais",
        url="ibge://setores/2022",
        name_fields=("NM_BAIRRO", "NM_DIST", "nome"),
        code_fields=("CD_SETOR",),
        nota="IBGE Censo 2022 — 733 setores (GeoPalmas/CTM oficial pendente)",
        prioridade=6,
    ),
    CtmSource(
        codigo_ibge="1702109",
        nome="Araguaína",
        uf="TO",
        kind="ibge_setores_individuais",
        url="ibge://setores/2022",
        name_fields=("NM_BAIRRO", "NM_DIST", "nome"),
        code_fields=("CD_SETOR",),
        nota="IBGE Censo 2022 — setores censitários (SIGA municipal sem REST público)",
        prioridade=6,
    ),
    CtmSource(
        codigo_ibge="1400233",
        nome="Caroebe",
        uf="RR",
        kind="ibge_setores_individuais",
        url="ibge://setores/2022",
        name_fields=("NM_BAIRRO", "NM_DIST", "nome"),
        code_fields=("CD_SETOR",),
        nota="IBGE Censo 2022 — setores censitários (município extenso, CTM pendente)",
        prioridade=6,
    ),
    CtmSource(
        codigo_ibge="3138203",
        nome="Lavras",
        uf="MG",
        kind="ibge_setores_individuais",
        url="ibge://setores/2022",
        name_fields=("NM_BAIRRO", "NM_DIST", "nome"),
        code_fields=("CD_SETOR",),
        nota="IBGE Censo 2022 — setores censitários (geoportal municipal sem REST)",
        prioridade=6,
    ),
    CtmSource(
        codigo_ibge="1504208",
        nome="Marabá",
        uf="PA",
        kind="ibge_setores_individuais",
        url="ibge://setores/2022",
        name_fields=("NM_BAIRRO", "NM_DIST", "nome"),
        code_fields=("CD_SETOR",),
        nota="IBGE Censo 2022 — setores censitários (SIG municipal em licitação)",
        prioridade=6,
    ),
    CtmSource(
        codigo_ibge="2111300",
        nome="São Luís",
        uf="MA",
        kind="ibge_setores_individuais",
        url="ibge://setores/2022",
        name_fields=("NM_BAIRRO", "NM_DIST", "nome"),
        code_fields=("CD_SETOR",),
        nota="IBGE Censo 2022 — setores censitários (INCID/shapefile sob demanda)",
        prioridade=6,
    ),
]

# Geoportais municipais ainda sem REST/shapefile automatizado (sondagem jul/2026).
CTM_RESEARCH_NOTES: dict[str, str] = {
    "1721000": (
        "Palmas: GeoPalmas em reestruturação; SEPLAN-TO geoportal com SSL inválido; "
        "IBGE CGM bairros agregados = 0 feições — manter setores individuais."
    ),
    "2111300": (
        "São Luís: INCID só sob demanda (incid.slz@gmail.com); "
        "IBGE CGM bairros agregados = 0 — manter setores individuais."
    ),
    "2913606": "Ilhéus/CONDER: maps.informs.conder.ba.gov.br offline na sondagem jul/2026.",
    "2924009": "Paulo Afonso/CONDER: mesmo serviço BAIRRO_GEO intermitente.",
}

CTM_BY_CODE: dict[str, CtmSource] = {s.codigo_ibge: s for s in CTM_SOURCES}

# Municípios alvo do plano de maturidade (BAIXA + MEDIA da revisão).
CTM_TARGET_CODES: list[str] = [
    "3509502",  # Campinas — BAIXA
    "3143906",  # Mariana
    "5208905",  # Goiás
    "5201108",  # Anápolis
    "3109006",  # Brumadinho
    "2407104",  # Macaíba
    "3303906",  # Petrópolis
    "5218805",  # Rio Verde
    "4104907",  # Castro
    "1721000",  # Palmas
    "5208707",  # Goiânia — BAIXA
    "1702109",  # Araguaína
    "5300108",  # Brasília — BAIXA
    "1400233",  # Caroebe
    "3138203",  # Lavras
    "1504208",  # Marabá
    "2924009",  # Paulo Afonso
    "1200401",  # Rio Branco
    "2111300",  # São Luís
    "2913606",  # Ilhéus — MEDIA
    "2602902",  # Cabo de Santo Agostinho
    "4318903",  # São Luiz Gonzaga
    "4304606",  # Canoas
    "2806701",  # São Cristóvão
]


def ctm_registry_stats() -> dict[str, int | dict[str, int]]:
    """Contagens estáticas do registry (sem probe ao vivo)."""
    alvo = set(CTM_TARGET_CODES)
    cadastrados = [c for c in CTM_TARGET_CODES if c in CTM_BY_CODE]
    por_kind: dict[str, int] = {}
    for source in CTM_SOURCES:
        if source.codigo_ibge in alvo:
            por_kind[source.kind] = por_kind.get(source.kind, 0) + 1
    return {
        "total_alvo": len(CTM_TARGET_CODES),
        "fontes_cadastradas": len(cadastrados),
        "sem_fonte": len(CTM_TARGET_CODES) - len(cadastrados),
        "fora_alvo_com_fonte": len([s for s in CTM_SOURCES if s.codigo_ibge not in alvo]),
        "por_kind": por_kind,
        "research_notes": len(CTM_RESEARCH_NOTES),
    }
