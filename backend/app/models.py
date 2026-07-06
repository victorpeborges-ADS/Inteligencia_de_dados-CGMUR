from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, ForeignKey, Text, Index, JSON, Boolean, BigInteger
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from app.db import Base
import datetime

class Municipio(Base):
    __tablename__ = "municipios"

    id = Column(Integer, primary_key=True, index=True)
    codigo_ibge = Column(String(7), unique=True, index=True, nullable=False)
    nome = Column(String(100), nullable=False)
    uf = Column(String(2), nullable=False)
    geom = Column(Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=True))
    populacao = Column(Integer, default=0)
    area_km2 = Column(Numeric(12, 2), default=0.0)

    bairros = relationship("Bairro", back_populates="municipio", cascade="all, delete-orphan")
    setores = relationship("SetorCensitario", back_populates="municipio", cascade="all, delete-orphan")
    desastres = relationship("HistoricoDesastreS2ID", back_populates="municipio", cascade="all, delete-orphan")
    alertas = relationship("AlertaCemaden", back_populates="municipio", cascade="all, delete-orphan")
    cobertura = relationship("CoberturaVegetalMapBiomas", back_populates="municipio", cascade="all, delete-orphan")
    infraestrutura = relationship("InfraestruturaUrbana", back_populates="municipio", cascade="all, delete-orphan")

class Bairro(Base):
    __tablename__ = "bairros"

    id = Column(Integer, primary_key=True, index=True)
    municipio_id = Column(Integer, ForeignKey("municipios.id", ondelete="CASCADE"), nullable=False)
    nome = Column(String(100), nullable=False)
    codigo_bairro = Column(String(15), nullable=True)
    geom = Column(Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=True))
    fonte_malha = Column(String(40), nullable=True)
    fonte_socioeconomico = Column(String(40), nullable=True)
    pop_censo2022 = Column(Integer, nullable=True)
    renda_media_censo2022 = Column(Numeric(12, 2), nullable=True)
    
    # Temporal columns
    valid_from = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    valid_to = Column(DateTime, nullable=True)

    municipio = relationship("Municipio", back_populates="bairros")

class SetorCensitario(Base):
    __tablename__ = "setores_censitarios"

    id = Column(Integer, primary_key=True, index=True)
    municipio_id = Column(Integer, ForeignKey("municipios.id", ondelete="CASCADE"), nullable=False)
    codigo_setor = Column(String(15), unique=True, index=True, nullable=False)
    populacao = Column(Integer, default=0)
    renda_media = Column(Numeric(12, 2), default=0.0)
    fonte_renda = Column(String(40), nullable=True)
    geom = Column(Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=True))
    
    # Temporal columns
    valid_from = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    valid_to = Column(DateTime, nullable=True)

    municipio = relationship("Municipio", back_populates="setores")

class HistoricoDesastreS2ID(Base):
    __tablename__ = "historico_desastres_s2id"

    id = Column(Integer, primary_key=True, index=True)
    municipio_id = Column(Integer, ForeignKey("municipios.id", ondelete="CASCADE"), nullable=False)
    tipo_desastre = Column(String(50), nullable=False) # e.g., Inundacao, Deslizamento
    data_ocorrencia = Column(Date, nullable=False)
    populacao_afetada = Column(Integer, default=0)
    danos_materiais = Column(Numeric(15, 2), default=0.0)
    geom = Column(Geometry(geometry_type="POINT", srid=4326, spatial_index=True))

    municipio = relationship("Municipio", back_populates="desastres")

class AlertaCemaden(Base):
    __tablename__ = "alertas_cemaden"

    id = Column(Integer, primary_key=True, index=True)
    municipio_id = Column(Integer, ForeignKey("municipios.id", ondelete="CASCADE"), nullable=False)
    nivel_alerta = Column(String(20), nullable=False) # BAIXO, MEDIO, ALTO, MUITO_ALTO
    data_alerta = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    descricao = Column(Text, nullable=True)
    geom = Column(Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=True))

    municipio = relationship("Municipio", back_populates="alertas")

