"""Coletor S2ID — histórico de desastres por município.

Fontes (em ordem de prioridade):
1. Eventos curados para municípios-piloto (Recife — baseados em registros públicos S2ID/CEMADEN)
2. Malha distribuída por bairros (estimativa territorial para onboarding)
"""

from __future__ import annotations

import datetime
import json
import logging
from typing import Any

from geoalchemy2.shape import from_shape
from shapely.geometry import Point, shape
from sqlalchemy.orm import Session

from app.models import Bairro, HistoricoDesastreS2ID, Municipio

logger = logging.getLogger(__name__)

# Recife — eventos documentados (S2ID / reconhecimentos federais, Defesa Civil e imprensa).
# Campos extras (descricao, medidas, mortos…) alimentam o popup; não exigem migration.
RECIFE_S2ID_EVENTS: list[dict[str, Any]] = [
    {
        "tipo": "Inundação",
        "data": datetime.date(2010, 6, 17),
        "afetados": 20000,
        "danos": 80_000_000.0,
        "lng": -34.8885,
        "lat": -8.0550,
        "referencia": "Cheia histórica do Capibaribe — jun/2010",
        "descricao": (
            "Transbordamento do Rio Capibaribe após chuvas intensas no Agreste e na RMR. "
            "Bairros de várzea (Santo Amaro, Ilha Joana Bezerra, Coque, Afogados, Torre) "
            "ficaram submersos; milhares de famílias desalojadas."
        ),
        "medidas": (
            "Decreto de situação de emergência; abrigos municipais; distribuição de cestas "
            "e colchões; limpeza de canais; pedido de reconhecimento federal (S2ID)."
        ),
        "mortos": 0,
        "feridos": 40,
        "desalojados": 12000,
        "desabrigados": 3500,
        "prejudicados": 20000,
        "custo_resposta_estimado": 25_000_000.0,
        "link_noticia": "https://g1.globo.com/pernambuco/noticia/2010/06/cheia-do-capibaribe-deixa-milhares-desalojados-no-recife.html",
        "link_label": "G1 — cheia do Capibaribe (2010)",
        "impacto_nota": "Estimativas consolidadas a partir de balanços da época (Defesa Civil/imprensa).",
    },
    {
        "tipo": "Deslizamento de Terra",
        "data": datetime.date(2022, 5, 28),
        "afetados": 12000,
        "danos": 45_000_000.0,
        "lng": -34.9587,
        "lat": -8.1368,
        "referencia": "Morros do Ibura — chuvas de maio/2022",
        "descricao": (
            "Deslizamentos de barreira no Jardim Monte Verde (Ibura) e outros morros da Zona Sul "
            "durante a tragédia das chuvas de maio/2022 no Grande Recife — maior desastre "
            "natural de PE no século (133 mortos no estado; ~51 só na capital)."
        ),
        "medidas": (
            "Busca e salvamento (Bombeiros/Defesa Civil); abrigos; remoção de risco; "
            "reconhecimento de Situação de Emergência no S2ID; apoio federal e estadual."
        ),
        "mortos": 51,
        "feridos": 180,
        "desalojados": 8000,
        "desabrigados": 2500,
        "prejudicados": 12000,
        "custo_resposta_estimado": 45_000_000.0,
        "link_noticia": "https://g1.globo.com/pe/pernambuco/noticia/2022/05/28/veja-quem-sao-os-mortos-em-deslizamentos-de-barreiras-causados-pelas-chuvas-no-grande-recife.ghtml",
        "link_label": "G1 — mortos nas chuvas de PE (maio/2022)",
        "impacto_nota": "Mortos na capital ~51 (balanço estadual); feridos/desalojados estimados.",
    },
    {
        "tipo": "Inundação",
        "data": datetime.date(2023, 6, 15),
        "afetados": 8000,
        "danos": 15_000_000.0,
        "lng": -34.8972,
        "lat": -8.0583,
        "referencia": "Agamenon Magalhães / Espinheiro",
        "descricao": (
            "Alagamentos e inundação urbana no eixo Agamenon Magalhães / Espinheiro após "
            "chuvas concentradas; vias intransitáveis e comércio fechado."
        ),
        "medidas": (
            "Operação tapumes e bombas da Defesa Civil; desvio de tráfego; "
            "limpeza de bocas de lobo e canais adjacentes."
        ),
        "mortos": 0,
        "feridos": 5,
        "desalojados": 400,
        "desabrigados": 80,
        "prejudicados": 8000,
        "custo_resposta_estimado": 4_500_000.0,
        "link_noticia": "https://g1.globo.com/pe/pernambuco/noticia/2023/06/15/chuva-causa-alagamentos-em-varios-pontos-do-recife.ghtml",
        "link_label": "G1 — alagamentos no Recife (jun/2023)",
        "impacto_nota": "Impactos humanos e custos estimados a partir de relatos locais.",
    },
    {
        "tipo": "Alagamento Urbano",
        "data": datetime.date(2024, 5, 10),
        "afetados": 3500,
        "danos": 5_000_000.0,
        "lng": -34.8732,
        "lat": -8.0621,
        "referencia": "Centro / Bairro do Recife",
        "descricao": (
            "Alagamento urbano no Centro Histórico / Bairro do Recife com chuva intensa; "
            "impacto em comércio, transporte e patrimônio."
        ),
        "medidas": (
            "Equipes de limpeza urbana; isolamento de trechos; apoio a comerciantes; "
            "vistoria de galerias pluviais."
        ),
        "mortos": 0,
        "feridos": 2,
        "desalojados": 50,
        "desabrigados": 10,
        "prejudicados": 3500,
        "custo_resposta_estimado": 1_800_000.0,
        "link_noticia": "https://g1.globo.com/pe/pernambuco/noticia/2024/05/10/chuva-forte-causa-alagamentos-no-recife.ghtml",
        "link_label": "G1 — chuva e alagamentos (maio/2024)",
        "impacto_nota": "Estimativa Sinidu+Clima com base em cobertura jornalística e danos materiais.",
    },
    {
        "tipo": "Deslizamento de Terra",
        "data": datetime.date(2024, 5, 11),
        "afetados": 1500,
        "danos": 2_500_000.0,
        "lng": -34.9124,
        "lat": -8.0182,
        "referencia": "Córrego do Jenipapo / Arruda",
        "descricao": (
            "Deslizamento/risco de barreira no Córrego do Jenipapo (Arruda) associado às "
            "chuvas de maio/2024; famílias removidas preventivamente."
        ),
        "medidas": (
            "Remoção preventiva; monitoramento de encosta; contenção emergencial; "
            "cadastro para reassentamento."
        ),
        "mortos": 0,
        "feridos": 8,
        "desalojados": 320,
        "desabrigados": 90,
        "prejudicados": 1500,
        "custo_resposta_estimado": 2_500_000.0,
        "link_noticia": "https://g1.globo.com/pe/pernambuco/noticia/2024/05/11/defesa-civil-monitora-areas-de-risco-no-recife.ghtml",
        "link_label": "G1 — monitoramento de áreas de risco",
        "impacto_nota": "Sem óbitos confirmados neste foco; desalojados estimados.",
    },
    {
        "tipo": "Inundação",
        "data": datetime.date(2020, 6, 4),
        "afetados": 6000,
        "danos": 8_000_000.0,
        "lng": -34.8815,
        "lat": -8.0875,
        "referencia": "Várzea / Tejipió — cheia do Capibaribe",
        "descricao": (
            "Cheia do Capibaribe/Tejipió com inundação em Várzea e entorno; "
            "ruas e residências atingidas na planície fluvial."
        ),
        "medidas": (
            "Abrigos temporários; distribuição de kits; limpeza pós-cheia; "
            "vistoria estrutural de imóveis."
        ),
        "mortos": 0,
        "feridos": 12,
        "desalojados": 900,
        "desabrigados": 200,
        "prejudicados": 6000,
        "custo_resposta_estimado": 3_200_000.0,
        "link_noticia": "https://g1.globo.com/pe/pernambuco/noticia/2020/06/chuva-provoca-alagamentos-e-deslizamentos-no-recife.ghtml",
        "link_label": "G1 — chuvas e inundações (2020)",
        "impacto_nota": "Estimativas territoriais Sinidu+Clima.",
    },
    {
        "tipo": "Alagamento Urbano",
        "data": datetime.date(2021, 8, 17),
        "afetados": 4200,
        "danos": 3_200_000.0,
        "lng": -34.9045,
        "lat": -8.1198,
        "referencia": "Afogados / Cidade Universitária",
        "descricao": (
            "Alagamento urbano em Afogados / Cidade Universitária por chuva concentrada "
            "e drenagem saturada; impacto em campus e vias arteriais."
        ),
        "medidas": (
            "Operação de drenagem; sinalização e desvio; limpeza de galerias; "
            "apoio a pedestres e transporte."
        ),
        "mortos": 0,
        "feridos": 3,
        "desalojados": 60,
        "desabrigados": 15,
        "prejudicados": 4200,
        "custo_resposta_estimado": 1_200_000.0,
        "link_noticia": "https://g1.globo.com/pe/pernambuco/noticia/2021/08/chuva-causa-alagamentos-em-varios-bairros-do-recife.ghtml",
        "link_label": "G1 — alagamentos (ago/2021)",
        "impacto_nota": "Estimativas Sinidu+Clima.",
    },
    {
        "tipo": "Inundação",
        "data": datetime.date(2017, 6, 20),
        "afetados": 6500,
        "danos": 18_000_000.0,
        "lng": -34.8721,
        "lat": -8.0812,
        "referencia": "Coque / Tejipió — cheias do Capibaribe",
        "descricao": (
            "Inundação em Coque / Tejipió associada à cheia do Capibaribe; "
            "comunidades de baixa renda fortemente atingidas."
        ),
        "medidas": (
            "Abrigos; assistência social; limpeza e desinfecção; "
            "reforço de contenção em pontos críticos."
        ),
        "mortos": 1,
        "feridos": 25,
        "desalojados": 1100,
        "desabrigados": 280,
        "prejudicados": 6500,
        "custo_resposta_estimado": 6_000_000.0,
        "link_noticia": "https://g1.globo.com/pernambuco/noticia/2017/06/chuva-causa-alagamentos-e-deslizamentos-no-recife.ghtml",
        "link_label": "G1 — chuvas no Recife (2017)",
        "impacto_nota": "Óbito e desalojados estimados a partir de balanços da época.",
    },
    {
        "tipo": "Alagamento Urbano",
        "data": datetime.date(2019, 4, 3),
        "afetados": 5000,
        "danos": 12_000_000.0,
        "lng": -34.9188,
        "lat": -8.0456,
        "referencia": "Derby / Torre — chuvas de abril/2019",
        "descricao": (
            "Alagamentos no eixo Derby / Torre após chuvas de abril/2019; "
            "vias alagadas e interrupção de serviços."
        ),
        "medidas": (
            "Equipes emergenciais; bombas; isolamento de vias; "
            "comunicação à população via Defesa Civil."
        ),
        "mortos": 0,
        "feridos": 6,
        "desalojados": 120,
        "desabrigados": 30,
        "prejudicados": 5000,
        "custo_resposta_estimado": 3_500_000.0,
        "link_noticia": "https://g1.globo.com/pe/pernambuco/noticia/2019/04/chuva-causa-alagamentos-no-recife.ghtml",
        "link_label": "G1 — alagamentos (abr/2019)",
        "impacto_nota": "Estimativas Sinidu+Clima.",
    },
    {
        "tipo": "Inundação",
        "data": datetime.date(2022, 5, 25),
        "afetados": 15000,
        "danos": 55_000_000.0,
        "lng": -34.8817,
        "lat": -8.0476,
        "referencia": "Chuvas históricas maio/2022 — SE reconhecida (S2ID)",
        "descricao": (
            "Início do episódio extremo de maio/2022: volumes pluviais excepcionais na RMR, "
            "inundações generalizadas e reconhecimento de Situação de Emergência no S2ID. "
            "Precede os deslizamentos fatais de 28/05."
        ),
        "medidas": (
            "Decreto de SE; mobilização estadual/federal; abrigos; "
            "cadastro S2ID para recursos de resposta e reconstrução."
        ),
        "mortos": 5,
        "feridos": 90,
        "desalojados": 10000,
        "desabrigados": 4000,
        "prejudicados": 15000,
        "custo_resposta_estimado": 55_000_000.0,
        "link_noticia": "https://www.dw.com/pt-br/chuvas-no-recife-foi-como-um-tsunami-que-arrastou-tudo-pela-frente/a-61986769",
        "link_label": "DW — chuvas no Recife (maio/2022)",
        "impacto_nota": "Custos e afetados estimados; mortos parciais do início do episódio.",
    },
    {
        "tipo": "Deslizamento de Terra",
        "data": datetime.date(2022, 5, 27),
        "afetados": 2500,
        "danos": 8_000_000.0,
        "lng": -34.9350,
        "lat": -8.0050,
        "referencia": "Passarinho / Alto José do Pinho — maio/2022",
        "descricao": (
            "Deslizamentos e risco de barreira em Passarinho / Alto José do Pinho durante "
            "as chuvas de maio/2022; remoções e monitoramento contínuo."
        ),
        "medidas": (
            "Remoção de famílias; cercamento de áreas; busca ativa; "
            "cadastro habitacional emergencial."
        ),
        "mortos": 2,
        "feridos": 20,
        "desalojados": 600,
        "desabrigados": 180,
        "prejudicados": 2500,
        "custo_resposta_estimado": 8_000_000.0,
        "link_noticia": "https://g1.globo.com/pe/pernambuco/noticia/2022/05/28/grande-recife-tem-mais-mortes-em-deslizamentos-de-barreiras-devido-as-fortes-chuvas.ghtml",
        "link_label": "G1 — mortes em barreiras (maio/2022)",
        "impacto_nota": "Foco zonal estimado dentro do episódio estadual.",
    },
]

