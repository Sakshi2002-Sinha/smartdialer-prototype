from enum import Enum


class AgentState(str, Enum):
    OFFLINE = "OFFLINE"
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    DIALING = "DIALING"
    CONNECTED = "CONNECTED"
    WRAP_UP = "WRAP_UP"
    PAUSED = "PAUSED"


class InvalidAgentTransition(ValueError):
    """Raised when an invalid agent state transition is attempted."""


AGENT_TRANSITIONS: dict[AgentState, set[AgentState]] = {
    AgentState.OFFLINE: {
        AgentState.AVAILABLE,
    },

    AgentState.AVAILABLE: {
        AgentState.RESERVED,
        AgentState.PAUSED,
        AgentState.OFFLINE,
    },

    AgentState.RESERVED: {
        AgentState.DIALING,
        AgentState.AVAILABLE,
        AgentState.OFFLINE,
    },

    AgentState.DIALING: {
        AgentState.CONNECTED,
        AgentState.AVAILABLE,
        AgentState.OFFLINE,
    },

    AgentState.CONNECTED: {
        AgentState.WRAP_UP,
        AgentState.OFFLINE,
    },

    AgentState.WRAP_UP: {
        AgentState.AVAILABLE,
        AgentState.PAUSED,
        AgentState.OFFLINE,
    },

    AgentState.PAUSED: {
        AgentState.AVAILABLE,
        AgentState.OFFLINE,
    },
}


def transition_agent(
    current: AgentState,
    target: AgentState,
) -> AgentState:
    """
    Validate and perform an agent state transition.

    Returns the target state if the transition is valid.
    Raises InvalidAgentTransition otherwise.
    """

    allowed = AGENT_TRANSITIONS.get(current, set())

    if target not in allowed:
        raise InvalidAgentTransition(
            f"Invalid agent transition: {current.value} -> {target.value}"
        )

    return target