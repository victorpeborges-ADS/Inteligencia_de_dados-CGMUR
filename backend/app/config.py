import os


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default).lower()).lower() in ("1", "true", "yes", "on")


def _env_ibge_list(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return list(default)
    codes: list[str] = []
    seen: set[str] = set()
    for part in raw.replace(";", ",").split(","):
        code = part.strip().zfill(7)[:7]
        if code.isdigit() and len(code) == 7 and code not in seen:
            seen.add(code)
            codes.append(code)
    return codes or list(default)


class Settings:
    PROJECT_NAME: str = "Sinidu+Clima - Plataforma Nacional de Inteligência Territorial"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://sinidu_user:sinidu_pass@localhost:5432/sinidu_db"
    )
    
    # Pilot City Configuration
    PILOT_IBGE_CODE: str = "2611606" # Recife - PE
    PILOT_NAME: str = "Recife"
    PILOT_UF: str = "PE"

    # Municípios sincronizados/carregados no boot (resto sob demanda ou scheduler semanal)
    BOOT_PRIORITY_IBGE_CODES: list[str] = _env_ibge_list(
        "BOOT_PRIORITY_IBGE_CODES",
        ["2611606", "2800308"],  # Recife, Aracaju
    )
    # Malhas sintéticas extras (Caroebe, Salvador, …) — desligado por padrão para boot leve
    SEED_DEMO_MUNICIPALITIES: bool = _env_bool("SEED_DEMO_MUNICIPALITIES", False)
    # Pré-aquecimento de simulação pluvial (cache Redis) para demo/officina
    SIMULATION_PREWARM_ENABLED: bool = _env_bool("SIMULATION_PREWARM_ENABLED", True)
    SIMULATION_PREWARM_MM: float = float(os.getenv("SIMULATION_PREWARM_MM", "120"))
    SIMULATION_PREWARM_BASELINE_MM: float = float(os.getenv("SIMULATION_PREWARM_BASELINE_MM", "80"))
    DEM_PREWARM_ENABLED: bool = _env_bool("DEM_PREWARM_ENABLED", True)
    STALE_JOB_HOURS: int = int(os.getenv("STALE_JOB_HOURS", "6"))

    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")

    # Catálogo piloto — espelho de app.data_connectors.constants.TARGET_IBGE_CODES
    TARGET_IBGE_CODES: list[str] = [
        "2611606",  # Recife
        "2800308",  # Aracaju
        "2927408",  # Salvador
        "3550308",  # São Paulo
        "3304557",  # Rio de Janeiro
        "5300108",  # Brasília
        "2603603",  # Camutanga (PE LiDAR / PE3D)
        "2607604",  # Ilha de Itamaracá (PE LiDAR / PE3D)
    ]

    REPORTS_DIR: str = os.getenv("REPORTS_DIR", "/data/reports")
    MODELS_DIR: str = os.getenv("MODELS_DIR", "/data/models")
    ML_DATA_DIR: str = os.getenv("ML_DATA_DIR", "/data/ml")
    CEMADEN_PLUVIO_DIR: str = os.getenv("CEMADEN_PLUVIO_DIR", "/data/cemaden_pluvio")
    DEM_DIR: str = os.getenv("DEM_DIR", "/data/dem")
    LOCAL_DEM_DIR: str = os.getenv("LOCAL_DEM_DIR", "/data/dem/local")
    CITYMODEL_DIR: str = os.getenv("CITYMODEL_DIR", "/data/citymodels")
    TILES3D_DIR: str = os.getenv("TILES3D_DIR", "/data/3dtiles")
    IBGE_MESH_CACHE_DIR: str = os.getenv("IBGE_MESH_CACHE_DIR", "/data/ibge/censo_2022")
    REFINE_PILOT_DEM: bool = _env_bool("REFINE_PILOT_DEM", True)
    GOOGLE_MAPS_API_KEY: str = os.getenv("GOOGLE_MAPS_API_KEY", "")

    # Autenticação (desligada por padrão em dev)
    AUTH_ENABLED: bool = _env_bool("AUTH_ENABLED", False)
    AUTH_JWT_SECRET: str = os.getenv("AUTH_JWT_SECRET", "sinidu-dev-secret-trocar-em-producao")
    AUTH_ADMIN_USER: str = os.getenv("AUTH_ADMIN_USER", "admin")
    AUTH_ADMIN_PASSWORD: str = os.getenv("AUTH_ADMIN_PASSWORD", "admin")
    AUTH_GESTOR_USER: str = os.getenv("AUTH_GESTOR_USER", "gestor")
    AUTH_GESTOR_PASSWORD: str = os.getenv("AUTH_GESTOR_PASSWORD", "gestor")
    AUTH_LEITOR_USER: str = os.getenv("AUTH_LEITOR_USER", "leitor")
    AUTH_LEITOR_PASSWORD: str = os.getenv("AUTH_LEITOR_PASSWORD", "leitor")
    AUTH_PASSWORD_LOGIN_ENABLED: bool = _env_bool("AUTH_PASSWORD_LOGIN_ENABLED", True)

    # Multi-tenant (Fase 4.3)
    MULTI_TENANT_ENABLED: bool = _env_bool("MULTI_TENANT_ENABLED", False)

    # OIDC / Keycloak / gov.br (Fase 4.4) — complementa login por senha
    OIDC_ENABLED: bool = _env_bool("OIDC_ENABLED", False)
    OIDC_ISSUER_URL: str = os.getenv("OIDC_ISSUER_URL", "")
    OIDC_CLIENT_ID: str = os.getenv("OIDC_CLIENT_ID", "")
    OIDC_CLIENT_SECRET: str = os.getenv("OIDC_CLIENT_SECRET", "")
    OIDC_REDIRECT_URI: str = os.getenv(
        "OIDC_REDIRECT_URI",
        "http://localhost:8000/api/v1/auth/oidc/callback",
    )
    OIDC_FRONTEND_REDIRECT: str = os.getenv("OIDC_FRONTEND_REDIRECT", "http://localhost:3000/")
    OIDC_SCOPES: str = os.getenv("OIDC_SCOPES", "openid profile email")
    OIDC_ROLE_CLAIM: str = os.getenv("OIDC_ROLE_CLAIM", "groups")
    OIDC_ADMIN_GROUPS: str = os.getenv("OIDC_ADMIN_GROUPS", "sinidu-admin,admin")
    OIDC_GESTOR_GROUPS: str = os.getenv("OIDC_GESTOR_GROUPS", "sinidu-gestor,gestor_municipal")
    OIDC_LEITOR_GROUPS: str = os.getenv("OIDC_LEITOR_GROUPS", "sinidu-leitor,leitor")
    OIDC_TENANT_UF_CLAIM: str = os.getenv("OIDC_TENANT_UF_CLAIM", "tenant_uf")
    OIDC_TENANT_IBGE_CLAIM: str = os.getenv("OIDC_TENANT_IBGE_CLAIM", "tenant_ibge")
    OIDC_DEFAULT_ROLE: str = os.getenv("OIDC_DEFAULT_ROLE", "leitor")

    # Reverse proxy / URL pública
    PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")
    TRUST_PROXY_HEADERS: bool = _env_bool("TRUST_PROXY_HEADERS", False)

    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    ]
    # Aceita origens da rede privada (192.168/10/172.16–31) — útil para demo na LAN do MCID
    CORS_ALLOW_LAN: bool = _env_bool("CORS_ALLOW_LAN", False)

    # Pipeline territorial agendado (Fase 8)
    SCHEDULED_PIPELINE_ENABLED: bool = _env_bool("SCHEDULED_PIPELINE_ENABLED", False)
    SCHEDULED_PIPELINE_LIMIT: int = int(os.getenv("SCHEDULED_PIPELINE_LIMIT", "61"))
    JOB_GOTIFY_NOTIFY: bool = _env_bool("JOB_GOTIFY_NOTIFY", True)
    JOB_STORE_REDIS: bool = _env_bool("JOB_STORE_REDIS", True)


settings = Settings()
