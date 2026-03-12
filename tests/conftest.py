"""Shared test fixtures for Cloudboosta Voice Agent tests.

Provides mock Firestore, Supabase, ADK, and genai fixtures used across
test_knowledge_loader.py, test_system_instruction.py, test_tools.py,
test_agent.py, and test_call_manager.py.
"""

import sys
import types as builtin_types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add backend directory to sys.path so imports work without package install
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))


# ---- Mock google.adk and google.genai modules ----
# These must be registered before any backend module that imports them at
# module level (e.g., agent.py imports Agent from google.adk.agents).


class _MockAgent:
    """Lightweight mock of google.adk.agents.Agent that stores constructor args."""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class _MockContent:
    """Lightweight mock of google.genai.types.Content."""

    def __init__(self, *, role: str = "", parts: list | None = None):
        self.role = role
        self.parts = parts or []


class _MockPart:
    """Lightweight mock of google.genai.types.Part."""

    def __init__(self, *, text: str = "", inline_data=None):
        self.text = text
        self.inline_data = inline_data


def _setup_mock_google_modules():
    """Register mock google.adk and google.genai module hierarchy in sys.modules."""
    # Only install mocks if the real packages are not available
    if "google.adk" in sys.modules or "google.genai" in sys.modules:
        return

    # google namespace package
    google_mod = sys.modules.get("google")
    if google_mod is None:
        google_mod = builtin_types.ModuleType("google")
        google_mod.__path__ = []
        sys.modules["google"] = google_mod

    # google.adk
    if "google.adk" not in sys.modules:
        adk_mod = builtin_types.ModuleType("google.adk")
        adk_mod.__path__ = []
        sys.modules["google.adk"] = adk_mod

    # google.adk.agents
    if "google.adk.agents" not in sys.modules:
        agents_mod = builtin_types.ModuleType("google.adk.agents")
        agents_mod.Agent = _MockAgent
        sys.modules["google.adk.agents"] = agents_mod

    # google.adk.runners
    if "google.adk.runners" not in sys.modules:
        runners_mod = builtin_types.ModuleType("google.adk.runners")
        runners_mod.Runner = MagicMock
        sys.modules["google.adk.runners"] = runners_mod

    # google.adk.agents.run_config
    if "google.adk.agents.run_config" not in sys.modules:
        run_config_mod = builtin_types.ModuleType("google.adk.agents.run_config")
        run_config_mod.RunConfig = MagicMock
        run_config_mod.StreamingMode = MagicMock()
        sys.modules["google.adk.agents.run_config"] = run_config_mod

    # google.adk.agents.live_request_queue
    if "google.adk.agents.live_request_queue" not in sys.modules:
        lrq_mod = builtin_types.ModuleType("google.adk.agents.live_request_queue")
        lrq_mod.LiveRequestQueue = MagicMock
        sys.modules["google.adk.agents.live_request_queue"] = lrq_mod

    # google.adk.sessions
    if "google.adk.sessions" not in sys.modules:
        sessions_mod = builtin_types.ModuleType("google.adk.sessions")
        sessions_mod.InMemorySessionService = MagicMock
        sys.modules["google.adk.sessions"] = sessions_mod

    # google.adk.tools
    if "google.adk.tools" not in sys.modules:
        tools_mod = builtin_types.ModuleType("google.adk.tools")
        tools_mod.ToolContext = MagicMock
        sys.modules["google.adk.tools"] = tools_mod

    # google.genai
    if "google.genai" not in sys.modules:
        genai_mod = builtin_types.ModuleType("google.genai")
        genai_mod.__path__ = []
        sys.modules["google.genai"] = genai_mod

    # google.genai.types
    if "google.genai.types" not in sys.modules:
        genai_types_mod = builtin_types.ModuleType("google.genai.types")
        genai_types_mod.Content = _MockContent
        genai_types_mod.Part = _MockPart
        genai_types_mod.Blob = MagicMock
        genai_types_mod.SpeechConfig = MagicMock
        genai_types_mod.VoiceConfig = MagicMock
        genai_types_mod.PrebuiltVoiceConfig = MagicMock
        genai_types_mod.AudioTranscriptionConfig = MagicMock
        sys.modules["google.genai.types"] = genai_types_mod


# Execute mock registration at import time (before any test module imports backend code)
_setup_mock_google_modules()


# ---- Firestore mock fixtures ----

KB_DOC_IDS = [
    "programmes",
    "conversation-sequence",
    "faqs",
    "payment-details",
    "objection-handling",
]

