"""Seed Firestore with knowledge base PDFs.

Reads PDF files from knowledge-base/ and uploads them to Firestore
as extracted Markdown text using pymupdf4llm.

Usage: python scripts/seed_firestore.py

Each PDF becomes a document in the 'knowledge_base' collection.
Re-running overwrites documents cleanly (idempotent).
"""

import os
import subprocess
import sys
from pathlib import Path

import pymupdf4llm
from google.cloud import firestore
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GCP_PROJECT = os.getenv("GCP_PROJECT_ID", "vision-gridai")
CREDENTIALS_PATH = os.getenv(
    "GOOGLE_APPLICATION_CREDENTIALS", "secrets/openclaw-key-google.json"
)
KB_DIR = Path("knowledge-base")

# Document ID -> PDF filename mapping
PDF_MAP: dict[str, str] = {
    "programmes": "programmes.pdf",
    "conversation-sequence": "conversation-sequence.pdf",
    "faqs": "faqs.pdf",
    "payment-details": "payment-details.pdf",
    "objection-handling": "objection-handling.pdf",
    "coming-soon": "coming-soon.pdf",
}

# Manually curated keywords per document
KEYWORDS: dict[str, list[str]] = {
    "programmes": [
        "cloud security",
        "SRE",
        "platform engineering",
        "pricing",
        "curriculum",
        "duration",
        "internship",
    ],
    "conversation-sequence": [
        "qualification",
        "opening",
        "recommendation",
        "objection",
        "closing",
        "decision tree",
    ],
    "faqs": [
        "frequently asked questions",
        "schedule",
        "prerequisites",
        "certification",
        "support",
    ],
    "payment-details": [
        "bank transfer",
        "payment",
        "account details",
        "installment",
        "pricing",
    ],
    "objection-handling": [
        "price objection",
        "time commitment",
        "job outcomes",
        "beginner concerns",
        "ROI",
    ],
    "coming-soon": [
        "future programmes",
        "cloud security specialisation",
        "DevSecOps",
        "data engineering",
        "notification list",
    ],
}


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------


def ensure_firestore_db() -> None:
    """Create Firestore database if it doesn't exist (idempotent).

    Uses gcloud CLI which must be available on the machine (VPS #1).
    """
    result = subprocess.run(
        [
            "gcloud",
            "firestore",
            "databases",
            "create",
            "--location=europe-west1",
            "--type=firestore-native",
            f"--project={GCP_PROJECT}",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("[OK] Firestore database created")
    elif "already exists" in result.stderr.lower():
        print("[OK] Firestore database already exists")
    else:
        print(f"[ERROR] Firestore creation failed: {result.stderr}")
        raise RuntimeError(f"Firestore database creation failed: {result.stderr}")


def extract_pdf_to_markdown(pdf_path: Path) -> tuple[str, int]:
    """Extract PDF content as Markdown text.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Tuple of (full_markdown_text, page_count).
        Returns ("", 0) on extraction failure.
    """
    try:
        chunks = pymupdf4llm.to_markdown(str(pdf_path), page_chunks=True)
        full_text = "\n\n".join(chunk["text"] for chunk in chunks)
        return full_text, len(chunks)
    except Exception as exc:
        print(f"[ERROR] Failed to extract {pdf_path}: {exc}")
        return "", 0


def seed_knowledge_base() -> None:
    """Extract all PDFs and seed Firestore knowledge_base collection.

    Sets GOOGLE_APPLICATION_CREDENTIALS, creates the Firestore database
    if needed, then writes each PDF as a document with full overwrite
    (idempotent).
    """
    # Set credentials for the Firestore SDK
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = CREDENTIALS_PATH

    # Ensure the Firestore database exists
    ensure_firestore_db()

    # Create Firestore client
    db = firestore.Client(project=GCP_PROJECT)

    for doc_id, pdf_name in PDF_MAP.items():
        pdf_path = KB_DIR / pdf_name

        if not pdf_path.exists():
            print(f"[SKIP] PDF not found: {pdf_path}")
            continue

        content, page_count = extract_pdf_to_markdown(pdf_path)
        if not content:
            print(f"[SKIP] Empty extraction for {pdf_name}, skipping upload")
            continue

        keywords = KEYWORDS.get(doc_id, [])

        # Full overwrite via set() -- NOT merge -- for idempotency
        doc_ref = db.collection("knowledge_base").document(doc_id)
        doc_ref.set({
            "content": content,
            "source_file": pdf_name,
            "page_count": page_count,
            "extracted_at": firestore.SERVER_TIMESTAMP,
            "version": "1.0",
            "keywords": keywords,
        })

        print(
            f"[OK] Seeded: {doc_id} "
            f"({page_count} pages, {len(content)} chars)"
        )

    print("\n[DONE] Knowledge base seeding complete.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    seed_knowledge_base()
