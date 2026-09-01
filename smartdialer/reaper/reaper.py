import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from smartdialer.models import Agent, Call
from smartdialer.config import settings


class Reaper:

    async def reap_stale_agents(
        self,
        session: AsyncSession,
    ) -> int:
        """
        Release agents whose reservation TTL has expired.

        We first identify stale agents and then update them.
        This keeps the recovery logic explicit and easy to reason about.
        """

        now = datetime.now(timezone.utc)

        cutoff = now - timedelta(
            seconds=settings.agent_reservation_ttl_sec
        )

        result = await session.execute(
            select(Agent)
            .where(
                Agent.state == "RESERVED",
                Agent.reserved_at.is_not(None),
                Agent.reserved_at < cutoff,
            )
        )

        agents = result.scalars().all()

        recovered = 0

        for agent in agents:
            # Re-check the state before modifying it.
            # Another worker may have changed it after our SELECT.
            if agent.state != "RESERVED":
                continue

            agent.state = "AVAILABLE"
            agent.reserved_by = None
            agent.reserved_at = None
            agent.version += 1
            agent.updated_at = now

            recovered += 1

        return recovered

    async def reap_stale_calls(
        self,
        session: AsyncSession,
    ) -> int:
        """
        Mark calls stuck in RESERVED beyond the call setup TTL
        as FAILED.
        """

        now = datetime.now(timezone.utc)

        cutoff = now - timedelta(
            seconds=settings.call_setup_ttl_sec
        )

        result = await session.execute(
            update(Call)
            .where(
                Call.state == "RESERVED",
                Call.reserved_at.is_not(None),
                Call.reserved_at < cutoff,
            )
            .values(
                state="FAILED",
        
                updated_at=now,
                version=Call.version + 1,
            )
        )

        return result.rowcount

    async def run_once(
        self,
        session: AsyncSession,
    ) -> dict[str, int]:
        """
        Execute one reaper cycle.
        """

        stale_calls = await self.reap_stale_calls(session)

        stale_agents = await self.reap_stale_agents(session)

        return {
            "stale_calls": stale_calls,
            "stale_agents": stale_agents,
        }