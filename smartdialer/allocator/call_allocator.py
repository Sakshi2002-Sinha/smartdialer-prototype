import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smartdialer.models import Agent, Borrower, Call
from smartdialer.repositories import (
    AgentRepository,
    BorrowerRepository,
    CallRepository,
)
class AllocationError(Exception):
    """Raised when an allocation cannot be completed atomically."""

class AllocationResult:
    def __init__(
        self,
        success: bool,
        call: Call | None = None,
        reason: str | None = None,
    ):
        self.success = success
        self.call = call
        self.reason = reason


class CallAllocator:

    def __init__(self):
        self.agent_repository = AgentRepository()
        self.borrower_repository = BorrowerRepository()
        self.call_repository = CallRepository()

    async def allocate(
        self,
        session: AsyncSession,
        campaign_id: uuid.UUID,
        worker_id: str,
    ) -> AllocationResult:
        """
        Atomically allocate:

        AVAILABLE agent
        +
        PENDING borrower
        +
        RESERVED call

        All changes happen inside the caller's transaction.
        """

        # ---------------------------------------------------------
        # 1. Find an available agent candidate.
        # ---------------------------------------------------------

        agent_result = await session.execute(
            select(Agent)
            .where(
                Agent.campaign_id == campaign_id,
                Agent.state == "AVAILABLE",
            )
            .order_by(Agent.updated_at)
            .limit(1)
        )

        agent = agent_result.scalar_one_or_none()

        if agent is None:
            return AllocationResult(
                success=False,
                reason="NO_AVAILABLE_AGENT",
            )

        # ---------------------------------------------------------
        # 2. Atomically reserve the agent.
        # ---------------------------------------------------------

        agent_reserved = await self.agent_repository.reserve_agent(
            session=session,
            agent_id=agent.id,
            worker_id=worker_id,
            expected_version=agent.version,
        )

        if not agent_reserved:
            return AllocationResult(
                success=False,
                reason="AGENT_RESERVATION_LOST",
            )

        # ---------------------------------------------------------
        # 3. Find highest-priority pending borrower.
        # ---------------------------------------------------------

        borrower_result = await session.execute(
            select(Borrower)
            .where(
                Borrower.campaign_id == campaign_id,
                Borrower.status == "PENDING",
                Borrower.attempt_count < 3,
            )
            .order_by(
                Borrower.priority.desc(),
                Borrower.created_at.asc(),
            )
            .limit(1)
        )

        borrower = borrower_result.scalar_one_or_none()

        if borrower is None:
           raise AllocationError("NO_PENDING_BORROWER")

        # ---------------------------------------------------------
        # 4. Atomically reserve borrower.
        # ---------------------------------------------------------

        borrower_reserved = (
            await self.borrower_repository.reserve_borrower(
                session=session,
                borrower_id=borrower.id,
            )
        )

        if not borrower_reserved:
            raise AllocationError("BORROWER_RESERVATION_LOST")

        # ---------------------------------------------------------
        # 5. Create the RESERVED call.
        # ---------------------------------------------------------

        attempt_number = borrower.attempt_count

        idempotency_key = (
            f"{campaign_id}:{borrower.id}:{attempt_number}"
        )

        call = await self.call_repository.create_reserved_call(
            session=session,
            campaign_id=campaign_id,
            agent_id=agent.id,
            borrower_id=borrower.id,
            idempotency_key=idempotency_key,
            attempt_number=attempt_number,
        )

        return AllocationResult(
            success=True,
            call=call,
        )