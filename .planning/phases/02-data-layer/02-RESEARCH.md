# Phase 2: Data Layer - Research

**Researched:** 2026-03-12
**Domain:** Supabase PostgreSQL (self-hosted), Google Cloud Firestore (Native mode), PDF text extraction, CSV data import
**Confidence:** HIGH

## Summary

Phase 2 deploys the data foundation for the entire sales pipeline: a Supabase PostgreSQL schema isolated in the `sales_agent` namespace, a Firestore knowledge base seeded from 5 PDFs, and a CSV import script for leads. The project uses a self-hosted Supabase instance running as Docker containers on VPS #1 (srv1297445.hstgr.cloud), which means schema exposure requires updating the `PGRST_DB_SCHEMAS` and `PG_META_DB_SCHEMAS` environment variables in the Supabase Docker configuration and restarting the rest/meta/studio containers.

The existing codebase establishes clear patterns: `backend/logger.py` already writes to Supabase via httpx REST API with `apikey` and `Bearer` token headers. The `pipeline_logs` table schema is implicitly defined by logger.py's payload (component, event_type, event_name, message, lead_id, metadata, created_at). Firestore access will use the `google-cloud-firestore` Python SDK (already in requirements.txt) with the service account key at `secrets/openclaw-key-google.json`. PDF extraction uses `pymupdf4llm` (already in requirements.txt) which converts PDFs to clean Markdown text -- ideal for LLM consumption.

**Primary recommendation:** Execute SQL migrations directly against the Supabase PostgreSQL database (via psql or Supabase Studio SQL editor), expose the `sales_agent` schema in PostgREST config, then use httpx REST API (matching logger.py pattern) for all data operations. Use `phonenumbers` library for E.164 validation in the CSV import script.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Full 10-stage pipeline status tracking: new -> outreach_sent -> responded -> booked -> call_scheduled -> call_in_progress -> committed/follow_up/declined -> payment_sent -> paid
- Rich profile fields: name, phone, email, company, role, experience_level, cloud_background, motivation, preferred_programme -- all populated by Sarah during the call (CSV only provides name/phone/email)
- Soft status enforcement: log warnings on skipped transitions, but allow them. Strict enforcement deferred to v2
- Key milestone timestamps on leads table: created_at, outreach_sent_at, booked_at, call_started_at, call_ended_at, payment_sent_at, paid_at
- Priority field: integer 1-5, default 3
- Retry tracking on leads table: retry_count (int, max 2), next_retry_at (timestamp), last_call_attempt_at
- Soft delete: status='archived' with archived_at timestamp. Never hard delete leads
- One Firestore document per PDF in `knowledge_base` collection (5 documents total)
- Document IDs match PDF names: 'programmes', 'conversation-sequence', 'faqs', 'payment-details', 'objection-handling'
- Each document stores: content (full markdown text), source_file, page_count, extracted_at, version, keywords[]
- Firestore in vision-gridai project, Native mode, europe-west1 location
- Firestore database must be created first (no existing DB) -- seed script creates DB if needed via gcloud
- Seed script runs on VPS #1 via SSH (where gcloud + Python 3.12 are available)
- Idempotent: overwrite existing documents on re-run (safe for PDF updates)
- Rich call record: lead_id, call_sid, status, outcome, duration_seconds, recording_url, started_at, ended_at, recommended_programme, objections_raised (JSON array), qualification_summary, gemini_model_used
- Full conversation transcript stored in a separate TEXT column
- One call_log row per call attempt. Twilio-aligned statuses: initiated, ringing, in_progress, completed, no_answer, busy, failed, canceled
- CSV columns: name, phone, email only
- Phone normalization: require explicit country code prefix (+), reject numbers without +
- Duplicate handling: skip duplicates (matching on phone), log warning. Safe for re-runs
- Import sets status='new' and default priority=3
- Supabase uses isolated `sales_agent` schema (not public)

