import asyncio
import uuid
import random

from .base import ProviderCallResult


class MockProviderA:

    def __init__(
        self,
        failure_rate: float = 0.02,
        latency_ms: int = 100,
    ):
        self.failure_rate = failure_rate
        self.latency_ms = latency_ms

    async def initiate_call(
        self,
        *,
        call_id: str,
        phone_number: str,
    ) -> ProviderCallResult:

        await asyncio.sleep(self.latency_ms / 1000)

        if random.random() < self.failure_rate:
            return ProviderCallResult(
                provider_call_id="",
                accepted=False,
                error="PROVIDER_REJECTED",
            )

        return ProviderCallResult(
            provider_call_id=str(uuid.uuid4()),
            accepted=True,
        )

    async def cancel_call(
        self,
        *,
        provider_call_id: str,
    ) -> bool:

        await asyncio.sleep(self.latency_ms / 1000)

        return True

    def health(self) -> float:
        return max(
            0.0,
            1.0 - self.failure_rate,
        )