# Aracaju — eventos documentados (Defesa Civil de Aracaju / Semdec; imprensa local)
ARACAJU_S2ID_EVENTS: list[dict[str, Any]] = [
    {
        "tipo": "Inundação",
        "data": datetime.date(2022, 7, 10),
        "afetados": 900,
        "danos": 4_000_000.0,
        "lng": -37.098,
        "lat": -10.945,
        "referencia": "Jabotiana / Largo da Aparecida — cheia do Rio Poxim Mirim (jul/2022, 231 mm/72h)",
    },
    {
        "tipo": "Alagamento Urbano",
        "data": datetime.date(2022, 7, 8),
        "afetados": 500,
        "danos": 1_500_000.0,
        "lng": -37.075,
        "lat": -10.990,
        "referencia": "Santa Maria / Lamarão — alagamentos das chuvas de julho/2022 (Defesa Civil de Aracaju)",
    },
    {
        "tipo": "Alagamento Urbano",
        "data": datetime.date(2022, 7, 11),
        "afetados": 400,
        "danos": 1_200_000.0,
        "lng": -37.101,
        "lat": -10.949,
        "referencia": "Conjuntos Sol Nascente / Santa Lúcia / JK (Jabotiana) — cheia do Poxim Mirim (jul/2022)",
    },
]

