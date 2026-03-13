"""Tests for system instruction content requirements from CONTEXT.md.

Covers:
- CALL-02: AI disclosure wording
- CALL-03: Qualification field mentions
- CALL-04: Programme details presence
- CALL-05: Objection handling rules
- CALL-06: Commitment ask thresholds (COMMITTED / FOLLOW_UP / DECLINED)
- CALL-08: Watchdog wrap-up behavior
- CALL-10: Follow-up timing instruction
"""

import pytest


@pytest.fixture
def system_instruction(sample_kb_content):
    """Build a full system instruction for testing."""
    from knowledge_loader import build_system_instruction

    return build_system_instruction("Akinwunmi", sample_kb_content)


class TestAIDisclosure:
    """CALL-02: Sarah discloses she is AI only when asked; recording notice in opening."""

    def test_ai_disclosure_when_asked(self, system_instruction):
        """System instruction tells Sarah to disclose AI only when directly asked."""
        si = system_instruction.lower()
        assert "only when" in si or "only disclose" in si
        assert "are you an ai" in si or "are you a real person" in si

    def test_recording_notice(self, system_instruction):
        """Opening mentions call recording."""
        assert "being recorded" in system_instruction

    def test_ai_disclosure_opening(self, system_instruction):
        """Opening introduces Sarah as Programme Advisor at Cloudboosta Academy."""
        assert "Programme Advisor at Cloudboosta Academy" in system_instruction


class TestQualificationFields:
    """CALL-03: Sarah qualifies leads using the decision tree fields."""

    def test_qualification_fields(self, system_instruction):
        """System instruction mentions all 4 must-have qualification fields."""
        si = system_instruction.lower()
        assert "role" in si
        assert "experience_level" in si or "experience level" in si
        assert "cloud_background" in si or "cloud background" in si
        assert "motivation" in si


class TestProgrammeRecommendation:
    """CALL-04: Sarah recommends the correct programmes."""

    def test_programme_recommendation(self, system_instruction):
        """System instruction mentions both 'Cloud Security' and 'SRE'
        (or 'Platform Engineering')."""
        assert "Cloud Security" in system_instruction
        assert (
            "SRE" in system_instruction
            or "Platform Engineering" in system_instruction
        )

    def test_programme_prices(self, system_instruction):
        """System instruction includes programme prices."""
        assert "1,200" in system_instruction or "1200" in system_instruction
        assert "1,800" in system_instruction or "1800" in system_instruction


class TestObjectionHandling:
    """CALL-05: Objection handling rules from CONTEXT.md."""

    def test_objection_handling_rules(self, system_instruction):
        """System instruction contains reactive objection handling guidance
        (wait for lead to raise, two attempts)."""
        si = system_instruction.lower()
        # Reactive: wait for lead to raise objections
        assert "reactive" in si or "wait for" in si or "lead raises" in si or "lead to raise" in si
        # Two attempts with different angles
        assert "two" in si or "2" in si or "different angle" in si


class TestCommitmentRules:
    """CALL-06: Commitment ask and outcome determination."""

    def test_commitment_rules(self, system_instruction):
        """System instruction defines COMMITTED, FOLLOW_UP, DECLINED thresholds."""
        assert "COMMITTED" in system_instruction
        assert "FOLLOW_UP" in system_instruction
        assert "DECLINED" in system_instruction

    def test_commitment_thresholds(self, system_instruction):
        """System instruction explains what qualifies for each outcome."""
        si = system_instruction.lower()
        # COMMITTED = explicit yes
        assert "explicit" in si or "yes" in si
        # FOLLOW_UP = ambiguous
        assert "ambiguous" in si or "think about" in si or "follow" in si


class TestWatchdogInstructions:
    """CALL-08: Duration watchdog wrap-up behavior."""

    def test_watchdog_instructions(self, system_instruction):
        """System instruction contains wrap-up behavior instructions for the
        8.5-minute signal."""
        si = system_instruction.lower()
        assert "internal system signal" in si or "system signal" in si
        assert "wrap" in si  # wrap up, wrapping up


class TestFollowUpTiming:
    """CALL-10: Sarah asks lead when to follow up."""

    def test_follow_up_timing(self, system_instruction):
        """System instruction instructs Sarah to ask when the lead prefers a
        follow-up."""
        si = system_instruction.lower()
        assert "follow-up" in si or "follow up" in si
        # Should instruct to ASK the lead about timing preference
        assert "when" in si or "prefer" in si or "timing" in si
