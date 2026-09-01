from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ProviderEventType(str, Enum):
    INITIATED = "INITIATED"
    RINGING = "RINGING"
    ANSWERED = "ANSWERED"
    CONNECTED = "CONNECTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class ProviderEvent:
    provider: str
    provider_event_id: str
    provider_call_id: str
    event_type: ProviderEventType
    occurred_at: datetime
    sequence: int | None = None
    payload: dict | None = None