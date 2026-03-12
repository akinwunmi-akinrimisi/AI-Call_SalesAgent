# Directive 08: Admin Notification

## Stage
08 — Admin Notification

## System
n8n

## What Happens
After every call, n8n sends a summary email to Akinwunmi's personal email.

### Email Contents
- Subject: `[OUTCOME] [Lead Name] - [Programme]`
- Lead details: name, phone, email, location, current role
- Programme recommended and price
- Call duration
- Objections raised
- AI-generated transcript summary (3-4 sentences)
- Status and next action
- Twilio recording URL

See DEFINITIVE v2.0, Step 6 for exact format.

## Done When
- Admin receives email after every call
- Email contains all required fields
- Recording URL is clickable
- Pipeline log: `admin_notified`
