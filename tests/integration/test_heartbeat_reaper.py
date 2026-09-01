import uuid
from datetime import datetime, timedelta, timezone

import pytest

from smartdialer.db import SessionLocal
from smartdialer.heartbeat import HeartbeatService
from smartdialer.models import Agent, Campaign
from smartdialer.reaper import Reaper


async def create_campaign(campaign_id):
    now = datetime.now(timezone.utc)

    async with SessionLocal() as session:
        campaign = Campaign(
            id=campaign_id,
            name="Heartbeat Reaper Integration",
            mode="PROGRESSIVE",
            max_overdial_cap=50,
            active=True,
            created_at=now,
            updated_at=now,
        )

        session.add(campaign)
        await session.commit()


async def cleanup(campaign_id):
    async with SessionLocal() as session:
        from sqlalchemy import delete

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
async def test_fresh_heartbeat_prevents_agent_from_being_stale():

    campaign_id = uuid.uuid4()
    worker_id = "heartbeat-reaper-worker"

    await create_campaign(campaign_id)

    now = datetime.now(timezone.utc)

    agent_id = uuid.uuid4()

    async with SessionLocal() as session:
        agent = Agent(
            id=agent_id,
            campaign_id=campaign_id,
            name="Fresh Agent",
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

    heartbeat = HeartbeatService()

    async with SessionLocal() as session:
        async with session.begin():
            updated = await heartbeat.heartbeat_for_worker(
                session=session,
                campaign_id=campaign_id,
                worker_id=worker_id,
            )

        assert updated == 1

    async with SessionLocal() as session:
        agent = await session.get(Agent, agent_id)

        assert agent is not None

        stale = await heartbeat.is_stale(
            agent,
            stale_after_sec=5,
        )

        assert stale is False

    await cleanup(campaign_id)


@pytest.mark.asyncio
async def test_stopped_heartbeat_eventually_becomes_stale():

    campaign_id = uuid.uuid4()
    worker_id = "dead-worker"

    await create_campaign(campaign_id)

    stale_time = datetime.now(timezone.utc) - timedelta(
        seconds=30
    )

    agent_id = uuid.uuid4()

    async with SessionLocal() as session:
        agent = Agent(
            id=agent_id,
            campaign_id=campaign_id,
            name="Dead Worker Agent",
            state="RESERVED",
            version=1,
            reserved_by=worker_id,
            reserved_at=stale_time,
            last_heartbeat=stale_time,
            created_at=stale_time,
            updated_at=stale_time,
        )

        session.add(agent)
        await session.commit()

    heartbeat = HeartbeatService()

    async with SessionLocal() as session:
        agent = await session.get(
            Agent,
            agent_id,
        )

        assert agent is not None

        stale = await heartbeat.is_stale(
            agent,
            stale_after_sec=5,
        )

        assert stale is True

    await cleanup(campaign_id)


@pytest.mark.asyncio
async def test_reaper_recovers_agent_after_heartbeat_stops():

    campaign_id = uuid.uuid4()
    worker_id = "dead-worker"

    await create_campaign(campaign_id)

    stale_time = datetime.now(timezone.utc) - timedelta(
        seconds=30
    )

    agent_id = uuid.uuid4()

    async with SessionLocal() as session:
        agent = Agent(
            id=agent_id,
            campaign_id=campaign_id,
            name="Reaper Recovery Agent",
            state="RESERVED",
            version=1,
            reserved_by=worker_id,
            reserved_at=stale_time,
            last_heartbeat=stale_time,
            created_at=stale_time,
            updated_at=stale_time,
        )

        session.add(agent)
        await session.commit()

    reaper = Reaper()

    async with SessionLocal() as session:
        result = await reaper.run_once(
            session=session,
        )

        await session.commit()

        assert result["stale_agents"] >= 1

    async with SessionLocal() as session:
        agent = await session.get(
            Agent,
            agent_id,
        )

        assert agent is not None
        assert agent.state == "AVAILABLE"
        assert agent.reserved_by is None
        assert agent.reserved_at is None

    await cleanup(campaign_id)