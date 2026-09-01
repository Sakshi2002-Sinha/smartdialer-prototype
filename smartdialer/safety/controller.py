from dataclasses import dataclass


@dataclass(frozen=True)
class SafetyRequest:
    requested_calls: int
    available_agents: int
    active_calls: int
    provider_health: float
    predicted_answer_rate: float


@dataclass(frozen=True)
class SafetyDecision:
    approved_calls: int
    reason: str
    fallback_progressive: bool = False


class SafetyController:

    def __init__(
        self,
        min_provider_health: float = 0.5,
        max_overdial_cap: int = 50,
        max_abandon_risk: int = 3,
    ):
        self.min_provider_health = min_provider_health
        self.max_overdial_cap = max_overdial_cap
        self.max_abandon_risk = max_abandon_risk

    def evaluate(
        self,
        request: SafetyRequest,
    ) -> SafetyDecision:

        # --------------------------------------------------
        # Rule 1: invalid request
        # --------------------------------------------------

        if request.requested_calls <= 0:
            return SafetyDecision(
                approved_calls=0,
                reason="NO_REQUEST",
            )

        # --------------------------------------------------
        # Rule 2: provider health
        # --------------------------------------------------

        if request.provider_health < self.min_provider_health:
            return SafetyDecision(
                approved_calls=0,
                reason="PROVIDER_UNHEALTHY",
                fallback_progressive=True,
            )

        # --------------------------------------------------
        # Rule 3: available-agent capacity
        # --------------------------------------------------

        agent_capacity = max(
            0,
            request.available_agents - request.active_calls,
        )

        # --------------------------------------------------
        # Rule 4: hard over-dial cap
        # --------------------------------------------------

        capped_request = min(
            request.requested_calls,
            self.max_overdial_cap,
        )

        allowed = min(
            capped_request,
            agent_capacity,
        )

        # --------------------------------------------------
        # Rule 5: connected-call risk
        # --------------------------------------------------

        expected_answers = (
            allowed * request.predicted_answer_rate
        )

        excess_risk = max(
            0,
            int(expected_answers - request.available_agents),
        )

        if excess_risk > self.max_abandon_risk:
            safe_calls = 0

            if request.predicted_answer_rate > 0:
                safe_calls = int(
                    (
                        request.available_agents
                        + self.max_abandon_risk
                    )
                    / request.predicted_answer_rate
                )

            allowed = min(
                allowed,
                max(0, safe_calls),
            )

        if allowed == 0:
            return SafetyDecision(
                approved_calls=0,
                reason="SAFETY_CAPACITY_LIMIT",
            )

        if allowed < request.requested_calls:
            return SafetyDecision(
                approved_calls=allowed,
                reason="REDUCED_BY_SAFETY",
            )

        return SafetyDecision(
            approved_calls=allowed,
            reason="APPROVED",
        )