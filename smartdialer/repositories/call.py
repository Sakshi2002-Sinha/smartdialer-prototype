import uuid
from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from smartdialer.models import Call


class CallRepository:

    async def create_reserved_call(
        self,
        session: AsyncSession,
        campaign_id: uuid.UUID,
        agent_id: uuid.UUID,
        borrower_id: uuid.UUID,
        idempotency_key: str,
        attempt_number: int,
    ) -> Call:
        """
        Create a new RESERVED call.

        The caller is responsible for transaction management.
        """

        now = datetime.now(timezone.utc)

        call = Call(
            id=uuid.uuid4(),
            campaign_id=campaign_id,
            agent_id=agent_id,
            borrower_id=borrower_id,
            state="RESERVED",
            attempt_number=attempt_number,
            idempotency_key=idempotency_key,
            reserved_at=now,
            version=0,
            created_at=now,
            updated_at=now,
        )

        session.add(call)

        await session.flush()

        return call