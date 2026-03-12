# Technology Stack

**Project:** Cloudboosta AI Sales Agent
**Researched:** 2026-03-12

## Recommended Stack

### Core Framework (Voice Agent Backend)

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Python | 3.12 | Runtime | Already on VPS #1. ADK and google-genai require >=3.9. 3.12 is stable with good async perf. | HIGH |
| FastAPI | 0.135.x | HTTP + WebSocket server | Native WebSocket support via Starlette for Twilio Media Streams. Async-first. Industry standard for AI backends in Python. | HIGH |
| google-genai | latest (GA) | Gemini Live API client | The **unified** Google GenAI SDK. Replaces the deprecated `google-generativeai` package. Provides `client.live.connect()` for real-time audio WebSocket sessions with Gemini. This is the only supported SDK for Gemini Live API. | HIGH |
| google-adk | 1.26.x | Agent framework | Google's Agent Development Kit. Provides agent definition, tool registration, and conversation management. Optimized for Gemini but model-agnostic. Actively maintained (bi-weekly releases). | HIGH |
| uvicorn | 0.34.x | ASGI server | Production server for FastAPI. Use with `--workers` for concurrency on Cloud Run. | HIGH |

### Voice / Telephony

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Twilio Voice + Media Streams | current | Outbound calling + audio streaming | Bidirectional Media Streams over WebSocket. Sends raw mulaw audio at 8kHz to our backend, receives audio back. Project spec requires Twilio and trial account is already active. | HIGH |
| twilio (Python SDK) | 9.x | Twilio API client | REST API for initiating outbound calls, managing recordings, looking up call status. | HIGH |

**Important decision: Media Streams vs ConversationRelay**

Use **Media Streams**, not ConversationRelay. Rationale:
- ConversationRelay handles STT/TTS/LLM orchestration for you -- but we need Gemini Live API's native audio-to-audio streaming, not a text-intermediated pipeline.
- Gemini Live API accepts raw audio and returns raw audio. There is no text step. ConversationRelay's STT->LLM->TTS pipeline would add latency and defeat the purpose.
- Media Streams gives us the raw audio we need to pipe directly into Gemini Live API's WebSocket.
- The tradeoff: we handle barge-in and audio buffering ourselves. Gemini Live API has native barge-in support, so this is manageable.

### Audio Processing

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| audioop-lts | 0.2.x | mulaw <-> PCM conversion | Twilio sends mulaw 8kHz. Gemini expects PCM 16kHz. Need format conversion. `audioop` was removed from Python 3.13 stdlib but `audioop-lts` provides drop-in replacement. On Python 3.12 the stdlib `audioop` still works. | MEDIUM |
| base64 (stdlib) | n/a | Encode/decode Twilio payloads | Twilio Media Streams sends base64-encoded audio. Standard library. | HIGH |

### Database

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Supabase (self-hosted) | running on VPS #1 | PostgreSQL for leads, call_logs, pipeline_logs | Already deployed at supabase.operscale.cloud. Schema isolation via `sales_agent` schema. | HIGH |
| supabase (Python client) | 2.28.x | Backend DB access | Official Python client. Supports all CRUD, RPC, realtime subscriptions. Install via `pip install supabase`. | HIGH |
| Firestore (GCP) | n/a | Knowledge base document store | Stores parsed PDF content (programmes, FAQs, payment details, conversation sequence). ADK tools read from Firestore at runtime. Already in GCP project. | HIGH |
| google-cloud-firestore | 2.x | Firestore Python client | Official client for reading knowledge base documents from Firestore. | HIGH |

### Knowledge Base Processing

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| PyPDF2 or pypdf | 4.x | PDF text extraction | Extract text from the 5 knowledge base PDFs for seeding into Firestore. `pypdf` is the maintained fork. One-time script use. | MEDIUM |

### Orchestration

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| n8n (self-hosted) | running on VPS #1 | Workflow orchestration | Bridges OpenClaw (text) and Cloud Run (voice). Handles lead intake, outreach triggers, call scheduling, post-call branching, monitoring. Already deployed. | HIGH |

### WhatsApp / Text Outreach

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| OpenClaw | installed on VPS #2 | WhatsApp messaging via personal number | Web bridge for WhatsApp. Handles outreach messages and booking conversations. Brain is Gemini API (text mode). Already installed, needs WhatsApp connection. | HIGH |

### Email

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Resend API | current | Transactional email | Outreach emails, payment details, admin notifications. Free tier sufficient for test phase. Called from n8n HTTP Request nodes. | HIGH |

### Frontend (Test Voice UI)

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| React | 18.x | Browser voice UI for testing | Test the voice agent from a browser before connecting Twilio. Lightweight SPA. | MEDIUM |
| Vite | 5.x | Build tool | Fast dev server and build for the React test UI. | MEDIUM |

### Deployment

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Docker | current | Containerization | Cloud Run requires container images. Also useful for local dev via docker-compose. | HIGH |
| Google Cloud Run | current | Voice agent hosting | Serverless containers. Scales to zero (cost control on $0-15 budget). Supports WebSocket connections needed for Twilio Media Streams. Concurrency setting allows multiple simultaneous calls. | HIGH |
| Google Artifact Registry | current | Container image storage | Store Docker images for Cloud Run deployment. Replaces deprecated Container Registry. | HIGH |
| gcloud CLI | current | Deployment commands | Already installed on VPS #1. Used for `gcloud run deploy` and service management. | HIGH |

