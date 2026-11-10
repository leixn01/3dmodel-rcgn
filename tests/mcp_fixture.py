"""Explicit test-only stdio server. Not installed in the cadkin distribution."""
import asyncio
from mcp.server.stdio import stdio_server
from cadkin.adapters.solidworks import SolidWorksAdapter
from cadkin.mcp_server import create_server
from cadkin.tools.solidworks import SolidWorksTools
from tests.sw_fakes import App, Document


async def main():
    service = SolidWorksTools(factory=lambda: SolidWorksAdapter(app=App(Document())))
    server = create_server(service)
    try:
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())
    finally:
        service.close()

if __name__ == '__main__':
    asyncio.run(main())
