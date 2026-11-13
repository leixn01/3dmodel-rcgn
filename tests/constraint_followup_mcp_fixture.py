"""Explicit test-only CAD transport for enhanced mate follow-up; never a production fallback."""
import argparse
import asyncio
from pathlib import Path
from mcp.server.stdio import stdio_server
from cadkin.mcp_server import create_server
from tests.constraint_fakes import write_constraint_followup_fixture
from tests.execution_fakes import live_service


async def main(root):
    app, _, _ = write_constraint_followup_fixture(root)
    service = live_service(root, app); server = create_server(service)
    try:
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())
    finally:
        service.close()


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True)
    asyncio.run(main(parser.parse_args().root))
