import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smartdialer.allocator import AllocationResult, CallAllocator
from smartdialer.models import Borrower, Call
from smartdialer.provider import TelecomProvider
from smartdialer.state_machine import CallState, transition_call


class DialingError(Exception):
    """Raised when a dialing operation cannot be completed."""


@dataclass(frozen=True)
class DialingResult:
    success: bool
    call: Call | None = None
    reason: str | None = None


class DialingOrchestrator:
    """
    Coordinates call allocation and telecom provider initiation.

    Flow:

        CallAllocator
             ↓
        RESERVED call
             ↓
        TelecomProvider
             ↓
        INITIATED / FAILED

    The caller owns the SQLAlchemy transaction.

    This class never commits or rolls back the session.
    """

    def __init__(
        self,
        provider: TelecomProvider,
        allocator: CallAllocator | None = None,
    ):
        self.provider = provider
        self.allocator = allocator or CallAllocator()

    async def dial_one(
        self,
        session: AsyncSession,
        campaign_id: uuid.UUID,
        worker_id: str,
    ) -> DialingResult:
        """
        Allocate one call and attempt provider initiation.

        Success:

            RESERVED → INITIATED

        Provider failure:

            RESERVED → FAILED
            Agent → AVAILABLE
            Borrower → PENDING
        """

        # --------------------------------------------------
        # 1. Allocate agent + borrower + call atomically.
        #
        # AllocationError is intentionally allowed to propagate.
        # The caller owns the transaction and can roll it back.
        # --------------------------------------------------

        allocation: AllocationResult = await self.allocator.allocate(
            session=session,
            campaign_id=campaign_id,
            worker_id=worker_id,
        )

        if not allocation.success:
            return DialingResult(
                success=False,
                reason=allocation.reason,
            )

        call = allocation.call

        if call is None:
            raise DialingError(
                "Allocator reported success without a call"
            )

        if call.state != CallState.RESERVED.value:
            raise DialingError(
                f"Expected RESERVED call, got {call.state}"
            )

        # --------------------------------------------------
        # 2. Explicitly load borrower.
        #
        # Do NOT use:
        #
        #     call.borrower.phone_number
        #
        # because that triggers SQLAlchemy async lazy loading
        # and can cause MissingGreenlet.
        # --------------------------------------------------

        borrower_result = await session.execute(
            select(Borrower.phone_number).where(
                Borrower.id == call.borrower_id
            )
        )

        phone_number = borrower_result.scalar_one_or_none()

        if phone_number is None:
            raise DialingError(
                f"Borrower {call.borrower_id} not found"
            )

        # --------------------------------------------------
        # 3. Initiate the telecom call.
        # --------------------------------------------------

        try:
            provider_result = await self.provider.initiate_call(
                call_id=str(call.id),
                phone_number=phone_number,
            )

        except Exception as exc:
            reason = str(exc) or "PROVIDER_ERROR"

            await self._handle_provider_failure(
                session=session,
                call=call,
                worker_id=worker_id,
                reason=reason,
            )

            return DialingResult(
                success=False,
                call=call,
                reason=reason,
            )

        # --------------------------------------------------
        # 4. Provider explicitly rejected the call.
        # --------------------------------------------------

        if not provider_result.accepted:
            reason = (
                provider_result.error
                or "PROVIDER_REJECTED"
            )

            await self._handle_provider_failure(
                session=session,
                call=call,
                worker_id=worker_id,
                reason=reason,
            )

            return DialingResult(
                success=False,
                call=call,
                reason=reason,
            )

        # --------------------------------------------------
        # 5. Provider accepted the call.
        #
        # RESERVED → INITIATED
        # --------------------------------------------------

        transition_call(
            CallState.RESERVED,
            CallState.INITIATED,
        )

        now = datetime.now(timezone.utc)

        call.state = CallState.INITIATED.value
        call.provider = type(self.provider).__name__
        call.provider_call_id = provider_result.provider_call_id
        call.initiated_at = now
        call.updated_at = now
        call.version += 1

        return DialingResult(
            success=True,
            call=call,
            reason="PROVIDER_ACCEPTED",
        )

    async def _handle_provider_failure(
        self,
        session: AsyncSession,
        call: Call,
        worker_id: str,
        reason: str,
    ) -> None:
        """
        Convert a provider failure into a failed call and release
        resources reserved by this worker.
        """

        transition_call(
            CallState.RESERVED,
            CallState.FAILED,
        )

        now = datetime.now(timezone.utc)

        call.state = CallState.FAILED.value
        call.failure_reason = reason
        call.updated_at = now
        call.version += 1

        # --------------------------------------------------
        # Release the exact agent reserved by this worker.
        # --------------------------------------------------

        if call.agent_id is not None:
            await self.allocator.agent_repository.release_agent(
                session=session,
                agent_id=call.agent_id,
                worker_id=worker_id,
            )

        # --------------------------------------------------
        # Return borrower to PENDING for retry.
        # --------------------------------------------------

        await self.allocator.borrower_repository.release_borrower(
            session=session,
            borrower_id=call.borrower_id,
        )