MOCK_KB_CONTENT = {
    "programmes": (
        "## Cloud Security Programme\n"
        "Duration: 12 weeks\n"
        "Price: GBP 1,200\n"
        "Focus: AWS/Azure security, IAM, compliance, incident response.\n"
        "Career path: Cloud Security Engineer, Security Analyst.\n"
        "Average UK salary: GBP 45,000 - GBP 75,000.\n\n"
        "## SRE & Platform Engineering Programme\n"
        "Duration: 16 weeks\n"
        "Price: GBP 1,800\n"
        "Focus: Kubernetes, Terraform, CI/CD, observability, SRE practices.\n"
        "Career path: Site Reliability Engineer, Platform Engineer, DevOps Engineer.\n"
        "Average UK salary: GBP 50,000 - GBP 95,000."
    ),
    "conversation-sequence": (
        "## Qualification Decision Tree\n"
        "1. Greet and disclose AI nature\n"
        "2. Ask about current role\n"
        "3. Assess experience_level (junior/mid/senior/career-changer)\n"
        "4. Explore cloud_background\n"
        "5. Understand motivation\n"
        "6. Recommend programme based on qualification\n"
        "7. Handle objections if raised\n"
        "8. Commitment ask\n"
        "9. Close call with next steps"
    ),
    "faqs": (
        "## Frequently Asked Questions\n"
        "Q: Is the training online or in-person?\n"
        "A: Fully online with live instructor-led sessions.\n"
        "Q: What certifications do I get?\n"
        "A: Industry-recognized cloud certifications (AWS/Azure/GCP).\n"
        "Q: Can I pay in installments?\n"
        "A: Yes, flexible payment plans are available."
    ),
    "payment-details": (
        "## Payment Information\n"
        "Cloud Security: GBP 1,200 (full) or 3 x GBP 420\n"
        "SRE & Platform Engineering: GBP 1,800 (full) or 3 x GBP 630\n"
        "Payment methods: Bank transfer, card payment\n"
        "30-day money-back guarantee"
    ),
    "objection-handling": (
        "## Objection Handling Guide\n"
        "### Price objection\n"
        "First angle: ROI -- cloud engineers earn GBP 40,000-95,000+. "
        "The programme pays for itself within the first month of employment.\n"
        "Second angle: Payment flexibility -- installment plans available.\n"
        "### Time objection\n"
        "First angle: Flexible schedule, evenings and weekends available.\n"
        "Second angle: Career investment -- 12-16 weeks vs years of self-study.\n"
        "### Salary figures\n"
        "Cloud engineers in the UK typically earn GBP 30,000-50,000 starting. "
        "With DevOps/SRE that goes to GBP 40,000-95,000+."
    ),
}


def _make_mock_doc(doc_id: str, content: str):
    """Create a mock Firestore document snapshot."""
    doc = MagicMock()
    doc.exists = True
    doc.id = doc_id
    doc.to_dict.return_value = {
        "content": content,
        "source_file": f"{doc_id}.pdf",
        "page_count": 5,
        "extracted_at": "2026-03-12T00:00:00Z",
        "version": "1.0",
        "keywords": [doc_id],
    }
    return doc


def _make_missing_doc(doc_id: str):
    """Create a mock Firestore document that does not exist."""
    doc = MagicMock()
    doc.exists = False
    doc.id = doc_id
    return doc


@pytest.fixture
def mock_firestore_db():
    """Mock AsyncClient with 5 documents in knowledge_base collection."""
    db = MagicMock()

    # Build the mock chain: db.collection("knowledge_base").document(doc_id).get()
    def mock_document(doc_id):
        doc_ref = MagicMock()
        if doc_id in MOCK_KB_CONTENT:
            mock_doc = _make_mock_doc(doc_id, MOCK_KB_CONTENT[doc_id])
        else:
            mock_doc = _make_missing_doc(doc_id)
        doc_ref.get = AsyncMock(return_value=mock_doc)
        return doc_ref

    collection_ref = MagicMock()
    collection_ref.document = mock_document

    db.collection.return_value = collection_ref

    return db


@pytest.fixture
def mock_firestore_db_missing_one():
    """Mock AsyncClient with only 4 documents (missing objection-handling)."""
    db = MagicMock()
    available = {k: v for k, v in MOCK_KB_CONTENT.items() if k != "objection-handling"}

    def mock_document(doc_id):
        doc_ref = MagicMock()
        if doc_id in available:
            mock_doc = _make_mock_doc(doc_id, available[doc_id])
        else:
            mock_doc = _make_missing_doc(doc_id)
        doc_ref.get = AsyncMock(return_value=mock_doc)
        return doc_ref

    collection_ref = MagicMock()
    collection_ref.document = mock_document

    db.collection.return_value = collection_ref

    return db


@pytest.fixture
def mock_supabase_config(monkeypatch):
    """Provide fake Supabase URL and service key via env vars."""
    monkeypatch.setenv("SUPABASE_URL", "https://fake-project.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "fake-service-key-for-testing")


@pytest.fixture
def sample_kb_content():
    """Representative KB content string for system instruction tests."""
    sections = []
    for doc_id in KB_DOC_IDS:
        content = MOCK_KB_CONTENT[doc_id]
        sections.append(f"## {doc_id.replace('-', ' ').title()}\n\n{content}")
    return "\n\n---\n\n".join(sections)
