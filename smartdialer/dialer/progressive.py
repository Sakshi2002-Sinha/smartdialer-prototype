from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from smartdialer.models import Agent, Call


class ProgressiveDialer:

    async def available_agent_count(
        self,
        session: AsyncSession,
        campaign_id,
    ) -> int:
        result = await session.execute(
            select(func.count(Agent.id))
            .where(
                Agent.campaign_id == campaign_id,
                Agent.state == "AVAILABLE",
            )
        )

        return result.scalar_one()

    async def active_call_count(
        self,
        session: AsyncSession,
        campaign_id,
    ) -> int:
        result = await session.execute(
            select(func.count(Call.id))
            .where(
                Call.campaign_id == campaign_id,
                Call.state.in_(
                    [
                        "RESERVED",
                        "INITIATED",
                        "RINGING",
                        "ANSWERED",
                        "CONNECTED",
                    ]
                ),
                Call.agent_id.is_not(None),
            )
        )

        return result.scalar_one()

    async def calculate_dial_count(
        self,
        session: AsyncSession,
        campaign_id,
    ) -> int:
        available_agents = await self.available_agent_count(
            session,
            campaign_id,
        )

        active_calls = await self.active_call_count(
            session,
            campaign_id,
        )

        capacity = max(
            0,
            available_agents - active_calls,
        )

        return capacity