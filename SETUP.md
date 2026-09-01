# SmartDialer — Setup & Run Guide

## Tech Stack

- **Language:** Python 3.11
- **Database:** PostgreSQL
- **ORM:** SQLAlchemy 2.x
- **Async Driver:** asyncpg
- **Testing:** pytest, pytest-asyncio
- **Containerization:** Docker Compose
- **Architecture:** Modular monolith
- **Dialing:** Progressive + Predictive
- **Concurrency:** PostgreSQL atomic updates + optimistic locking
- **Telecom:** Provider abstraction + Mock Provider A/B
- **Simulation:** Python-based simulator

---

## 1. Clone

```powershell
git clone https://github.com/Sakshi2002-Sinha/smartdialer-prototype.git
cd smartdialer-prototype
```

## 2. Create Virtual Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Verify:

```powershell
python --version
```

Python 3.11 is recommended.

## 3. Install Dependencies

```powershell
python -m pip install --upgrade pip
pip install -e .
```

## 4. Configure Environment

```powershell
Copy-Item .env.example .env
```

The default development database is:

```text
postgresql+asyncpg://smartdialer:smartdialer_dev@localhost:55432/smartdialer
```

Do not commit `.env`.

## 5. Start PostgreSQL

```powershell
docker compose up -d
```

Verify:

```powershell
docker compose ps
```

PostgreSQL should be available on port `55432`.

## 6. Run Tests

Run the complete test suite:

```powershell
python -m pytest -v
```

Current baseline:

```text
74 passed
```

The tests cover:

- Agent concurrency
- Borrower reservation
- Atomic call allocation
- Progressive dialing
- Predictive pacing
- Safety-controller enforcement
- Provider failures
- Duplicate provider events
- Out-of-order events
- Heartbeats
- Stale-agent recovery
- Worker runtime
- Simulation
- Load scenarios
- Agent/call state machines

## 7. Run the Simulator

```powershell
python -m smartdialer.simulator
```

The simulator evaluates dialing behaviour under different answer rates, provider health, latency, failures, and call-duration conditions.

## 8. Run Load Tests

```powershell
python -m pytest tests/load -v
```

---

## Architecture

```text
                    ┌─────────────────┐
                    │    Campaign     │
                    └────────┬────────┘
                             │
                             ▼
                ┌─────────────────────────┐
                │ Progressive / Predictive│
                │        Dialer           │
                └────────────┬────────────┘
                             │
                             ▼
                ┌─────────────────────────┐
                │   Predictive Pacing     │
                │        Engine           │
                └────────────┬────────────┘
                             │
                             ▼
                ┌─────────────────────────┐
                │    Safety Controller    │
                │  FINAL SAFETY BOUNDARY  │
                └────────────┬────────────┘
                             │
                             ▼
                ┌─────────────────────────┐
                │     Call Allocator      │
                └────────────┬────────────┘
                             │
                             ▼
                ┌─────────────────────────┐
                │   Dialing Orchestrator  │
                └────────────┬────────────┘
                             │
                             ▼
                ┌─────────────────────────┐
                │    Telecom Provider     │
                │      Mock A / Mock B    │
                └─────────────────────────┘
```

### Safety Invariant

The predictive algorithm **never directly places a call**.

```text
Pacing Recommendation
        ↓
Safety Controller
        ↓
Approved Calls
        ↓
Call Allocation
        ↓
Provider
```

The Safety Controller can:

- approve a request;
- reduce the requested number;
- reject the request;
- trigger progressive fallback.

---

## Project Structure

```text
smartdialer-prototype/
│
├── smartdialer/
│   ├── allocator/
│   ├── dialer/
│   ├── events/
│   ├── heartbeat/
│   ├── models/
│   ├── orchestrator/
│   ├── pacing/
│   ├── provider/
│   ├── reaper/
│   ├── repositories/
│   ├── safety/
│   ├── simulator/
│   ├── state_machine/
│   └── worker/
│
├── tests/
│   ├── integration/
│   ├── load/
│   ├── scenario/
│   └── unit/
│
├── migrations/
├── docker-compose.yml
├── .env.example
├── pyproject.toml
├── README.md
├── ARCHITECTURE_DECISIONS.md
└── SCENARIOS.md
```

## Quick Start

```powershell
git clone https://github.com/Sakshi2002-Sinha/smartdialer-prototype.git
cd smartdialer-prototype
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
Copy-Item .env.example .env
docker compose up -d
python -m pytest -v
```

Expected:

```text
74 passed
```
