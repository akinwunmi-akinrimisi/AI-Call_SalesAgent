-- 002: Create tables in sales_agent schema
-- Phase 2 Plan 01: Supabase Schema Migration
-- Run AFTER 001_create_schema.sql

-- =============================================================
-- Leads table: Every person in the sales pipeline
-- Status tracks the full 10-stage lifecycle + archived
-- CSV import populates name, phone, email only;
-- Sarah (voice agent) fills the rest during the call
-- =============================================================
CREATE TABLE sales_agent.leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Core contact info (CSV import fields)
    name TEXT NOT NULL,
    phone TEXT NOT NULL UNIQUE,
    email TEXT,

    -- Profile fields (populated by Sarah during the call)
    company TEXT,
    role TEXT,
    experience_level TEXT,
    cloud_background TEXT,
    motivation TEXT,
    preferred_programme TEXT,

    -- Pipeline status with CHECK constraint for all valid statuses
    status TEXT NOT NULL DEFAULT 'new'
        CHECK (status IN (
            'new',
            'outreach_sent',
            'responded',
            'booked',
            'call_scheduled',
            'call_in_progress',
            'committed',
            'follow_up',
            'declined',
            'payment_sent',
            'paid',
            'archived'
        )),

    -- Priority for smart call ordering (1=highest, 5=lowest)
    priority INTEGER NOT NULL DEFAULT 3
        CHECK (priority BETWEEN 1 AND 5),

    -- Retry tracking
    retry_count INTEGER NOT NULL DEFAULT 0,
    next_retry_at TIMESTAMPTZ,
    last_call_attempt_at TIMESTAMPTZ,

    -- Milestone timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    outreach_sent_at TIMESTAMPTZ,
    booked_at TIMESTAMPTZ,
    call_started_at TIMESTAMPTZ,
    call_ended_at TIMESTAMPTZ,
    payment_sent_at TIMESTAMPTZ,
    paid_at TIMESTAMPTZ,
    archived_at TIMESTAMPTZ
);

-- =============================================================
-- Call logs table: One row per call attempt (including retries)
-- Twilio-aligned statuses; outcome set after call completes
-- =============================================================
CREATE TABLE sales_agent.call_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES sales_agent.leads(id),
    call_sid TEXT UNIQUE,

    -- Twilio-aligned call status
    status TEXT NOT NULL DEFAULT 'initiated'
        CHECK (status IN (
            'initiated',
            'ringing',
            'in_progress',
            'completed',
            'no_answer',
            'busy',
            'failed',
            'canceled'
        )),

    -- Call outcome (set after call completes)
    outcome TEXT
        CHECK (outcome IN ('committed', 'follow_up', 'declined')),

    -- Call metadata
    duration_seconds INTEGER,
    recording_url TEXT,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,

    -- Qualification data from Sarah
    recommended_programme TEXT,
    objections_raised JSONB DEFAULT '[]'::jsonb,
    qualification_summary TEXT,
    transcript TEXT,
    gemini_model_used TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================
-- Pipeline logs table: Matches backend/logger.py payload exactly
-- lead_id is TEXT (not UUID FK) for flexibility -- events may
-- come from n8n, OpenClaw, or other systems before lead exists
-- =============================================================
CREATE TABLE sales_agent.pipeline_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    component TEXT NOT NULL,
    event_type TEXT NOT NULL DEFAULT 'info',
    event_name TEXT NOT NULL,
    message TEXT,
    lead_id TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
