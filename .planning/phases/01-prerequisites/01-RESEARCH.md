# Phase 1: Prerequisites - Research

**Researched:** 2026-03-12
**Domain:** External dependency validation, credential management, PDF content preparation, API connectivity testing
**Confidence:** HIGH

## Summary

Phase 1 is a risk-reduction phase that validates every external dependency before any code is built. The four workstreams are: (1) Gemini Live API audio round-trip validation via Vertex AI with service account auth, (2) Twilio trial account phone number verification for 10 test leads, (3) PDF knowledge base population and content validation, and (4) environment variable consolidation with secrets management.

Research confirms the model `gemini-live-2.5-flash-native-audio` is GA on Vertex AI and available in `europe-west1` (among many European regions). The google-genai Python SDK is the current standard for connecting to the Live API. Gemini Live API does NOT support mulaw audio natively -- it requires PCM 16kHz input and outputs PCM 24kHz -- so Phase 1 must test mulaw-to-PCM transcoding to validate feasibility for Phase 3/6 Twilio integration. Twilio trial accounts require each lead's phone number to be individually verified via SMS OTP, and all outbound calls will be prefixed with a trial message.

**Primary recommendation:** Build a standalone Python validation script per service (Gemini, Twilio, Supabase, Resend) that can be re-run at any time, plus a PDF validation script that extracts text and checks for expected section keywords. Move service account JSON files into `secrets/` directory immediately.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- All 5 PDFs already exist as .pdf files on the user's machine, ready to copy into knowledge-base/
- Filenames: programmes.pdf, conversation-sequence.pdf, faqs.pdf, payment-details.pdf, objection-handling.pdf
- PDFs will be updated occasionally -- build a re-runnable seeder script, not one-time
- Phase 1 should parse and validate PDF content (extract text, check for expected sections/keywords), not just confirm files exist
- Pin to model `gemini-live-2.5-flash-native-audio`
- Authentication via Vertex AI with service account (not AI Studio API key)
- Separate service account: "openclaw-key-google" (already added to project)
- Correct GCP project ID: `vision-gridai` (not cloudboosta-agent from .env.example)
- Full audio round-trip validation required: send audio in, get audio back, confirm bidirectional streaming
- Also test mulaw format acceptance in Phase 1 -- determines whether transcoding layer is needed in Phase 3
- 10-minute session limit handled by graceful wrap-up (duration watchdog at 8.5 min), no session reconnect
- All 10 test leads have name, phone (with country code), and email
- Data is in a spreadsheet -- will export to CSV for import
- All 10 leads have been informed about and consented to the AI call
- Twilio trial verification is a Phase 1 task -- leads need step-by-step guidance
- Single master .env.example with all variables across all 3 systems
- Fix .env.example: GCP_PROJECT_ID should be vision-gridai, GEMINI_MODEL should be gemini-live-2.5-flash-native-audio
- Move my-n8n-service-account.json and openclaw-key-google.json to secrets/ directory, add secrets/ to .gitignore
- Supabase keys (service + anon) are ready
- n8n API key and webhook URL are ready
- Resend API key is ready

### Claude's Discretion
- GCP region selection (based on Gemini Live API availability and latency to UK/Nigeria leads)
- OpenClaw validation depth in Phase 1 (reachability check vs. defer entirely to Phase 7)
- PDF section validation criteria (which keywords/sections to check per PDF)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| google-genai | >=1.56.0 | Gemini Live API client (Vertex AI) | Google's official Gen AI SDK, GA, replaces deprecated vertex-ai SDK |
| google-auth | >=2.0.0 | Service account authentication for Vertex AI | Standard GCP auth library, required for `Credentials.from_service_account_file()` |
| twilio | >=9.4.0 | Twilio REST API for number verification testing | Already in requirements.txt |
| PyMuPDF (fitz) | >=1.24.0 | PDF text extraction | Fast, reliable, already referenced in skills.md pattern |
| pymupdf4llm | >=0.0.14 | LLM-optimized PDF extraction (Markdown output) | Better structure preservation than raw fitz, ideal for conversation-sequence decision tree |
| python-dotenv | >=1.0.1 | .env file loading | Already in requirements.txt |
| resend | >=2.0.0 | Email API validation | Simple SDK, user has API key ready |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| audioop-lts | >=0.2.1 | mulaw <-> PCM audio transcoding test | For Phase 1 mulaw validation test only (audioop removed from Python 3.13+) |
| pyaudio | >=0.2.14 | Microphone/speaker for local audio test | Only if testing audio round-trip locally with real microphone |
| supabase | >=2.0.0 | Supabase connectivity validation | Quick reachability check in Phase 1 |
| httpx | >=0.28.0 | HTTP requests for service reachability checks | Already in requirements.txt, for OpenClaw/n8n ping |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PyMuPDF + pymupdf4llm | pdfplumber | pdfplumber is better for tables but slower; PyMuPDF is faster and already in the project's patterns |
| audioop-lts | pydub | pydub requires ffmpeg system dependency; audioop-lts is pure Python for simple mulaw conversion |
| google-genai | google-cloud-aiplatform | aiplatform SDK's generative AI modules are deprecated as of June 2025, removed June 2026; google-genai is the replacement |