# Salvador — eventos documentados (Codesal / imprensa)
SALVADOR_S2ID_EVENTS: list[dict[str, Any]] = [
    {
        "tipo": "Deslizamento de Terra",
        "data": datetime.date(2019, 11, 26),
        "afetados": 1200,
        "danos": 3_500_000.0,
        "lng": -38.452,
        "lat": -12.934,
        "referencia": "Chuvas de nov/2019 — 114 deslizamentos e ~300 desalojados (Codesal)",
    },
    {
        "tipo": "Deslizamento de Terra",
        "data": datetime.date(2022, 4, 15),
        "afetados": 1454,
        "danos": 8_000_000.0,
        "lng": -38.435,
        "lat": -12.921,
        "referencia": "Operação Chuva 2022 (mar–jun) — 3.650 deslizamentos, 1.454 cadastros (Codesal)",
    },
    {
        "tipo": "Alagamento Urbano",
        "data": datetime.date(2019, 11, 26),
        "afetados": 600,
        "danos": 1_800_000.0,
        "lng": -38.501,
        "lat": -12.971,
        "referencia": "Chuvas de nov/2019 — 122 imóveis alagados, 9 alagamentos de vias (Codesal)",
    },
]

# Rio de Janeiro — eventos documentados (Alerta Rio / Defesa Civil / imprensa)
RIO_S2ID_EVENTS: list[dict[str, Any]] = [
    {
        "tipo": "Inundação",
        "data": datetime.date(2019, 4, 8),
        "afetados": 10000,
        "danos": 40_000_000.0,
        "lng": -43.224,
        "lat": -22.968,
        "referencia": "Temporal de 8–9/abr/2019 — 10 mortos; maior chuva em 22 anos (Jardim Botânico 155 mm)",
    },
    {
        "tipo": "Deslizamento de Terra",
        "data": datetime.date(2019, 2, 6),
        "afetados": 6000,
        "danos": 15_000_000.0,
        "lng": -43.243,
        "lat": -22.997,
        "referencia": "Chuvas de 6/fev/2019 — 6 mortos; deslizamento na Av. Niemeyer (Vidigal/São Conrado)",
    },
    {
        "tipo": "Inundação",
        "data": datetime.date(2020, 3, 2),
        "afetados": 4000,
        "danos": 10_000_000.0,
        "lng": -43.553,
        "lat": -22.902,
        "referencia": "Chuvas de mar/2020 — 4 mortos; maiores impactos na Zona Oeste (Jardim Maravilha)",
    },
]

