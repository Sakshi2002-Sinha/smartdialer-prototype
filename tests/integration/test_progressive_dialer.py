import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from smartdialer.db import SessionLocal
from smartdialer.dialer import ProgressiveDialer
from smartdialer.models import Agent, Campaign


@pytest.mark.asyncio
async def test_progressive_dialer_returns_available_capacity():
    campaign_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    async with SessionLocal() as session:

        campaign = Campaign(
            id=campaign_id,
            name="Progressive Test",
            mode="PROGRESSIVE",
            max_overdial_cap=50,
            active=True,
            created_at=now,
            updated_at=now,
        )

        agents = [
            Agent(
                id=uuid.uuid4(),
                campaign_id=campaign_id,
                name=f"Agent-{i}",
                state="AVAILABLE",
                version=0,
                created_at=now,
                updated_at=now,
            )
            for i in range(5)
        ]

        session.add(campaign)
        session.add_all(agents)

        await session.commit()

    dialer = ProgressiveDialer()

    async with SessionLocal() as session:
        count = await dialer.calculate_dial_count(
            session,
            campaign_id,
        )

        assert count == 5

    async with SessionLocal() as session:
        for agent in agents:
            await session.execute(
                delete(Agent).where(Agent.id == agent.id)
            )

        await session.execute(
            delete(Campaign).where(Campaign.id == campaign_id)
        )

        await session.commit()