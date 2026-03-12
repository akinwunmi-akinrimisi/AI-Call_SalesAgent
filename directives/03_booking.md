# Directive 03: Booking

## Stage
03 — Booking

## System
OpenClaw

## What Happens
Lead replies on WhatsApp. OpenClaw (powered by Gemini) handles the booking conversation:
- Offers available time slots
- Confirms the selected slot
- Sends confirmation message

If lead replies via email, n8n forwards to OpenClaw or it's handled manually (test phase).

## Duplicate Check
Before booking, n8n checks Supabase to ensure the lead hasn't already booked
or been contacted on the other channel.

## Data Flow
1. Lead replies on WhatsApp
2. OpenClaw handles natural conversation → books a time
3. OpenClaw notifies n8n of the booking
4. n8n updates Supabase: `status = 'call_scheduled'`, `call_scheduled_at = [time]`
5. OpenClaw sends confirmation: "You're booked for [day] at [time]..."
6. Log to `pipeline_logs`: `call_booked`

## Done When
- Lead has a confirmed call time
- Supabase has `call_scheduled_at` populated
- Confirmation message sent via WhatsApp
