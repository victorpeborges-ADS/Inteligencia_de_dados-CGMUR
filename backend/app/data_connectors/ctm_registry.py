"""Catálogo de fontes CTM (Cartografia Territorial Municipal) abertas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SourceKind = Literal["arcgis", "geojson_url", "geoserver_wfs"]


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
    prioridade: int = 1
    nota: str = ""
    nivel_alvo: str = "BAIXA"  # BAIXA | MEDIA


# 24 municípios abaixo do patamar Salvador/Recife (19 BAIXA + 5 MEDIA).
# Fontes verificadas manualmente (ArcGIS REST com geoJSON).
RS_STATE_BAIRROS_URL = (
    "https://iede.rs.gov.br/server/rest/services/SEPLAG/"
    "Malha_de_Bairros___Censo_Demogr%C3%A1fico_2022/MapServer/0/query"
)

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
    # Campinas: camada vetorial de bairros (Hosted/Bairros) é linha, não polígono.
    # UTB shapefile exige download manual do portal DIDT — pendente cadastro.
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
        url=(
            "https://maps.informs.conder.ba.gov.br/arcgis/rest/services/"
            "BAHIA/BAIRRO_GEO/MapServer/0/query"
        ),
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
        url=(
            "https://maps.informs.conder.ba.gov.br/arcgis/rest/services/"
            "BAHIA/BAIRRO_GEO/MapServer/0/query"
        ),
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
]

# Pesquisa de geoportais — municípios ainda sem REST público verificado (jun/2026).
CTM_RESEARCH_NOTES: dict[str, str] = {
    "3509502": "Campinas: CATI/Bairros é linha; UTB poligonal exige shapefile DIDT (exporta_shp id=91).",
    "3143906": "Mariana: sem ArcGIS público; malha IBGE parcial (7 bairros).",
    "5208905": "Goiás (GO): sem geoportal REST; 6 bairros IBGE + setores.",
    "5201108": "Anápolis: Plano Diretor define 25 bairros (PDF); sem REST aberto.",
    "3109006": "Brumadinho: sem REST municipal; 5 bairros IBGE.",
    "2407104": "Macaíba: bairros no Plano Diretor (PDF); sem shapefile aberto.",
    "3303906": "Petrópolis: portal cartográfico web; sem FeatureServer público.",
    "5218805": "Rio Verde: sem REST verificado.",
    "4104907": "Castro: sem REST verificado.",
    "1721000": "Palmas: GeoPalmas/SEPLAN-TO (shapefile); sem ArcGIS REST estável.",
    "1702109": "Araguaína: Topovision/SIGA (camada bairros visual); sem REST exportável.",
    "1400233": "Caroebe: 1 bairro IBGE + 36 setores; limite municipal enorme (RR).",
    "3138203": "Lavras: portal cidadão ArcGIS Experience; sem camada bairros REST.",
    "1504208": "Marabá: SIG municipal em licitação (2024); sem geoportal aberto.",
    "2111300": "São Luís: INCID/arquivodacidade — shapefile sob demanda (e-mail).",
    "2602902": "Cabo: ArcGIS Experience Builder; shapefile comercial/OSM (~24 bairros).",
    "2806701": "São Cristóvão: Geodados SaaS municipal; sem REST público.",
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
