import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

from smartdialer.db import SessionLocal
from smartdialer.models import Agent, Campaign
from smartdialer.models.borrower import Borrower
from smartdialer.models.call import Call
from smartdialer.reaper import Reaper


@pytest.mark.asyncio
async def test_reaper_releases_stale_agent():
    campaign_id = uuid.uuid4()
    agent_id = uuid.uuid4()

    stale_time = datetime.now(timezone.utc) - timedelta(
        seconds=30
    )

    async with SessionLocal() as session:
        campaign = Campaign(
            id=campaign_id,
            name="Reaper Test",
            mode="PROGRESSIVE",
            max_overdial_cap=50,
            active=True,
            created_at=stale_time,
            updated_at=stale_time,
        )

        agent = Agent(
            id=agent_id,
            campaign_id=campaign_id,
            name="Stale Agent",
            state="RESERVED",
            version=1,
            reserved_by="dead-worker",
            reserved_at=stale_time,
            created_at=stale_time,
            updated_at=stale_time,
        )

        session.add_all([
            campaign,
            agent,
        ])

        await session.commit()

    reaper = Reaper()

    async with SessionLocal() as session:
        async with session.begin():
            result = await reaper.run_once(session)

            assert result["stale_agents"] >= 1

    async with SessionLocal() as session:
        agent = await session.get(Agent, agent_id)

        assert agent is not None
        assert agent.state == "AVAILABLE"
        assert agent.reserved_by is None
        assert agent.reserved_at is None
        assert agent.version == 2

        await session.execute(
            delete(Agent).where(Agent.id == agent_id)
        )

        await session.execute(
            delete(Campaign).where(Campaign.id == campaign_id)
        )

        await session.commit()
        
@pytest.mark.asyncio
async def test_reaper_fails_stale_call():
    campaign_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    borrower_id = uuid.uuid4()
    call_id = uuid.uuid4()

    stale_time = datetime.now(timezone.utc) - timedelta(
        seconds=30
    )

    async with SessionLocal() as session:
        campaign = Campaign(
            id=campaign_id,
            name="Stale Call Test",
            mode="PROGRESSIVE",
            max_overdial_cap=50,
            active=True,
            created_at=stale_time,
            updated_at=stale_time,
        )

        agent = Agent(
            id=agent_id,
            campaign_id=campaign_id,
            name="Call Test Agent",
            state="RESERVED",
            version=1,
            reserved_by="dead-worker",
            reserved_at=stale_time,
            created_at=stale_time,
            updated_at=stale_time,
        )

        borrower = Borrower(
            id=borrower_id,
            campaign_id=campaign_id,
            phone_number="+911234567890",
            status="RESERVED",
            priority=1,
            attempt_count=1,
            last_attempt_at=stale_time,
            created_at=stale_time,
            updated_at=stale_time,
        )

        call = Call(
            id=call_id,
            campaign_id=campaign_id,
            agent_id=agent_id,
            borrower_id=borrower_id,
            state="RESERVED",
            attempt_number=1,
            idempotency_key=f"reaper-test-{call_id}",
            reserved_at=stale_time,
            version=0,
            created_at=stale_time,
            updated_at=stale_time,
        )

        session.add_all([
            campaign,
            agent,
            borrower,
            call,
        ])

        await session.commit()

    reaper = Reaper()

    async with SessionLocal() as session:
        async with session.begin():
            result = await reaper.run_once(session)

            assert result["stale_calls"] >= 1

    async with SessionLocal() as session:
        call = await session.get(Call, call_id)

        assert call is not None
        assert call.state == "FAILED"
        assert call.version == 1

        # Clean up
        await session.delete(call)

        borrower = await session.get(Borrower, borrower_id)
        if borrower:
            await session.delete(borrower)

        agent = await session.get(Agent, agent_id)
        if agent:
            await session.delete(agent)

        campaign = await session.get(Campaign, campaign_id)
        if campaign:
            await session.delete(campaign)

        await session.commit()        