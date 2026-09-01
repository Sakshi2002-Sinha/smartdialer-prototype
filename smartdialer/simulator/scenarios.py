
from dataclasses import dataclass
import random

from smartdialer.pacing import PacingInput, PredictivePacingEngine
from smartdialer.safety import SafetyController


@dataclass(frozen=True)
class SimulationScenario:
    name: str
    answer_rate: float
    average_talk_time_sec: float
    provider_latency_ms: int
    provider_failure_rate: float
    duration_sec: int = 300
    agents: int = 50


@dataclass(frozen=True)
class SimulationResult:
    scenario: str
    agents: int
    answer_rate: float
    average_talk_time_sec: float
    provider_latency_ms: int
    provider_failure_rate: float
    calls_initiated: int
    calls_answered: int
    calls_connected: int
    calls_failed: int
    safety_approved: int
    safety_reduced: int
    safety_rejected: int
    average_utilization: float
    peak_active_calls: int


@dataclass
class SimulatedCall:
    start_time: int
    answer_time: int | None
    end_time: int
    answered: bool


class SmartDialerSimulator:
    """
    Lightweight deterministic simulation of the SmartDialer.

    This deliberately does not use the database or telecom providers.
    It exercises the same pacing + safety decision logic under
    controlled operating conditions.
    """

    def __init__(
        self,
        pacing_engine: PredictivePacingEngine | None = None,
        safety_controller: SafetyController | None = None,
        seed: int = 42,
    ):
        self.pacing_engine = pacing_engine or PredictivePacingEngine()
        self.safety_controller = (
            safety_controller or SafetyController()
        )
        self.seed = seed

    def run(
        self,
        scenario: SimulationScenario,
    ) -> SimulationResult:

        rng = random.Random(self.seed)

        active_calls: list[SimulatedCall] = []

        initiated = 0
        answered = 0
        connected = 0
        failed = 0

        safety_approved = 0
        safety_reduced = 0
        safety_rejected = 0

        utilization_samples: list[float] = []
        peak_active = 0

        for current_time in range(scenario.duration_sec):

            # --------------------------------------------------
            # Complete calls whose talk/setup lifecycle ended.
            # --------------------------------------------------

            remaining_calls = []

            for call in active_calls:
                if current_time >= call.end_time:
                    continue

                remaining_calls.append(call)

            active_calls = remaining_calls

            # --------------------------------------------------
            # Determine current ringing calls.
            # --------------------------------------------------

            ringing_calls = sum(
                1
                for call in active_calls
                if call.answer_time is not None
                and current_time < call.answer_time
            )

            active_count = len(active_calls)

            available_agents = max(
                0,
                scenario.agents,
            )

            # --------------------------------------------------
            # Predictive pacing.
            # --------------------------------------------------

            pacing_input = PacingInput(
                available_agents=available_agents,
                active_calls=active_count,
                ringing_calls=ringing_calls,
                predicted_answer_rate=scenario.answer_rate,
                provider_health=max(
                    0.0,
                    1.0 - scenario.provider_failure_rate,
                ),
                average_call_duration_sec=scenario.average_talk_time_sec,
                average_call_setup_sec=(
                    scenario.provider_latency_ms / 1000
                ),
            )

            pacing_decision = self.pacing_engine.calculate(
                pacing_input
            )

            # --------------------------------------------------
            # Safety Controller remains authoritative.
            # --------------------------------------------------

            from smartdialer.safety import SafetyRequest

            safety_request = SafetyRequest(
                requested_calls=pacing_decision.recommended_calls,
                available_agents=available_agents,
                active_calls=active_count,
                provider_health=max(
                    0.0,
                    1.0 - scenario.provider_failure_rate,
                ),
                predicted_answer_rate=scenario.answer_rate,
            )

            safety_decision = self.safety_controller.evaluate(
                safety_request
            )

            requested = pacing_decision.recommended_calls
            approved = safety_decision.approved_calls

            if approved > 0:
                safety_approved += approved

                if approved < requested:
                    safety_reduced += 1
            elif requested > 0:
                safety_rejected += 1

            # --------------------------------------------------
            # Initiate provider calls.
            # --------------------------------------------------

            capacity = max(
                0,
                scenario.agents - active_count,
            )

            calls_to_start = min(
                approved,
                capacity,
            )

            for _ in range(calls_to_start):

                initiated += 1

                # Provider failure.
                if (
                    rng.random()
                    < scenario.provider_failure_rate
                ):
                    failed += 1
                    continue

                # Provider latency before answer.
                setup_sec = max(
                    1,
                    round(
                        scenario.provider_latency_ms
                        / 1000
                    ),
                )

                will_answer = (
                    rng.random()
                    < scenario.answer_rate
                )

                if will_answer:
                    answer_time = (
                        current_time
                        + setup_sec
                    )

                    end_time = (
                        answer_time
                        + max(
                            1,
                            round(
                                scenario.average_talk_time_sec
                            ),
                        )
                    )

                    answered += 1
                    connected += 1

                else:
                    answer_time = None

                    # Non-answering calls are released after
                    # the provider setup window.
                    end_time = (
                        current_time
                        + setup_sec
                    )

                active_calls.append(
                    SimulatedCall(
                        start_time=current_time,
                        answer_time=answer_time,
                        end_time=end_time,
                        answered=will_answer,
                    )
                )

            # --------------------------------------------------
            # Metrics.
            # --------------------------------------------------

            current_active = len(active_calls)

            peak_active = max(
                peak_active,
                current_active,
            )

            utilization = min(
                1.0,
                current_active / scenario.agents
                if scenario.agents > 0
                else 0.0,
            )

            utilization_samples.append(
                utilization
            )

        average_utilization = (
            sum(utilization_samples)
            / len(utilization_samples)
            if utilization_samples
            else 0.0
        )

        return SimulationResult(
            scenario=scenario.name,
            agents=scenario.agents,
            answer_rate=scenario.answer_rate,
            average_talk_time_sec=scenario.average_talk_time_sec,
            provider_latency_ms=scenario.provider_latency_ms,
            provider_failure_rate=scenario.provider_failure_rate,
            calls_initiated=initiated,
            calls_answered=answered,
            calls_connected=connected,
            calls_failed=failed,
            safety_approved=safety_approved,
            safety_reduced=safety_reduced,
            safety_rejected=safety_rejected,
            average_utilization=average_utilization,
            peak_active_calls=peak_active,
        )


