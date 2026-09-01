import asyncio
import uuid
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import delete, select

from smartdialer.db import SessionLocal
from smartdialer.heartbeat import HeartbeatService
from smartdialer.models import Agent, Campaign
from smartdialer.provider import MockProviderA
from smartdialer.worker import DialerWorker


async def create_campaign(campaign_id):
    now = datetime.now(timezone.utc)

    async with SessionLocal() as session:
        campaign = Campaign(
            id=campaign_id,
            name="Heartbeat Runtime Test",
            mode="PROGRESSIVE",
            max_overdial_cap=50,
            active=True,
            created_at=now,
            updated_at=now,
        )

        session.add(campaign)
        await session.commit()


async def cleanup_campaign(campaign_id):
    async with SessionLocal() as session:
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


async def create_reserved_agent(
    campaign_id,
    worker_id,
):
    now = datetime.now(timezone.utc)

    agent_id = uuid.uuid4()

    async with SessionLocal() as session:
        agent = Agent(
            id=agent_id,
            campaign_id=campaign_id,
            name="Runtime Heartbeat Agent",
            state="RESERVED",
            version=1,
            reserved_by=worker_id,
            reserved_at=now,
            last_heartbeat=now - timedelta(seconds=30),
            created_at=now,
            updated_at=now,
        )

        session.add(agent)
        await session.commit()

    return agent_id


@pytest.mark.asyncio
async def test_worker_heartbeat_updates_reserved_agent():

    campaign_id = uuid.uuid4()
    worker_id = "heartbeat-runtime-worker"

    await create_campaign(campaign_id)

    agent_id = await create_reserved_agent(
        campaign_id,
        worker_id,
    )

    worker = DialerWorker(
        provider=MockProviderA(
            latency_ms=0,
        ),
        worker_id=worker_id,
    )

    before = datetime.now(timezone.utc)

    updated = await worker.heartbeat(
        campaign_id,
    )

    assert updated == 1

    async with SessionLocal() as session:
        agent = await session.get(
            Agent,
            agent_id,
        )

        assert agent is not None
        assert agent.last_heartbeat is not None
        assert agent.last_heartbeat >= before

    await cleanup_campaign(campaign_id)


@pytest.mark.asyncio
async def test_worker_heartbeat_does_not_update_other_workers():

    campaign_id = uuid.uuid4()

    await create_campaign(campaign_id)

    matching_id = await create_reserved_agent(
        campaign_id,
        "worker-A",
    )

    other_id = await create_reserved_agent(
        campaign_id,
        "worker-B",
    )

    old_time = datetime.now(timezone.utc) - timedelta(
        seconds=30
    )

    async with SessionLocal() as session:
        other = await session.get(
            Agent,
            other_id,
        )

        assert other is not None

        other.last_heartbeat = old_time

        await session.commit()

    worker = DialerWorker(
        provider=MockProviderA(
            latency_ms=0,
        ),
        worker_id="worker-A",
    )

    updated = await worker.heartbeat(
        campaign_id,
    )

    assert updated == 1

    async with SessionLocal() as session:
        matching = await session.get(
            Agent,
            matching_id,
        )

        other = await session.get(
            Agent,
            other_id,
        )

        assert matching is not None
        assert other is not None

        assert matching.last_heartbeat is not None
        assert matching.last_heartbeat > old_time

        assert other.last_heartbeat == old_time

    await cleanup_campaign(campaign_id)


@pytest.mark.asyncio
async def test_worker_runtime_calls_heartbeat_each_tick():

    worker = DialerWorker.__new__(DialerWorker)

    worker.running = False

    campaign_id = uuid.uuid4()

    heartbeat_count = 0
    tick_count = 0

    async def fake_heartbeat(campaign_id_arg):
        nonlocal heartbeat_count

        assert campaign_id_arg == campaign_id

        heartbeat_count += 1

    async def fake_run_once(campaign_id_arg):
        nonlocal tick_count

        assert campaign_id_arg == campaign_id

        tick_count += 1

        if tick_count >= 3:
            worker.stop()

    worker.heartbeat = fake_heartbeat
    worker.run_once = fake_run_once

    await worker.run_forever(
        campaign_id=campaign_id,
        interval_sec=0,
    )

    assert tick_count == 3
    assert heartbeat_count == 3
    assert worker.running is False


@pytest.mark.asyncio
async def test_worker_runtime_survives_heartbeat_failure():

    worker = DialerWorker.__new__(DialerWorker)

    worker.running = False

    campaign_id = uuid.uuid4()

    tick_count = 0

    async def failing_heartbeat(campaign_id_arg):
        raise RuntimeError(
            "heartbeat database temporarily unavailable"
        )

    async def fake_run_once(campaign_id_arg):
        nonlocal tick_count

        tick_count += 1

        if tick_count >= 2:
            worker.stop()

    worker.heartbeat = failing_heartbeat
    worker.run_once = fake_run_once

    await worker.run_forever(
        campaign_id=campaign_id,
        interval_sec=0,
    )

    assert tick_count == 2
    assert worker.running is False


@pytest.mark.asyncio
async def test_worker_runtime_cancellation_stops_cleanly():

    worker = DialerWorker.__new__(DialerWorker)

    worker.running = False

    campaign_id = uuid.uuid4()

    async def fake_heartbeat(campaign_id_arg):
        await asyncio.sleep(10)

    async def fake_run_once(campaign_id_arg):
        pass

    worker.heartbeat = fake_heartbeat
    worker.run_once = fake_run_once

    task = asyncio.create_task(
        worker.run_forever(
            campaign_id=campaign_id,
            interval_sec=0,
        )
    )

    await asyncio.sleep(0)

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert worker.running is False