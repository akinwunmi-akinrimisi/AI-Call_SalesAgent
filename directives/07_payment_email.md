# Directive 07: Payment Email

## Stage
07 — Payment Email

## System
OpenClaw + n8n

## What Happens
After a COMMITTED outcome, OpenClaw sends an email with bank transfer details
read from `payment-details.pdf` in the knowledge base.

### Email Template
See DEFINITIVE v2.0, Step 6 (If Outcome = COMMITTED) for exact copy.

### WhatsApp Confirmation
"Hi [Name], I've just sent you an email with the payment details for the
[programme]. Check your inbox! Let me know if you have any questions."

### Reminders
- 48 hours: "Just checking in on your enrolment..."
- 96 hours: Final reminder (if configured)

## Done When
- Payment email sent with correct bank details
- WhatsApp confirmation sent
- 48hr reminder scheduled
- Pipeline log entries confirm all messages