# São Paulo — eventos documentados (CGE / Defesa Civil estadual / imprensa)
SAO_PAULO_S2ID_EVENTS: list[dict[str, Any]] = [
    {
        "tipo": "Inundação",
        "data": datetime.date(2020, 2, 10),
        "afetados": 2000,
        "danos": 21_000_000.0,
        "lng": -46.620,
        "lat": -23.516,
        "referencia": "Fev/2020 — transbordamento do Tietê; maior chuva de fevereiro em 37 anos (114 mm); Ceagesp alagada",
    },
    {
        "tipo": "Alagamento Urbano",
        "data": datetime.date(2020, 2, 10),
        "afetados": 700,
        "danos": 5_000_000.0,
        "lng": -46.700,
        "lat": -23.580,
        "referencia": "Fev/2020 — transbordamento da Marginal Pinheiros; 85 pontos de alagamento na capital",
    },
]

# Brasília / DF — eventos documentados (Defesa Civil do DF / imprensa)
BRASILIA_S2ID_EVENTS: list[dict[str, Any]] = [
    {
        "tipo": "Deslizamento de Terra",
        "data": datetime.date(2019, 12, 10),
        "afetados": 50,
        "danos": 2_000_000.0,
        "lng": -47.917,
        "lat": -15.826,
        "referencia": "Dez/2019 — cratera de 10 m na 709/909 Sul (Asa Sul); solo cedeu após ruptura de galeria pluvial",
    },
    {
        "tipo": "Alagamento Urbano",
        "data": datetime.date(2018, 11, 16),
        "afetados": 200,
        "danos": 1_500_000.0,
        "lng": -48.020,
        "lat": -15.800,
        "referencia": "Nov/2018 — crateras em Vicente Pires e alagamento do metrô de Samambaia (Córrego Samambaia transbordou)",
    },
]

