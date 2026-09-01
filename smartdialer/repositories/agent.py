import uuid
from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from smartdialer.models import Agent


class AgentRepository:

    async def reserve_agent(
        self,
        session: AsyncSession,
        agent_id: uuid.UUID,
        worker_id: str,
        expected_version: int,
    ) -> bool:
        """
        Atomically reserve an AVAILABLE agent.

        The reservation succeeds only if:
        - the agent is still AVAILABLE
        - the version is unchanged

        Returns True if this worker won the reservation race.
        """

        now = datetime.now(timezone.utc)

        result = await session.execute(
            update(Agent)
            .where(
                Agent.id == agent_id,
                Agent.state == "AVAILABLE",
                Agent.version == expected_version,
            )
            .values(
                state="RESERVED",
                reserved_by=worker_id,
                reserved_at=now,
                version=Agent.version + 1,
                updated_at=now,
            )
        )

        return result.rowcount == 1

    async def release_agent(
        self,
        session: AsyncSession,
        agent_id: uuid.UUID,
        worker_id: str,
    ) -> bool:
        """
        Release an agent reserved by this worker.
        """

        now = datetime.now(timezone.utc)

        result = await session.execute(
            update(Agent)
            .where(
                Agent.id == agent_id,
                Agent.state == "RESERVED",
                Agent.reserved_by == worker_id,
            )
            .values(
                state="AVAILABLE",
                reserved_by=None,
                reserved_at=None,
                version=Agent.version + 1,
                updated_at=now,
            )
        )

        return result.rowcount == 1

    async def heartbeat(
        self,
        session: AsyncSession,
        agent_id: uuid.UUID,
    ) -> bool:
        """
        Update the agent heartbeat.

        Only non-offline agents are allowed to heartbeat.
        """

        now = datetime.now(timezone.utc)

        result = await session.execute(
            update(Agent)
            .where(
                Agent.id == agent_id,
                Agent.state != "OFFLINE",
            )
            .values(
                last_heartbeat=now,
                updated_at=now,
            )
        )

        return result.rowcount == 1