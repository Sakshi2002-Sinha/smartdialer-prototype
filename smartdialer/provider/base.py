from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ProviderCallResult:
    provider_call_id: str
    accepted: bool
    error: str | None = None


class TelecomProvider(Protocol):

    async def initiate_call(
        self,
        *,
        call_id: str,
        phone_number: str,
    ) -> ProviderCallResult:
        ...

    async def cancel_call(
        self,
        *,
        provider_call_id: str,
    ) -> bool:
        ...

    def health(self) -> float:
        ...