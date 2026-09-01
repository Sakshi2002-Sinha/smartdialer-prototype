import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smartdialer.models import Agent
from smartdialer.repositories import AgentRepository


class HeartbeatService:
    """
    Maintains agent liveness.

    The service is deliberately small:

        Worker
          ↓
        HeartbeatService
          ↓
        AgentRepository
          ↓
        agents.last_heartbeat

    It does not change agent state and does not own
    transactions.
    """

    def __init__(
        self,
        agent_repository: AgentRepository | None = None,
    ):
        self.agent_repository = (
            agent_repository or AgentRepository()
        )

    async def heartbeat(
        self,
        session: AsyncSession,
        agent_id: uuid.UUID,
    ) -> bool:
        """
        Record a heartbeat for an active agent.

        Returns False when:
        - the agent does not exist
        - the agent is OFFLINE
        """

        return await self.agent_repository.heartbeat(
            session=session,
            agent_id=agent_id,
        )

    async def heartbeat_for_worker(
        self,
        session: AsyncSession,
        campaign_id: uuid.UUID,
        worker_id: str,
    ) -> int:
        """
        Heartbeat all active agents currently reserved by
        this worker in the campaign.

        Returns the number of agents updated.
        """

        result = await session.execute(
            select(Agent.id).where(
                Agent.campaign_id == campaign_id,
                Agent.reserved_by == worker_id,
                Agent.state != "OFFLINE",
            )
        )

        agent_ids = result.scalars().all()

        updated = 0

        for agent_id in agent_ids:
            success = await self.heartbeat(
                session=session,
                agent_id=agent_id,
            )

            if success:
                updated += 1

        return updated

    async def is_stale(
        self,
        agent: Agent,
        stale_after_sec: int,
    ) -> bool:
        """
        Determine whether an agent heartbeat is stale.
        """

        if agent.last_heartbeat is None:
            return True

        now = datetime.now(timezone.utc)

        heartbeat_time = agent.last_heartbeat

        if heartbeat_time.tzinfo is None:
            heartbeat_time = heartbeat_time.replace(
                tzinfo=timezone.utc
            )

        age = (
            now - heartbeat_time
        ).total_seconds()

        return age > stale_after_sec