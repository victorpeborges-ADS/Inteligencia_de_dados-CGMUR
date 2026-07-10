import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://sinidu_user:sinidu_pass@localhost:5432/sinidu_db"
)

# Use pool_pre_ping to check connection health automatically.
# Boot/scheduler threads + API requests precisam de folga no pool.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=int(os.getenv("DB_POOL_SIZE", "12")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "24")),
    pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
