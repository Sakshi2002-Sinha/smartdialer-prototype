import uuid

import pytest

from smartdialer.simulator import ProviderEventSimulator


@pytest.mark.asyncio
async def test_normal_call_sequence():

    call_id = uuid.uuid4()

    simulator = ProviderEventSimulator(
        provider_call_id="provider-123"
    )

    events = await simulator.normal_call(call_id)

    assert [
        event.event_type
        for event in events
    ] == [
        "INITIATED",
        "RINGING",
        "ANSWERED",
        "CONNECTED",
        "COMPLETED",
    ]

    assert all(
        event.call_id == call_id
        for event in events
    )


@pytest.mark.asyncio
async def test_duplicate_answer_events():

    call_id = uuid.uuid4()

    simulator = ProviderEventSimulator()

    events = await simulator.duplicate_answer(call_id)

    assert len(events) == 3

    assert all(
        event.event_type == "ANSWERED"
        for event in events
    )


@pytest.mark.asyncio
async def test_out_of_order_events():

    call_id = uuid.uuid4()

    simulator = ProviderEventSimulator()

    events = await simulator.out_of_order_completion(call_id)

    assert [
        event.event_type
        for event in events
    ] == [
        "COMPLETED",
        "ANSWERED",
        "RINGING",
    ]