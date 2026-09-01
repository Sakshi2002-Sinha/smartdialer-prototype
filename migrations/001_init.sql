-- ============================================================
-- SmartDialer initial schema
-- ============================================================

-- ------------------------------------------------------------
-- Campaigns
-- ------------------------------------------------------------

CREATE TABLE campaigns (
    id UUID PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    mode VARCHAR(20) NOT NULL
        CHECK (mode IN ('PROGRESSIVE', 'PREDICTIVE')),
    max_overdial_cap INTEGER NOT NULL DEFAULT 50
        CHECK (max_overdial_cap >= 0),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ------------------------------------------------------------
-- Agents
-- ------------------------------------------------------------

CREATE TABLE agents (
    id UUID PRIMARY KEY,
    campaign_id UUID NOT NULL
        REFERENCES campaigns(id) ON DELETE CASCADE,

    name VARCHAR(200) NOT NULL,

    state VARCHAR(20) NOT NULL
        CHECK (
            state IN (
                'OFFLINE',
                'AVAILABLE',
                'RESERVED',
                'DIALING',
                'CONNECTED',
                'WRAP_UP',
                'PAUSED'
            )
        ),

    version BIGINT NOT NULL DEFAULT 0,

    reserved_by VARCHAR(100),
    reserved_at TIMESTAMPTZ,

    last_heartbeat TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ------------------------------------------------------------
-- Borrowers
-- ------------------------------------------------------------

CREATE TABLE borrowers (
    id UUID PRIMARY KEY,
    campaign_id UUID NOT NULL
        REFERENCES campaigns(id) ON DELETE CASCADE,

    phone_number VARCHAR(30) NOT NULL,

    status VARCHAR(20) NOT NULL DEFAULT 'PENDING'
        CHECK (
            status IN (
                'PENDING',
                'RESERVED',
                'CALLED',
                'COMPLETED',
                'FAILED',
                'DNC'
            )
        ),

    priority INTEGER NOT NULL DEFAULT 0,

    attempt_count INTEGER NOT NULL DEFAULT 0
        CHECK (attempt_count >= 0),

    last_attempt_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ------------------------------------------------------------
-- Calls
-- ------------------------------------------------------------

CREATE TABLE calls (
    id UUID PRIMARY KEY,

    campaign_id UUID NOT NULL
        REFERENCES campaigns(id) ON DELETE CASCADE,

    agent_id UUID
        REFERENCES agents(id) ON DELETE SET NULL,

    borrower_id UUID NOT NULL
        REFERENCES borrowers(id) ON DELETE RESTRICT,

    state VARCHAR(20) NOT NULL DEFAULT 'QUEUED'
        CHECK (
            state IN (
                'QUEUED',
                'RESERVED',
                'INITIATED',
                'RINGING',
                'ANSWERED',
                'CONNECTED',
                'COMPLETED',
                'FAILED',
                'CANCELLED'
            )
        ),

    attempt_number INTEGER NOT NULL DEFAULT 1
        CHECK (attempt_number > 0),

    provider VARCHAR(50),
    provider_call_id VARCHAR(200),

    idempotency_key VARCHAR(200) NOT NULL,

    reserved_at TIMESTAMPTZ,
    initiated_at TIMESTAMPTZ,
    ringing_at TIMESTAMPTZ,
    answered_at TIMESTAMPTZ,
    connected_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    failure_reason TEXT,

    version BIGINT NOT NULL DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_calls_idempotency_key
        UNIQUE (idempotency_key)
);


-- ------------------------------------------------------------
-- Provider events
-- ------------------------------------------------------------

CREATE TABLE provider_events (
    id UUID PRIMARY KEY,

    provider VARCHAR(50) NOT NULL,

    provider_event_id VARCHAR(200) NOT NULL,

    call_id UUID NOT NULL
        REFERENCES calls(id) ON DELETE CASCADE,

    event_type VARCHAR(30) NOT NULL,

    provider_sequence BIGINT,

    payload JSONB NOT NULL DEFAULT '{}'::jsonb,

    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_provider_event
        UNIQUE (provider, provider_event_id)
);


-- ------------------------------------------------------------
-- Campaign metrics
-- ------------------------------------------------------------

CREATE TABLE campaign_metrics (
    campaign_id UUID PRIMARY KEY
        REFERENCES campaigns(id) ON DELETE CASCADE,

    answer_rate_ewma DOUBLE PRECISION NOT NULL DEFAULT 0.05,

    avg_setup_time_sec DOUBLE PRECISION NOT NULL DEFAULT 1.0,

    avg_talk_time_sec DOUBLE PRECISION NOT NULL DEFAULT 120.0,

    provider_health DOUBLE PRECISION NOT NULL DEFAULT 1.0
        CHECK (provider_health >= 0.0 AND provider_health <= 1.0),

    total_calls BIGINT NOT NULL DEFAULT 0,
    answered_calls BIGINT NOT NULL DEFAULT 0,
    failed_calls BIGINT NOT NULL DEFAULT 0,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================
-- Indexes
-- ============================================================

CREATE INDEX idx_agents_campaign_state
    ON agents(campaign_id, state);

CREATE INDEX idx_agents_heartbeat
    ON agents(last_heartbeat);

CREATE INDEX idx_borrowers_campaign_status_priority
    ON borrowers(campaign_id, status, priority DESC);

CREATE INDEX idx_calls_campaign_state
    ON calls(campaign_id, state);

CREATE INDEX idx_calls_agent
    ON calls(agent_id);

CREATE INDEX idx_calls_borrower
    ON calls(borrower_id);

CREATE INDEX idx_calls_provider_call
    ON calls(provider, provider_call_id);

CREATE INDEX idx_provider_events_call
    ON provider_events(call_id);

CREATE INDEX idx_provider_events_received
    ON provider_events(received_at);