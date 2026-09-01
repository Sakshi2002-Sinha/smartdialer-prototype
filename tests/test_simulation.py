
from smartdialer.simulator.scenarios import (
    SimulationScenario,
    SmartDialerSimulator,
)


def test_simulation_produces_metrics():
    simulator = SmartDialerSimulator(seed=42)

    result = simulator.run(
        SimulationScenario(
            name="TEST",
            answer_rate=0.5,
            average_talk_time_sec=90,
            provider_latency_ms=100,
            provider_failure_rate=0.02,
            duration_sec=30,
            agents=10,
        )
    )

    assert result.calls_initiated >= 0
    assert result.calls_answered >= 0
    assert result.calls_failed >= 0

    assert 0.0 <= result.average_utilization <= 1.0

    assert result.peak_active_calls <= 10


def test_unhealthy_provider_stops_predictive_dialing():
    simulator = SmartDialerSimulator(seed=42)

    result = simulator.run(
        SimulationScenario(
            name="OUTAGE",
            answer_rate=0.5,
            average_talk_time_sec=90,
            provider_latency_ms=500,
            provider_failure_rate=0.6,
            duration_sec=30,
            agents=10,
        )
    )

    assert result.calls_initiated == 0