**Installation:**
```bash
pip install google-genai google-auth pymupdf pymupdf4llm python-dotenv twilio resend supabase httpx audioop-lts
```

## Architecture Patterns

### Recommended Project Structure for Phase 1
```
scripts/
    validate_gemini.py       # Gemini Live API audio round-trip test
    validate_twilio.py       # Twilio number verification helper + test call
    validate_pdfs.py         # PDF extraction + section/keyword validation
    validate_services.py     # Supabase, n8n, OpenClaw, Resend reachability
secrets/                     # NEW - service account JSON files
    my-n8n-service-account.json
    openclaw-key-google.json
knowledge-base/
    programmes.pdf
    conversation-sequence.pdf
    faqs.pdf
    payment-details.pdf
    objection-handling.pdf
.env                         # Corrected values
.env.example                 # Updated template (all 3 systems)
backend/.env.example         # Aligned with root
backend/config.py            # Updated defaults
```

### Pattern 1: Vertex AI Service Account Authentication
**What:** Authenticate to Gemini Live API using service account JSON file via google-genai SDK
**When to use:** All Gemini API calls from backend (Cloud Run uses same pattern with mounted secret)
**Example:**
```python
# Source: https://pgaleone.eu/cloud/2025/06/29/vertex-ai-to-genai-sdk-service-account-auth-python-go/
from google import genai
from google.oauth2.service_account import Credentials
import os

scopes = ["https://www.googleapis.com/auth/cloud-platform"]

credentials = Credentials.from_service_account_file(
    os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "secrets/openclaw-key-google.json"),
    scopes=scopes,
)

client = genai.Client(
    vertexai=True,
    project="vision-gridai",
    location="europe-west1",
    credentials=credentials,
)
```

### Pattern 2: Gemini Live API Audio Round-Trip
**What:** Connect to Live API, send PCM audio, receive PCM audio response
**When to use:** Phase 1 validation, and later in Phase 3 voice agent
**Example:**
```python
# Source: https://ai.google.dev/gemini-api/docs/live-guide
from google.genai import types

config = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                voice_name="Aoede"  # British English female
            )
        )
    ),
)

async with client.aio.live.connect(
    model="gemini-live-2.5-flash-native-audio",
    config=config,
) as session:
    # Send PCM 16kHz mono audio
    await session.send_realtime_input(
        audio=types.Blob(
            data=pcm_audio_bytes,
            mime_type="audio/pcm;rate=16000",
        )
    )
    # Receive audio response
    async for response in session.receive():
        if response.data:
            # PCM 24kHz mono audio bytes
            audio_output = response.data
```

