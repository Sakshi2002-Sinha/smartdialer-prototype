import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, select

from smartdialer.db import SessionLocal
from smartdialer.models import Agent, Borrower, Call, Campaign
from smartdialer.provider import MockProviderA
from smartdialer.worker import DialerWorker


async def create_campaign(
    campaign_id,
    mode="PROGRESSIVE",
    active=True,
):
    now = datetime.now(timezone.utc)

    async with SessionLocal() as session:
        campaign = Campaign(
            id=campaign_id,
            name=f"Worker {mode} Test",
            mode=mode,
            max_overdial_cap=50,
            active=active,
            created_at=now,
            updated_at=now,
        )

        session.add(campaign)
        await session.commit()


async def create_agent(
    campaign_id,
    state="AVAILABLE",
):
    now = datetime.now(timezone.utc)
    agent_id = uuid.uuid4()

    async with SessionLocal() as session:
        agent = Agent(
            id=agent_id,
            campaign_id=campaign_id,
            name="Worker Agent",
            state=state,
            version=0,
            created_at=now,
            updated_at=now,
        )

        session.add(agent)
        await session.commit()

    return agent_id


async def create_borrower(
    campaign_id,
    priority=10,
):
    now = datetime.now(timezone.utc)
    borrower_id = uuid.uuid4()

    async with SessionLocal() as session:
        borrower = Borrower(
            id=borrower_id,
            campaign_id=campaign_id,
            phone_number="+919999999999",
            status="PENDING",
            priority=priority,
            attempt_count=0,
            created_at=now,
            updated_at=now,
        )

        session.add(borrower)
        await session.commit()

    return borrower_id


async def cleanup_campaign(campaign_id):
    async with SessionLocal() as session:
        await session.execute(
            delete(Call).where(
                Call.campaign_id == campaign_id
            )
        )

        await session.execute(
            delete(Borrower).where(
                Borrower.campaign_id == campaign_id
            )
        )

        await session.execute(
            delete(Agent).where(
                Agent.campaign_id == campaign_id
            )
        )

        await session.execute(
            delete(Campaign).where(
                Campaign.id == campaign_id
            )
        )

        await session.commit()


@pytest.mark.asyncio
async def test_worker_progressive_campaign_dials_call():
    campaign_id = uuid.uuid4()

    await create_campaign(
        campaign_id,
        mode="PROGRESSIVE",
    )

    agent_id = await create_agent(campaign_id)
    borrower_id = await create_borrower(campaign_id)

    provider = MockProviderA(
        failure_rate=0.0,
        latency_ms=0,
    )

    worker = DialerWorker(
        provider=provider,
        worker_id="worker-progressive",
    )

    result = await worker.run_once(
        campaign_id,
    )

    assert result.mode == "PROGRESSIVE"
    assert result.requested_calls == 1
    assert result.successful_calls == 1
    assert result.failed_calls == 0

    async with SessionLocal() as session:
        agent = await session.get(
            Agent,
            agent_id,
        )

        borrower = await session.get(
            Borrower,
            borrower_id,
        )

        assert agent is not None
        assert borrower is not None

        assert agent.state == "RESERVED"
        assert borrower.status == "RESERVED"

        calls_result = await session.execute(
            select(Call).where(
                Call.campaign_id == campaign_id
            )
        )

        calls = calls_result.scalars().all()

        assert len(calls) == 1
        assert calls[0].state == "INITIATED"

    await cleanup_campaign(campaign_id)


@pytest.mark.asyncio
async def test_worker_does_nothing_for_inactive_campaign():
    campaign_id = uuid.uuid4()

    await create_campaign(
        campaign_id,
        mode="PROGRESSIVE",
        active=False,
    )

    await create_agent(campaign_id)
    await create_borrower(campaign_id)

    provider = MockProviderA(
        failure_rate=0.0,
        latency_ms=0,
    )

    worker = DialerWorker(
        provider=provider,
        worker_id="worker-inactive",
    )

    result = await worker.run_once(
        campaign_id,
    )

    assert result.requested_calls == 0
    assert result.successful_calls == 0
    assert result.failed_calls == 0
    assert result.reason == "CAMPAIGN_INACTIVE"

    async with SessionLocal() as session:
        calls_result = await session.execute(
            select(Call).where(
                Call.campaign_id == campaign_id
            )
        )

        assert calls_result.scalars().all() == []

    await cleanup_campaign(campaign_id)


