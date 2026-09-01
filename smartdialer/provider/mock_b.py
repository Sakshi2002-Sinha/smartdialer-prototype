import asyncio
import random
import uuid

from .base import ProviderCallResult


class MockProviderB:

    def __init__(
        self,
        failure_rate: float = 0.15,
        timeout_rate: float = 0.10,
        latency_ms: int = 500,
    ):
        self.failure_rate = failure_rate
        self.timeout_rate = timeout_rate
        self.latency_ms = latency_ms

    async def initiate_call(
        self,
        *,
        call_id: str,
        phone_number: str,
    ) -> ProviderCallResult:

        await asyncio.sleep(self.latency_ms / 1000)

        if random.random() < self.timeout_rate:
            raise TimeoutError(
                "MockProviderB timed out"
            )

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
            1.0
            - self.failure_rate
            - self.timeout_rate,
        )