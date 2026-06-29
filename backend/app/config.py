import os


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default).lower()).lower() in ("1", "true", "yes", "on")


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

    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")

    TARGET_IBGE_CODES: list[str] = [
        "1200401", "2704302", "1600303", "1302603", "2927408", "2304400", "5300108",
        "3205309", "5208707", "2111300", "5103403", "5002704", "3106200", "1501402",
        "2507507", "4106902", "2611606", "2211001", "3304557", "2408102", "4314902",
        "1100205", "1400100", "4205407", "2800308", "3550308", "1721000",
        "3303906", "3303401", "3305802", "3550704", "3300100", "4202404", "1504208",
        "3143906", "2914802", "2913606", "4316907", "3109006", "2602902", "4318908",
        "3201506", "1702109", "1400233", "2604106", "2407104", "2924009", "2806701",
        "5201108", "5208905", "5218805", "4302105", "4304606", "4104907", "4305108",
        "3200607", "3509502", "3138203", "3548708", "3549904", "3305505",
    ]

    REPORTS_DIR: str = os.getenv("REPORTS_DIR", "/data/reports")
    MODELS_DIR: str = os.getenv("MODELS_DIR", "/data/models")
    ML_DATA_DIR: str = os.getenv("ML_DATA_DIR", "/data/ml")
    DEM_DIR: str = os.getenv("DEM_DIR", "/data/dem")
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

    # Pipeline territorial agendado (Fase 8)
    SCHEDULED_PIPELINE_ENABLED: bool = _env_bool("SCHEDULED_PIPELINE_ENABLED", False)
    SCHEDULED_PIPELINE_LIMIT: int = int(os.getenv("SCHEDULED_PIPELINE_LIMIT", "61"))
    JOB_GOTIFY_NOTIFY: bool = _env_bool("JOB_GOTIFY_NOTIFY", True)


settings = Settings()
