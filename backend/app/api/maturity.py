from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Municipio
from app.security.municipio_access import assert_codigo_ibge_access, get_accessible_municipio
from app.services.maturity_engine import compute_maturity, persist_maturity

router = APIRouter()


@router.get("/{codigo_ibge}")
def get_municipal_maturity(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    code = str(codigo_ibge).zfill(7)[:7]
    get_accessible_municipio(db, code, request=request)
    return compute_maturity(db, code)


@router.post("/{codigo_ibge}/recalculate")
def recalculate_maturity(
    codigo_ibge: str,
    request: Request,
    persist: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    code = assert_codigo_ibge_access(db, codigo_ibge, request=request)
    if persist:
        return persist_maturity(db, code)
    return compute_maturity(db, code)
