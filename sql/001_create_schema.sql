-- 001: Create sales_agent schema with role grants
-- Phase 2 Plan 01: Supabase Schema Migration
-- Run this FIRST before 002 and 003

-- Create isolated schema for the sales pipeline
CREATE SCHEMA IF NOT EXISTS sales_agent;

-- Grant access to all Supabase roles
GRANT USAGE ON SCHEMA sales_agent TO anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA sales_agent TO anon, authenticated, service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA sales_agent TO anon, authenticated, service_role;

-- Ensure future tables/sequences in this schema inherit the grants
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA sales_agent
  GRANT ALL ON TABLES TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA sales_agent
  GRANT ALL ON SEQUENCES TO anon, authenticated, service_role;
