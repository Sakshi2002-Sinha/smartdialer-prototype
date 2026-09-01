from smartdialer.pacing import (
    PacingInput,
    PredictivePacingEngine,
)


def test_predictive_pacing_estimates_calls_from_answer_rate():

    engine = PredictivePacingEngine()

    result = engine.calculate(
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

    assert result.recommended_calls == 12
    assert result.reason == "PREDICTIVE_ESTIMATE"


def test_predictive_pacing_accounts_for_ringing_calls():

    engine = PredictivePacingEngine()

    result = engine.calculate(
        PacingInput(
            available_agents=10,
            active_calls=5,
            ringing_calls=2,
            predicted_answer_rate=0.5,
            provider_health=1.0,
            average_call_duration_sec=90,
            average_call_setup_sec=2,
        )
    )

    assert result.recommended_calls == 10


def test_predictive_pacing_stops_when_no_capacity():

    engine = PredictivePacingEngine()

    result = engine.calculate(
        PacingInput(
            available_agents=10,
            active_calls=10,
            ringing_calls=0,
            predicted_answer_rate=0.7,
            provider_health=1.0,
            average_call_duration_sec=90,
            average_call_setup_sec=2,
        )
    )

    assert result.recommended_calls == 0


def test_predictive_pacing_stops_when_answer_rate_is_zero():

    engine = PredictivePacingEngine()

    result = engine.calculate(
        PacingInput(
            available_agents=10,
            active_calls=2,
            ringing_calls=0,
            predicted_answer_rate=0.0,
            provider_health=1.0,
            average_call_duration_sec=90,
            average_call_setup_sec=2,
        )
    )

    assert result.recommended_calls == 0


def test_unhealthy_provider_makes_pacing_conservative():

    engine = PredictivePacingEngine()

    result = engine.calculate(
        PacingInput(
            available_agents=10,
            active_calls=2,
            ringing_calls=0,
            predicted_answer_rate=0.5,
            provider_health=0.7,
            average_call_duration_sec=90,
            average_call_setup_sec=2,
        )
    )

    assert result.recommended_calls > 0
    assert result.recommended_calls < 20


def test_very_unhealthy_provider_stops_pacing():

    engine = PredictivePacingEngine()

    result = engine.calculate(
        PacingInput(
            available_agents=10,
            active_calls=2,
            ringing_calls=0,
            predicted_answer_rate=0.5,
            provider_health=0.5,
            average_call_duration_sec=90,
            average_call_setup_sec=2,
        )
    )

    assert result.recommended_calls == 0


def test_pacing_has_hard_recommendation_cap():

    engine = PredictivePacingEngine(
        max_overdial_cap=5,
    )

    result = engine.calculate(
        PacingInput(
            available_agents=100,
            active_calls=0,
            ringing_calls=0,
            predicted_answer_rate=0.1,
            provider_health=1.0,
            average_call_duration_sec=90,
            average_call_setup_sec=2,
        )
    )

    assert result.recommended_calls <= 5