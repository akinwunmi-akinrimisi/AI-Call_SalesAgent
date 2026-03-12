# Directive 09: Monitoring

## Stage
09 — Monitoring

## System
n8n

## What Happens
Automated health checks and pipeline monitoring:

### Health Checks (every 5 minutes)
- Cloud Run backend: GET /health
- Supabase: connectivity check
- OpenClaw: connectivity check
- Write results to `service_health` table

### Stuck Lead Detector (every 15 minutes)
- Query `leads` for status stuck > threshold:
  - `outreach_sent` for > 48hrs with no response
  - `call_scheduled` with `call_scheduled_at` in the past
  - `committed` for > 96hrs with no payment
- Alert admin via email if stuck leads found

### Daily Report (9pm)
- Compute `daily_metrics`: leads contacted, calls made, commitments, conversion rate
- Email summary to admin
- WhatsApp summary to admin

## Done When
- Health checks run every 5 minutes and log to `service_health`
- Stuck leads detected and admin alerted
- Daily report sent at 9pm
- All events logged to `pipeline_logs`