### Claude's Discretion
- Exact Supabase SQL migration syntax and RLS policies
- pipeline_logs table schema (must match existing logger.py payload structure)
- Index strategy for leads and call_logs tables
- Error handling in import and seed scripts
- Whether to use Supabase client library or raw REST API in scripts

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DATA-01 | Leads can be imported into Supabase via CSV with name, phone (with country code), and email | CSV import script using httpx REST API + phonenumbers library for E.164 validation; duplicate detection via phone match |
| DATA-02 | Supabase schema deployed in isolated `sales_agent` schema with leads, call_logs, and pipeline_logs tables | SQL migration creating schema + tables + indexes; PostgREST config update (PGRST_DB_SCHEMAS) on self-hosted Docker |
| DATA-03 | Firestore knowledge base seeded from 5 PDFs (programmes, conversation-sequence, FAQs, payment details, objection handling) | pymupdf4llm for PDF-to-Markdown extraction; google-cloud-firestore SDK for document writes; gcloud CLI for database creation |
| DATA-04 | All significant pipeline actions logged to `pipeline_logs` table in Supabase | Table schema derived from existing logger.py payload; logger.py must be updated to use sales_agent schema via Content-Profile header |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | >=0.28.0 | Supabase REST API client | Already established in logger.py; async support; used for all Supabase operations |
| google-cloud-firestore | >=2.19.0 | Firestore document read/write | Official Google Cloud Python SDK; already in requirements.txt |
| pymupdf4llm | >=0.0.14 | PDF to Markdown extraction | Already in requirements.txt; purpose-built for LLM/RAG PDF conversion |
| phonenumbers | >=8.13.0 | E.164 phone number validation | Google's libphonenumber Python port; definitive phone validation library |
| python-dotenv | >=1.0.1 | Environment variable loading | Already in requirements.txt; established pattern |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pymupdf | >=1.24.0 | PDF parsing engine (pymupdf4llm dependency) | Automatically used by pymupdf4llm |
| google-auth | >=2.0.0 | Service account authentication | Already in requirements.txt; used for Firestore credentials |
| supabase | >=2.0.0 | Alternative Supabase client | Already in requirements.txt but NOT recommended for this phase -- httpx REST API is simpler and matches established patterns |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| httpx REST API | supabase-py client | supabase-py has inconsistent custom schema support; httpx with headers is simpler and matches logger.py |
| phonenumbers | regex validation | phonenumbers handles international formats, carrier detection, and edge cases that regex cannot |
| pymupdf4llm | raw pymupdf text extraction | pymupdf4llm produces cleaner Markdown with headers, tables, and formatting preserved for LLM consumption |
| Direct SQL via psql | Supabase migration system | For a self-hosted instance, direct SQL execution is simpler and more transparent |

**Installation (new dependency only):**
```bash
pip install phonenumbers>=8.13.0
```
Add `phonenumbers>=8.13.0` to `backend/requirements.txt` (or a separate `scripts/requirements.txt`).

## Architecture Patterns

### Recommended Project Structure
```
scripts/
  import_leads.py          # CSV import script (Phase 2 deliverable)
  seed_firestore.py        # Firestore seeder (Phase 2 deliverable)
  requirements.txt         # Script-specific dependencies (phonenumbers)
sql/
  001_create_schema.sql    # CREATE SCHEMA + GRANT statements
  002_create_tables.sql    # leads, call_logs, pipeline_logs tables
  003_create_indexes.sql   # Performance indexes
  README.md                # Migration execution instructions
backend/
  logger.py                # UPDATE: Add Content-Profile header for sales_agent schema
  config.py                # No changes needed
knowledge-base/
  programmes.pdf           # Already present (6 PDFs including coming-soon.pdf)
  conversation-sequence.pdf
  faqs.pdf
  payment-details.pdf
  objection-handling.pdf
```

