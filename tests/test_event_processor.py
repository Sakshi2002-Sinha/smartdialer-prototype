from datetime import datetime, timezone

from smartdialer.events.processor import ProviderEventProcessor
from smartdialer.events.types import (
    ProviderEvent,
    ProviderEventType,
)
from smartdialer.state_machine import CallState


def make_event(event_type: ProviderEventType, sequence: int = 1):
    return ProviderEvent(
        provider="provider_b",
        provider_event_id=f"event-{sequence}",
        provider_call_id="provider-call-1",
        event_type=event_type,
        occurred_at=datetime.now(timezone.utc),
        sequence=sequence,
    )


def test_answered_event_is_applied():
    processor = ProviderEventProcessor()

    result = processor.process(
        CallState.RINGING,
        make_event(ProviderEventType.ANSWERED),
    )

    assert result.action == "APPLIED"
    assert result.state == CallState.ANSWERED


def test_duplicate_state_event_is_ignored():
    processor = ProviderEventProcessor()

    result = processor.process(
        CallState.ANSWERED,
        make_event(ProviderEventType.ANSWERED),
    )

    assert result.action == "IGNORED_DUPLICATE"
    assert result.state == CallState.ANSWERED


def test_event_after_completed_is_ignored():
    processor = ProviderEventProcessor()

    result = processor.process(
        CallState.COMPLETED,
        make_event(ProviderEventType.ANSWERED),
    )

    assert result.action == "IGNORED_TERMINAL"
    assert result.state == CallState.COMPLETED


def test_event_after_failed_is_ignored():
    processor = ProviderEventProcessor()

    result = processor.process(
        CallState.FAILED,
        make_event(ProviderEventType.RINGING),
    )

    assert result.action == "IGNORED_TERMINAL"
    assert result.state == CallState.FAILED


def test_invalid_backward_event_is_ignored():
    processor = ProviderEventProcessor()

    result = processor.process(
        CallState.CONNECTED,
        make_event(ProviderEventType.RINGING),
    )

    assert result.action == "IGNORED_STALE"
    assert result.state == CallState.CONNECTED


def test_connected_event_after_answered():
    processor = ProviderEventProcessor()

    result = processor.process(
        CallState.ANSWERED,
        make_event(ProviderEventType.CONNECTED),
    )

    assert result.action == "APPLIED"
    assert result.state == CallState.CONNECTED