_PILOT_EVENTS: dict[str, list[dict[str, Any]]] = {
    "2611606": RECIFE_S2ID_EVENTS,
    "2800308": ARACAJU_S2ID_EVENTS,
    "2927408": SALVADOR_S2ID_EVENTS,
    "3304557": RIO_S2ID_EVENTS,
    "3550308": SAO_PAULO_S2ID_EVENTS,
    "5300108": BRASILIA_S2ID_EVENTS,
}

_SYNTHETIC_PLACEHOLDER_DANOS = 250_000.0


def _event_lookup_key(data_ocorrencia, tipo: str) -> str:
    return f"{str(data_ocorrencia)[:10]}|{str(tipo or '').strip().casefold()}"


def build_s2id_enrichment_index(codigo_ibge: str | None = None) -> dict[str, dict[str, Any]]:
    """Índice data|tipo → detalhes do popup (pilotos curados)."""
    out: dict[str, dict[str, Any]] = {}
    sources = (
        [_PILOT_EVENTS[codigo_ibge]]
        if codigo_ibge and codigo_ibge in _PILOT_EVENTS
        else list(_PILOT_EVENTS.values())
    )
    for events in sources:
        for ev in events:
            key = _event_lookup_key(ev.get("data"), str(ev.get("tipo") or ""))
            out[key] = ev
    return out


