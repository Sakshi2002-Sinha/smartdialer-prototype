from smartdialer.dialer import PredictiveDialer
from smartdialer.pacing import PacingInput
from smartdialer.safety import SafetyController


def test_predictive_request_is_reduced_by_safety():

    dialer = PredictiveDialer(
        safety_controller=SafetyController(
            max_overdial_cap=50,
            max_abandon_risk=3,
        )
    )

    result = dialer.decide(
        PacingInput(
            available_agents=10,
            active_calls=5,
            ringing_calls=0,
            predicted_answer_rate=0.5,
            provider_health=1.0,
            average_call_duration_sec=90,
            average_call_setup_sec=2,
        )
    )

    # Pacing recommends 12.
    assert result.requested_calls == 12

    # Safety must remain authoritative.
    assert result.approved_calls <= 5


def test_predictive_dialer_never_exceeds_agent_capacity():

    dialer = PredictiveDialer()

    result = dialer.decide(
        PacingInput(
            available_agents=5,
            active_calls=4,
            ringing_calls=0,
            predicted_answer_rate=0.2,
            provider_health=1.0,
            average_call_duration_sec=90,
            average_call_setup_sec=2,
        )
    )

    assert result.approved_calls <= 1


def test_unhealthy_provider_blocks_predictive_dialing():

    dialer = PredictiveDialer()

    result = dialer.decide(
        PacingInput(
            available_agents=10,
            active_calls=2,
            ringing_calls=0,
            predicted_answer_rate=0.7,
            provider_health=0.2,
            average_call_duration_sec=90,
            average_call_setup_sec=2,
        )
    )

    assert result.approved_calls == 0
    assert result.fallback_progressive is True


def test_predictive_dialer_preserves_safety_boundary():

    dialer = PredictiveDialer()

    result = dialer.decide(
        PacingInput(
            available_agents=3,
            active_calls=0,
            ringing_calls=0,
            predicted_answer_rate=0.1,
            provider_health=1.0,
            average_call_duration_sec=120,
            average_call_setup_sec=2,
        )
    )

    assert result.requested_calls > 3
    assert result.approved_calls <= 3