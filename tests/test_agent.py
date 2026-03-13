"""Tests for ADK Agent definition (Sarah).

Verifies that create_sarah_agent() produces a correctly configured ADK Agent
with the right name, model, tools, and dynamic system instruction.
"""

from unittest.mock import MagicMock, patch

import pytest


def test_create_agent_returns_agent_with_correct_name():
    """create_sarah_agent returns an Agent with name='Sarah'."""
    from agent import create_sarah_agent

    instruction = "You are Sarah, a test agent."
    agent = create_sarah_agent(instruction)
    assert agent.name == "Sarah"


def test_create_agent_uses_correct_model():
    """Agent uses gemini-live-2.5-flash-native-audio model."""
    from agent import create_sarah_agent

    instruction = "You are Sarah, a test agent."
    agent = create_sarah_agent(instruction)
    assert agent.model == "gemini-2.5-flash-native-audio-latest"


def test_agent_has_two_tools():
    """Agent has exactly 2 tools bound."""
    from agent import create_sarah_agent

    instruction = "You are Sarah, a test agent."
    agent = create_sarah_agent(instruction)
    assert len(agent.tools) == 2


def test_agent_has_update_lead_tool():
    """Agent.tools includes update_lead_profile."""
    from agent import create_sarah_agent
    from tools import update_lead_profile

    instruction = "You are Sarah, a test agent."
    agent = create_sarah_agent(instruction)
    assert update_lead_profile in agent.tools


def test_agent_has_outcome_tool():
    """Agent.tools includes determine_call_outcome."""
    from agent import create_sarah_agent
    from tools import determine_call_outcome

    instruction = "You are Sarah, a test agent."
    agent = create_sarah_agent(instruction)
    assert determine_call_outcome in agent.tools


def test_agent_instruction_set():
    """Agent.instruction matches the provided system_instruction string."""
    from agent import create_sarah_agent

    instruction = "You are Sarah, a custom instruction for testing."
    agent = create_sarah_agent(instruction)
    assert agent.instruction == instruction


def test_agent_description():
    """Agent has a descriptive description string."""
    from agent import create_sarah_agent

    instruction = "You are Sarah, a test agent."
    agent = create_sarah_agent(instruction)
    assert "Cloudboosta" in agent.description
    assert "sales" in agent.description.lower()
