from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Municipio
from app.schemas import (
    AIProviderOption,
    AIProvidersResponse,
    AIProvidersStatusRequest,
    AIProviderTestRequest,
    AIProviderTestResponse,
    ChatRequest,
    ChatResponse,
    ContextualChatRequest,
    CasoSucessoOut,
    MunicipalAssistantContext,
    MunicipalDataSource,
    RagSource,
)
from app.services.municipal_assistant_context import build_municipal_assistant_context
from app.services.contextual_agent_service import contextual_chat_stream, contextual_chat_sync
from rag.chat import rag_assistant
from rag.providers.registry import (
    default_chat_provider_id,
    list_chat_providers,
    test_chat_provider,
)
from app.security.municipio_access import get_accessible_municipio
from typing import List
import json
from shapely.geometry import shape

router = APIRouter()


def municipality_focus(db: Session, muni: Municipio):
    geom = shape(json.loads(db.scalar(muni.geom.ST_AsGeoJSON())))
    centroid = geom.centroid
    return [round(centroid.y, 5), round(centroid.x, 5)]


@router.get("/providers", response_model=AIProvidersResponse)
def list_ai_providers():
    """Lista provedores de LLM (disponibilidade via env/server)."""
    providers = [AIProviderOption(**p.__dict__) for p in list_chat_providers()]
    return AIProvidersResponse(
        default_provider=default_chat_provider_id(),
        providers=providers,
    )


@router.post("/providers/status", response_model=AIProvidersResponse)
def providers_status(payload: AIProvidersStatusRequest):
    """Atualiza disponibilidade considerando API keys informadas pelo usuário."""
    providers = [AIProviderOption(**p.__dict__) for p in list_chat_providers(payload.api_keys)]
    return AIProvidersResponse(
        default_provider=default_chat_provider_id(),
        providers=providers,
    )


@router.post("/providers/test", response_model=AIProviderTestResponse)
def test_ai_provider(payload: AIProviderTestRequest):
    """Testa conexão instantânea com o LLM usando API key do usuário."""
    result = test_chat_provider(
        payload.ai_provider,
        api_key=payload.ai_api_key,
        model=payload.ai_model,
    )
    return AIProviderTestResponse(**result)


@router.get("/municipal/{codigo_ibge}/context", response_model=MunicipalAssistantContext)
def get_municipal_assistant_context(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    return build_municipal_assistant_context(db, muni)


@router.get("/municipal/{codigo_ibge}/suggestions")
def get_municipal_suggestions(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    ctx = build_municipal_assistant_context(db, muni)
    return {"suggestions": ctx.get("suggested_questions") or []}


@router.post("/chat", response_model=ChatResponse)
def assistant_chat(payload: ChatRequest, request: Request, db: Session = Depends(get_db)):
    muni = get_accessible_municipio(db, payload.codigo_ibge, request=request)
    history = [{"role": h.role, "content": h.content} for h in payload.history]
    result = rag_assistant.chat(
        db,
        muni,
        payload.message,
        history,
        ai_provider=payload.ai_provider,
        ai_model=payload.ai_model,
        ai_api_key=payload.ai_api_key,
    )

    coords = result.get("coordinates")
    if result.get("suggested_layer") and not coords:
        coords = municipality_focus(db, muni)

    rag_sources = [RagSource(**src) for src in result.get("rag_sources", [])]
    municipal_sources = [MunicipalDataSource(**src) for src in result.get("municipal_sources", [])]

    from app.services.layer_crosswalk_service import recommend_layer_crosswalk

    cross = recommend_layer_crosswalk(payload.message, cod_ibge=muni.codigo_ibge)
    layers = result.get("recommended_layers") or cross.get("recommended_layers")
    suggested = result.get("suggested_layer")
    if not suggested and layers:
        suggested = next((L for L in layers if L not in ("bairros", "municipio")), layers[0])

    return ChatResponse(
        response=result["response"],
        suggested_layer=suggested,
        recommended_layers=layers,
        crosswalk_rationale=cross.get("rationale"),
        coordinates=coords,
        zoom=result.get("zoom", 13),
        source_url=result.get("source_url"),
        rag_sources=rag_sources,
        municipal_sources=municipal_sources,
        suggested_questions=result.get("suggested_questions") or [],
        response_time_ms=result.get("response_time_ms"),
        ai_provider=result.get("ai_provider"),
        ai_model=result.get("ai_model"),
    )


@router.post("/municipal/{codigo_ibge}/prewarm")
def prewarm_municipal_agent_context(
    codigo_ibge: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Pré-aquece bundle de contexto do agente Sinidu (background)."""
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    from app.services.contextual_agent_prewarm import prewarm_agent_bundle

    prewarm_agent_bundle(muni.codigo_ibge)
    return {"codigo_ibge": muni.codigo_ibge, "status": "scheduled"}


@router.post("/chat-contextual")
def assistant_chat_contextual(payload: ContextualChatRequest, request: Request, db: Session = Depends(get_db)):
    """Agente contextual com dados da página e function calling Mistral."""
    muni = get_accessible_municipio(db, payload.municipio_codigo, request=request)
    history = [{"role": h.role, "content": h.content} for h in payload.historico]
    descricao = payload.descricao_pagina or f"Módulo {payload.pagina_atual}"

    if payload.stream:
        generator = contextual_chat_stream(
            db,
            muni,
            message=payload.message,
            pagina_atual=payload.pagina_atual,
            descricao_pagina=descricao,
            dados_pagina=payload.dados_pagina,
            historico=history,
            ai_provider=payload.ai_provider,
            ai_model=payload.ai_model,
            ai_api_key=payload.ai_api_key,
        )
        return StreamingResponse(generator, media_type="text/event-stream")

    result = contextual_chat_sync(
        db,
        muni,
        message=payload.message,
        pagina_atual=payload.pagina_atual,
        descricao_pagina=descricao,
        dados_pagina=payload.dados_pagina,
        historico=history,
        ai_provider=payload.ai_provider,
        ai_model=payload.ai_model,
        ai_api_key=payload.ai_api_key,
    )
    from app.services.layer_crosswalk_service import recommend_layer_crosswalk

    cross = result.get("crosswalk") or recommend_layer_crosswalk(
        payload.message, cod_ibge=muni.codigo_ibge
    )
    layers = result.get("recommended_layers") or cross.get("recommended_layers")
    suggested = None
    if layers:
        suggested = next((L for L in layers if L not in ("bairros", "municipio")), layers[0])
    return ChatResponse(
        response=result.get("response") or "",
        suggested_layer=suggested,
        recommended_layers=layers,
        crosswalk_rationale=cross.get("rationale"),
        response_time_ms=result.get("response_time_ms"),
        ai_provider=result.get("ai_provider"),
        ai_model=result.get("ai_model"),
    )


@router.get("/eval/retrieval")
def rag_retrieval_eval(db: Session = Depends(get_db)):
    """Avaliação de retrieval RAG contra dataset fixo (sem LLM)."""
    from rag.eval.runner import run_retrieval_eval

    return run_retrieval_eval(db)


@router.get("/cases/search", response_model=List[CasoSucessoOut])
def search_success_cases(q: str = Query(..., min_length=2), db: Session = Depends(get_db)):
    """Busca semântica de casos de sucesso (compatibilidade GET — preferir POST /cases/search)."""
    from app.services.casos_sucesso_service import search_casos

    return search_casos(db, query=q, top_k=10)