class CoberturaVegetalMapBiomas(Base):
    __tablename__ = "cobertura_vegetal_mapbiomas"

    id = Column(Integer, primary_key=True, index=True)
    municipio_id = Column(Integer, ForeignKey("municipios.id", ondelete="CASCADE"), nullable=False)
    ano = Column(Integer, nullable=False)
    classe_uso = Column(String(50), nullable=False) # Floresta, Area Urbana, Agua, etc.
    geom = Column(Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=True))

    municipio = relationship("Municipio", back_populates="cobertura")

class MapBiomasMunicipalStat(Base):
    __tablename__ = "mapbiomas_municipal_stats"

    id = Column(Integer, primary_key=True, index=True)
    codigo_ibge = Column(String(7), index=True, nullable=False)
    municipio_id = Column(Integer, ForeignKey("municipios.id", ondelete="CASCADE"), nullable=True)
    ano = Column(Integer, nullable=False)
    classe_uso = Column(String(80), nullable=False)
    area_ha = Column(Numeric(14, 3), nullable=False)
    colecao = Column(String(32), default="10.1")
    data_quality = Column(String(24), default="derivado")
    fonte = Column(String(255), default="MapBiomas / Sinidu+Clima")
    atualizado_em = Column(DateTime, default=datetime.datetime.utcnow)

    municipio = relationship("Municipio", backref="mapbiomas_stats")

class InfraestruturaUrbana(Base):
    __tablename__ = "infraestrutura_urbana"

    id = Column(Integer, primary_key=True, index=True)
    municipio_id = Column(Integer, ForeignKey("municipios.id", ondelete="CASCADE"), nullable=False)
    tipo = Column(String(50), nullable=False) # via, escola, hospital, etc.
    nome = Column(String(150), nullable=False)
    subgrupo = Column(String(50), nullable=True) # rodovia, atendimento_medico, etc.
    geom = Column(Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=True))

    municipio = relationship("Municipio", back_populates="infraestrutura")

class MunicipioIbge(Base):
    __tablename__ = "municipios_ibge"

    id = Column(Integer, primary_key=True, index=True)
    codigo_ibge = Column(String(7), unique=True, index=True, nullable=False)
    municipio_id = Column(Integer, ForeignKey("municipios.id", ondelete="SET NULL"), nullable=True)
    populacao = Column(Integer)
    populacao_ano = Column(Integer)
    area_km2 = Column(Numeric(12, 3))
    area_ano = Column(Integer)
    pib_per_capita = Column(Numeric(14, 2))
    pib_ano = Column(Integer)
    idh = Column(Numeric(4, 3))
    idh_ano = Column(Integer)
    densidade_demografica = Column(Numeric(12, 2))
    data_quality = Column(String(20), default="oficial")
    fonte = Column(String(255))
    atualizado_em = Column(DateTime)
    raw_payload = Column(Text)


class MunicipioSaneamento(Base):
    __tablename__ = "municipios_saneamento"

    id = Column(Integer, primary_key=True, index=True)
    codigo_ibge = Column(String(7), unique=True, index=True, nullable=False)
    municipio_id = Column(Integer, ForeignKey("municipios.id", ondelete="SET NULL"), nullable=True)
    cobertura_agua_pct = Column(Numeric(6, 2))
    cobertura_esgoto_pct = Column(Numeric(6, 2))
    indice_perdas_agua_pct = Column(Numeric(6, 2))
    indice_atendimento_esgoto_pct = Column(Numeric(6, 2))
    indice_drenagem = Column(Numeric(6, 2))
    ano_referencia = Column(Integer)
    data_quality = Column(String(20), default="oficial")
    fonte = Column(String(255))
    atualizado_em = Column(DateTime)
    raw_payload = Column(Text)


class MunicipioFiscal(Base):
    __tablename__ = "municipios_fiscal"

    id = Column(Integer, primary_key=True, index=True)
    codigo_ibge = Column(String(7), unique=True, index=True, nullable=False)
    municipio_id = Column(Integer, ForeignKey("municipios.id", ondelete="SET NULL"), nullable=True)
    receita_corrente_liquida = Column(Numeric(18, 2))
    despesa_pessoal_pct_rcl = Column(Numeric(8, 4))
    divida_consolidada = Column(Numeric(18, 2))
    resultado_primario = Column(Numeric(18, 2))
    exec_saude = Column(Numeric(18, 2))
    exec_habitacao = Column(Numeric(18, 2))
    exec_saneamento = Column(Numeric(18, 2))
    exec_meio_ambiente = Column(Numeric(18, 2))
    exec_defesa_civil = Column(Numeric(18, 2))
    nota_capag = Column(String(2))
    exercicio = Column(Integer)
    periodo = Column(Integer)
    data_quality = Column(String(20), default="oficial")
    fonte = Column(String(255))
    atualizado_em = Column(DateTime)
    raw_payload = Column(Text)


