"""ADK agent definition for Sarah -- Cloudboosta AI Sales Agent.

Creates the ADK Agent instance with Sarah's persona, dynamic system instruction
(from knowledge_loader.py), and tool bindings (from tools.py). The system
instruction is received as a parameter -- never hardcoded here.

Knowledge comes from Firestore PDFs pre-loaded into the system instruction
at call start. See knowledge_loader.py for the instruction builder.

Exports:
    create_sarah_agent: Factory function that returns a configured ADK Agent.
"""

from __future__ import annotations

from google.adk.agents import Agent

from tools import determine_call_outcome, update_lead_profile


def create_sarah_agent(system_instruction: str) -> Agent:
    """Create Sarah agent with pre-loaded KB in system instruction.

    Args:
        system_instruction: Complete system instruction string built by
            build_system_instruction() from knowledge_loader.py. Contains
            persona, AI disclosure, qualification flow, programme details,
            objection handling rules, commitment thresholds, watchdog
            behavior, and the full knowledge base content.

    Returns:
        Configured ADK Agent ready for use with Runner.run_live().
    """
    return Agent(
        name="Sarah",
        model="gemini-live-2.5-flash-native-audio",
        description="Cloudboosta AI sales agent for qualification calls",
        instruction=system_instruction,
        tools=[
            update_lead_profile,
            determine_call_outcome,
        ],
    )
