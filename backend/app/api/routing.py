"""Status e metadados de roteamento OSRM."""

from fastapi import APIRouter

from app.services.osrm_router import osrm_status

router = APIRouter()


@router.get("/status")
def get_routing_status():
    return osrm_status()
