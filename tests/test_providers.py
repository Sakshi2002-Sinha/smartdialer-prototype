import pytest

from smartdialer.provider import (
    MockProviderA,
    MockProviderB,
)


@pytest.mark.asyncio
async def test_provider_a_success():

    provider = MockProviderA(
        failure_rate=0.0,
        latency_ms=1,
    )

    result = await provider.initiate_call(
        call_id="call-1",
        phone_number="+911234567890",
    )

    assert result.accepted is True
    assert result.provider_call_id


@pytest.mark.asyncio
async def test_provider_a_can_fail():

    provider = MockProviderA(
        failure_rate=1.0,
        latency_ms=1,
    )

    result = await provider.initiate_call(
        call_id="call-1",
        phone_number="+911234567890",
    )

    assert result.accepted is False
    assert result.error == "PROVIDER_REJECTED"


@pytest.mark.asyncio
async def test_provider_b_can_timeout():

    provider = MockProviderB(
        timeout_rate=1.0,
        latency_ms=1,
    )

    with pytest.raises(TimeoutError):
        await provider.initiate_call(
            call_id="call-1",
            phone_number="+911234567890",
        )


def test_provider_health_differs():

    provider_a = MockProviderA(
        failure_rate=0.02,
    )

    provider_b = MockProviderB(
        failure_rate=0.15,
        timeout_rate=0.10,
    )

    assert provider_a.health() > provider_b.health()