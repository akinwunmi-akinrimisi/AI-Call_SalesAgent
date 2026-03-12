"""Tests for backend/knowledge_loader.py -- KB loading and system instruction building.

Covers:
- CALL-05: All 5 KB documents loaded into system instruction
- Knowledge loader resilience when documents are missing
"""

import pytest


class TestLoadKnowledgeBase:
    """Tests for load_knowledge_base() function."""

    async def test_kb_preload(self, mock_firestore_db):
        """Mock Firestore returns 5 docs -> load_knowledge_base() returns
        concatenated string containing all 5 doc sections."""
        from knowledge_loader import load_knowledge_base

        result = await load_knowledge_base(mock_firestore_db)

        # All 5 document sections should be present
        assert "Programmes" in result
        assert "Conversation Sequence" in result
        assert "Faqs" in result
        assert "Payment Details" in result
        assert "Objection Handling" in result

        # Actual content from each doc should appear
        assert "Cloud Security Programme" in result
        assert "Qualification Decision Tree" in result
        assert "Frequently Asked Questions" in result
        assert "Payment Information" in result
        assert "Objection Handling Guide" in result

    async def test_kb_missing_doc(self, mock_firestore_db_missing_one):
        """Mock Firestore returns only 4 docs -> load_knowledge_base() still
        returns the 4 available docs without error."""
        from knowledge_loader import load_knowledge_base

        result = await load_knowledge_base(mock_firestore_db_missing_one)

        # 4 present docs should appear
        assert "Programmes" in result
        assert "Conversation Sequence" in result
        assert "Faqs" in result
        assert "Payment Details" in result

        # Missing doc should NOT appear
        assert "Objection Handling Guide" not in result


class TestBuildSystemInstruction:
    """Tests for build_system_instruction() function."""

    def test_name_personalization(self, sample_kb_content):
        """build_system_instruction("Akinwunmi", kb_content) output contains
        "Akinwunmi"."""
        from knowledge_loader import build_system_instruction

        result = build_system_instruction("Akinwunmi", sample_kb_content)

        assert "Akinwunmi" in result

    def test_kb_content_included(self, sample_kb_content):
        """System instruction includes the KB content."""
        from knowledge_loader import build_system_instruction

        result = build_system_instruction("TestLead", sample_kb_content)

        assert "Cloud Security Programme" in result
        assert "SRE & Platform Engineering Programme" in result
        assert "Objection Handling Guide" in result
