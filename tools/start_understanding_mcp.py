"""Standalone read-only understanding MCP. No existing MCP configuration changed."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from model_understanding_workbench.mcp_tools import UnderstandingTools


async def main():
    server = Server("catia-model-understanding-baseline")
    module = UnderstandingTools()

    @server.list_tools()
    async def list_tools():
        return [Tool(**definition) for definition in module.get_tool_definitions()]

    @server.call_tool()
    async def call_tool(name, arguments):
        # The SDK wraps raised failures with isError=true; never return an error
        # string as a successful tool result.
        value = module.execute(name, arguments or {})
        return [TextContent(type="text", text=json.dumps(value, ensure_ascii=False, allow_nan=False))]

    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
