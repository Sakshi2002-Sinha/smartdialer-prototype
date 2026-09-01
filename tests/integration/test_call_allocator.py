import uuid
from datetime import datetime, timezone
import asyncio
import pytest
from sqlalchemy import delete ,select

from smartdialer.allocator import CallAllocator
from smartdialer.db import SessionLocal
from smartdialer.models import Agent, Borrower, Campaign
from smartdialer.allocator import AllocationError

@pytest.mark.asyncio
async def test_call_allocator_creates_atomic_allocation():
    campaign_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    borrower_id = uuid.uuid4()

    now = datetime.now(timezone.utc)

    async with SessionLocal() as session:
        campaign = Campaign(
            id=campaign_id,
            name="Allocator Test",
            mode="PROGRESSIVE",
            max_overdial_cap=50,
            active=True,
            created_at=now,
            updated_at=now,
        )

        agent = Agent(
            id=agent_id,
            campaign_id=campaign_id,
            name="Allocator Agent",
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

    allocator = CallAllocator()

    async with SessionLocal() as session:
        async with session.begin():

            result = await allocator.allocate(
                session=session,
                campaign_id=campaign_id,
                worker_id="worker-1",
            )

            assert result.success is True
            assert result.call is not None

            call_id = result.call.id

    async with SessionLocal() as session:
        agent = await session.get(Agent, agent_id)
        borrower = await session.get(Borrower, borrower_id)

        assert agent is not None
        assert borrower is not None

        assert agent.state == "RESERVED"
        assert agent.reserved_by == "worker-1"
        assert agent.version == 1

        assert borrower.status == "RESERVED"
        assert borrower.attempt_count == 1

        from smartdialer.models import Call

        call = await session.get(Call, call_id)

        assert call is not None
        assert call.state == "RESERVED"
        assert call.agent_id == agent_id
        assert call.borrower_id == borrower_id
        assert call.attempt_number == 1

        await session.execute(
            delete(Call).where(Call.id == call_id)
        )

        await session.execute(
            delete(Borrower).where(Borrower.id == borrower_id)
        )

        await session.execute(
            delete(Agent).where(Agent.id == agent_id)
        )

        await session.execute(
            delete(Campaign).where(Campaign.id == campaign_id)
        )

        await session.commit()
@pytest.mark.asyncio
async def test_allocation_rolls_back_agent_when_no_borrower_exists():
    campaign_id = uuid.uuid4()
    agent_id = uuid.uuid4()

    now = datetime.now(timezone.utc)

    async with SessionLocal() as session:
        campaign = Campaign(
            id=campaign_id,
            name="Rollback Test",
            mode="PROGRESSIVE",
            max_overdial_cap=50,
            active=True,
            created_at=now,
            updated_at=now,
        )

        agent = Agent(
            id=agent_id,
            campaign_id=campaign_id,
            name="Rollback Agent",
            state="AVAILABLE",
            version=0,
            created_at=now,
            updated_at=now,
        )

        session.add_all([campaign, agent])
        await session.commit()

    allocator = CallAllocator()

    async with SessionLocal() as session:

        with pytest.raises(AllocationError):
            async with session.begin():
                await allocator.allocate(
                    session=session,
                    campaign_id=campaign_id,
                    worker_id="worker-rollback",
                )

    async with SessionLocal() as session:
        agent = await session.get(Agent, agent_id)

        assert agent is not None
        assert agent.state == "AVAILABLE"
        assert agent.reserved_by is None
        assert agent.reserved_at is None
        assert agent.version == 0

        await session.execute(
            delete(Agent).where(Agent.id == agent_id)
        )

        await session.execute(
            delete(Campaign).where(Campaign.id == campaign_id)
        )

        await session.commit()

@pytest.mark.asyncio
async def test_two_workers_cannot_allocate_same_agent_and_borrower():
    campaign_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    borrower_id = uuid.uuid4()

    now = datetime.now(timezone.utc)

    async with SessionLocal() as session:
        campaign = Campaign(
            id=campaign_id,
            name="Concurrent Allocation Test",
            mode="PROGRESSIVE",
            max_overdial_cap=50,
            active=True,
            created_at=now,
            updated_at=now,
        )

        agent = Agent(
            id=agent_id,
            campaign_id=campaign_id,
            name="Concurrent Agent",
            state="AVAILABLE",
            version=0,
            created_at=now,
            updated_at=now,
        )

        borrower = Borrower(
            id=borrower_id,
            campaign_id=campaign_id,
            phone_number="+919888888888",
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

    allocator = CallAllocator()

    async def attempt(worker_id: str):
        async with SessionLocal() as session:
            try:
                async with session.begin():
                    result = await allocator.allocate(
                        session=session,
                        campaign_id=campaign_id,
                        worker_id=worker_id,
                    )

                    return result

            except AllocationError:
                return None

    result_a, result_b = await asyncio.gather(
        attempt("worker-A"),
        attempt("worker-B"),
    )

    successful_results = [
        result
        for result in (result_a, result_b)
        if result is not None and result.success
    ]

    # Exactly one worker must successfully allocate.
    assert len(successful_results) == 1

    successful_call = successful_results[0].call

    assert successful_call is not None

    async with SessionLocal() as session:
        agent = await session.get(Agent, agent_id)
        borrower = await session.get(Borrower, borrower_id)

        assert agent is not None
        assert borrower is not None

        assert agent.state == "RESERVED"
        assert agent.reserved_by in {
            "worker-A",
            "worker-B",
        }

        assert borrower.status == "RESERVED"
        assert borrower.attempt_count == 1

        from smartdialer.models import Call

        calls_result = await session.execute(
            select(Call).where(
                Call.campaign_id == campaign_id,
                Call.agent_id == agent_id,
                Call.borrower_id == borrower_id,
            )
        )

        calls = calls_result.scalars().all()

        # Exactly one call must exist.
        assert len(calls) == 1

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