@pytest.mark.asyncio
async def test_worker_handles_unknown_campaign():
    campaign_id = uuid.uuid4()

    provider = MockProviderA(
        failure_rate=0.0,
        latency_ms=0,
    )

    worker = DialerWorker(
        provider=provider,
        worker_id="worker-unknown",
    )

    result = await worker.run_once(
        campaign_id,
    )

    assert result.mode == "UNKNOWN"
    assert result.requested_calls == 0
    assert result.successful_calls == 0
    assert result.reason == "CAMPAIGN_NOT_FOUND"


@pytest.mark.asyncio
async def test_worker_provider_failure_releases_resources():
    campaign_id = uuid.uuid4()

    await create_campaign(
        campaign_id,
        mode="PROGRESSIVE",
    )

    agent_id = await create_agent(campaign_id)
    borrower_id = await create_borrower(campaign_id)

    provider = MockProviderA(
        failure_rate=1.0,
        latency_ms=0,
    )

    worker = DialerWorker(
        provider=provider,
        worker_id="worker-failure",
    )

    result = await worker.run_once(
        campaign_id,
    )

    assert result.requested_calls == 1
    assert result.successful_calls == 0
    assert result.failed_calls == 1

    async with SessionLocal() as session:
        agent = await session.get(
            Agent,
            agent_id,
        )

        borrower = await session.get(
            Borrower,
            borrower_id,
        )

        assert agent is not None
        assert borrower is not None

        assert agent.state == "AVAILABLE"
        assert agent.reserved_by is None
        assert agent.reserved_at is None

        assert borrower.status == "PENDING"

        calls_result = await session.execute(
            select(Call).where(
                Call.campaign_id == campaign_id
            )
        )

        calls = calls_result.scalars().all()

        assert len(calls) == 1
        assert calls[0].state == "FAILED"

    await cleanup_campaign(campaign_id)


@pytest.mark.asyncio
async def test_worker_progressive_does_not_exceed_capacity():
    campaign_id = uuid.uuid4()

    await create_campaign(
        campaign_id,
        mode="PROGRESSIVE",
    )

    agent_ids = [
        await create_agent(campaign_id)
        for _ in range(3)
    ]

    borrower_ids = [
        await create_borrower(campaign_id)
        for _ in range(5)
    ]

    provider = MockProviderA(
        failure_rate=0.0,
        latency_ms=0,
    )

    worker = DialerWorker(
        provider=provider,
        worker_id="worker-capacity",
    )

    result = await worker.run_once(
        campaign_id,
    )

    assert result.requested_calls == 3
    assert result.successful_calls == 3
    assert result.failed_calls == 0

    async with SessionLocal() as session:
        calls_result = await session.execute(
            select(Call).where(
                Call.campaign_id == campaign_id
            )
        )

        calls = calls_result.scalars().all()

        assert len(calls) == 3

    await cleanup_campaign(campaign_id)


@pytest.mark.asyncio
async def test_worker_predictive_campaign_respects_provider_health():
    campaign_id = uuid.uuid4()

    await create_campaign(
        campaign_id,
        mode="PREDICTIVE",
    )

    await create_agent(campaign_id)
    await create_borrower(campaign_id)

    provider = MockProviderA(
        failure_rate=1.0,
        latency_ms=0,
    )

    worker = DialerWorker(
        provider=provider,
        worker_id="worker-predictive",
    )

    result = await worker.run_once(
        campaign_id,
    )

    assert result.mode == "PREDICTIVE"
    assert result.successful_calls == 0

    async with SessionLocal() as session:
        calls_result = await session.execute(
            select(Call).where(
                Call.campaign_id == campaign_id
            )
        )

        calls = calls_result.scalars().all()

        assert len(calls) == 0

    await cleanup_campaign(campaign_id)



