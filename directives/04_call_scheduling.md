# Directive 04: Call Scheduling

## Stage
04 — Call Scheduling

## System
n8n

## What Happens
n8n creates a scheduled trigger for the booked call time.
1 hour before the call, n8n triggers OpenClaw to send a WhatsApp reminder.

## Reminder Message
"Hi [Name], just a reminder that Sarah from Cloudboosta will be calling you
at [time] today. The call will come from a US number. Speak soon!"

## Data Flow
1. n8n monitors `call_scheduled_at` timestamps
2. 1hr before → trigger OpenClaw reminder via WhatsApp
3. At call time → HTTP POST to Cloud Run with lead details
4. Log to `pipeline_logs`: `reminder_sent`, then `call_triggered`

## Done When
- Reminder sent 1 hour before call
- Cloud Run receives the call trigger at the scheduled time
- Pipeline logs confirm both events
