# Directive 10: Enrolment

## Stage
10 — Enrolment

## System
Manual + n8n

## What Happens
Payment is confirmed manually (you check your bank account for the transfer).
Once confirmed:

1. Update lead in Supabase: `status = 'enrolled'`
2. n8n detects the status change
3. n8n triggers OpenClaw → welcome WhatsApp message
4. n8n triggers OpenClaw → welcome email with login credentials and welcome pack
5. Admin notification: enrolment confirmed

### Production Upgrade
Replace manual bank checking with Paystack payment links for automated confirmation.

## Done When
- Lead status = `enrolled` in Supabase
- Welcome message sent via WhatsApp and email
- Admin notified of enrolment
- Pipeline log: `lead_enrolled`
