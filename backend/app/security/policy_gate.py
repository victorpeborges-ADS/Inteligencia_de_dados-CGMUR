"""Policy gate — confirmação humana para ações sensíveis (Fase 20a.3).

Auth/role ≠ confirmação explícita. Endpoints que ativam plano de contingência
ou disseminam aviso público exigem `confirm=true` (query ou body).
"""

from __future__ import annotations

from fastapi import HTTPException

SENSITIVE_ACTIONS = frozenset({
    "contingency.activate",
    "alert.disseminate",
})

CONFIRM_REQUIRED_DETAIL = (
    "Confirmação humana obrigatória. Reenvie com confirm=true "
    "(ação sensível — não é automática pelo agente)."
)


def require_human_confirm(confirm: bool | None, *, action: str) -> None:
    """Levanta 409 se confirm não for verdadeiramente True."""
    if action not in SENSITIVE_ACTIONS:
        return
    if confirm is True:
        return
    raise HTTPException(
        status_code=409,
        detail={
            "code": "human_confirm_required",
            "action": action,
            "message": CONFIRM_REQUIRED_DETAIL,
        },
    )