### Pattern 1: Supabase REST API with Custom Schema Headers
**What:** When writing to a table in the `sales_agent` schema via Supabase REST API, the URL path stays the same (`/rest/v1/table_name`) but you must include a schema profile header.
**When to use:** All reads and writes to sales_agent schema tables.
**Example:**
```python
# Source: PostgREST v14 docs + Supabase custom schema docs
# For POST/PUT/PATCH/DELETE requests:
headers = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
    "Content-Profile": "sales_agent",  # <-- THIS IS THE KEY ADDITION
    "Prefer": "return=minimal",
}

# For GET/HEAD requests:
headers = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY},
    "Accept-Profile": "sales_agent",  # <-- Different header for reads
}
```

### Pattern 2: Existing logger.py Integration
**What:** The existing `backend/logger.py` writes to `pipeline_logs` via `/rest/v1/pipeline_logs`. Once the table moves to `sales_agent` schema, logger.py must add the `Content-Profile: sales_agent` header.
**When to use:** After schema migration is complete.
**Example:**
```python
# Source: Existing backend/logger.py (lines 42-56)
# Current code writes to /rest/v1/pipeline_logs with these headers:
headers = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
    "Content-Profile": "sales_agent",  # ADD THIS LINE
}
```

### Pattern 3: Firestore Document Set with Specific ID
**What:** Seed a Firestore document with a predetermined ID matching the PDF name.
**When to use:** Firestore knowledge base seeding.
**Example:**
```python
# Source: Google Cloud Firestore Python SDK docs
from google.cloud import firestore

db = firestore.Client(project="vision-gridai")

doc_ref = db.collection("knowledge_base").document("programmes")
doc_ref.set({
    "content": markdown_text,        # Full markdown from pymupdf4llm
    "source_file": "programmes.pdf",
    "page_count": 12,
    "extracted_at": firestore.SERVER_TIMESTAMP,
    "version": "1.0",
    "keywords": ["cloud security", "SRE", "platform engineering", "pricing"],
})
# set() without merge=True replaces the entire document (idempotent overwrite)
```

### Pattern 4: PDF to Markdown Extraction
**What:** Convert PDF files to clean Markdown text for LLM consumption.
**When to use:** Firestore seeding script.
**Example:**
```python
# Source: pymupdf4llm official docs
import pymupdf4llm

# Basic full-document extraction (returns single string)
markdown_text = pymupdf4llm.to_markdown("knowledge-base/programmes.pdf")

# With page metadata (returns list of dicts)
chunks = pymupdf4llm.to_markdown(
    "knowledge-base/programmes.pdf",
    page_chunks=True,
)
# chunks[0] = {"text": "# Page content...", "metadata": {...}, "toc_items": [...], ...}
page_count = len(chunks)
full_text = "\n\n".join(chunk["text"] for chunk in chunks)
```

### Pattern 5: Phone Number Validation (E.164)
**What:** Validate and normalize phone numbers to E.164 format, rejecting those without country code prefix.
**When to use:** CSV import script.
**Example:**
```python
# Source: python-phonenumbers docs
import phonenumbers

def validate_phone(phone_str: str) -> str | None:
    """Validate and normalize phone to E.164. Returns None if invalid."""
    if not phone_str.startswith("+"):
        return None  # Reject numbers without explicit country code
    try:
        parsed = phonenumbers.parse(phone_str, None)  # None = no default region
        if not phonenumbers.is_valid_number(parsed):
            return None
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        return None

# Usage:
validate_phone("+2348012345678")   # -> "+2348012345678" (Nigeria)
validate_phone("+447986123456")    # -> "+447986123456"  (UK)
validate_phone("08012345678")      # -> None (no country code)
validate_phone("+123")             # -> None (too short)
```

