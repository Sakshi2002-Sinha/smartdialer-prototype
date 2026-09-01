# Final Failure-Scenario Review

## 1. Two workers reserve the same agent

**Situation:** both observe `AVAILABLE`.

**Protection:** atomic conditional update using state + expected version.

**Result:** one update succeeds; the other affects zero rows.

**Interview line:** “The initial read is not my concurrency guarantee; the database conditional update is.”

## 2. Worker crashes during dialing

Possible state:

```text
Agent RESERVED
Borrower RESERVED
Call RESERVED/INITIATED
Worker dies
```

Transactions prevent incomplete work from being committed. Persisted reservations have timestamps and are recoverable by heartbeat/reaper TTL logic.

A production system would additionally reconcile provider-side state when a timeout/crash occurs after provider acceptance.

## 3. Provider outage

New calls should be admitted less aggressively or rejected when health falls below the configured safety threshold. Predictive pacing reacts first, while the Safety Controller remains authoritative.

Existing calls are handled through their persisted call state and provider events rather than being arbitrarily rewritten by pacing.

Retries are bounded by borrower attempt count and provider health.

## 4. 100 agents suddenly become 60

Predictive estimates may be stale, but allocation and safety use current database state.

Reservations that can no longer be made fail safely. Heartbeat/reaper logic removes stale workers from effective capacity.

The key principle:

> Prediction may be stale; safety cannot depend on prediction being correct.

## 5. Duplicate provider events

```text
ANSWERED
ANSWERED
ANSWERED
COMPLETED
```

The first valid transition advances state. Later duplicate `ANSWERED` events are ignored. `COMPLETED` advances the call if valid.

No duplicate lifecycle transitions are created.

## 6. Out-of-order events

```text
COMPLETED
ANSWERED
RINGING
```

The event processor validates transitions against current persisted state. Invalid/backward transitions are ignored. A terminal call stays terminal.

## 7. Answer rate suddenly drops from 70% to 10%

The pacing recommendation falls as the estimate changes. The Safety Controller still independently enforces capacity and hard limits.

Production improvement: use recent observations, confidence bounds and fast adaptation rather than trusting a stale point estimate.

## Predictive scenario matrix

Run/record these scenarios:

| Scenario | Answer rate | Talk time | Expected behavior |
|---|---:|---:|---|
| A | 20% | 120s | more calls required, but bounded |
| B | 50% | 90s | balanced pacing |
| C | 70% | 180s | potentially aggressive, still bounded |
| D | changing | changing | adaptation without safety bypass |

Record:

- available agents
- active/ringing calls
- answer rate
- provider health
- pacing recommendation
- Safety approval
- calls initiated
- calls connected
- utilization
- failures
- fallback decisions

## Production gaps to acknowledge

1. Provider timeout after acceptance can create uncertainty about whether a call exists.
2. Provider webhooks should be durably recorded.
3. Idempotency keys are required for robust retry semantics.
4. Clock/TTL decisions need careful time consistency.
5. Large campaigns require allocation sharding/partitioning.
6. Production needs metrics/tracing around pacing, safety, allocation and provider latency.
