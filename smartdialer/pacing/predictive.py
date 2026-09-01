
import math
from dataclasses import dataclass


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

    This component ONLY recommends how many calls
    should be attempted.

    It does not:
    - reserve agents
    - reserve borrowers
    - allocate calls
    - call telecom providers
    - bypass the SafetyController
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

        if pacing_input.available_agents <= 0:
            return PacingDecision(
                recommended_calls=0,
                reason="NO_AVAILABLE_AGENTS",
            )

        if pacing_input.predicted_answer_rate <= 0:
            return PacingDecision(
                recommended_calls=0,
                reason="NO_EXPECTED_ANSWERS",
            )

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

        desired_answers = (
            free_capacity
            + self.target_answered_buffer
        )

        estimated_calls = math.ceil(
            desired_answers
            / pacing_input.predicted_answer_rate
        )

        # Calls already ringing are expected to consume
        # agent capacity soon.
        estimated_calls = max(
            0,
            estimated_calls
            - pacing_input.ringing_calls,
        )

        # Become conservative when provider health
        # starts deteriorating.
        if pacing_input.provider_health < 0.8:
            estimated_calls = max(
                1,
                estimated_calls // 2,
            )

        # Stop predictive dialing when provider health
        # is critically low.
        if pacing_input.provider_health < 0.6:
            estimated_calls = 0

        # This is only a pacing recommendation.
        # SafetyController remains the final authority.
        estimated_calls = min(
            estimated_calls,
            self.max_overdial_cap,
        )

        if estimated_calls == 0:
            return PacingDecision(
                recommended_calls=0,
                reason="PROVIDER_OR_CAPACITY_CONSTRAINT",
            )

        return PacingDecision(
            recommended_calls=estimated_calls,
            reason="PREDICTIVE_ESTIMATE",
        )