### Anti-Patterns to Avoid
- **Writing to public schema instead of sales_agent:** Always include the Content-Profile/Accept-Profile header. The URL path does NOT change -- only the header switches the schema.
- **Hardcoding PDF content in code:** All knowledge must come from PDF extraction at seed time. Update the PDF, re-run the seeder.
- **Using supabase-py client for custom schema operations:** The Python client has inconsistent custom schema support. Use httpx REST API with explicit headers (matches logger.py pattern).
- **Creating Firestore database from Python SDK:** Use `gcloud firestore databases create` CLI command, not the SDK. The SDK assumes the database already exists.
- **Storing raw PDF bytes in Firestore:** Use pymupdf4llm to convert to Markdown text first. Raw bytes are unusable by the LLM.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Phone number validation | Regex patterns for E.164 | `phonenumbers` library | International formats have 200+ country codes, variable lengths, carrier-specific rules |
| PDF text extraction | Raw pymupdf page.get_text() | `pymupdf4llm.to_markdown()` | Handles tables, headers, multi-column layouts, preserves semantic structure |
| UUID generation | Custom ID functions | PostgreSQL `gen_random_uuid()` | Built into PostgreSQL 14+, no extension needed, cryptographically random |
| Timestamp handling | Manual datetime formatting | PostgreSQL `now()` / `CURRENT_TIMESTAMP` | Server-side timestamps avoid clock skew between client and database |
| JSON validation | Manual dict parsing for metadata | PostgreSQL `JSONB` type | Native indexing, querying, and validation |

**Key insight:** The Supabase PostgreSQL database handles UUIDs, timestamps, and JSON natively. Let the database do the work rather than generating these values in Python.

## Common Pitfalls

### Pitfall 1: Self-Hosted Schema Exposure
**What goes wrong:** Creating the `sales_agent` schema via SQL succeeds, but REST API requests return 404 because PostgREST doesn't know about the schema.
**Why it happens:** Self-hosted Supabase requires manual configuration. Unlike Supabase Cloud (which has a dashboard toggle), self-hosted needs environment variable updates.
**How to avoid:** After creating the schema in SQL:
1. SSH into VPS #1
2. Find the Supabase `.env` file (usually in the Supabase Docker directory)
3. Update `PGRST_DB_SCHEMAS` from `public,storage,graphql_public` to `public,storage,graphql_public,sales_agent`
4. Update `PG_META_DB_SCHEMAS` similarly (for Supabase Studio visibility)
5. Restart the `rest`, `meta`, and `studio` containers: `docker compose restart rest meta studio`
**Warning signs:** 404 errors when accessing `/rest/v1/leads` with `Accept-Profile: sales_agent`

### Pitfall 2: Missing GRANT Statements
**What goes wrong:** Schema and tables are created, PostgREST is configured, but API calls return 401/403.
**Why it happens:** PostgreSQL schemas are private by default. The `anon`, `authenticated`, and `service_role` roles need explicit USAGE and table grants.
**How to avoid:** Run the full grant block after CREATE SCHEMA:
```sql
GRANT USAGE ON SCHEMA sales_agent TO anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA sales_agent TO anon, authenticated, service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA sales_agent TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA sales_agent
  GRANT ALL ON TABLES TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA sales_agent
  GRANT ALL ON SEQUENCES TO anon, authenticated, service_role;
```
**Warning signs:** REST API returns permission denied or empty results despite data existing.

