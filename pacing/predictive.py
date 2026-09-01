from dataclasses import dataclass
import math

from smartdialer.dialer.predictive import PredictiveDialDecision
from smartdialer.safety.controller import SafetyDecision, SafetyRequest


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
        # 3. Provider completely unhealthy
        #
        # A very unhealthy provider should stop predictive
        # pacing entirely.
        #
        # The PredictiveDialer/SafetyController can then
        # activate progressive fallback.
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
        #
        # Example:
        #
        # free capacity = 5
        # answer rate = 50%
        #
        # desired answers = 5 + buffer
        # estimated calls = desired answers / 0.5
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
        # 6. Ringing calls are likely to consume capacity.
        #
        # Reduce the new dialing recommendation accordingly.
        # --------------------------------------------------

        estimated_calls = max(
            0,
            estimated_calls
            - pacing_input.ringing_calls,
        )

        # --------------------------------------------------
        # 7. Poor provider health.
        #
        # Health below 0.8 makes pacing conservative.
        # --------------------------------------------------

        if pacing_input.provider_health < 0.8:
            estimated_calls = max(
                1,
                estimated_calls // 2,
            )

        # --------------------------------------------------
        # 8. Hard recommendation cap.
        #
        # This is only a pacing cap.
        # SafetyController is still authoritative.
        # --------------------------------------------------

        estimated_calls = min(
            estimated_calls,
            self.max_overdial_cap,
        )

        # --------------------------------------------------
        # 9. Nothing safe/reasonable to recommend
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
    
    def decide(
        self,
        pacing_input: PacingInput,
    ) -> PredictiveDialDecision:

        # --------------------------------------------------
        # 1. Predictive engine recommends a number.
        # --------------------------------------------------

        pacing_decision = self.pacing_engine.calculate(
            pacing_input
        )

        # --------------------------------------------------
        # 2. Provider health is a safety condition.
        #
        # The pacing engine may return 0 calls when the
        # provider is severely unhealthy. In that case,
        # SafetyController would normally return NO_REQUEST
        # and never reach its provider-health rule.
        #
        # We explicitly preserve the provider-health
        # fallback here.
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
        # 3. Safety controller independently evaluates the
        # predictive recommendation.
        #
        # SafetyController remains authoritative.
        # --------------------------------------------------

        safety_request = SafetyRequest(
            requested_calls=pacing_decision.recommended_calls,
            available_agents=pacing_input.available_agents,
            active_calls=pacing_input.active_calls,
            provider_health=pacing_input.provider_health,
            predicted_answer_rate=pacing_input.predicted_answer_rate,
        )

        safety_decision: SafetyDecision = (
            self.safety_controller.evaluate(
                safety_request
            )
        )

        # --------------------------------------------------
        # 4. Return final decision.
        # --------------------------------------------------

        return PredictiveDialDecision(
            requested_calls=pacing_decision.recommended_calls,
            approved_calls=safety_decision.approved_calls,
            pacing_reason=pacing_decision.reason,
            safety_reason=safety_decision.reason,
            fallback_progressive=safety_decision.fallback_progressive,
        )    