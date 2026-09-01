import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from smartdialer.db import SessionLocal
from smartdialer.models import Agent, Borrower, Call, Campaign
from smartdialer.orchestrator import DialingOrchestrator
from smartdialer.provider.base import ProviderCallResult
from smartdialer.allocator import AllocationError

# ---------------------------------------------------------
# Deterministic test providers
# ---------------------------------------------------------


class SuccessfulProvider:
    async def initiate_call(
        self,
        *,
        call_id: str,
        phone_number: str,
    ) -> ProviderCallResult:
        return ProviderCallResult(
            provider_call_id="provider-call-success",
            accepted=True,
        )

    async def cancel_call(
        self,
        *,
        provider_call_id: str,
    ) -> bool:
        return True

    def health(self) -> float:
        return 1.0


class RejectingProvider:
    async def initiate_call(
        self,
        *,
        call_id: str,
        phone_number: str,
    ) -> ProviderCallResult:
        return ProviderCallResult(
            provider_call_id="",
            accepted=False,
            error="PROVIDER_REJECTED",
        )

    async def cancel_call(
        self,
        *,
        provider_call_id: str,
    ) -> bool:
        return True

    def health(self) -> float:
        return 0.5


class FailingProvider:
    async def initiate_call(
        self,
        *,
        call_id: str,
        phone_number: str,
    ) -> ProviderCallResult:
        raise TimeoutError("provider timeout")

    async def cancel_call(
        self,
        *,
        provider_call_id: str,
    ) -> bool:
        return True

    def health(self) -> float:
        return 0.0


# ---------------------------------------------------------
# Test data helper
# ---------------------------------------------------------


async def create_campaign_agent_borrower():
    campaign_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    borrower_id = uuid.uuid4()

    now = datetime.now(timezone.utc)

    async with SessionLocal() as session:
        campaign = Campaign(
            id=campaign_id,
            name="Orchestrator Test",
            mode="PROGRESSIVE",
            max_overdial_cap=50,
            active=True,
            created_at=now,
            updated_at=now,
        )

        agent = Agent(
            id=agent_id,
            campaign_id=campaign_id,
            name="Orchestrator Agent",
            state="AVAILABLE",
            version=0,
            created_at=now,
            updated_at=now,
        )

        borrower = Borrower(
            id=borrower_id,
            campaign_id=campaign_id,
            phone_number="+919999999999",
            status="PENDING",
            priority=10,
            attempt_count=0,
            created_at=now,
            updated_at=now,
        )

        session.add_all([
            campaign,
            agent,
            borrower,
        ])

        await session.commit()

    return campaign_id, agent_id, borrower_id


async def cleanup(
    campaign_id,
    agent_id,
    borrower_id,
):
    async with SessionLocal() as session:

        await session.execute(
            delete(Call).where(
                Call.campaign_id == campaign_id
            )
        )

        await session.execute(
            delete(Borrower).where(
                Borrower.id == borrower_id
            )
        )

        await session.execute(
            delete(Agent).where(
                Agent.id == agent_id
            )
        )

        await session.execute(
            delete(Campaign).where(
                Campaign.id == campaign_id
            )
        )

        await session.commit()


# ---------------------------------------------------------
# 1. Successful provider initiation
# ---------------------------------------------------------


@pytest.mark.asyncio
async def test_dialing_orchestrator_initiates_allocated_call():

    campaign_id, agent_id, borrower_id = (
        await create_campaign_agent_borrower()
    )

    try:
        orchestrator = DialingOrchestrator(
            provider=SuccessfulProvider()
        )

        async with SessionLocal() as session:
            async with session.begin():

                result = await orchestrator.dial_one(
                    session=session,
                    campaign_id=campaign_id,
                    worker_id="worker-1",
                )

                assert result.success is True
                assert result.call is not None
                assert result.reason == "PROVIDER_ACCEPTED"

                call_id = result.call.id

        async with SessionLocal() as session:

            call = await session.get(Call, call_id)
            agent = await session.get(Agent, agent_id)
            borrower = await session.get(
                Borrower,
                borrower_id,
            )

            assert call is not None
            assert agent is not None
            assert borrower is not None

            # RESERVED -> INITIATED
            assert call.state == "INITIATED"

            assert call.provider == "SuccessfulProvider"
            assert call.provider_call_id == "provider-call-success"
            assert call.initiated_at is not None

            # Agent remains reserved while call is active.
            assert agent.state == "RESERVED"
            assert agent.reserved_by == "worker-1"

            # Borrower remains reserved for the active call.
            assert borrower.status == "RESERVED"
            assert borrower.attempt_count == 1

    finally:
        await cleanup(
            campaign_id,
            agent_id,
            borrower_id,
        )


