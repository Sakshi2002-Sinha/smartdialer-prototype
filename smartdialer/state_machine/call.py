from enum import Enum


class CallState(str, Enum):
    QUEUED = "QUEUED"
    RESERVED = "RESERVED"
    INITIATED = "INITIATED"
    RINGING = "RINGING"
    ANSWERED = "ANSWERED"
    CONNECTED = "CONNECTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class InvalidCallTransition(ValueError):
    """Raised when an invalid call state transition is attempted."""


CALL_TRANSITIONS: dict[CallState, set[CallState]] = {
    CallState.QUEUED: {
        CallState.RESERVED,
        CallState.CANCELLED,
    },

    CallState.RESERVED: {
        CallState.INITIATED,
        CallState.FAILED,
        CallState.CANCELLED,
    },

    CallState.INITIATED: {
        CallState.RINGING,
        CallState.ANSWERED,
        CallState.CONNECTED,
        CallState.FAILED,
        CallState.CANCELLED,
    },

    CallState.RINGING: {
        CallState.ANSWERED,
        CallState.FAILED,
        CallState.CANCELLED,
    },

    CallState.ANSWERED: {
        CallState.CONNECTED,
        CallState.COMPLETED,
    },

    CallState.CONNECTED: {
        CallState.COMPLETED,
        CallState.FAILED,
    },

    CallState.COMPLETED: set(),

    CallState.FAILED: set(),

    CallState.CANCELLED: set(),
}


def transition_call(
    current: CallState,
    target: CallState,
) -> CallState:
    """
    Validate and perform a call state transition.

    Returns the target state if valid.
    Raises InvalidCallTransition otherwise.
    """

    allowed = CALL_TRANSITIONS.get(current, set())

    if target not in allowed:
        raise InvalidCallTransition(
            f"Invalid call transition: {current.value} -> {target.value}"
        )

    return target