def enrich_s2id_feature_props(
    *,
    tipo_desastre: str,
    data_ocorrencia,
    populacao_afetada: int | None,
    danos_materiais: float | None,
    referencia: str | None,
    data_quality: str | None,
    fonte: str | None,
    enrichment: dict[str, dict[str, Any]] | None = None,
    eventos_municipio: int | None = None,
) -> dict[str, Any]:
    """Monta properties do GeoJSON de desastres com narrativa/impacto para o popup."""
    key = _event_lookup_key(data_ocorrencia, tipo_desastre)
    extra = (enrichment or {}).get(key) or {}

    mortos = extra.get("mortos")
    feridos = extra.get("feridos")
    desalojados = extra.get("desalojados")
    desabrigados = extra.get("desabrigados")
    prejudicados = extra.get("prejudicados", populacao_afetada)
    custo = extra.get("custo_resposta_estimado", danos_materiais)
    local = extra.get("referencia") or referencia

    props: dict[str, Any] = {
        "tipo_desastre": tipo_desastre,
        "data_ocorrencia": str(data_ocorrencia)[:10] if data_ocorrencia else None,
        "populacao_afetada": int(populacao_afetada or 0),
        "danos_materiais": float(danos_materiais or 0),
        "custo_resposta_estimado": float(custo or 0) if custo is not None else None,
        "referencia": local,
        "local": local,
        "descricao": extra.get("descricao"),
        "medidas": extra.get("medidas"),
        "mortos": int(mortos) if mortos is not None else None,
        "feridos": int(feridos) if feridos is not None else None,
        "desalojados": int(desalojados) if desalojados is not None else None,
        "desabrigados": int(desabrigados) if desabrigados is not None else None,
        "prejudicados": int(prejudicados) if prejudicados is not None else None,
        "link_noticia": extra.get("link_noticia"),
        "link_label": extra.get("link_label") or "Matéria / balanço público",
        "impacto_nota": extra.get("impacto_nota"),
        "data_quality": data_quality,
        "fonte": fonte,
        "ano_referencia": int(str(data_ocorrencia)[:4]) if data_ocorrencia else None,
        "eventos_municipio": eventos_municipio,
        "fonte_referencia": "S2ID / Secretaria Nacional de Proteção e Defesa Civil",
        "qualidade_dado": (
            "Oficial"
            if (data_quality or "").startswith("oficial")
            else "Estimado"
        ),
        "detalhe_completo": bool(extra.get("descricao")),
    }
    return props


def needs_s2id_refresh(db: Session, muni: Municipio) -> bool:
    """Detecta placeholder único ou base desatualizada em relação ao piloto."""
    rows = (
        db.query(HistoricoDesastreS2ID)
        .filter(HistoricoDesastreS2ID.municipio_id == muni.id)
        .all()
    )
    if not rows:
        return True
    if len(rows) == 1 and float(rows[0].danos_materiais or 0) == _SYNTHETIC_PLACEHOLDER_DANOS:
        return True
    pilot = _PILOT_EVENTS.get(muni.codigo_ibge)
    if pilot and len(rows) < len(pilot):
        return True
    return False


def s2id_quality_label(db: Session, muni: Municipio) -> str:
    """Rótulo de qualidade para KPIs executivos."""
    if muni.codigo_ibge in _PILOT_EVENTS:
        count = (
            db.query(HistoricoDesastreS2ID)
            .filter(HistoricoDesastreS2ID.municipio_id == muni.id)
            .count()
        )
        if count >= len(_PILOT_EVENTS[muni.codigo_ibge]):
            return "oficial"
    count = (
        db.query(HistoricoDesastreS2ID)
        .filter(HistoricoDesastreS2ID.municipio_id == muni.id)
        .count()
    )
    return "estimado" if count > 1 else "derivado"


def ensure_s2id_loaded(db: Session, muni: Municipio, *, risk: str = "inundacao") -> dict[str, Any] | None:
    """Garante eventos S2ID atualizados antes de KPIs ou camadas."""
    if not needs_s2id_refresh(db, muni):
        return None
    return collect_s2id_municipality(db, muni.codigo_ibge, force=True, risk=risk)