class IntegrationRun(Base):
    __tablename__ = "integration_runs"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)
    records_count = Column(Integer, default=0)
    last_success_at = Column(DateTime)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class MunicipioFonteExterna(Base):
    __tablename__ = "municipio_fontes_externas"

    id = Column(Integer, primary_key=True, index=True)
    codigo_ibge = Column(String(7), nullable=False, unique=True, index=True)
    municipio_id = Column(Integer, ForeignKey("municipios.id", ondelete="SET NULL"), nullable=True)
    adapta_score = Column(Numeric(8, 4), nullable=True)
    adapta_indicadores = Column(JSON, default=dict)
    adapta_data_quality = Column(String(24), default="ausente")
    geosgb_score = Column(Numeric(8, 4), nullable=True)
    geosgb_indicadores = Column(JSON, default=dict)
    geosgb_data_quality = Column(String(24), default="ausente")
    sirene_emissoes_tco2 = Column(Numeric(14, 2), nullable=True)
    sirene_indicadores = Column(JSON, default=dict)
    sirene_data_quality = Column(String(24), default="ausente")
    brasil_mais_indice = Column(Numeric(8, 4), nullable=True)
    brasil_mais_indicadores = Column(JSON, default=dict)
    brasil_mais_data_quality = Column(String(24), default="ausente")
    fonte_metodo = Column(String(64), default="derivado_sinidu")
    sincronizado_em = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    municipio = relationship("Municipio")


class CasoSucesso(Base):
    __tablename__ = "casos_sucesso"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), nullable=True, index=True)
    titulo = Column(String(255), nullable=False, default="")
    municipio_nome = Column(String(100), nullable=False)
    municipio_uf = Column(String(2), nullable=False)
    # colunas legadas (compatibilidade)
    municipio = Column(String(100), nullable=True)
    uf = Column(String(2), nullable=True)
    populacao_aprox = Column(Integer, nullable=True)
    regiao = Column(String(20), nullable=True, index=True)
    tipo_intervencao = Column(String(100), nullable=True, index=True)
    problema_original = Column(Text, nullable=False)
    solucao_implementada = Column(Text, nullable=False)
    resultado_mensuravel = Column(Text, nullable=True)
    # legado
    problema = Column(Text, nullable=True)
    solucao = Column(Text, nullable=True)
    resultado = Column(Text, nullable=True)
    custo_estimado_reais = Column(BigInteger, nullable=True)
    programa_financiador = Column(String(100), nullable=True)
    ano_implementacao = Column(Integer, nullable=True)
    fonte_referencia = Column(Text, nullable=True)
    tags = Column(ARRAY(String), nullable=True)
    imagem_url = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=True)


class RelatorioMunicipal(Base):
    __tablename__ = "relatorios_municipais"

    id = Column(Integer, primary_key=True, index=True)
    municipio_id = Column(Integer, ForeignKey("municipios.id", ondelete="CASCADE"), nullable=False, index=True)
    codigo_ibge = Column(String(7), nullable=False, index=True)
    nome_arquivo = Column(String(255), nullable=False)
    caminho_arquivo = Column(String(512), nullable=False)
    tamanho_bytes = Column(Integer, default=0)
    status = Column(String(20), default="concluido")  # gerando, concluido, falha
    erro_mensagem = Column(Text, nullable=True)
    sha256_hash = Column(String(64), nullable=True, index=True)
    gerado_em = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    municipio = relationship("Municipio")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), nullable=False, index=True)
    role = Column(String(32), nullable=False)
    action = Column(String(64), nullable=False, index=True)
    resource_type = Column(String(64), nullable=True)
    resource_id = Column(String(64), nullable=True)
    codigo_ibge = Column(String(7), nullable=True, index=True)
    metadata_json = Column("metadata", JSON, default=dict)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)


