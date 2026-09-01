import asyncio
import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class SimulatedEvent:
    call_id: uuid.UUID
    event_type: str
    provider_call_id: str
    sequence: int


class ProviderEventSimulator:

    def __init__(self, provider_call_id: str | None = None):
        self.provider_call_id = (
            provider_call_id or str(uuid.uuid4())
        )

    async def normal_call(
        self,
        call_id: uuid.UUID,
    ) -> list[SimulatedEvent]:
        """
        Simulate a normal provider lifecycle.
        """

        events = [
            SimulatedEvent(
                call_id=call_id,
                event_type="INITIATED",
                provider_call_id=self.provider_call_id,
                sequence=1,
            ),
            SimulatedEvent(
                call_id=call_id,
                event_type="RINGING",
                provider_call_id=self.provider_call_id,
                sequence=2,
            ),
            SimulatedEvent(
                call_id=call_id,
                event_type="ANSWERED",
                provider_call_id=self.provider_call_id,
                sequence=3,
            ),
            SimulatedEvent(
                call_id=call_id,
                event_type="CONNECTED",
                provider_call_id=self.provider_call_id,
                sequence=4,
            ),
            SimulatedEvent(
                call_id=call_id,
                event_type="COMPLETED",
                provider_call_id=self.provider_call_id,
                sequence=5,
            ),
        ]

        await asyncio.sleep(0)

        return events

    async def duplicate_answer(
        self,
        call_id: uuid.UUID,
    ) -> list[SimulatedEvent]:
        """
        Simulate a provider sending ANSWERED multiple times.
        """

        events = [
            SimulatedEvent(
                call_id=call_id,
                event_type="ANSWERED",
                provider_call_id=self.provider_call_id,
                sequence=1,
            ),
            SimulatedEvent(
                call_id=call_id,
                event_type="ANSWERED",
                provider_call_id=self.provider_call_id,
                sequence=2,
            ),
            SimulatedEvent(
                call_id=call_id,
                event_type="ANSWERED",
                provider_call_id=self.provider_call_id,
                sequence=3,
            ),
        ]

        await asyncio.sleep(0)

        return events

    async def out_of_order_completion(
        self,
        call_id: uuid.UUID,
    ) -> list[SimulatedEvent]:
        """
        Simulate provider events arriving out of order.
        """

        events = [
            SimulatedEvent(
                call_id=call_id,
                event_type="COMPLETED",
                provider_call_id=self.provider_call_id,
                sequence=1,
            ),
            SimulatedEvent(
                call_id=call_id,
                event_type="ANSWERED",
                provider_call_id=self.provider_call_id,
                sequence=2,
            ),
            SimulatedEvent(
                call_id=call_id,
                event_type="RINGING",
                provider_call_id=self.provider_call_id,
                sequence=3,
            ),
        ]

        await asyncio.sleep(0)

        return events