### Pitfall 3: Logger.py Breaks After Migration
**What goes wrong:** After creating `pipeline_logs` in the `sales_agent` schema, the existing logger.py fails because it writes to the `public` schema by default.
**Why it happens:** logger.py currently does not include a `Content-Profile` header, so PostgREST routes to the default (first listed) schema, which is `public`.
**How to avoid:** Update logger.py to include `"Content-Profile": "sales_agent"` in its headers. Do NOT create a `pipeline_logs` table in the `public` schema as a workaround.
**Warning signs:** logger.py calls succeed but data appears in the wrong schema (or nowhere if there's no matching table).

### Pitfall 4: Firestore Database Does Not Exist
**What goes wrong:** The seed script tries to write documents but gets a "database not found" error.
**Why it happens:** The GCP project (vision-gridai) may not have a Firestore database created yet. The Python SDK does not create the database -- it only reads/writes to an existing one.
**How to avoid:** The seed script must first check/create the database using gcloud CLI:
```bash
gcloud firestore databases create --location=europe-west1 --type=firestore-native --project=vision-gridai
```
This command is idempotent (returns success if database already exists). Run it before any Python SDK operations.
**Warning signs:** `google.api_core.exceptions.NotFound: 404 The database (default) does not exist`

### Pitfall 5: CSV Phone Numbers Missing Country Code
**What goes wrong:** Import script accepts phone numbers like "08012345678" (common Nigerian format) without a country code, making them unroutable by Twilio.
**Why it happens:** Users often store phone numbers without the + prefix in their contact lists.
**How to avoid:** The CONTEXT.md locks this decision: reject numbers without `+` prefix, log a warning. Do not auto-detect country codes as this introduces ambiguity.
**Warning signs:** Leads imported with invalid phone numbers, Twilio calls fail with "invalid number."

### Pitfall 6: Firestore Region Mismatch
**What goes wrong:** Firestore database is created in the wrong region (e.g., us-east1 instead of europe-west1).
**Why it happens:** Firestore database location cannot be changed after creation. The default region may not match the project's preferred region.
**How to avoid:** Always specify `--location=europe-west1` explicitly in the gcloud create command. Verify after creation with `gcloud firestore databases describe --project=vision-gridai`.
**Warning signs:** Higher latency for European/African leads, potential data residency concerns.

## Code Examples

Verified patterns from official sources and existing codebase:

### SQL Migration: Create Schema and Tables
```sql
-- Source: Supabase custom schema docs + CONTEXT.md field specifications

-- 001: Create isolated schema
CREATE SCHEMA IF NOT EXISTS sales_agent;

-- Grant access to Supabase roles
GRANT USAGE ON SCHEMA sales_agent TO anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA sales_agent TO anon, authenticated, service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA sales_agent TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA sales_agent
  GRANT ALL ON TABLES TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA sales_agent
  GRANT ALL ON SEQUENCES TO anon, authenticated, service_role;

-- 002: Leads table
CREATE TABLE sales_agent.leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    phone TEXT NOT NULL UNIQUE,
    email TEXT,
    company TEXT,
    role TEXT,
    experience_level TEXT,
    cloud_background TEXT,
    motivation TEXT,
    preferred_programme TEXT,
    status TEXT NOT NULL DEFAULT 'new'
        CHECK (status IN ('new','outreach_sent','responded','booked',
            'call_scheduled','call_in_progress','committed','follow_up',
            'declined','payment_sent','paid','archived')),
    priority INTEGER NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    retry_count INTEGER NOT NULL DEFAULT 0,
    next_retry_at TIMESTAMPTZ,
    last_call_attempt_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    outreach_sent_at TIMESTAMPTZ,
    booked_at TIMESTAMPTZ,
    call_started_at TIMESTAMPTZ,
    call_ended_at TIMESTAMPTZ,
    payment_sent_at TIMESTAMPTZ,
    paid_at TIMESTAMPTZ,
    archived_at TIMESTAMPTZ
);

-- 002: Call logs table
CREATE TABLE sales_agent.call_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES sales_agent.leads(id),
    call_sid TEXT UNIQUE,
    status TEXT NOT NULL DEFAULT 'initiated'
        CHECK (status IN ('initiated','ringing','in_progress','completed',
            'no_answer','busy','failed','canceled')),
    outcome TEXT CHECK (outcome IN ('committed','follow_up','declined')),
    duration_seconds INTEGER,
    recording_url TEXT,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    recommended_programme TEXT,
    objections_raised JSONB DEFAULT '[]'::jsonb,
    qualification_summary TEXT,
    transcript TEXT,
    gemini_model_used TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 002: Pipeline logs table (matches logger.py payload)
CREATE TABLE sales_agent.pipeline_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    component TEXT NOT NULL,
    event_type TEXT NOT NULL DEFAULT 'info',
    event_name TEXT NOT NULL,
    message TEXT,
    lead_id TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 003: Indexes for common queries
CREATE INDEX idx_leads_status ON sales_agent.leads(status);
CREATE INDEX idx_leads_phone ON sales_agent.leads(phone);
CREATE INDEX idx_leads_priority_status ON sales_agent.leads(priority DESC, status);
CREATE INDEX idx_leads_next_retry ON sales_agent.leads(next_retry_at)
    WHERE next_retry_at IS NOT NULL;
CREATE INDEX idx_call_logs_lead_id ON sales_agent.call_logs(lead_id);
CREATE INDEX idx_call_logs_call_sid ON sales_agent.call_logs(call_sid);
CREATE INDEX idx_call_logs_created ON sales_agent.call_logs(created_at DESC);
CREATE INDEX idx_pipeline_logs_lead_id ON sales_agent.pipeline_logs(lead_id);
CREATE INDEX idx_pipeline_logs_event ON sales_agent.pipeline_logs(event_name, created_at DESC);
CREATE INDEX idx_pipeline_logs_created ON sales_agent.pipeline_logs(created_at DESC);
```

### CSV Import Script Pattern
```python
# Source: Established httpx pattern from logger.py + phonenumbers docs
import csv
import sys
import phonenumbers
import httpx
from dotenv import load_dotenv
import os

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

def validate_phone(phone_str: str) -> str | None:
    if not phone_str.strip().startswith("+"):
        return None
    try:
        parsed = phonenumbers.parse(phone_str.strip(), None)
        if not phonenumbers.is_valid_number(parsed):
            return None
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        return None

def import_leads(csv_path: str):
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Content-Profile": "sales_agent",
        "Prefer": "return=representation",
    }

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            phone = validate_phone(row["phone"])
            if phone is None:
                print(f"[SKIP] Invalid phone: {row['phone']} for {row['name']}")
                continue

            # Check for duplicate (by phone)
            check_headers = {
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                "Accept-Profile": "sales_agent",
            }
            resp = httpx.get(
                f"{SUPABASE_URL}/rest/v1/leads?phone=eq.{phone}&select=id",
                headers=check_headers,
            )
            if resp.json():
                print(f"[SKIP] Duplicate phone: {phone} for {row['name']}")
                continue

            # Insert new lead
            payload = {
                "name": row["name"].strip(),
                "phone": phone,
                "email": row.get("email", "").strip() or None,
                "status": "new",
                "priority": 3,
            }
            resp = httpx.post(
                f"{SUPABASE_URL}/rest/v1/leads",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            print(f"[OK] Imported: {row['name']} ({phone})")

if __name__ == "__main__":
    import_leads(sys.argv[1])
```

### Firestore Seeder Pattern
```python
# Source: google-cloud-firestore SDK docs + pymupdf4llm docs
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pymupdf4llm
from google.cloud import firestore
from dotenv import load_dotenv

load_dotenv()

GCP_PROJECT = os.getenv("GCP_PROJECT_ID", "vision-gridai")
CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "secrets/openclaw-key-google.json")
KB_DIR = Path("knowledge-base")

# Document ID -> PDF filename mapping
PDF_MAP = {
    "programmes": "programmes.pdf",
    "conversation-sequence": "conversation-sequence.pdf",
    "faqs": "faqs.pdf",
    "payment-details": "payment-details.pdf",
    "objection-handling": "objection-handling.pdf",
}

def ensure_firestore_db():
    """Create Firestore database if it doesn't exist (idempotent)."""
    result = subprocess.run(
        ["gcloud", "firestore", "databases", "create",
         "--location=europe-west1", "--type=firestore-native",
         f"--project={GCP_PROJECT}"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print("[OK] Firestore database created")
    elif "already exists" in result.stderr.lower():
        print("[OK] Firestore database already exists")
    else:
        print(f"[ERROR] Firestore creation failed: {result.stderr}")
        raise RuntimeError(result.stderr)

def extract_pdf_to_markdown(pdf_path: Path) -> tuple[str, int]:
    """Extract PDF content as Markdown. Returns (text, page_count)."""
    chunks = pymupdf4llm.to_markdown(str(pdf_path), page_chunks=True)
    full_text = "\n\n".join(chunk["text"] for chunk in chunks)
    return full_text, len(chunks)

def seed_knowledge_base():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = CREDENTIALS_PATH
    ensure_firestore_db()

    db = firestore.Client(project=GCP_PROJECT)

    for doc_id, pdf_name in PDF_MAP.items():
        pdf_path = KB_DIR / pdf_name
        if not pdf_path.exists():
            print(f"[SKIP] PDF not found: {pdf_path}")
            continue

        content, page_count = extract_pdf_to_markdown(pdf_path)

        doc_ref = db.collection("knowledge_base").document(doc_id)
        doc_ref.set({
            "content": content,
            "source_file": pdf_name,
            "page_count": page_count,
            "extracted_at": firestore.SERVER_TIMESTAMP,
            "version": "1.0",
            "keywords": [],  # Populated per-document by implementation
        })
        print(f"[OK] Seeded: {doc_id} ({page_count} pages)")

if __name__ == "__main__":
    seed_knowledge_base()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| PostgREST v12 | PostgREST v14 (in new Supabase) | 2025-2026 | 20% more RPS, faster schema cache loading |
| pymupdf raw text | pymupdf4llm Markdown | 2024 | Semantic structure preserved, better for LLM consumption |
| Firestore single DB | Firestore multiple databases per project | 2023 | Can isolate if needed, but default (default) DB is fine for this project |
| google-cloud-firestore 2.19 | 2.22.0 (Jan 2026) | 2026-01-14 | Minor improvements, 2.19+ is fine |
| supabase-py 1.x | supabase-py 2.x | 2024 | New client, but custom schema support still inconsistent -- stick with httpx |

**Deprecated/outdated:**
- `pymupdf.Page.getText()` is deprecated -- use `pymupdf4llm.to_markdown()` for LLM use cases
- Firestore Datastore mode is legacy for this use case -- Native mode is correct for document-based access

## Open Questions

1. **Supabase Docker directory location on VPS #1**
   - What we know: Supabase is running as Docker containers on VPS #1 (srv1297445.hstgr.cloud)
   - What's unclear: Exact path to the Supabase docker-compose.yml and .env file on VPS #1
   - Recommendation: During execution, SSH into VPS #1 and locate via `docker compose ls` or `find / -name "docker-compose.yml" -path "*/supabase/*"`. Common paths: `/opt/supabase/docker/`, `/root/supabase/`, or similar.

2. **pipeline_logs lead_id type: UUID vs TEXT**
   - What we know: logger.py sends `lead_id` as a string. The leads table uses UUID for id.
   - What's unclear: Whether lead_id in pipeline_logs should be a UUID foreign key or keep it as TEXT for flexibility (n8n and other systems may log before lead exists)
   - Recommendation: Use TEXT (not UUID FK). Pipeline logs come from multiple systems (voice agent, n8n, OpenClaw) and some events may occur before or without a lead record. TEXT is more flexible and matches the existing logger.py behavior. The field is informational, not relational.

3. **RLS policies**
   - What we know: The service_role key bypasses RLS. All current access is server-to-server.
   - What's unclear: Whether RLS should be enabled now or deferred
   - Recommendation: Defer RLS to v2. All access is via service_role key (from backend, n8n, and scripts). Enabling RLS now adds complexity with no security benefit since there are no end-user clients.

4. **Keywords extraction for Firestore documents**
   - What we know: Each document should have a `keywords[]` field
   - What's unclear: Whether to manually define keywords per document or auto-extract
   - Recommendation: Manually define a small set of keywords per PDF document in the seed script. The voice agent (Phase 3) queries by document ID, not by keyword search. Keywords are metadata for future use.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (to be installed) |
| Config file | none -- see Wave 0 |
| Quick run command | `pytest tests/test_data_layer.py -x -v` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DATA-01 | CSV import creates leads with correct fields | integration | `pytest tests/test_import_leads.py::test_csv_import_creates_leads -x` | No -- Wave 0 |
| DATA-01 | Phone validation rejects numbers without + | unit | `pytest tests/test_import_leads.py::test_phone_validation -x` | No -- Wave 0 |
| DATA-02 | Schema exists with correct tables/columns | smoke | `pytest tests/test_schema.py::test_sales_agent_schema_exists -x` | No -- Wave 0 |
| DATA-02 | Tables are isolated from public schema | smoke | `pytest tests/test_schema.py::test_schema_isolation -x` | No -- Wave 0 |
| DATA-03 | Firestore documents exist with correct content | integration | `pytest tests/test_firestore.py::test_knowledge_base_seeded -x` | No -- Wave 0 |
| DATA-03 | Test query returns programme details | integration | `pytest tests/test_firestore.py::test_query_programme_details -x` | No -- Wave 0 |
| DATA-04 | Writing to pipeline_logs succeeds | integration | `pytest tests/test_pipeline_logs.py::test_log_event_writes -x` | No -- Wave 0 |
| DATA-04 | Log record is queryable by lead_id | integration | `pytest tests/test_pipeline_logs.py::test_query_by_lead_id -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_data_layer.py -x -v` (unit tests only)
- **Per wave merge:** `pytest tests/ -v` (all tests including integration)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_import_leads.py` -- covers DATA-01 (phone validation unit tests + import integration)
- [ ] `tests/test_schema.py` -- covers DATA-02 (schema existence, table structure, isolation)
- [ ] `tests/test_firestore.py` -- covers DATA-03 (document existence, content query)
- [ ] `tests/test_pipeline_logs.py` -- covers DATA-04 (write + read pipeline logs)
- [ ] `tests/conftest.py` -- shared fixtures (Supabase client config, test CSV data)
- [ ] Framework install: `pip install pytest pytest-asyncio` -- no test framework currently installed
- [ ] `pytest.ini` or `pyproject.toml` -- pytest configuration with asyncio mode

## Sources

### Primary (HIGH confidence)
- [Supabase Custom Schema Docs](https://supabase.com/docs/guides/api/using-custom-schemas) -- schema creation, grants, header patterns
- [PostgREST v14 Schema Docs](https://postgrest.org/en/stable/references/api/schemas.html) -- Accept-Profile / Content-Profile header specification
- [pymupdf4llm API Docs](https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/api.html) -- to_markdown() function signature and parameters
- Existing `backend/logger.py` -- established Supabase REST API pattern with httpx
- Existing `backend/config.py` -- environment variable loading pattern
- Existing `backend/requirements.txt` -- already includes google-cloud-firestore, pymupdf4llm, httpx

### Secondary (MEDIUM confidence)
- [Supabase Self-Hosted Docker Docs](https://supabase.com/docs/guides/self-hosting/docker) -- PGRST_DB_SCHEMAS configuration
- [Google Cloud Firestore Python SDK](https://pypi.org/project/google-cloud-firestore/) -- version 2.22.0 (Jan 2026)
- [gcloud firestore databases create](https://docs.cloud.google.com/sdk/gcloud/reference/firestore/databases/create) -- CLI database creation
- [phonenumbers PyPI](https://pypi.org/project/phonenumbers/) -- Google libphonenumber Python port

### Tertiary (LOW confidence)
- Supabase Docker .env location on VPS #1 -- not verified, must discover during execution

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in requirements.txt except phonenumbers; patterns established by logger.py
- Architecture: HIGH -- custom schema approach verified against PostgREST v14 docs and Supabase custom schema docs; Firestore SDK is well-documented
- Pitfalls: HIGH -- self-hosted schema exposure and GRANT requirements verified against multiple sources; logger.py update requirement identified from code inspection

**Research date:** 2026-03-12
**Valid until:** 2026-04-12 (stable technologies, no fast-moving dependencies)