class DiagnosticoExecutivo(Base):
    __tablename__ = "diagnosticos_executivos"

    id = Column(Integer, primary_key=True, index=True)
    municipio_id = Column(Integer, ForeignKey("municipios.id", ondelete="CASCADE"), nullable=False, index=True)
    codigo_ibge = Column(String(7), nullable=False, index=True)
    versao = Column(Integer, default=1, nullable=False)
    status = Column(String(20), default="concluido")
    headline = Column(Text, nullable=False)
    conteudo = Column(JSON, default=dict)
    narrativa_md = Column(Text, nullable=False)
    narrativa_ia = Column(Text, nullable=True)
    narrativa_ia_meta = Column(JSON, default=dict)
    origem = Column(String(24), default="manual")
    gerado_em = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    municipio = relationship("Municipio")


class PlanoAcaoMunicipal(Base):
    __tablename__ = "planos_acao_municipais"

    id = Column(Integer, primary_key=True, index=True)
    municipio_id = Column(Integer, ForeignKey("municipios.id", ondelete="CASCADE"), nullable=False, index=True)
    codigo_ibge = Column(String(7), nullable=False, index=True)
    versao = Column(Integer, default=1, nullable=False)
    diagnostic_id = Column(Integer, ForeignKey("diagnosticos_executivos.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(20), default="concluido")
    severidade = Column(String(24), nullable=True)
    headline = Column(Text, nullable=True)
    conteudo = Column(JSON, default=dict)
    origem = Column(String(24), default="manual")
    gerado_em = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    municipio = relationship("Municipio")


class RagDocument(Base):
    """Chunks indexados para RAG (pgvector)."""

    __tablename__ = "rag_documents"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(512), nullable=False, index=True)
    source_label = Column(String(256), nullable=False)
    chunk_idx = Column(Integer, nullable=False, default=0)
    content = Column(Text, nullable=False)
    doc_meta = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class MunicipioSeed(Base):
    __tablename__ = "municipios_seed"

    id = Column(Integer, primary_key=True, index=True)
    municipio_id = Column(Integer, ForeignKey("municipios.id", ondelete="SET NULL"), nullable=True, index=True)
    codigo_ibge = Column(String(7), unique=True, index=True, nullable=False)
    nome = Column(String(120), nullable=False)
    uf = Column(String(2), nullable=False)
    criterio = Column(String(40), nullable=False)
    decretos_emergencia = Column(Integer, default=0)
    score_sinidu = Column(Numeric(6, 3), nullable=True)
    score_confiabilidade = Column(String(16), nullable=True)
    malha_fonte = Column(String(40), nullable=True)
    auditoria_flags = Column(JSON, default=dict)
    auditoria_at = Column(DateTime, nullable=True)
    status_carga = Column(String(24), default="pendente")
    onboarding_status = Column(String(24), default="pendente")
    maturity_score = Column(Numeric(6, 2), nullable=True)
    completeness_score = Column(Numeric(6, 2), nullable=True)
    lacunas = Column(JSON, default=list)
    integration_errors = Column(JSON, default=list)
    integration_steps = Column(JSON, default=dict)
    prioridade = Column(Integer, default=0)
    geom_fonte = Column(String(40), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class EstabelecimentoSaude(Base):
    __tablename__ = "estabelecimentos_saude"

    id = Column(Integer, primary_key=True, index=True)
    municipio_id = Column(Integer, ForeignKey("municipios.id", ondelete="CASCADE"), nullable=False, index=True)
    codigo_ibge = Column(String(7), nullable=False, index=True)
    cnes_codigo = Column(String(20), nullable=True)
    nome = Column(String(255), nullable=False)
    tipo = Column(String(40), nullable=False)
    leitos_sus = Column(Integer, default=0)
    esf = Column(Boolean, default=False)
    geom = Column(Geometry(geometry_type="POINT", srid=4326, spatial_index=True))
    fonte = Column(String(80), default="CNES/DataSUS")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    municipio = relationship("Municipio")


class MunicipioSaude(Base):
    __tablename__ = "municipios_saude"

    id = Column(Integer, primary_key=True, index=True)
    codigo_ibge = Column(String(7), unique=True, index=True, nullable=False)
    mortalidade_causas_externas = Column(Numeric(10, 2), nullable=True)
    taxa_afogamento = Column(Numeric(10, 4), nullable=True)
    taxa_desabamento = Column(Numeric(10, 4), nullable=True)
    cobertura_esf = Column(Numeric(6, 3), nullable=True)
    ubs_count = Column(Integer, default=0)
    caps_count = Column(Integer, default=0)
    hospital_count = Column(Integer, default=0)
    leitos_sus_total = Column(Integer, default=0)
    cobertura_saude_score = Column(Numeric(6, 3), nullable=True)
    ano_ref = Column(Integer, nullable=True)
    lacunas = Column(JSON, default=list)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class MunicipioSeguranca(Base):
    __tablename__ = "municipios_seguranca"

    id = Column(Integer, primary_key=True, index=True)
    codigo_ibge = Column(String(7), nullable=False, index=True)
    mes_ref = Column(String(7), nullable=False)
    ocorrencias_violentas = Column(Integer, default=0)
    mortes_violentas = Column(Integer, default=0)
    roubos = Column(Integer, default=0)
    taxa_100k = Column(Numeric(10, 2), nullable=True)
    cobertura_seguranca_score = Column(Numeric(6, 3), nullable=True)
    fonte = Column(String(80), default="SINESP/dados.gov.br")
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class ContingencyPlan(Base):
    __tablename__ = "contingency_plans"

    id = Column(Integer, primary_key=True, index=True)
    municipio_id = Column(Integer, ForeignKey("municipios.id", ondelete="CASCADE"), nullable=False, index=True)
    cenario_tipo = Column(String(20), nullable=False)  # INUNDACAO | DESLIZAMENTO | MULTIPLO
    nivel_alerta = Column(String(10), nullable=False, default="VERDE")
    data_criacao = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    data_revisao = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    criado_por = Column(String(120), default="sistema")
    zonas_evacuacao = Column(JSON, default=list)
    rotas_fuga = Column(JSON, default=list)
    pontos_apoio = Column(JSON, default=list)
    contatos_defesa_civil = Column(JSON, default=list)
    acoes_por_nivel = Column(JSON, default=dict)
    status = Column(String(20), default="RASCUNHO")  # RASCUNHO | ATIVO | ARQUIVADO
    versao = Column(Integer, default=1)
    simulacao_ref = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    municipio = relationship("Municipio")
    revisions = relationship("ContingencyPlanRevision", back_populates="plan", cascade="all, delete-orphan")


class ContingencyPlanRevision(Base):
    __tablename__ = "contingency_plan_revisions"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("contingency_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    versao = Column(Integer, nullable=False)
    snapshot = Column(JSON, nullable=False)
    revisado_em = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    revisado_por = Column(String(120), default="sistema")

    plan = relationship("ContingencyPlan", back_populates="revisions")


class MonitoringAlert(Base):
    __tablename__ = "monitoring_alerts"

    id = Column(Integer, primary_key=True, index=True)
    municipio_id = Column(Integer, ForeignKey("municipios.id", ondelete="SET NULL"), nullable=True)
    codigo_ibge = Column(String(7), nullable=False, index=True)
    tipo = Column(String(30), nullable=False)  # CEMADEN_ALERT | RISK_THRESHOLD | WEATHER_UPDATE
    nivel = Column(String(20), nullable=False, default="VERDE")
    titulo = Column(String(255), nullable=False)
    mensagem = Column(Text, nullable=True)
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=True)


class WeatherForecastCache(Base):
    __tablename__ = "weather_forecast_cache"

    id = Column(Integer, primary_key=True, index=True)
    codigo_ibge = Column(String(7), nullable=False, index=True)
    lat = Column(Numeric(10, 6), nullable=True)
    lng = Column(Numeric(10, 6), nullable=True)
    precip_24h_mm = Column(Numeric(8, 2), default=0)
    precip_72h_mm = Column(Numeric(8, 2), default=0)
    risk_probability = Column(Numeric(5, 4), default=0)
    raw_payload = Column(JSON, nullable=True)
    fetched_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
