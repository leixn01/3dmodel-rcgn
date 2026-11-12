"""Explicit synthetic CAD stdio fixture; never installed or used as production fallback."""
import argparse
import asyncio
from pathlib import Path
from mcp.server.stdio import stdio_server
from cadkin.mcp_server import create_server
from tests.execution_fakes import write_execution_fixture,live_service


async def main(root):
    app=write_execution_fixture(root,degraded=True)
    service=live_service(root,app);server=create_server(service)
    try:
        async with stdio_server() as (read,write):
            await server.run(read,write,server.create_initialization_options())
    finally:service.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True)
    asyncio.run(main(parser.parse_args().root))