### Development / Quality

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| python-dotenv | 1.x | Environment variable loading | Load `.env` files in local development. Not needed in Cloud Run (env vars set via console/deploy). | HIGH |
| pydantic | 2.x | Data validation + settings | FastAPI's native validation layer. Use for request/response models and settings management via `BaseSettings`. | HIGH |
| pytest | 8.x | Testing | Unit and integration tests. Standard Python testing. | HIGH |
| httpx | 0.28.x | HTTP client for testing | Async HTTP client. Use with `pytest` for testing FastAPI endpoints. Also useful as async HTTP client in production code. | HIGH |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| AI Model | Gemini Live API (native audio) | OpenAI Realtime API | Project spec mandates Gemini. Single API key already provisioned. Google ADK designed for Gemini. |
| Voice Platform | Twilio Media Streams | Twilio ConversationRelay | ConversationRelay does STT->text->TTS. We need raw audio-to-audio via Gemini Live API. ConversationRelay would add an unnecessary text intermediary. |
| Voice Platform | Twilio Media Streams | Vapi / Retell / Bland.ai | Managed voice AI platforms abstract too much. We need direct Gemini Live API integration. Also adds cost on a $0-15 budget. |
| Agent Framework | Google ADK | LangChain / LangGraph | ADK is purpose-built for Gemini agents. LangChain adds abstraction overhead without benefit when you are already committed to Gemini. |
| Agent Framework | Google ADK | CrewAI / AutoGen | Multi-agent orchestration frameworks. Overkill -- Sarah is a single agent with tools, not a multi-agent system. |
| Web Framework | FastAPI | Flask | Flask lacks native async/WebSocket. FastAPI's async-first design is essential for concurrent WebSocket streams (Twilio + Gemini simultaneously). |
| Web Framework | FastAPI | Django | Too heavy. No WebSocket support without channels. Not suited for real-time audio streaming. |
| Database | Supabase (PostgreSQL) | Firebase Realtime DB | Supabase already deployed. PostgreSQL is better for structured lead/CRM data than Firebase's document model. |
| Knowledge Base | Firestore | Supabase/PostgreSQL | Firestore's document model is natural for PDF-derived content. Separate concern from transactional data. Already in GCP project. |
| Deployment | Cloud Run | AWS Lambda / ECS | Project is GCP-native. Cloud Run supports WebSockets (Lambda does not natively). GCP project already configured. |
| Email | Resend API | SendGrid / Mailgun | Resend has generous free tier, clean API, good deliverability. Simpler than SendGrid for transactional-only use. |
| Python SDK | google-genai (unified) | google-generativeai (deprecated) | The old `google-generativeai` package is officially deprecated. `google-genai` is the replacement and the only SDK supporting Gemini Live API. |

## Critical Version Notes

### Gemini Live API Model Migration
The model `gemini-live-2.5-flash-preview-native-audio-09-2025` is being **deprecated on March 19, 2026**. Migrate to `gemini-live-2.5-flash-native-audio` before that date. The AGENT.md currently references `gemini-2.0-flash-live` which may also need updating -- verify against current API docs during Phase 3.

### Gemini Live API Session Limit
Sessions max out at **10 minutes**. Target call duration is 5-10 minutes (per PROJECT.md), which is right at the boundary. Implement session handoff logic: save conversation context, reconnect if approaching the limit. This is a critical architecture concern.

### Twilio Audio Format
Twilio Media Streams: mulaw 8kHz, base64-encoded. Gemini Live API: PCM 16kHz. The backend MUST handle bidirectional audio transcoding in real-time with minimal latency.

## Installation

```bash
# Core backend
pip install fastapi uvicorn google-genai google-adk google-cloud-firestore supabase twilio pydantic python-dotenv httpx

# PDF processing (for knowledge base seeding script)
pip install pypdf

# Dev dependencies
pip install pytest pytest-asyncio

# Frontend (test UI)
npm create vite@latest frontend -- --template react
cd frontend && npm install
```

## Environment Variables Required

```bash
# Google Cloud / Gemini
GOOGLE_API_KEY=              # Gemini API key (shared across text + voice)
GCP_PROJECT_ID=vision-gridai
GEMINI_LIVE_MODEL=gemini-live-2.5-flash-native-audio

# Twilio
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=+17404943597

# Supabase
SUPABASE_URL=https://supabase.operscale.cloud
SUPABASE_SERVICE_KEY=

# n8n webhooks
N8N_BASE_URL=https://n8n.srv1297445.hstgr.cloud
N8N_WEBHOOK_SECRET=

# OpenClaw
OPENCLAW_API_URL=
OPENCLAW_GATEWAY_TOKEN=

# Admin
ADMIN_EMAIL=akinolaakinrimisi@gmail.com
```

## Sources

- [Gemini Live API overview (Google AI)](https://ai.google.dev/gemini-api/docs/live-api)
- [Gemini Live API on Vertex AI](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/live-api)
- [Google ADK Python (GitHub)](https://github.com/google/adk-python)
- [Google ADK on PyPI](https://pypi.org/project/google-adk/)
- [google-genai SDK (GitHub)](https://github.com/googleapis/python-genai)
- [Twilio Media Streams overview](https://www.twilio.com/docs/voice/media-streams)
- [Twilio Media Streams WebSocket messages](https://www.twilio.com/docs/voice/media-streams/websocket-messages)
- [Twilio ConversationRelay](https://www.twilio.com/en-us/products/conversational-ai/conversationrelay)
- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)
- [supabase-py on PyPI](https://pypi.org/project/supabase/)
- [Supabase Python docs](https://supabase.com/docs/reference/python/introduction)
- [Twilio + OpenAI Realtime API Python tutorial](https://www.twilio.com/en-us/blog/voice-ai-assistant-openai-realtime-api-python) (architecture pattern applicable to Gemini)
