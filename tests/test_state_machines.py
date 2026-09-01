import pytest

from smartdialer.state_machine import (
    AgentState,
    CallState,
    InvalidAgentTransition,
    InvalidCallTransition,
    transition_agent,
    transition_call,
)


def test_agent_normal_lifecycle():
    state = AgentState.OFFLINE

    state = transition_agent(state, AgentState.AVAILABLE)
    state = transition_agent(state, AgentState.RESERVED)
    state = transition_agent(state, AgentState.DIALING)
    state = transition_agent(state, AgentState.CONNECTED)
    state = transition_agent(state, AgentState.WRAP_UP)
    state = transition_agent(state, AgentState.AVAILABLE)

    assert state == AgentState.AVAILABLE


def test_agent_can_recover_from_reservation():
    state = transition_agent(
        AgentState.RESERVED,
        AgentState.AVAILABLE,
    )

    assert state == AgentState.AVAILABLE


def test_invalid_agent_transition_is_rejected():
    with pytest.raises(InvalidAgentTransition):
        transition_agent(
            AgentState.OFFLINE,
            AgentState.CONNECTED,
        )


def test_call_normal_lifecycle():
    state = CallState.QUEUED

    state = transition_call(state, CallState.RESERVED)
    state = transition_call(state, CallState.INITIATED)
    state = transition_call(state, CallState.RINGING)
    state = transition_call(state, CallState.ANSWERED)
    state = transition_call(state, CallState.CONNECTED)
    state = transition_call(state, CallState.COMPLETED)

    assert state == CallState.COMPLETED


def test_call_can_fail_during_setup():
    state = transition_call(
        CallState.RESERVED,
        CallState.FAILED,
    )

    assert state == CallState.FAILED


def test_invalid_call_transition_is_rejected():
    with pytest.raises(InvalidCallTransition):
        transition_call(
            CallState.QUEUED,
            CallState.CONNECTED,
        )


def test_terminal_call_cannot_transition():
    with pytest.raises(InvalidCallTransition):
        transition_call(
            CallState.COMPLETED,
            CallState.RINGING,
        )