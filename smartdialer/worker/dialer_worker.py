import asyncio
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from smartdialer.db import SessionLocal
from smartdialer.dialer import PredictiveDialer, ProgressiveDialer
from smartdialer.heartbeat import HeartbeatService
from smartdialer.models import Campaign
from smartdialer.orchestrator import DialingOrchestrator
from smartdialer.pacing import PacingInput
from smartdialer.provider import TelecomProvider


@dataclass(frozen=True)
class WorkerTickResult:
    campaign_id: uuid.UUID
    mode: str
    requested_calls: int
    successful_calls: int
    failed_calls: int
    reason: str


class DialerWorker:
    """
    Runtime worker responsible for executing dialing cycles.

    Architecture:

        Worker Runtime
             |
             +--------------------+
             |                    |
             v                    v
        HeartbeatService      run_once()
             |                    |
             v                    v
        AgentRepository      Dialer selection
                                  |
                         +--------+--------+
                         |                 |
                         v                 v
                    Progressive       Predictive
                         |                 |
                         +--------+--------+
                                  |
                                  v
                         DialingOrchestrator
                                  |
                                  v
                            CallAllocator
                                  |
                                  v
                           TelecomProvider

    Heartbeat is intentionally independent from dialing.
    """

    def __init__(
        self,
        provider: TelecomProvider,
        worker_id: str,
    ):
        self.provider = provider
        self.worker_id = worker_id

        self.progressive_dialer = ProgressiveDialer()
        self.predictive_dialer = PredictiveDialer()

        self.orchestrator = DialingOrchestrator(
            provider=provider,
        )

        self.heartbeat_service = HeartbeatService()

        self.running = False

    async def run_once(
        self,
        campaign_id: uuid.UUID,
    ) -> WorkerTickResult:
        """
        Execute exactly one worker tick for a campaign.
        """

        async with SessionLocal() as session:

            campaign = await session.get(
                Campaign,
                campaign_id,
            )

            if campaign is None:
                return WorkerTickResult(
                    campaign_id=campaign_id,
                    mode="UNKNOWN",
                    requested_calls=0,
                    successful_calls=0,
                    failed_calls=0,
                    reason="CAMPAIGN_NOT_FOUND",
                )

            if not campaign.active:
                return WorkerTickResult(
                    campaign_id=campaign_id,
                    mode=campaign.mode,
                    requested_calls=0,
                    successful_calls=0,
                    failed_calls=0,
                    reason="CAMPAIGN_INACTIVE",
                )

            if campaign.mode == "PROGRESSIVE":

                requested_calls = (
                    await self.progressive_dialer.calculate_dial_count(
                        session,
                        campaign_id,
                    )
                )

                return await self._execute_calls(
                    campaign_id=campaign_id,
                    mode=campaign.mode,
                    requested_calls=requested_calls,
                )

            if campaign.mode == "PREDICTIVE":

                return await self._run_predictive(
                    campaign=campaign,
                )

            return WorkerTickResult(
                campaign_id=campaign_id,
                mode=campaign.mode,
                requested_calls=0,
                successful_calls=0,
                failed_calls=0,
                reason="UNSUPPORTED_CAMPAIGN_MODE",
            )

    async def heartbeat(
        self,
        campaign_id: uuid.UUID,
    ) -> int:
        """
        Send a heartbeat for all agents currently reserved
        by this worker in the campaign.

        Returns the number of agents updated.

        The heartbeat owns its own short transaction and does
        not interfere with dialing transactions.
        """

        async with SessionLocal() as session:

            async with session.begin():

                return await (
                    self.heartbeat_service.heartbeat_for_worker(
                        session=session,
                        campaign_id=campaign_id,
                        worker_id=self.worker_id,
                    )
                )

    async def _run_predictive(
        self,
        campaign: Campaign,
    ) -> WorkerTickResult:
        """
        Build predictive pacing input and execute the approved
        number of calls.

        SafetyController remains authoritative.
        """

        async with SessionLocal() as session:

            available_agents = (
                await self.progressive_dialer.available_agent_count(
                    session,
                    campaign.id,
                )
            )

            active_calls = (
                await self.progressive_dialer.active_call_count(
                    session,
                    campaign.id,
                )
            )

            pacing_input = PacingInput(
                available_agents=available_agents,
                active_calls=active_calls,
                ringing_calls=0,
                predicted_answer_rate=0.5,
                provider_health=self.provider.health(),
                average_call_duration_sec=90,
                average_call_setup_sec=2,
            )

            decision = self.predictive_dialer.decide(
                pacing_input,
            )

            if decision.approved_calls <= 0:
                return WorkerTickResult(
                    campaign_id=campaign.id,
                    mode=campaign.mode,
                    requested_calls=decision.requested_calls,
                    successful_calls=0,
                    failed_calls=0,
                    reason=decision.safety_reason,
                )

        return await self._execute_calls(
            campaign_id=campaign.id,
            mode=campaign.mode,
            requested_calls=decision.approved_calls,
        )

    async def _execute_calls(
        self,
        campaign_id: uuid.UUID,
        mode: str,
        requested_calls: int,
    ) -> WorkerTickResult:
        """
        Execute individual dialing attempts.

        Each call gets its own SQLAlchemy session and transaction.
        """

        successful_calls = 0
        failed_calls = 0

        for _ in range(requested_calls):

            async with SessionLocal() as session:

                try:
                    async with session.begin():

                        result = await self.orchestrator.dial_one(
                            session=session,
                            campaign_id=campaign_id,
                            worker_id=self.worker_id,
                        )

                        if result.success:
                            successful_calls += 1
                        else:
                            failed_calls += 1

                except Exception:
                    failed_calls += 1

        if successful_calls > 0:
            reason = "CALLS_EXECUTED"
        elif failed_calls > 0:
            reason = "NO_CALLS_EXECUTED"
        else:
            reason = "NO_CALLS_REQUESTED"

        return WorkerTickResult(
            campaign_id=campaign_id,
            mode=mode,
            requested_calls=requested_calls,
            successful_calls=successful_calls,
            failed_calls=failed_calls,
            reason=reason,
        )

    async def run_forever(
        self,
        campaign_id: uuid.UUID,
        interval_sec: float = 1.0,
    ) -> None:
        """
        Continuously execute worker ticks.

        Every iteration:

            1. Heartbeat this worker's reserved agents.
            2. Execute one dialing tick.
            3. Sleep until the next iteration.
        """

        self.running = True

        try:
            while self.running:

                # Keep currently reserved agents alive.
                try:
                    await self.heartbeat(
                        campaign_id,
                    )
                except Exception:
                    # Heartbeat failure must not kill the
                    # dialing runtime.
                    pass

                await self.run_once(
                    campaign_id,
                )

                await asyncio.sleep(
                    interval_sec,
                )

        except asyncio.CancelledError:
            self.running = False
            raise

        finally:
            self.running = False

    def stop(self) -> None:
        """
        Gracefully stop the worker loop.
        """

        self.running = False