def default_scenarios() -> list[SimulationScenario]:
    return [
        SimulationScenario(
            name="A",
            answer_rate=0.20,
            average_talk_time_sec=120,
            provider_latency_ms=100,
            provider_failure_rate=0.02,
        ),
        SimulationScenario(
            name="B",
            answer_rate=0.50,
            average_talk_time_sec=90,
            provider_latency_ms=100,
            provider_failure_rate=0.02,
        ),
        SimulationScenario(
            name="C",
            answer_rate=0.70,
            average_talk_time_sec=180,
            provider_latency_ms=100,
            provider_failure_rate=0.02,
        ),
        SimulationScenario(
            name="D - Provider Degradation",
            answer_rate=0.50,
            average_talk_time_sec=120,
            provider_latency_ms=500,
            provider_failure_rate=0.20,
        ),
    ]


def run_default_simulation() -> list[SimulationResult]:
    simulator = SmartDialerSimulator()

    return [
        simulator.run(scenario)
        for scenario in default_scenarios()
    ]


def print_results(
    results: list[SimulationResult],
) -> None:

    print()
    print("=" * 110)
    print("SMARTDIALER PREDICTIVE SIMULATION")
    print("=" * 110)

    header = (
        f"{'Scenario':<24}"
        f"{'Init':>8}"
        f"{'Ans':>8}"
        f"{'Fail':>8}"
        f"{'Safety':>9}"
        f"{'Reduced':>9}"
        f"{'Rejected':>10}"
        f"{'Util %':>9}"
        f"{'Peak':>8}"
    )

    print(header)
    print("-" * 110)

    for result in results:

        print(
            f"{result.scenario:<24}"
            f"{result.calls_initiated:>8}"
            f"{result.calls_answered:>8}"
            f"{result.calls_failed:>8}"
            f"{result.safety_approved:>9}"
            f"{result.safety_reduced:>9}"
            f"{result.safety_rejected:>10}"
            f"{result.average_utilization * 100:>8.1f}%"
            f"{result.peak_active_calls:>8}"
        )

    print("=" * 110)
    print()
