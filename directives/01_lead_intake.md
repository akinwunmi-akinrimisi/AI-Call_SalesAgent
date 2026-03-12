# Directive 01: Lead Intake

## Stage
01 — Lead Intake

## System
n8n + Supabase

## What Happens
New leads are added to Supabase from CSV upload, Mailerlite sync, or Facebook ad forms.
Each lead is validated (phone format, email format, duplicate check) and stored with status `new`.

## Data Flow
1. Source (CSV / Mailerlite / Facebook) → n8n workflow
2. n8n validates: name present, phone has country code, email valid
3. n8n checks Supabase for duplicate (phone or email match)
4. If new → INSERT into `leads` table with `status = 'new'`
5. Log to `pipeline_logs`: `lead_intake`, `"New lead added: {name}"`

## Done When
- Lead exists in Supabase `leads` table with status `new`
- Pipeline log entry confirms intake
- Duplicate leads are rejected (not inserted)

## Test Phase
- 10 leads added manually via Supabase dashboard or CSV import script
