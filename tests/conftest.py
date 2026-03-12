"""Shared test fixtures for Cloudboosta Voice Agent tests.

Provides mock Firestore, Supabase, and ADK fixtures used across
test_knowledge_loader.py, test_system_instruction.py, and test_tools.py.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add backend directory to sys.path so imports work without package install
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))


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
