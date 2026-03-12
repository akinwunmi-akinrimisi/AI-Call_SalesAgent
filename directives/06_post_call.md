# Directive 06: Post-Call

## Stage
06 — Post-Call Automation

## System
n8n

## What Happens
n8n receives the outcome webhook from Cloud Run and branches:

### If COMMITTED
1. Update lead: `status = 'committed'`
2. Trigger OpenClaw → payment email with bank transfer details
3. Trigger OpenClaw → WhatsApp confirmation
4. Send admin summary email
5. Start 48hr payment reminder timer

### If FOLLOW_UP
1. Update lead: `status = 'follow_up'`, `follow_up_at = [date]`
2. Trigger OpenClaw → WhatsApp with programme details (not payment)
3. Send admin summary email
4. Schedule follow-up at `follow_up_at`

### If DECLINED
1. Update lead: `status = 'declined'`, `decline_reason = [reason]`
2. Send admin summary email
3. No further contact

## Done When
- Lead status updated correctly based on outcome
- Appropriate messages sent
- Admin notified
- Pipeline log entries for all actions
