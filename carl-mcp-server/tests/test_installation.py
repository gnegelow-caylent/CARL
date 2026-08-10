"""
Installation verification tests for CARL MCP Server

Ensures critical dependencies are installed correctly.
"""
import pytest


def test_mcp_version_compatibility():
    """Test that MCP version is in compatible range (1.x, not 2.x)."""
    from importlib.metadata import version

    mcp_version = version('mcp')
    major_version = int(mcp_version.split('.')[0])

    # MCP 2.0 removed decorator-based API that server.py depends on
    # See: https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.0.0
    assert major_version < 2, (
        f"MCP {mcp_version} is incompatible. "
        f"Server requires MCP 1.x (decorator-based API). "
        f"Check requirements.txt and setup.py for correct pinning: mcp>=0.9.0,<2.0.0"
    )

    # Also verify we're not on an ancient version
    assert major_version >= 0 and int(mcp_version.split('.')[1]) >= 9, (
        f"MCP {mcp_version} is too old. Minimum required: 0.9.0"
    )


def test_botocore_crt_available():
    """Test that botocore CRT dependency is available."""
    try:
        import awscrt
        # If import succeeds, CRT is available
        assert True
    except ImportError as e:
        pytest.fail(
            f"AWS CRT not available: {e}\n"
            f"This breaks SSO-based credential providers.\n"
            f"Fix: Change 'botocore>=1.34.0' to 'botocore[crt]>=1.34.0' in requirements.txt and setup.py"
        )


def test_critical_imports():
    """Test that all critical dependencies can be imported."""
    # These imports should not raise exceptions
    import mcp
    import boto3
    import botocore
    import aiofiles

    # If we got here, all imports succeeded
    assert True


def test_package_metadata():
    """Test that package metadata is correct."""
    from importlib.metadata import version, metadata

    # Package should be installed
    pkg_version = version('carl-mcp-server')
    assert pkg_version is not None

    # Metadata should be accessible
    meta = metadata('carl-mcp-server')
    assert meta['Name'] == 'carl-mcp-server'
    assert 'AWS' in meta['Summary'] or 'security' in meta['Summary'].lower()


def test_entry_point_exists():
    """Test that console script entry point is registered."""
    from importlib.metadata import entry_points

    # Check for carl-mcp entry point
    eps = entry_points()

    # In different Python versions, entry_points() returns different types
    if hasattr(eps, 'select'):
        # Python 3.10+
        console_scripts = eps.select(group='console_scripts')
    else:
        # Python 3.9
        console_scripts = eps.get('console_scripts', [])

    entry_point_names = [ep.name for ep in console_scripts]

    assert 'carl-mcp' in entry_point_names, (
        f"Entry point 'carl-mcp' not found. "
        f"Available: {entry_point_names}. "
        f"Check setup.py entry_points configuration."
    )
