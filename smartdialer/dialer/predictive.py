from dataclasses import dataclass
import math

from smartdialer.safety import (
    SafetyController,
    SafetyDecision,
    SafetyRequest,
)


# ============================================================
# Predictive Pacing
# ============================================================

@dataclass(frozen=True)
class PacingInput:
    available_agents: int
    active_calls: int
    ringing_calls: int
    predicted_answer_rate: float
    provider_health: float
    average_call_duration_sec: float
    average_call_setup_sec: float


@dataclass(frozen=True)
class PacingDecision:
    recommended_calls: int
    reason: str


class PredictivePacingEngine:
    """
    Conservative predictive pacing engine.

    This class ONLY recommends how many calls could be started.

    It never:
    - reserves agents
    - allocates borrowers
    - calls telecom providers
    - bypasses SafetyController

    SafetyController remains the final authority for
    approving actual calls.
    """

    def __init__(
        self,
        max_overdial_cap: int = 50,
        target_answered_buffer: int = 1,
    ):
        self.max_overdial_cap = max_overdial_cap
        self.target_answered_buffer = target_answered_buffer

    def calculate(
        self,
        pacing_input: PacingInput,
    ) -> PacingDecision:

        # --------------------------------------------------
        # 1. No available agents
        # --------------------------------------------------

        if pacing_input.available_agents <= 0:
            return PacingDecision(
                recommended_calls=0,
                reason="NO_AVAILABLE_AGENTS",
            )

        # --------------------------------------------------
        # 2. No expected answers
        # --------------------------------------------------

        if pacing_input.predicted_answer_rate <= 0:
            return PacingDecision(
                recommended_calls=0,
                reason="NO_EXPECTED_ANSWERS",
            )

        # --------------------------------------------------
        # 3. Very unhealthy provider
        #
        # Predictive pacing stops.
        #
        # PredictiveDialer will convert this into a
        # progressive fallback decision.
        # --------------------------------------------------

        if pacing_input.provider_health < 0.6:
            return PacingDecision(
                recommended_calls=0,
                reason="PROVIDER_OR_CAPACITY_CONSTRAINT",
            )

        # --------------------------------------------------
        # 4. Calculate free agent capacity
        # --------------------------------------------------

        free_capacity = max(
            0,
            pacing_input.available_agents
            - pacing_input.active_calls,
        )

        if free_capacity <= 0:
            return PacingDecision(
                recommended_calls=0,
                reason="NO_FREE_CAPACITY",
            )

        # --------------------------------------------------
        # 5. Estimate required calls
        # --------------------------------------------------

        desired_answers = (
            free_capacity
            + self.target_answered_buffer
        )

        estimated_calls = math.ceil(
            desired_answers
            / pacing_input.predicted_answer_rate
        )

        # --------------------------------------------------
        # 6. Account for ringing calls
        #
        # Ringing calls are expected to consume capacity.
        # --------------------------------------------------

        estimated_calls = max(
            0,
            estimated_calls
            - pacing_input.ringing_calls,
        )

        # --------------------------------------------------
        # 7. Poor provider health
        #
        # Provider health below 0.8 makes predictive
        # pacing more conservative.
        # --------------------------------------------------

        if pacing_input.provider_health < 0.8:
            estimated_calls = max(
                1,
                estimated_calls // 2,
            )

        # --------------------------------------------------
        # 8. Hard recommendation cap
        #
        # This is NOT the final safety boundary.
        # SafetyController remains authoritative.
        # --------------------------------------------------

        estimated_calls = min(
            estimated_calls,
            self.max_overdial_cap,
        )

        # --------------------------------------------------
        # 9. No calls recommended
        # --------------------------------------------------

        if estimated_calls == 0:
            return PacingDecision(
                recommended_calls=0,
                reason="PROVIDER_OR_CAPACITY_CONSTRAINT",
            )

        # --------------------------------------------------
        # 10. Return predictive recommendation
        # --------------------------------------------------

        return PacingDecision(
            recommended_calls=estimated_calls,
            reason="PREDICTIVE_ESTIMATE",
        )


# ============================================================
# Predictive Dialer
# ============================================================

@dataclass(frozen=True)
class PredictiveDialDecision:
    requested_calls: int
    approved_calls: int
    pacing_reason: str
    safety_reason: str
    fallback_progressive: bool


class PredictiveDialer:
    """
    Coordinates predictive pacing and deterministic safety.

    Architectural invariant:

        Pacing Engine -> Safety Controller

    The pacing engine only recommends a number.

    SafetyController has final authority over the number
    of calls that may actually be initiated.
    """

    def __init__(
        self,
        pacing_engine: PredictivePacingEngine | None = None,
        safety_controller: SafetyController | None = None,
    ):
        self.pacing_engine = (
            pacing_engine
            or PredictivePacingEngine()
        )

        self.safety_controller = (
            safety_controller
            or SafetyController()
        )

    def decide(
        self,
        pacing_input: PacingInput,
    ) -> PredictiveDialDecision:

        # --------------------------------------------------
        # 1. Get predictive recommendation
        # --------------------------------------------------

        pacing_decision = self.pacing_engine.calculate(
            pacing_input
        )

        # --------------------------------------------------
        # 2. Provider health is an explicit safety boundary
        #
        # The pacing engine may return 0 calls for a severely
        # unhealthy provider.
        #
        # If we passed requested_calls=0 directly to the
        # SafetyController, its NO_REQUEST rule would execute
        # before its provider-health rule.
        #
        # Therefore preserve the provider-health fallback here.
        # --------------------------------------------------

        if (
            pacing_input.provider_health
            < self.safety_controller.min_provider_health
        ):
            return PredictiveDialDecision(
                requested_calls=pacing_decision.recommended_calls,
                approved_calls=0,
                pacing_reason=pacing_decision.reason,
                safety_reason="PROVIDER_UNHEALTHY",
                fallback_progressive=True,
            )

        # --------------------------------------------------
        # 3. Build safety request
        # --------------------------------------------------

        safety_request = SafetyRequest(
            requested_calls=pacing_decision.recommended_calls,
            available_agents=pacing_input.available_agents,
            active_calls=pacing_input.active_calls,
            provider_health=pacing_input.provider_health,
            predicted_answer_rate=pacing_input.predicted_answer_rate,
        )

        # --------------------------------------------------
        # 4. SafetyController is authoritative
        # --------------------------------------------------

        safety_decision: SafetyDecision = (
            self.safety_controller.evaluate(
                safety_request
            )
        )

        # --------------------------------------------------
        # 5. Return final decision
        # --------------------------------------------------

        return PredictiveDialDecision(
            requested_calls=pacing_decision.recommended_calls,
            approved_calls=safety_decision.approved_calls,
            pacing_reason=pacing_decision.reason,
            safety_reason=safety_decision.reason,
            fallback_progressive=safety_decision.fallback_progressive,
        )