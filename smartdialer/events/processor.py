from dataclasses import dataclass

from .types import ProviderEvent, ProviderEventType
from smartdialer.state_machine import CallState


TERMINAL_STATES = {
    CallState.COMPLETED,
    CallState.FAILED,
    CallState.CANCELLED,
}


EVENT_TO_CALL_STATE = {
    ProviderEventType.INITIATED: CallState.INITIATED,
    ProviderEventType.RINGING: CallState.RINGING,
    ProviderEventType.ANSWERED: CallState.ANSWERED,
    ProviderEventType.CONNECTED: CallState.CONNECTED,
    ProviderEventType.COMPLETED: CallState.COMPLETED,
    ProviderEventType.FAILED: CallState.FAILED,
    ProviderEventType.CANCELLED: CallState.CANCELLED,
}


@dataclass(frozen=True)
class EventProcessingResult:
    action: str
    state: CallState


class ProviderEventProcessor:
    """
    Decides what to do with a normalized provider event.

    Database persistence and event deduplication will be added
    in the repository layer.
    """

    def process(
        self,
        current_state: CallState,
        event: ProviderEvent,
    ) -> EventProcessingResult:

        # Never resurrect a terminal call.
        if current_state in TERMINAL_STATES:
            return EventProcessingResult(
                action="IGNORED_TERMINAL",
                state=current_state,
            )

        target_state = EVENT_TO_CALL_STATE[event.event_type]

        # Duplicate event/state notification.
        if target_state == current_state:
            return EventProcessingResult(
                action="IGNORED_DUPLICATE",
                state=current_state,
            )

        # Normal legal transition.
        allowed_transitions = {
            CallState.QUEUED: {
                CallState.RESERVED,
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
                CallState.CONNECTED,
                CallState.FAILED,
                CallState.CANCELLED,
            },
            CallState.ANSWERED: {
                CallState.CONNECTED,
                CallState.COMPLETED,
                CallState.FAILED,
            },
            CallState.CONNECTED: {
                CallState.COMPLETED,
                CallState.FAILED,
            },
        }

        allowed = allowed_transitions.get(current_state, set())

        if target_state not in allowed:
            return EventProcessingResult(
                action="IGNORED_STALE",
                state=current_state,
            )

        return EventProcessingResult(
            action="APPLIED",
            state=target_state,
        )