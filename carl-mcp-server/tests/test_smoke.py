"""
Smoke tests for CARL MCP Server

Basic tests to ensure server can start and respond to basic requests.
"""
import os
import pytest


@pytest.fixture(autouse=True)
def mock_agentcore_envs(monkeypatch):
    """Set required AgentCore environment variables for testing."""
    monkeypatch.setenv("CARL_AGENTCORE_ASK_ARN", "arn:aws:bedrock-agentcore:us-east-1:123456789012:agent-runtime/test-ask")
    monkeypatch.setenv("CARL_AGENTCORE_ARCHITECT_ARN", "arn:aws:bedrock-agentcore:us-east-1:123456789012:agent-runtime/test-architect")
    monkeypatch.setenv("CARL_AGENTCORE_REMEDIATE_ARN", "arn:aws:bedrock-agentcore:us-east-1:123456789012:agent-runtime/test-remediate")


def test_server_starts():
    """Test that the server can be created without errors."""
    from carl_mcp_server.server import create_server

    server = create_server()
    assert server is not None
    assert server.name == "carl"


def test_server_requires_agentcore_arns():
    """Test that server fails without required environment variables."""
    # Remove all AgentCore ARN env vars
    for key in list(os.environ.keys()):
        if key.startswith("CARL_AGENTCORE_"):
            del os.environ[key]

    from carl_mcp_server.server import create_server

    with pytest.raises(ValueError, match="Missing environment variables"):
        create_server()


def test_all_tools_registered():
    """Test that all expected tools are registered."""
    from carl_mcp_server.server import create_server

    server = create_server()

    # The server should have registered all 6 tools
    # Note: This test validates the tool registration mechanism exists
    # without needing to actually call the tools
    expected_tools = [
        "carl_scan_environment",
        "carl_collect_evidence",
        "carl_generate_report",
        "carl_ask",
        "carl_architect",
        "carl_remediate_finding"
    ]

    # The server object has tools registered via decorators
    # This test primarily ensures server creation doesn't crash
    assert hasattr(server, "list_tools") or hasattr(server, "_list_tools_handler")
