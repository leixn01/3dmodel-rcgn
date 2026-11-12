"""Local stdio MCP transport; all business operations live in cadkin.tools."""
import argparse
import asyncio
import json
import logging
from pathlib import Path

from cadkin.tools.solidworks import SolidWorksTools, TOOLS


def create_server(service):
    from mcp.server import Server
    from mcp.types import Tool, TextContent, CallToolResult
    server = Server("3dmodel-rcgn-solidworks", version="0.20.0")

    @server.list_tools()
    async def list_tools():
        return [Tool(**tool) for tool in TOOLS]

    @server.call_tool(validate_input=False)  # Shared dispatcher validates CLI and MCP equally.
    async def call_tool(name, arguments):
        try:
            result = await asyncio.to_thread(service.call, name, arguments)
        except asyncio.CancelledError:
            if name.startswith("sw_"):
                service.worker.mark_uncertain()
            raise
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(result, ensure_ascii=False))],
            structuredContent=result, isError=result["status"] == "error")

    return server


async def serve(root, timeout):
    from mcp.server.stdio import stdio_server
    service = SolidWorksTools(root=root, timeout=timeout)
    server = create_server(service)
    try:
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())
    finally:
        service.close()


def main():
    parser = argparse.ArgumentParser(description="SOLIDWORKS MCP over local stdio (Windows COM)")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Project root for input paths")
    parser.add_argument("--timeout", type=float, default=180.0, help="COM call timeout, seconds; timed-out operations are never retried")
    args = parser.parse_args()
    if not 0 < args.timeout <= 600:
        parser.error("timeout must be in (0, 600]")
    logging.basicConfig(level=logging.WARNING)  # stderr only; stdout is reserved for MCP.
    try:
        asyncio.run(serve(args.root.resolve(), args.timeout))
    except ImportError as exc:
        parser.exit(2, f'Missing MCP dependency: {exc}. Install with python -m pip install -e ".[solidworks]"\n')


if __name__ == "__main__":
    main()
