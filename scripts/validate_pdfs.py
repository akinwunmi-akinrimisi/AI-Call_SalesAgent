"""Validate knowledge base PDFs: existence, extractability, and expected content.

Checks all 5 PDFs in knowledge-base/ directory:
- programmes.pdf: Programme details, pricing, duration
- conversation-sequence.pdf: Qualification decision tree
- faqs.pdf: Common questions and answers
- payment-details.pdf: Bank transfer instructions
- objection-handling.pdf: Objection response scripts

Usage: python scripts/validate_pdfs.py
"""

import os
import sys

import fitz  # PyMuPDF
import pymupdf4llm


# Expected keywords per PDF (case-insensitive matching)
# Confidence: MEDIUM -- keywords inferred from AGENT.md and directives.
# Script reports findings; missing keywords produce WARN, not hard FAIL.
PDF_EXPECTATIONS = {
    "programmes.pdf": {
        "description": "Programme details, pricing, duration",
        "keywords": [
            "Cloud Security",
            "SRE",
            "Platform Engineering",
            "1,200",
            "1,800",
            "duration",
            "curriculum",
        ],
    },
    "conversation-sequence.pdf": {
        "description": "Qualification decision tree",
        "keywords": [
            "qualification",
            "background",
            "experience",
            "recommend",
            "Cloud Security",
            "SRE",
            "objection",
            "committed",
            "follow up",
            "declined",
        ],
    },
    "faqs.pdf": {
        "description": "Common questions and answers",
        "keywords": [
            "FAQ",
            "question",
            "internship",
            "payment",
            "beginner",
        ],
    },
    "payment-details.pdf": {
        "description": "Bank transfer instructions",
        "keywords": [
            "bank",
            "transfer",
            "account",
            "payment",
        ],
    },
    "objection-handling.pdf": {
        "description": "Objection response scripts",
        "keywords": [
            "objection",
            "expensive",
            "time",
            "job",
            "beginner",
            "guarantee",
        ],
    },
}

KNOWLEDGE_BASE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "knowledge-base",
)


def extract_and_validate(pdf_name: str, expected: dict) -> dict:
    """Extract text from a PDF and check for expected content.

    Returns a result dict with status (PASS/WARN/FAIL), page count,
    character count, markdown length, and keyword match details.
    """
    pdf_path = os.path.join(KNOWLEDGE_BASE_DIR, pdf_name)
    result = {
        "name": pdf_name,
        "description": expected["description"],
        "path": pdf_path,
        "status": "FAIL",
        "pages": 0,
        "char_count": 0,
        "markdown_length": 0,
        "found_keywords": [],
        "missing_keywords": [],
        "error": None,
    }

    # Check file exists
    if not os.path.isfile(pdf_path):
        result["error"] = "File not found"
        return result

    try:
        # Open with PyMuPDF and extract plain text
        doc = fitz.open(pdf_path)
        result["pages"] = doc.page_count

        plain_text = ""
        for page in doc:
            plain_text += page.get_text()
        doc.close()

        result["char_count"] = len(plain_text)

        if result["char_count"] == 0:
            result["error"] = "No extractable text (PDF may be image-only)"
            return result

        # Extract markdown with pymupdf4llm for quality check
        md_text = pymupdf4llm.to_markdown(pdf_path)
        result["markdown_length"] = len(md_text)

        # Case-insensitive keyword matching
        plain_lower = plain_text.lower()
        for keyword in expected["keywords"]:
            if keyword.lower() in plain_lower:
                result["found_keywords"].append(keyword)
            else:
                result["missing_keywords"].append(keyword)

        # Determine status
        if len(result["missing_keywords"]) == 0:
            result["status"] = "PASS"
        else:
            result["status"] = "WARN"

    except Exception as e:
        result["error"] = str(e)

    return result


def print_result(result: dict) -> None:
    """Print a formatted result for a single PDF."""
    status_marker = {
        "PASS": "PASS",
        "WARN": "WARN",
        "FAIL": "FAIL",
    }
    marker = status_marker.get(result["status"], "????")

    print(f"\n  [{marker}] {result['name']} -- {result['description']}")

    if result["error"]:
        print(f"         Error: {result['error']}")
        return

    print(f"         Pages: {result['pages']}")
    print(f"         Characters: {result['char_count']:,}")
    print(f"         Markdown length: {result['markdown_length']:,}")

    if result["found_keywords"]:
        print(f"         Keywords found ({len(result['found_keywords'])}): {', '.join(result['found_keywords'])}")

    if result["missing_keywords"]:
        print(f"         Keywords MISSING ({len(result['missing_keywords'])}): {', '.join(result['missing_keywords'])}")


def main() -> int:
    """Run PDF validation and return exit code."""
    print("\n===== Knowledge Base PDF Validation =====")
    print(f"  Directory: {KNOWLEDGE_BASE_DIR}\n")

    results = []
    for pdf_name, expected in PDF_EXPECTATIONS.items():
        result = extract_and_validate(pdf_name, expected)
        results.append(result)
        print_result(result)

    # Summary
    pass_count = sum(1 for r in results if r["status"] == "PASS")
    warn_count = sum(1 for r in results if r["status"] == "WARN")
    fail_count = sum(1 for r in results if r["status"] == "FAIL")

    print("\n===== Summary =====")
    print(f"  PASS: {pass_count}")
    print(f"  WARN: {warn_count}")
    print(f"  FAIL: {fail_count}")
    print(f"  Total: {len(results)}")

    # Exit 0 if all PDFs at least WARN (exist and extractable)
    # Exit 1 if any FAIL (missing or not extractable)
    if fail_count > 0:
        print("\n  RESULT: INCOMPLETE -- some PDFs are missing or not extractable.")
        print("  Place the missing PDFs in knowledge-base/ and re-run this script.")
        return 1
    else:
        print("\n  RESULT: All PDFs exist and are extractable.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
