import uuid
from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from smartdialer.models import Borrower


class BorrowerRepository:

    async def reserve_borrower(
        self,
        session: AsyncSession,
        borrower_id: uuid.UUID,
    ) -> bool:
        """
        Atomically reserve a pending borrower for a call attempt.
        """

        now = datetime.now(timezone.utc)

        result = await session.execute(
            update(Borrower)
            .where(
                Borrower.id == borrower_id,
                Borrower.status == "PENDING",
                Borrower.attempt_count < 3,
            )
            .values(
                status="RESERVED",
                attempt_count=Borrower.attempt_count + 1,
                last_attempt_at=now,
                updated_at=now,
            )
        )

        return result.rowcount == 1

    async def release_borrower(
        self,
        session: AsyncSession,
        borrower_id: uuid.UUID,
    ) -> bool:
        """
        Return a reserved borrower to PENDING.
        """

        now = datetime.now(timezone.utc)

        result = await session.execute(
            update(Borrower)
            .where(
                Borrower.id == borrower_id,
                Borrower.status == "RESERVED",
            )
            .values(
                status="PENDING",
                updated_at=now,
            )
        )

        return result.rowcount == 1