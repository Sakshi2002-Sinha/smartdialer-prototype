from smartdialer.safety import (
    SafetyController,
    SafetyRequest,
)


def test_safety_never_exceeds_available_agents():

    controller = SafetyController()

    request = SafetyRequest(
        requested_calls=20,
        available_agents=5,
        active_calls=0,
        provider_health=1.0,
        predicted_answer_rate=0.2,
    )

    decision = controller.evaluate(request)

    assert decision.approved_calls <= 5


def test_unhealthy_provider_blocks_new_calls():

    controller = SafetyController()

    request = SafetyRequest(
        requested_calls=10,
        available_agents=10,
        active_calls=0,
        provider_health=0.2,
        predicted_answer_rate=0.5,
    )

    decision = controller.evaluate(request)

    assert decision.approved_calls == 0
    assert decision.reason == "PROVIDER_UNHEALTHY"
    assert decision.fallback_progressive is True


def test_safety_applies_hard_overdial_cap():

    controller = SafetyController(
        max_overdial_cap=5,
    )

    request = SafetyRequest(
        requested_calls=20,
        available_agents=20,
        active_calls=0,
        provider_health=1.0,
        predicted_answer_rate=0.1,
    )

    decision = controller.evaluate(request)

    assert decision.approved_calls <= 5


def test_safety_can_reduce_aggressive_request():

    controller = SafetyController(
        max_abandon_risk=1,
    )

    request = SafetyRequest(
        requested_calls=10,
        available_agents=5,
        active_calls=0,
        provider_health=1.0,
        predicted_answer_rate=1.0,
    )

    decision = controller.evaluate(request)

    assert decision.approved_calls < 10