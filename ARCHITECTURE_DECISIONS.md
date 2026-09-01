# Architecture Decision Document

## 1. Decision

Use a modular Python application with PostgreSQL and SQLAlchemy async. Keep pacing, safety, allocation, orchestration, provider abstraction, state machines, heartbeat and recovery as explicit boundaries.

### Main invariant

```text
Pacing -> Safety Controller -> Allocator -> Provider
```

Predictive code never has a provider reference.

## 2. PostgreSQL as source of truth

Reservations are concurrency-sensitive, so the database—not a cache—is authoritative.

Agent reservation uses a conditional update on:

- agent id
- `AVAILABLE` state
- expected version

Only one concurrent worker can change the row from the expected state/version.

### Why this choice

**Pros:** simple, deterministic, transactional, no second locking system.

**Cost:** database contention becomes a scaling concern.

For this prototype, correctness and simplicity outweigh premature distributed infrastructure.

## 3. Optimistic versioning

Each agent has a version counter. A successful reservation increments it.

This prevents a stale worker from overwriting a newer reservation and provides a useful concurrency/audit signal.

## 4. Transactional allocator

Allocation conceptually performs:

```text
reserve agent
reserve borrower
create call
```

These belong to one transaction. If borrower selection or call creation fails, the reservation work rolls back.

This directly prevents partial allocation.

## 5. Safety Controller

The predictor is not trusted to enforce safety because prediction can be wrong.

The Safety Controller independently enforces deterministic constraints such as current capacity, provider health, hard overdial limits and fallback behavior.

Therefore a pacing bug can reduce efficiency but cannot directly authorize unsafe dialing.

## 6. Explicit state machines

Providers may duplicate or reorder events. Centralized transition tables make legal lifecycle transitions explicit and testable.

Terminal call states have no outgoing transitions.

This prevents an old provider event from reopening a completed/failed call.

## 7. Worker recovery

Workers are not assumed to clean up after crashes.

The system uses:

- reservation timestamps
- heartbeat timestamps
- reservation/setup TTLs
- a reaper

A stale worker's reserved resources can therefore be recovered.

## 8. Provider abstraction

The worker depends on `TelecomProvider`, not concrete mock implementations.

This keeps provider behavior replaceable and lets failure/latency behavior be tested independently.

## 9. Predictive algorithm

A rule-based estimator was selected instead of ML.

```text
capacity
  -> desired answers
  -> divide by answer rate
  -> subtract ringing calls
  -> provider-health adjustment
  -> hard pacing cap
  -> Safety Controller
```

This is explainable, deterministic and easy to test. In production, the answer-rate input could be an EWMA/Bayesian estimate without changing the safety boundary.

## 10. Alternatives rejected

### Redis locks
Not needed because PostgreSQL already owns the reservation state and can atomically enforce the race condition.

### Kafka
Not required for the prototype's event volume. A durable event bus becomes reasonable at larger scale.

### Microservices
The assignment rewards a simple architecture. Module boundaries are explicit without paying deployment/operational complexity.

### ML-first prediction
No need for training data or model complexity to demonstrate safe adaptive pacing.

## 11. Scaling

Likely bottlenecks, in order:

1. database contention and allocation queries;
2. transaction latency;
3. provider rate limits/throughput;
4. event processing;
5. worker coordination.

Evolution:

```text
single DB + workers
       |
campaign/worker sharding
       |
index + transaction optimization
       |
durable event processing
       |
database partitioning / further horizontal scaling
```

The safety invariant remains unchanged.

## 12. Known production limitations

The prototype does not implement a full telecom reconciliation platform.

Important next steps would be provider idempotency keys, durable webhook/event inbox, provider status reconciliation, richer answer-rate estimation, observability, and fault-injection testing around crash timing windows.

## 13. Core invariants

1. Never exceed safe agent-bound capacity.
2. One agent cannot be successfully reserved by two workers.
3. Failed allocation cannot leave partial reservations.
4. Predictive pacing cannot call a provider directly.
5. Terminal calls cannot transition again.
6. Worker disappearance cannot permanently consume an agent.
