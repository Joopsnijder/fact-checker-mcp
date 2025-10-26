"""
Simple integration test for the refactored fact checker.
Tests that basic imports work and agents can be instantiated.
"""

import pytest


def test_imports():
    """Test that all imports work."""
    from agent_loop import AgentOrchestrator, ExecutionContext, create_task
    from agents import (
        ClaimExtractorAgent,
        FactCheckReport,
        ReportCompilerAgent,
        ResearchSpecialistAgent,
        VerificationAnalystAgent,
    )
    from portkey_client import create_metadata, get_anthropic_client
    from search_wrapper import create_search_tool

    assert AgentOrchestrator is not None
    assert ExecutionContext is not None
    assert create_task is not None
    assert ClaimExtractorAgent is not None
    assert FactCheckReport is not None
    assert ReportCompilerAgent is not None
    assert ResearchSpecialistAgent is not None
    assert VerificationAnalystAgent is not None
    assert create_metadata is not None
    assert get_anthropic_client is not None
    assert create_search_tool is not None


def test_agent_instantiation():
    """Test that agents can be instantiated."""
    from agents import (
        ClaimExtractorAgent,
        ReportCompilerAgent,
        ResearchSpecialistAgent,
        VerificationAnalystAgent,
    )

    extractor = ClaimExtractorAgent()
    assert extractor.name == "claim_extractor"

    researcher = ResearchSpecialistAgent()
    assert researcher.name == "research_specialist"

    verifier = VerificationAnalystAgent()
    assert verifier.name == "verification_analyst"

    compiler = ReportCompilerAgent()
    assert compiler.name == "report_compiler"


def test_search_tool():
    """Test that search tool can be created."""
    from search_wrapper import create_search_tool

    search_tool = create_search_tool()
    assert search_tool is not None
    assert hasattr(search_tool, "run")
    assert hasattr(search_tool, "search")


def test_execution_context():
    """Test ExecutionContext."""
    from agent_loop import ExecutionContext

    context = ExecutionContext(original_text="Test text")
    assert context.original_text == "Test text"

    context.set("key1", "value1")
    assert context.get("key1") == "value1"

    context.update({"key2": "value2", "key3": "value3"})
    assert context.get("key2") == "value2"
    assert context.get("key3") == "value3"


def test_portkey_metadata():
    """Test metadata creation for Portkey."""
    from portkey_client import create_metadata

    metadata = create_metadata(agent="test_agent", phase="test_phase", iteration=1)
    assert metadata["project"] == "fact-checker-mcp"
    assert metadata["agent"] == "test_agent"
    assert metadata["phase"] == "test_phase"
    assert metadata["iteration"] == 1
    assert metadata["user"] is not None
    assert metadata["environment"] is not None


@pytest.mark.asyncio
async def test_task_creation():
    """Test task creation."""
    from agent_loop import create_task
    from agents import ClaimExtractorAgent

    agent = ClaimExtractorAgent()
    task = create_task(
        task_id="test_task",
        description="Test description",
        agent=agent,
        expected_output="Test output",
    )

    assert task.id == "test_task"
    assert task.description == "Test description"
    assert task.agent == agent
    assert task.expected_output == "Test output"
    assert task.depends_on == []
    assert task.async_execution is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
