# SmartDialer

A safety-first SmartDialer prototype supporting **Progressive** and **Predictive** dialing.

## Core architecture

```text
Campaign
   |
   +--> Progressive Dialer --------+
   |                               |
   +--> Predictive Pacing Engine --+--> Safety Controller
                                           |
                                           v
                                     Call Allocator
                                      /          \
                                   Agent       Borrower
                                      \          /
                                       v        v
                                  Dialing Orchestrator
                                           |
                                           v
                                    Telecom Provider
                                           |
                                           v
                                  Provider Event Processor
```

The key invariant is:

> Predictive pacing is advisory. It can recommend calls, but it can never directly place a call or bypass the Safety Controller.

PostgreSQL is the authoritative source of truth for reservations.

## Agent lifecycle

```text
OFFLINE <--> AVAILABLE --> RESERVED --> DIALING --> CONNECTED --> WRAP_UP --> AVAILABLE
                  |             |           |            |
                  +----------> PAUSED       +----------> OFFLINE
```

## Call lifecycle

```text
QUEUED --> RESERVED --> INITIATED --> RINGING --> ANSWERED --> CONNECTED --> COMPLETED
              |            |            |            |             |
              +----------> FAILED <----+------------+-------------+
              +----------> CANCELLED
```

Invalid, duplicate, stale, and backward provider events are rejected/ignored by explicit transition validation.

## Concurrency

Agent reservation is an atomic conditional database update using agent id, `AVAILABLE` state, and expected version.

```text
Worker A ----              +--> UPDATE ... WHERE state=AVAILABLE AND version=N
Worker B ----/              |
                             +--> exactly one worker changes one row
```

The winner increments the version. The loser sees zero affected rows.

Borrower reservation is also conditional on `PENDING` status and the attempt limit. Agent reservation, borrower reservation, and call creation are performed transactionally by the allocator.

## Predictive pacing

The prototype uses an explainable rule-based approach:

```text
free_capacity = max(0, available_agents - active_calls)
desired_answers = free_capacity + target_buffer
estimated_calls = ceil(desired_answers / predicted_answer_rate)
estimated_calls -= ringing_calls
```

Provider health makes pacing more conservative or stops predictive pacing below the configured threshold. A hard recommendation cap is applied.

The result then passes through the Safety Controller.

## Failure recovery

- **Worker crash:** transactions roll back incomplete work; persisted reservations are recoverable by TTL/reaper logic.
- **Provider outage:** provider health reduces/rejects new predictive dialing; existing calls remain governed by their call state/events.
- **Agent disappearance:** current DB state controls capacity; stale reservations are recovered.
- **Duplicate events:** state validation prevents repeated lifecycle transitions.
- **Out-of-order events:** invalid backward transitions are ignored.
- **Heartbeat failure:** stale agents are recovered by the reaper.
- **Borrower retries:** attempts are bounded.

## Providers

`TelecomProvider` is a protocol. `MockProviderA` is fast/reliable; `MockProviderB` is slower and can fail or timeout. The dialer does not depend on provider internals.

## Running

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest -v
```

The project currently verifies with **74 passing tests**.

Default database URL:

```text
postgresql+asyncpg://smartdialer:smartdialer_dev@localhost:55432/smartdialer
```

Override with `DATABASE_URL`.

## Tests include

Atomic/concurrent allocation, rollback, progressive and predictive dialing, safety limits, provider failures, duplicate/out-of-order events, heartbeat, reaper recovery, worker runtime/cancellation, simulation, and load tests.

## Scale

At 100 agents, PostgreSQL plus multiple workers is appropriate. At 1,000 agents, optimize indexes, transaction duration, campaign partitioning and worker sharding. At 10,000+, database contention, provider throughput and event processing become the main concerns. Durable event infrastructure and database partitioning can then be introduced based on measurements.

## Submission documents

- `ARCHITECTURE_DECISIONS.md` — architecture decisions and trade-offs
- `SCENARIOS.md` — failure analysis and predictive scenarios