# ---------------------------------------------------------
# 2. Provider rejection
# ---------------------------------------------------------


@pytest.mark.asyncio
async def test_provider_rejection_fails_call_and_releases_resources():

    campaign_id, agent_id, borrower_id = (
        await create_campaign_agent_borrower()
    )

    try:
        orchestrator = DialingOrchestrator(
            provider=RejectingProvider()
        )

        async with SessionLocal() as session:
            async with session.begin():

                result = await orchestrator.dial_one(
                    session=session,
                    campaign_id=campaign_id,
                    worker_id="worker-reject",
                )

                assert result.success is False
                assert result.call is not None
                assert result.reason == "PROVIDER_REJECTED"

                call_id = result.call.id

        async with SessionLocal() as session:

            call = await session.get(Call, call_id)
            agent = await session.get(Agent, agent_id)
            borrower = await session.get(
                Borrower,
                borrower_id,
            )

            assert call is not None
            assert agent is not None
            assert borrower is not None

            assert call.state == "FAILED"
            assert call.failure_reason == "PROVIDER_REJECTED"

            # Failed call releases the agent.
            assert agent.state == "AVAILABLE"
            assert agent.reserved_by is None
            assert agent.reserved_at is None

            # Borrower becomes retryable.
            assert borrower.status == "PENDING"

            # Reservation attempt was still recorded.
            assert borrower.attempt_count == 1

    finally:
        await cleanup(
            campaign_id,
            agent_id,
            borrower_id,
        )


# ---------------------------------------------------------
# 3. Provider timeout / exception
# ---------------------------------------------------------


@pytest.mark.asyncio
async def test_provider_exception_fails_call_and_releases_resources():

    campaign_id, agent_id, borrower_id = (
        await create_campaign_agent_borrower()
    )

    try:
        orchestrator = DialingOrchestrator(
            provider=FailingProvider()
        )

        async with SessionLocal() as session:
            async with session.begin():

                result = await orchestrator.dial_one(
                    session=session,
                    campaign_id=campaign_id,
                    worker_id="worker-timeout",
                )

                assert result.success is False
                assert result.call is not None
                assert "provider timeout" in result.reason

                call_id = result.call.id

        async with SessionLocal() as session:

            call = await session.get(Call, call_id)
            agent = await session.get(Agent, agent_id)
            borrower = await session.get(
                Borrower,
                borrower_id,
            )

            assert call is not None
            assert agent is not None
            assert borrower is not None

            assert call.state == "FAILED"
            assert call.failure_reason == "provider timeout"

            assert agent.state == "AVAILABLE"
            assert agent.reserved_by is None
            assert agent.reserved_at is None

            assert borrower.status == "PENDING"
            assert borrower.attempt_count == 1

    finally:
        await cleanup(
            campaign_id,
            agent_id,
            borrower_id,
        )


# ---------------------------------------------------------
# 4. No allocation available
# ---------------------------------------------------------


@pytest.mark.asyncio
async def test_dialing_orchestrator_returns_allocation_failure():

    campaign_id = uuid.uuid4()
    agent_id = uuid.uuid4()

    now = datetime.now(timezone.utc)

    async with SessionLocal() as session:

        campaign = Campaign(
            id=campaign_id,
            name="No Borrower Test",
            mode="PROGRESSIVE",
            max_overdial_cap=50,
            active=True,
            created_at=now,
            updated_at=now,
        )

        agent = Agent(
            id=agent_id,
            campaign_id=campaign_id,
            name="Available Agent",
            state="AVAILABLE",
            version=0,
            created_at=now,
            updated_at=now,
        )

        session.add_all([
            campaign,
            agent,
        ])

        await session.commit()

    try:
        orchestrator = DialingOrchestrator(
            provider=SuccessfulProvider()
        )

        async with SessionLocal() as session:

            with pytest.raises(
                AllocationError,
                match="NO_PENDING_BORROWER",
            ):
                async with session.begin():

                    await orchestrator.dial_one(
                        session=session,
                        campaign_id=campaign_id,
                        worker_id="worker-no-borrower",
                    )

        # The transaction should have rolled back the
        # agent reservation performed by the allocator.
        async with SessionLocal() as session:

            agent = await session.get(
                Agent,
                agent_id,
            )

            assert agent is not None
            assert agent.state == "AVAILABLE"
            assert agent.reserved_by is None
            assert agent.reserved_at is None
            assert agent.version == 0

    finally:
        async with SessionLocal() as session:

            await session.execute(
                delete(Agent).where(
                    Agent.id == agent_id
                )
            )

            await session.execute(
                delete(Campaign).where(
                    Campaign.id == campaign_id
                )
            )

            await session.commit()