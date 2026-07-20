import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.boot import initialize_database, start_background_jobs
from app.config import settings
from app.middleware.request_metrics import RequestMetricsMiddleware
from app.observability.logging_config import configure_logging
from app.security.auth import authorize_request

configure_logging()
logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            user = authorize_request(request)
            request.state.user = user
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=dict(exc.headers) if exc.headers else {},
            )
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando boot resiliente Sinidu+Clima...")
    initialize_database()
    start_background_jobs()
    yield
    logger.info("Encerrando API.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API for the National Spatial Intelligence Platform (SINIDU)",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(AuthMiddleware)
app.add_middleware(RequestMetricsMiddleware)
if settings.TRUST_PROXY_HEADERS:
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {
        "status": "online",
        "platform": settings.PROJECT_NAME,
        "pilot_city": f"{settings.PILOT_NAME} - {settings.PILOT_UF} ({settings.PILOT_IBGE_CODE})",
        "auth_enabled": settings.AUTH_ENABLED,
    }


from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.indicators import router as indicators_router
from app.api.analytics import router as analytics_router
from app.api.simulations import router as simulations_router
from app.api.assistant import router as assistant_router
from app.api.data_catalog import router as data_catalog_router
from app.api.integrations import router as integrations_router
from app.api.reports import router as reports_router
from app.api.predictions import router as predictions_router
from app.api.terrain import router as terrain_router
from app.api.contingency import router as contingency_router
from app.api.monitoring import router as monitoring_router
from app.api.onboarding import router as onboarding_router
from app.api.maturity import router as maturity_router
from app.api.diagnostic import router as diagnostic_router
from app.api.action_plan import router as action_plan_router
from app.api.cases import router as cases_router
from app.api.audit import router as audit_router
from app.api.system import router as system_router
from app.api.municipios import router as municipios_router
from app.api.routing import router as routing_router
from app.api.map import router as map_router
from app.api.geoportal import router as geoportal_router
from app.services.alert_broadcaster import alert_manager

app.include_router(health_router, tags=["health"])
app.include_router(auth_router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(indicators_router, prefix=f"{settings.API_V1_STR}/indicators", tags=["indicators"])
app.include_router(analytics_router, prefix=f"{settings.API_V1_STR}/analytics", tags=["analytics"])
app.include_router(simulations_router, prefix=f"{settings.API_V1_STR}/simulations", tags=["simulations"])
app.include_router(assistant_router, prefix=f"{settings.API_V1_STR}/assistant", tags=["assistant"])
app.include_router(data_catalog_router, prefix=f"{settings.API_V1_STR}/data-catalog", tags=["data-catalog"])
app.include_router(integrations_router, prefix=f"{settings.API_V1_STR}/integrations", tags=["integrations"])
app.include_router(reports_router, prefix=f"{settings.API_V1_STR}/reports", tags=["reports"])
app.include_router(predictions_router, prefix=f"{settings.API_V1_STR}/predictions", tags=["predictions"])
app.include_router(terrain_router, prefix=f"{settings.API_V1_STR}/terrain", tags=["terrain"])
app.include_router(contingency_router, prefix=f"{settings.API_V1_STR}/contingency", tags=["contingency"])
app.include_router(monitoring_router, prefix=f"{settings.API_V1_STR}/monitoring", tags=["monitoring"])
app.include_router(onboarding_router, prefix=f"{settings.API_V1_STR}/onboarding", tags=["onboarding"])
app.include_router(maturity_router, prefix=f"{settings.API_V1_STR}/maturity", tags=["maturity"])
app.include_router(diagnostic_router, prefix=f"{settings.API_V1_STR}/diagnostic", tags=["diagnostic"])
app.include_router(action_plan_router, prefix=f"{settings.API_V1_STR}/action-plan", tags=["action-plan"])
app.include_router(cases_router, prefix=f"{settings.API_V1_STR}/cases", tags=["cases"])
app.include_router(audit_router, prefix=f"{settings.API_V1_STR}/audit", tags=["audit"])
app.include_router(system_router, prefix=f"{settings.API_V1_STR}/system", tags=["system"])
app.include_router(municipios_router, prefix=f"{settings.API_V1_STR}/municipios", tags=["municipios"])
app.include_router(routing_router, prefix=f"{settings.API_V1_STR}/routing", tags=["routing"])
app.include_router(map_router, prefix=f"{settings.API_V1_STR}/map", tags=["map"])
app.include_router(geoportal_router, prefix=f"{settings.API_V1_STR}/geoportal", tags=["geoportal"])


@app.websocket("/ws/alerts/{codigo_ibge}")
async def websocket_alerts(websocket: WebSocket, codigo_ibge: str):
    await alert_manager.connect(codigo_ibge, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await alert_manager.disconnect(codigo_ibge, websocket)


_dem_static = Path(os.getenv("DEM_DIR", "/data/dem"))
try:
    _dem_static.mkdir(parents=True, exist_ok=True)
except OSError:
    # Host local / pytest sem volume Docker: fallback gravável
    _dem_static = Path(__file__).resolve().parent / ".data" / "dem"
    _dem_static.mkdir(parents=True, exist_ok=True)
app.mount("/static/dem", StaticFiles(directory=str(_dem_static)), name="dem_static")
