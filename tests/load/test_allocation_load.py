import asyncio
import time
import uuid

import pytest

from smartdialer.pacing import PacingInput, PredictivePacingEngine
from smartdialer.safety import SafetyController


async def run_allocation_simulation(
    agents: int,
    attempts: int,
) -> dict:
    pacing = PredictivePacingEngine()
    safety = SafetyController()

    successful = 0
    rejected = 0

    start = time.perf_counter()

    async def attempt() -> bool:
        nonlocal successful, rejected

        decision = pacing.calculate(
            PacingInput(
                available_agents=agents,
                active_calls=0,
                ringing_calls=0,
                predicted_answer_rate=0.5,
                provider_health=0.98,
                average_call_duration_sec=90,
                average_call_setup_sec=2,
            )
        )

        safety_decision = safety.evaluate(
            __import__(
                "smartdialer.safety",
                fromlist=["SafetyRequest"],
            ).SafetyRequest(
                requested_calls=decision.recommended_calls,
                available_agents=agents,
                active_calls=0,
                provider_health=0.98,
                predicted_answer_rate=0.5,
            )
        )

        if safety_decision.approved_calls > 0:
            successful += 1
            return True

        rejected += 1
        return False

    await asyncio.gather(
        *(attempt() for _ in range(attempts))
    )

    elapsed = time.perf_counter() - start

    return {
        "agents": agents,
        "attempts": attempts,
        "successful": successful,
        "rejected": rejected,
        "elapsed_sec": elapsed,
        "throughput": (
            attempts / elapsed
            if elapsed > 0
            else 0
        ),
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "agents,attempts",
    [
        (100, 1_000),
        (1_000, 10_000),
        (10_000, 100_000),
    ],
)
async def test_pacing_load(
    agents: int,
    attempts: int,
):
    result = await run_allocation_simulation(
        agents=agents,
        attempts=attempts,
    )

    assert result["attempts"] == attempts
    assert result["successful"] >= 0
    assert result["rejected"] >= 0
    assert result["successful"] + result["rejected"] == attempts

    print(
        "\n"
        f"Agents: {result['agents']}\n"
        f"Attempts: {result['attempts']}\n"
        f"Elapsed: {result['elapsed_sec']:.4f}s\n"
        f"Throughput: {result['throughput']:.2f} ops/sec\n"
    )