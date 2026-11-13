"""Explicit synthetic geometry evidence transport; never production fallback."""
import argparse
import asyncio
from pathlib import Path
from mcp.server.stdio import stdio_server
from cadkin.mcp_server import create_server
from tests.geometry_connection_fakes import geometry_fixture


async def main(root):
    service,_=geometry_fixture(root);server=create_server(service)
    try:
        async with stdio_server() as (read,write):
            await server.run(read,write,server.create_initialization_options())
    finally:service.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    asyncio.run(main(p.parse_args().root))