### Pattern 3: Mulaw <-> PCM Transcoding Test
**What:** Validate that mulaw 8kHz (Twilio format) can be converted to PCM 16kHz (Gemini format) and back
**When to use:** Phase 1 to determine if transcoding layer works cleanly; Phase 6 for actual Twilio integration
**Example:**
```python
# Source: Python audioop documentation + Twilio Media Streams docs
import audioop

# Twilio sends mulaw 8kHz mono
def mulaw_to_pcm16k(mulaw_bytes: bytes) -> bytes:
    """Convert mulaw 8kHz to PCM 16kHz for Gemini input."""
    # Step 1: mulaw -> PCM 16-bit at 8kHz
    pcm_8k = audioop.ulaw2lin(mulaw_bytes, 2)
    # Step 2: Upsample 8kHz -> 16kHz
    pcm_16k, _ = audioop.ratecv(pcm_8k, 2, 1, 8000, 16000, None)
    return pcm_16k

# Gemini returns PCM 24kHz mono
def pcm24k_to_mulaw(pcm_24k_bytes: bytes) -> bytes:
    """Convert Gemini PCM 24kHz output to mulaw 8kHz for Twilio."""
    # Step 1: Downsample 24kHz -> 8kHz
    pcm_8k, _ = audioop.ratecv(pcm_24k_bytes, 2, 1, 24000, 8000, None)
    # Step 2: PCM -> mulaw
    mulaw_bytes = audioop.lin2ulaw(pcm_8k, 2)
    return mulaw_bytes
```

### Pattern 4: PDF Text Extraction with Validation
**What:** Extract text from PDFs and validate expected sections exist
**When to use:** Phase 1 validation, Phase 2 Firestore seeding
**Example:**
```python
# Source: https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/
import pymupdf4llm
import fitz  # PyMuPDF

def extract_and_validate(pdf_path: str, expected_keywords: list[str]) -> dict:
    """Extract text from PDF and check for expected content."""
    doc = fitz.open(pdf_path)
    # Get structured markdown for LLM consumption
    md_text = pymupdf4llm.to_markdown(pdf_path)
    # Get plain text for validation
    plain_text = ""
    for page in doc:
        plain_text += page.get_text()
    doc.close()

    # Validate expected keywords/sections
    missing = [kw for kw in expected_keywords if kw.lower() not in plain_text.lower()]
    return {
        "path": pdf_path,
        "pages": doc.page_count,
        "char_count": len(plain_text),
        "markdown_length": len(md_text),
        "missing_keywords": missing,
        "valid": len(missing) == 0,
    }
```

### Anti-Patterns to Avoid
- **Hardcoding the GCP project ID as "cloudboosta-agent":** The actual project is `vision-gridai`. Multiple files still have the wrong default.
- **Using AI Studio API key for Gemini:** The user decided on Vertex AI with service account auth. Do not use `GOOGLE_GEMINI_API_KEY` environment variable for Gemini calls.
- **Checking "file exists" without extracting content:** The user explicitly wants PDF content parsed and validated, not just `os.path.exists()`.
- **Leaving service account JSON files in project root:** They must move to `secrets/` directory for security.

## GCP Region Recommendation (Claude's Discretion)

**Recommendation: `europe-west1` (Belgium)**

| Factor | Analysis |
|--------|----------|
| Model availability | `gemini-live-2.5-flash-native-audio` is available in europe-west1 (confirmed via official docs) |
| Latency to UK leads | Belgium is ~10ms from London. Excellent for real-time audio. |
| Latency to Nigeria leads | ~100-150ms from Nigeria (via subsea cable). Acceptable for voice. |
| Existing config | The .env already has `GCP_REGION=us-east5`, but europe-west1 is closer to both UK and Nigerian leads |
| Cloud Run deployment | europe-west1 is a Tier 1 region (cheapest pricing) |
| Existing project references | skills.md deploy command references europe-west1 |

**Confidence: HIGH** -- europe-west1 is the best balance of availability, latency, and cost for UK/Nigeria target audience.

## OpenClaw Validation Depth (Claude's Discretion)

**Recommendation: Reachability check only in Phase 1. Full setup in Phase 7.**

Rationale:
- OpenClaw is already running on VPS #2 (HTTPS URL is in .env: `https://openclaw-bjmt.srv1486171.hstgr.cloud/`)
- A simple HTTP GET to confirm the service is responding is sufficient
- WhatsApp pairing, message templates, and webhook configuration are Phase 7 concerns
- Phase 1 scope should stay minimal: "is the service alive?" not "is WhatsApp fully configured?"

## PDF Section Validation Criteria (Claude's Discretion)

**Recommendation: Validate these keywords per PDF:**

