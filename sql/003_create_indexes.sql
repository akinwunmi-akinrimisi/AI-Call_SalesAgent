-- 003: Create indexes for common queries
-- Phase 2 Plan 01: Supabase Schema Migration
-- Run AFTER 002_create_tables.sql

-- Leads indexes
CREATE INDEX idx_leads_status
    ON sales_agent.leads(status);

CREATE INDEX idx_leads_phone
    ON sales_agent.leads(phone);

CREATE INDEX idx_leads_priority_status
    ON sales_agent.leads(priority DESC, status);

-- Partial index: only index leads that have a scheduled retry
CREATE INDEX idx_leads_next_retry
    ON sales_agent.leads(next_retry_at)
    WHERE next_retry_at IS NOT NULL;

-- Call logs indexes
CREATE INDEX idx_call_logs_lead_id
    ON sales_agent.call_logs(lead_id);

CREATE INDEX idx_call_logs_call_sid
    ON sales_agent.call_logs(call_sid);

CREATE INDEX idx_call_logs_created
    ON sales_agent.call_logs(created_at DESC);

-- Pipeline logs indexes
CREATE INDEX idx_pipeline_logs_lead_id
    ON sales_agent.pipeline_logs(lead_id);

CREATE INDEX idx_pipeline_logs_event
    ON sales_agent.pipeline_logs(event_name, created_at DESC);

CREATE INDEX idx_pipeline_logs_created
    ON sales_agent.pipeline_logs(created_at DESC);
