from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Protocol


@dataclass
class ProviderInfo:
    id: str
    label: str
    description: str
    available: bool
    is_local: bool
    requires_api_key: bool
    default_model: str
    models: List[str] = field(default_factory=list)
    privacy_note: str = ""


class ChatProvider(Protocol):
    id: str
    label: str
    is_local: bool

    def info(self) -> ProviderInfo: ...

    def is_available(self) -> bool: ...

    def chat(
        self,
        messages: List[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.2,
    ) -> str: ...

    def with_api_key(self, api_key: str) -> "ChatProvider": ...