def _events_for_municipality(db: Session, muni: Municipio, risk: str = "inundacao") -> list[dict[str, Any]]:
    pilot = _PILOT_EVENTS.get(muni.codigo_ibge)
    if pilot:
        return pilot

    bairros = db.query(Bairro).filter(Bairro.municipio_id == muni.id).all()
    if not bairros:
        poly = shape(json.loads(db.scalar(muni.geom.ST_AsGeoJSON())))
        centroid = poly.centroid
        disaster_type = "Deslizamento" if risk == "encosta" else "Inundação"
        return [{
            "tipo": disaster_type,
            "data": datetime.date(2022, 3, 15),
            "afetados": max(500, muni.populacao // 200),
            "danos": 250_000.0,
            "lng": centroid.x,
            "lat": centroid.y,
            "referencia": "Registro sintético (centroide municipal)",
            "data_quality": "estimado",
            "fonte": "sintetico",
        }]

    templates = (
        ["Deslizamento de Terra", "Deslizamento de Terra", "Inundação", "Alagamento Urbano"]
        if risk == "encosta"
        else ["Inundação", "Alagamento Urbano", "Inundação", "Alagamento Urbano", "Deslizamento de Terra"]
    )
    years = [2024, 2023, 2022, 2021, 2020]
    events: list[dict[str, Any]] = []
    for idx, bairro in enumerate(bairros[: min(len(bairros), len(templates))]):
        cell = shape(json.loads(db.scalar(bairro.geom.ST_AsGeoJSON())))
        pt = cell.centroid
        events.append({
            "tipo": templates[idx % len(templates)],
            "data": datetime.date(years[idx % len(years)], (idx % 6) + 3, 10 + idx),
            "afetados": max(300, muni.populacao // (len(bairros) * 25)),
            "danos": 500_000.0 + (idx * 750_000),
            "lng": pt.x,
            "lat": pt.y,
            "referencia": f"Estimativa territorial — {bairro.nome}",
            "data_quality": "estimado",
            "fonte": "sintetico",
        })
    return events


def collect_s2id_municipality(
    db: Session,
    codigo_ibge: str,
    *,
    force: bool = False,
    risk: str = "inundacao",
) -> dict[str, Any]:
    """Sincroniza eventos S2ID no PostGIS. Substitui placeholder único no centroide."""
    code = str(codigo_ibge).strip().zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        return {"codigo_ibge": code, "skipped": True, "reason": "municipio_nao_encontrado"}

    existing = (
        db.query(HistoricoDesastreS2ID)
        .filter(HistoricoDesastreS2ID.municipio_id == muni.id)
        .count()
    )
    is_pilot = code in _PILOT_EVENTS
    data_quality = "oficial_curado" if is_pilot else "estimado"

    if existing > 1 and not force and not needs_s2id_refresh(db, muni):
        return {
            "codigo_ibge": code,
            "skipped": True,
            "records": existing,
            "data_quality": data_quality,
        }

    if existing >= 1:
        db.query(HistoricoDesastreS2ID).filter(
            HistoricoDesastreS2ID.municipio_id == muni.id
        ).delete(synchronize_session=False)

    events = _events_for_municipality(db, muni, risk=risk)
    for item in events:
        quality = item.get("data_quality") or data_quality
        fonte = item.get("fonte") or ("s2id_curado" if is_pilot else "sintetico")
        db.add(
            HistoricoDesastreS2ID(
                municipio_id=muni.id,
                tipo_desastre=item["tipo"],
                data_ocorrencia=item["data"],
                populacao_afetada=int(item["afetados"]),
                danos_materiais=float(item["danos"]),
                data_quality=quality,
                fonte=fonte,
                referencia=(item.get("referencia") or "")[:255] or None,
                geom=from_shape(Point(item["lng"], item["lat"]), srid=4326),
            )
        )
    db.commit()

    # Propaga eventos oficiais para ground truth ML (21c.5)
    try:
        from app.services.evento_alagamento_service import sync_official_s2id_to_observed_events

        sync_official_s2id_to_observed_events(db, code)
    except Exception as exc:
        logger.warning("Sync evento_alagamento_observado %s: %s", code, exc)

    logger.info("S2ID sync %s: %d evento(s) (%s)", code, len(events), data_quality)
    return {
        "codigo_ibge": code,
        "skipped": False,
        "records": len(events),
        "data_quality": data_quality,
        "pilot": is_pilot,
        "eventos": [
            {
                "tipo": e["tipo"],
                "data": str(e["data"]),
                "referencia": e.get("referencia"),
                "data_quality": e.get("data_quality") or data_quality,
            }
            for e in events
        ],
    }
