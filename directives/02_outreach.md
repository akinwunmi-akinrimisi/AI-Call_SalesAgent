# Directive 02: Outreach

## Stage
02 — Outreach

## System
OpenClaw (WhatsApp) + n8n (email)

## What Happens
n8n detects leads with `status = 'new'` and triggers dual-channel outreach:
1. WhatsApp message via OpenClaw (from personal Nigerian number)
2. Email via Resend API or Gmail SMTP

## Rate Limiting
- Test phase: 10/day
- Production: 50/day

## WhatsApp Message Template
See DEFINITIVE v2.0, Step 2 for exact copy.

## Email Template
See DEFINITIVE v2.0, Step 2 for exact copy.

## Data Flow
1. n8n cron/trigger detects `status = 'new'` leads
2. n8n calls OpenClaw API → WhatsApp message sent
3. n8n sends email via SMTP/Resend
4. n8n updates lead: `status = 'outreach_sent'`
5. Log to `pipeline_logs`: `outreach_sent`

## Done When
- Lead receives WhatsApp message from personal number
- Lead receives email
- Supabase status = `outreach_sent`
- Pipeline log entry confirms both channels
