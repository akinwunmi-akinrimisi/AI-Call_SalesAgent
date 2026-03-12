# Phase 1: Prerequisites - Context

**Gathered:** 2026-03-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Validate all external dependencies (APIs, accounts, credentials, content) before any downstream building. Every service must be confirmed reachable and functional. PDFs must exist and be parseable. Environment variables must be documented and populated. No code is built here -- only validation and preparation.

</domain>

<decisions>
## Implementation Decisions

### PDF Knowledge Base
- All 5 PDFs already exist as .pdf files on this machine, ready to copy into knowledge-base/
- Filenames match expected: programmes.pdf, conversation-sequence.pdf, faqs.pdf, payment-details.pdf, objection-handling.pdf
- Content is mixed structure: some PDFs are well-structured (e.g., pricing tables), others are conversational (e.g., objection scripts)
- conversation-sequence.pdf has a clear decision tree with explicit branching (if background is X -> recommend Y)
- PDFs will be updated occasionally (every few weeks) -- build a re-runnable seeder script, not one-time
- Phase 1 should parse and validate PDF content (extract text, check for expected sections/keywords), not just confirm files exist

### Gemini API Setup
- Pin to model `gemini-live-2.5-flash-native-audio` (research recommendation, latest stable)
- Update .env.example to reflect correct model
- Authentication via Vertex AI with service account (not AI Studio API key)
- Separate service account from n8n: "openclaw-key-google" (just added to project)
- Correct GCP project ID: `vision-gridai` (not cloudboosta-agent from .env.example)
- GCP region: Claude's discretion based on Gemini Live API availability and latency
- Full audio round-trip validation required: send audio in, get audio back, confirm bidirectional streaming
- Also test mulaw format acceptance in Phase 1 -- determines whether transcoding layer is needed in Phase 3
- 10-minute session limit handled by graceful wrap-up (duration watchdog at 8.5 min), no session reconnect

### Test Leads & Twilio
- All 10 test leads have name, phone (with country code), and email collected
- Data is in a spreadsheet -- will export to CSV for import
- All 10 leads have been informed about and consented to the AI call
- Twilio number verification is a Phase 1 task -- leads need step-by-step guidance for verifying each number in Twilio console
- Twilio trial limitations acknowledged: "trial account" message prefix, 10-minute cutoff

### Env Vars & Secrets
- Single master .env.example with all variables across all 3 systems (Cloud Run, VPS #1, VPS #2)
- Fix .env.example: GCP_PROJECT_ID should be vision-gridai, GEMINI_MODEL should be gemini-live-2.5-flash-native-audio
- Move my-n8n-service-account.json and openclaw-key-google to secrets/ directory, add secrets/ to .gitignore
- Supabase keys (service + anon) are ready
- n8n API key and webhook URL are ready
- Resend API key is ready
- OpenClaw API validation level: Claude's discretion (validate reachability in Phase 1 vs. full setup in Phase 7)

### Claude's Discretion
- GCP region selection (based on Gemini Live API availability and latency to UK/Nigeria leads)
- OpenClaw validation depth in Phase 1 (reachability check vs. defer entirely to Phase 7)
- PDF section validation criteria (which keywords/sections to check per PDF)

</decisions>

<specifics>
## Specific Ideas

- conversation-sequence.pdf has a clear decision tree -- this is the core of Sarah's qualification logic. Parsing quality matters.
- PDFs will be updated occasionally, so the seeder must be re-runnable (idempotent)
- Twilio verification is new to the user -- include clear step-by-step instructions

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `.env.example` (root): Master env template -- needs correction (wrong project ID, wrong model)
- `backend/.env.example`: Separate backend env template -- needs alignment with root
- `scripts/seed_firestore.py`: Stub seeder script exists -- needs real implementation in Phase 2
- `scripts/test_call.py`: Stub test script exists -- can be used as starting point for Gemini validation

### Established Patterns
- `.env` at root with `.env.example` as template
- `backend/config.py` reads environment variables (existing pattern to follow)
- `backend/logger.py` exists for logging

### Integration Points
- `knowledge-base/` directory exists but is empty -- PDFs go here
- `secrets/` directory needs creation for service account files
- `.gitignore` needs updating for secrets/ and service account files

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 01-prerequisites*
*Context gathered: 2026-03-12*
