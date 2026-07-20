"""
CARL MCP Server Entry Point

Run with: python -m carl_mcp_server
"""
import asyncio
import sys
from .server import run_server

def main():
    """Main entry point for CARL MCP server."""
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        print("\n🛑 CARL MCP Server stopped", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"❌ Fatal error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
