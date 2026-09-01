import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from smartdialer.db import SessionLocal
from smartdialer.models import Agent, Campaign
from smartdialer.repositories import AgentRepository

@pytest.mark.asyncio
async def test_two_workers_cannot_reserve_same_agent():
    campaign_id = uuid.uuid4()
    agent_id = uuid.uuid4()

    now = datetime.now(timezone.utc)

    async with SessionLocal() as session:
        campaign = Campaign(
            id=campaign_id,
            name="Concurrent Reservation Test",
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

        session.add(campaign)
        session.add(agent)

        await session.commit()

    async def attempt_reservation(worker_id: str):
        async with SessionLocal() as session:
            repo = AgentRepository()

            success = await repo.reserve_agent(
                session=session,
                agent_id=agent_id,
                worker_id=worker_id,
                expected_version=0,
            )

            await session.commit()

            return success

    worker_a, worker_b = await asyncio.gather(
        attempt_reservation("worker-A"),
        attempt_reservation("worker-B"),
    )

    # Exactly one worker must win.
    assert worker_a != worker_b
    assert worker_a or worker_b

    async with SessionLocal() as session:
        agent = await session.get(Agent, agent_id)

        assert agent is not None
        assert agent.state == "RESERVED"
        assert agent.reserved_by in {"worker-A", "worker-B"}
        assert agent.version == 1

        await session.execute(
            delete(Agent).where(Agent.id == agent_id)
        )

        await session.execute(
            delete(Campaign).where(Campaign.id == campaign_id)
        )

        await session.commit()