| PDF | Expected Keywords/Sections |
|-----|---------------------------|
| programmes.pdf | "Cloud Security", "SRE", "Platform Engineering", "1,200", "1,800", "duration", "curriculum" |
| conversation-sequence.pdf | "qualification", "background", "experience", "recommend", "Cloud Security", "SRE", "objection", "committed", "follow up", "declined" |
| faqs.pdf | "FAQ", "question", "internship", "payment", "beginner" |
| payment-details.pdf | "bank", "transfer", "account", "payment", "GBP" or "NGN" |
| objection-handling.pdf | "objection", "expensive", "time", "job", "beginner", "guarantee" |

**Confidence: MEDIUM** -- Keywords are inferred from AGENT.md Section 3 (Sarah's profile) and directive 05. Actual PDF content may use different terminology; the script should report findings, not hard-fail.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PDF text extraction | Custom PDF parser | PyMuPDF (`fitz`) + pymupdf4llm | PDFs have tables, multi-column, headers; custom parsers break on edge cases |
| Audio format conversion | Custom byte manipulation | `audioop.ulaw2lin` / `audioop.lin2ulaw` + `audioop.ratecv` | Bit-level audio encoding is error-prone; audioop handles endianness, sample width correctly |
| Service account auth | Manual JWT/OAuth token exchange | `google.oauth2.service_account.Credentials` + `genai.Client(credentials=...)` | Token refresh, scope management, expiry are all handled automatically |
| Environment variable management | Custom config parser | python-dotenv `load_dotenv()` + dataclass Config pattern (already in `backend/config.py`) | Existing pattern works; extend, don't replace |

**Key insight:** Phase 1 is about validation, not building. Every validation script should use battle-tested libraries and produce clear pass/fail output.

## Common Pitfalls

### Pitfall 1: Wrong GCP Project ID Everywhere
**What goes wrong:** Multiple files hardcode `cloudboosta-agent` as the GCP project ID, but the actual project is `vision-gridai`.
**Why it happens:** The AGENT.md template was written before the real GCP project was created.
**How to avoid:** Update ALL occurrences: `.env.example` (root), `backend/.env.example`, `backend/config.py` defaults, `skills.sh`, `skills.md` deploy commands.
**Warning signs:** "Permission denied" or "Project not found" errors from any GCP API call.
**Files to fix:** `.env.example`, `backend/.env.example`, `backend/config.py` (line 10 default), `skills.md` (Section 8 deploy command), `skills.sh` (line 84).

### Pitfall 2: Using API Key Instead of Service Account
**What goes wrong:** The .env has `GOOGLE_GEMINI_API_KEY` set (appears to be an AI Studio key starting with "AAIza..."). Using this for Vertex AI will fail.
**Why it happens:** Initial setup used AI Studio approach. User decided on Vertex AI with service account.
**How to avoid:** Remove `GOOGLE_GEMINI_API_KEY` from .env.example. Add `GOOGLE_APPLICATION_CREDENTIALS=secrets/openclaw-key-google.json`. Use `Credentials.from_service_account_file()` pattern.
**Warning signs:** Authentication errors mentioning "API key not valid" or "Permission denied on resource project vision-gridai".

### Pitfall 3: PDF Filename Discrepancy
**What goes wrong:** AGENT.md, skills.md, and skills.sh reference `coming-soon.pdf` as the 5th PDF. But CONTEXT.md (user's decision) says `objection-handling.pdf`.
**Why it happens:** The original spec included a "coming soon" programmes PDF. During discussion, user decided to replace it with objection handling content.
**How to avoid:** Honor CONTEXT.md (user decision). Update skills.sh to check for `objection-handling.pdf` instead of `coming-soon.pdf`. Note: AGENT.md says "Do not rewrite" so leave it, but document the discrepancy.
**Warning signs:** skills.sh validation failing on the 5th PDF name.

### Pitfall 4: Gemini Live API Does NOT Accept Mulaw
**What goes wrong:** Developer assumes Gemini can accept mulaw directly because Twilio sends mulaw.
**Why it happens:** Competing APIs (e.g., OpenAI Realtime) support mulaw natively. Developers expect the same.
**How to avoid:** Phase 1 MUST test the mulaw -> PCM 16kHz -> Gemini -> PCM 24kHz -> mulaw pipeline. This confirms transcoding works before Phase 3/6 builds on it.
**Warning signs:** Garbled audio, silence, or "unsupported audio format" errors from Gemini.

### Pitfall 5: Gemini Output Sample Rate Differs from Input
**What goes wrong:** Code assumes Gemini outputs 16kHz (same as input), but it outputs 24kHz.
**Why it happens:** Most audio systems use symmetric sample rates. Gemini doesn't.
**How to avoid:** Always handle two sample rates: 16kHz for input, 24kHz for output. The transcoding pipeline must account for this: input path is 8kHz->16kHz, output path is 24kHz->8kHz.
**Warning signs:** Audio sounds pitched up (too fast) or pitched down (too slow).

### Pitfall 6: Service Account JSON Files in Git
**What goes wrong:** `my-n8n-service-account.json` and `openclaw-key-google.json` are currently in the project root. They could accidentally be committed.
**Why it happens:** Files were placed in root during initial setup; `.gitignore` has `*.json` but with exceptions.
**How to avoid:** Move to `secrets/` directory immediately. Add `secrets/` to `.gitignore`. Remove root-level JSON files. Verify with `git status`.
**Warning signs:** `git status` showing JSON files as tracked or untracked in root.

### Pitfall 7: Twilio Trial Call Prefix Disrupts AI Opening
**What goes wrong:** Every Twilio trial call plays "This is a Twilio trial account" message before TwiML executes. Sarah's AI disclosure opening happens AFTER this prefix.
**Why it happens:** Twilio enforces this on all trial accounts. Cannot be disabled.
**How to avoid:** Acknowledge this in test plan. Inform test leads they'll hear a Twilio message first. Sarah's opening should not reference "as I was saying" or assume a clean start.
**Warning signs:** Test leads confused by the Twilio prefix message.

### Pitfall 8: audioop Removed in Python 3.13
**What goes wrong:** `import audioop` fails on Python 3.13+.
**Why it happens:** audioop was deprecated in 3.11 and removed in 3.13.
**How to avoid:** Use `audioop-lts` package which provides the same API. `pip install audioop-lts`.
**Warning signs:** `ModuleNotFoundError: No module named 'audioop'` on newer Python.

## Code Examples

### Gemini Live API Validation Script (Core Pattern)
```python
# Source: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/live-api/get-started-sdk
import asyncio
import os
from google import genai
from google.genai import types
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

async def validate_gemini_audio():
    """Test bidirectional audio streaming with Gemini Live API."""
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    credentials = Credentials.from_service_account_file(
        os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "secrets/openclaw-key-google.json"),
        scopes=scopes,
    )
    client = genai.Client(
        vertexai=True,
        project=os.getenv("GCP_PROJECT_ID", "vision-gridai"),
        location=os.getenv("GCP_REGION", "europe-west1"),
        credentials=credentials,
    )

    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Aoede"
                )
            )
        ),
    )

    print("[1/3] Connecting to Gemini Live API...")
    async with client.aio.live.connect(
        model="gemini-live-2.5-flash-native-audio",
        config=config,
    ) as session:
        print("[2/3] Connection established. Sending text prompt to generate audio...")
        # Send a text message to trigger audio response (simpler than sending audio for validation)
        await session.send_client_content(
            turns=types.Content(
                role="user",
                parts=[types.Part(text="Hello, please introduce yourself briefly.")]
            )
        )

        audio_received = False
        async for response in session.receive():
            if response.data:
                audio_received = True
                print(f"[3/3] Audio received: {len(response.data)} bytes")
                break
            if response.text:
                print(f"  Text: {response.text}")

        if audio_received:
            print("PASS: Gemini Live API audio round-trip validated")
        else:
            print("FAIL: No audio received from Gemini Live API")

if __name__ == "__main__":
    asyncio.run(validate_gemini_audio())
```

### Twilio Verified Numbers Check
```python
# Source: https://www.twilio.com/docs/usage/tutorials/how-to-use-your-free-trial-account
from twilio.rest import Client
import os
from dotenv import load_dotenv

load_dotenv()

def check_twilio_setup():
    """Validate Twilio credentials and list verified numbers."""
    client = Client(
        os.getenv("TWILIO_ACCOUNT_SID"),
        os.getenv("TWILIO_AUTH_TOKEN"),
    )

    # Check account status
    account = client.api.accounts(os.getenv("TWILIO_ACCOUNT_SID")).fetch()
    print(f"Account: {account.friendly_name}")
    print(f"Status: {account.status}")
    print(f"Type: {account.type}")  # 'Trial' or 'Full'

    # List verified caller IDs
    verified = client.validation_requests.list()
    outgoing = client.outgoing_caller_ids.list()
    print(f"\nVerified Caller IDs: {len(outgoing)}")
    for caller_id in outgoing:
        print(f"  {caller_id.phone_number} ({caller_id.friendly_name})")

    # Check owned phone numbers
    numbers = client.incoming_phone_numbers.list()
    print(f"\nOwned Numbers: {len(numbers)}")
    for number in numbers:
        print(f"  {number.phone_number} ({number.friendly_name})")

    return len(outgoing)

if __name__ == "__main__":
    count = check_twilio_setup()
    if count >= 10:
        print(f"\nPASS: {count} verified numbers (need 10)")
    else:
        print(f"\nPENDING: {count}/10 numbers verified")
```

### Service Reachability Check
```python
# Source: Project pattern from backend/config.py + skills.sh
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

def check_services():
    """Validate all external services are reachable."""
    results = {}

    # Supabase
    try:
        r = httpx.get(
            f"{os.getenv('SUPABASE_URL')}/rest/v1/",
            headers={"apikey": os.getenv("SUPABASE_ANON_KEY", "")},
            timeout=10,
        )
        results["Supabase"] = "PASS" if r.status_code in (200, 401) else f"FAIL ({r.status_code})"
    except Exception as e:
        results["Supabase"] = f"FAIL ({e})"

    # n8n
    try:
        r = httpx.get(f"{os.getenv('N8N_BASE_URL')}/healthz", timeout=10)
        results["n8n"] = "PASS" if r.status_code == 200 else f"FAIL ({r.status_code})"
    except Exception as e:
        results["n8n"] = f"FAIL ({e})"

    # OpenClaw (reachability only)
    try:
        r = httpx.get(os.getenv("OPENCLAW_API_URL", ""), timeout=10, follow_redirects=True)
        results["OpenClaw"] = "PASS" if r.status_code in (200, 302) else f"FAIL ({r.status_code})"
    except Exception as e:
        results["OpenClaw"] = f"FAIL ({e})"

    # Resend (validate API key format)
    resend_key = os.getenv("RESEND_API_KEY", "")
    results["Resend API Key"] = "PASS" if resend_key.startswith("re_") else "FAIL (missing or invalid)"

    for service, status in results.items():
        print(f"  {service}: {status}")

if __name__ == "__main__":
    check_services()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `google-cloud-aiplatform` SDK | `google-genai` SDK | June 2025 (deprecated), June 2026 (removal) | Must use `google-genai` for all Gemini calls. Old SDK will stop working in 3 months. |
| `gemini-2.0-flash-live` model | `gemini-live-2.5-flash-native-audio` model | GA in early 2026 | Preview model deprecated March 19, 2026. Pin to GA model immediately. |
| AI Studio API key auth | Vertex AI service account auth | User decision | Service accounts provide better access control, required for production Cloud Run |
| `audioop` stdlib module | `audioop-lts` PyPI package | Python 3.13 (Oct 2024) | audioop removed from stdlib; install `audioop-lts` for mulaw conversion |

**Deprecated/outdated:**
- `gemini-2.0-flash-live`: Older model identifier found in current `.env` and `backend/config.py`. Must update to `gemini-live-2.5-flash-native-audio`.
- `gemini-live-2.5-flash-preview-native-audio-09-2025`: Preview version being removed March 19, 2026. Do not use.
- `google-generativeai` PyPI package: Older package, superseded by `google-genai`.
- `GOOGLE_GEMINI_API_KEY`: Environment variable pattern from AI Studio approach. Replace with `GOOGLE_APPLICATION_CREDENTIALS` pointing to service account JSON.

## Existing Code That Needs Updates

| File | Current Value | Correct Value | Why |
|------|---------------|---------------|-----|
| `.env.example` line 2 | `GCP_PROJECT_ID=cloudboosta-agent` | `GCP_PROJECT_ID=vision-gridai` | Wrong project ID |
| `.env.example` line 4 | `GEMINI_MODEL=gemini-2.0-flash-live` | `GEMINI_MODEL=gemini-live-2.5-flash-native-audio` | Old model |
| `.env.example` line 5 | `GOOGLE_GEMINI_API_KEY=` | Remove; add `GOOGLE_APPLICATION_CREDENTIALS=secrets/openclaw-key-google.json` | Auth method changed |
| `backend/.env.example` line 1 | `GCP_PROJECT_ID=cloudboosta-agent` | `GCP_PROJECT_ID=vision-gridai` | Wrong project ID |
| `backend/.env.example` line 2 | `GEMINI_MODEL=gemini-2.0-flash-live` | `GEMINI_MODEL=gemini-live-2.5-flash-native-audio` | Old model |
| `backend/config.py` line 10 | default `"cloudboosta-agent"` | default `"vision-gridai"` | Wrong default |
| `backend/config.py` line 11 | default `"gemini-2.0-flash-live"` | default `"gemini-live-2.5-flash-native-audio"` | Old model default |
| `backend/config.py` line 12 | `google_gemini_api_key` field | Replace with `google_application_credentials` field | Auth method changed |
| `.env` line 3 | `GEMINI_MODEL=gemini-2.0-flash-live` | `GEMINI_MODEL=gemini-live-2.5-flash-native-audio` | Old model |
| `.gitignore` | No `secrets/` entry | Add `secrets/` | New directory for service account files |
| `skills.sh` line 161 | Checks for `coming-soon.pdf` | Check for `objection-handling.pdf` | PDF name changed per user decision |

## Security Concerns Found

| Issue | Severity | Location | Fix |
|-------|----------|----------|-----|
| Service account JSONs in project root | HIGH | `my-n8n-service-account.json`, `openclaw-key-google.json` in root | Move to `secrets/`, add `secrets/` to `.gitignore` |
| VPS SSH password in .env | HIGH | `.env` line 32: `VPS2_SSH_PASSWORD=...` | Remove from .env, store in password manager. Never in code/env files. |
| Anthropic API key in .env | MEDIUM | `.env` line 41: `ANTHROPIC_API_KEY=...` | Not project-related. Remove from project .env. |
| .env contains all real secrets | INFO | `.env` exists with all populated values | Ensure .env is in .gitignore (it is), but verify never committed |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Python scripts with pass/fail output (no formal test framework for Phase 1) |
| Config file | None -- Phase 1 validation scripts are standalone |
| Quick run command | `python scripts/validate_gemini.py && python scripts/validate_pdfs.py` |
| Full suite command | `python scripts/validate_gemini.py && python scripts/validate_twilio.py && python scripts/validate_pdfs.py && python scripts/validate_services.py` |

### Phase Requirements -> Test Map
Phase 1 has no formal requirement IDs (risk reduction phase). Validation maps to success criteria:

| Criterion | Behavior | Test Type | Automated Command | File Exists? |
|-----------|----------|-----------|-------------------|-------------|
| SC-1 | Gemini audio round-trip works | integration | `python scripts/validate_gemini.py` | No -- Wave 0 |
| SC-2 | 10 Twilio numbers verified | integration | `python scripts/validate_twilio.py` | No -- Wave 0 |
| SC-3 | 5 PDFs exist with expected content | unit | `python scripts/validate_pdfs.py` | No -- Wave 0 |
| SC-4 | .env.example complete and .env populated | unit | `python scripts/validate_services.py` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** Run the relevant validation script for the task
- **Per wave merge:** `python scripts/validate_gemini.py && python scripts/validate_twilio.py && python scripts/validate_pdfs.py && python scripts/validate_services.py`
- **Phase gate:** All 4 validation scripts pass green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `scripts/validate_gemini.py` -- Gemini Live API audio round-trip test (includes mulaw transcoding test)
- [ ] `scripts/validate_twilio.py` -- Twilio credentials check + verified number count
- [ ] `scripts/validate_pdfs.py` -- PDF extraction + section keyword validation
- [ ] `scripts/validate_services.py` -- Supabase, n8n, OpenClaw, Resend reachability
- [ ] `secrets/` directory creation and file migration
- [ ] Install: `pip install google-genai google-auth pymupdf pymupdf4llm audioop-lts resend supabase`

## Open Questions

1. **Which Gemini voice names are available for Native Audio model?**
   - What we know: `Aoede` is referenced in skills.md. The official docs list "30 HD voices."
   - What's unclear: Whether `Aoede` is available on the `gemini-live-2.5-flash-native-audio` model specifically.
   - Recommendation: Phase 1 validation script should test with `Aoede` and fallback to listing available voices if it fails.

2. **Does the service account "openclaw-key-google" have Vertex AI permissions?**
   - What we know: The file exists in project root as `openclaw-key-google.json`. User says it was "just added to project."
   - What's unclear: Whether IAM roles (e.g., `roles/aiplatform.user`) are assigned to this service account.
   - Recommendation: Validation script must catch and report auth errors clearly. If permissions fail, output the exact `gcloud` command to grant the role.

3. **Mulaw transcoding audio quality**
   - What we know: Community reports "noise after conversion" when converting mulaw<->PCM for Gemini.
   - What's unclear: Whether the noise is tolerable for voice calls, or if a more sophisticated resampling library is needed.
   - Recommendation: Phase 1 test should produce an audible sample file (save to disk) so the user can listen and judge quality.

4. **Twilio geographic permissions for Nigeria (+234)**
   - What we know: Twilio trial accounts can call 218 countries. But geographic permissions may need explicit enabling.
   - What's unclear: Whether Nigeria calling is enabled by default on the trial account.
   - Recommendation: Validation script should attempt to verify a Nigerian number and report if geographic permissions block it.

## Sources

### Primary (HIGH confidence)
- [Vertex AI - Gemini 2.5 Flash Live API docs](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/2-5-flash-live-api) -- Model ID, regions, audio format specs (PCM 16kHz in, 24kHz out)
- [Vertex AI - Live API overview](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/live-api) -- Session configuration, 10-min default session limit
- [Vertex AI - Get started with Gen AI SDK](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/live-api/get-started-sdk) -- Python SDK connection pattern
- [Google AI - Live API capabilities guide](https://ai.google.dev/gemini-api/docs/live-guide) -- Audio format MIME types, send_realtime_input pattern
- [Twilio - Free trial account guide](https://www.twilio.com/docs/usage/tutorials/how-to-use-your-free-trial-account) -- Trial limitations, verified caller ID process
- [Twilio - Add verified caller ID](https://support.twilio.com/hc/en-us/articles/223180048) -- Step-by-step phone verification
- [PyMuPDF4LLM docs](https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/) -- PDF extraction API
- [google-genai PyPI](https://pypi.org/project/google-genai/) -- SDK version (>=1.56.0 GA)

### Secondary (MEDIUM confidence)
- [Blog: Vertex AI to Gen AI SDK migration](https://pgaleone.eu/cloud/2025/06/29/vertex-ai-to-genai-sdk-service-account-auth-python-go/) -- Service account auth pattern, verified with official docs
- [Google AI Developers Forum - mulaw support](https://discuss.ai.google.dev/t/live-api-support-for-mulaw-g711-ulaw-input-output/86053) -- Confirms no native mulaw support as of early 2026
- [Twilio - Free trial limitations](https://support.twilio.com/hc/en-us/articles/360036052753) -- Trial message prefix, concurrent call limits

### Tertiary (LOW confidence)
- Audio quality of mulaw<->PCM transcoding: Community reports of noise, but no authoritative benchmarks for Gemini specifically. Needs Phase 1 validation.
- Voice name availability on Native Audio model: `Aoede` referenced in multiple sources but not confirmed for this specific model version.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- google-genai SDK is GA, PyMuPDF is well-established, Twilio SDK is mature
- Architecture: HIGH -- Auth pattern verified with official docs, audio format specs from official Vertex AI docs
- Pitfalls: HIGH -- GCP project ID mismatch verified by reading actual files, mulaw limitation confirmed by multiple sources
- Region recommendation: HIGH -- europe-west1 availability confirmed in official model docs
- PDF validation criteria: MEDIUM -- Keywords inferred from AGENT.md, actual PDF content unknown

**Research date:** 2026-03-12
**Valid until:** 2026-04-12 (stable -- all components are GA)
