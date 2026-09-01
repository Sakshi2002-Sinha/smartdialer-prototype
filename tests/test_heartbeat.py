import uuid
from datetime import datetime, timedelta, timezone

import pytest

from smartdialer.db import SessionLocal
from smartdialer.heartbeat import HeartbeatService
from smartdialer.models import Agent, Campaign


@pytest.mark.asyncio
async def test_heartbeat_updates_active_agent():
    campaign_id = uuid.uuid4()
    agent_id = uuid.uuid4()

    old_time = (
        datetime.now(timezone.utc)
        - timedelta(seconds=10)
    )

    async with SessionLocal() as session:
        campaign = Campaign(
            id=campaign_id,
            name="Heartbeat Test",
            mode="PROGRESSIVE",
            max_overdial_cap=50,
            active=True,
            created_at=old_time,
            updated_at=old_time,
        )

        agent = Agent(
            id=agent_id,
            campaign_id=campaign_id,
            name="Heartbeat Agent",
            state="AVAILABLE",
            version=0,
            last_heartbeat=old_time,
            created_at=old_time,
            updated_at=old_time,
        )

        session.add_all([campaign, agent])
        await session.commit()

    service = HeartbeatService()

    async with SessionLocal() as session:
        before = datetime.now(timezone.utc)

        result = await service.heartbeat(
            session=session,
            agent_id=agent_id,
        )

        await session.commit()

        assert result is True

    async with SessionLocal() as session:
        updated_agent = await session.get(
            Agent,
            agent_id,
        )

        assert updated_agent is not None
        assert updated_agent.last_heartbeat is not None
        assert updated_agent.last_heartbeat >= before

        await session.delete(updated_agent)
        await session.delete(
            await session.get(Campaign, campaign_id)
        )
        await session.commit()


@pytest.mark.asyncio
async def test_heartbeat_does_not_update_offline_agent():
    campaign_id = uuid.uuid4()
    agent_id = uuid.uuid4()

    old_time = (
        datetime.now(timezone.utc)
        - timedelta(seconds=10)
    )

    async with SessionLocal() as session:
        campaign = Campaign(
            id=campaign_id,
            name="Offline Heartbeat Test",
            mode="PROGRESSIVE",
            max_overdial_cap=50,
            active=True,
            created_at=old_time,
            updated_at=old_time,
        )

        agent = Agent(
            id=agent_id,
            campaign_id=campaign_id,
            name="Offline Agent",
            state="OFFLINE",
            version=0,
            last_heartbeat=old_time,
            created_at=old_time,
            updated_at=old_time,
        )

        session.add_all([campaign, agent])
        await session.commit()

    service = HeartbeatService()

    async with SessionLocal() as session:
        result = await service.heartbeat(
            session=session,
            agent_id=agent_id,
        )

        await session.commit()

        assert result is False

    async with SessionLocal() as session:
        agent = await session.get(
            Agent,
            agent_id,
        )

        assert agent is not None
        assert agent.last_heartbeat == old_time

        await session.delete(agent)
        await session.delete(
            await session.get(Campaign, campaign_id)
        )
        await session.commit()


@pytest.mark.asyncio
async def test_heartbeat_for_worker_updates_reserved_agents():
    campaign_id = uuid.uuid4()
    worker_id = "heartbeat-worker"

    now = datetime.now(timezone.utc)

    async with SessionLocal() as session:
        campaign = Campaign(
            id=campaign_id,
            name="Worker Heartbeat Test",
            mode="PROGRESSIVE",
            max_overdial_cap=50,
            active=True,
            created_at=now,
            updated_at=now,
        )

        matching_agent = Agent(
            id=uuid.uuid4(),
            campaign_id=campaign_id,
            name="Matching Agent",
            state="RESERVED",
            version=1,
            reserved_by=worker_id,
            reserved_at=now,
            created_at=now,
            updated_at=now,
        )

        other_agent = Agent(
            id=uuid.uuid4(),
            campaign_id=campaign_id,
            name="Other Agent",
            state="RESERVED",
            version=1,
            reserved_by="other-worker",
            reserved_at=now,
            created_at=now,
            updated_at=now,
        )

        session.add_all([
            campaign,
            matching_agent,
            other_agent,
        ])

        await session.commit()

        matching_agent_id = matching_agent.id
        other_agent_id = other_agent.id

    service = HeartbeatService()

    async with SessionLocal() as session:
        count = await service.heartbeat_for_worker(
            session=session,
            campaign_id=campaign_id,
            worker_id=worker_id,
        )

        await session.commit()

        assert count == 1

    async with SessionLocal() as session:
        updated_matching = await session.get(
            Agent,
            matching_agent_id,
        )

        updated_other = await session.get(
            Agent,
            other_agent_id,
        )

        assert updated_matching is not None
        assert updated_matching.last_heartbeat is not None

        assert updated_other is not None
        assert updated_other.last_heartbeat is None

        await session.delete(updated_matching)
        await session.delete(updated_other)
        await session.delete(
            await session.get(Campaign, campaign_id)
        )
        await session.commit()


@pytest.mark.asyncio
async def test_stale_agent_without_heartbeat_is_stale():
    campaign_id = uuid.uuid4()

    now = datetime.now(timezone.utc)

    async with SessionLocal() as session:
        campaign = Campaign(
            id=campaign_id,
            name="Stale Heartbeat Test",
            mode="PROGRESSIVE",
            max_overdial_cap=50,
            active=True,
            created_at=now,
            updated_at=now,
        )

        agent = Agent(
            id=uuid.uuid4(),
            campaign_id=campaign_id,
            name="Stale Agent",
            state="AVAILABLE",
            version=0,
            last_heartbeat=None,
            created_at=now,
            updated_at=now,
        )

        session.add_all([campaign, agent])
        await session.commit()

        service = HeartbeatService()

        assert await service.is_stale(
            agent,
            stale_after_sec=5,
        ) is True

        await session.delete(agent)
        await session.delete(campaign)
        await session.commit()


@pytest.mark.asyncio
async def test_recent_heartbeat_is_not_stale():
    campaign_id = uuid.uuid4()

    now = datetime.now(timezone.utc)

    async with SessionLocal() as session:
        campaign = Campaign(
            id=campaign_id,
            name="Fresh Heartbeat Test",
            mode="PROGRESSIVE",
            max_overdial_cap=50,
            active=True,
            created_at=now,
            updated_at=now,
        )

        agent = Agent(
            id=uuid.uuid4(),
            campaign_id=campaign_id,
            name="Fresh Agent",
            state="AVAILABLE",
            version=0,
            last_heartbeat=now,
            created_at=now,
            updated_at=now,
        )

        session.add_all([campaign, agent])
        await session.commit()

        service = HeartbeatService()

        assert await service.is_stale(
            agent,
            stale_after_sec=5,
        ) is False

        await session.delete(agent)
        await session.delete(campaign)
        await session.commit()