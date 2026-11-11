"""Explicit test-only stdio server. Not installed in the cadkin distribution."""
import asyncio
import sys
from mcp.server.stdio import stdio_server
from cadkin.adapters.solidworks import SolidWorksAdapter
from cadkin.mcp_server import create_server
from cadkin.tools.solidworks import SolidWorksTools
from tests.sw_fakes import App, Document, SessionHarness, runtime
from tests.evidence_fakes import evidence_document
from tests.mate_fakes import MateApp, attach_features

def mate_app():
    doc = evidence_document()
    attach_features(doc)
    return MateApp(doc)


def face_app():
    from tests.face_fakes import face_document
    return face_document()[4]


async def main():
    factory = (lambda: SessionHarness().adapter) if '--cold-start' in sys.argv else (lambda: SolidWorksAdapter(
        app=face_app() if '--faces' in sys.argv else mate_app(), runtime=runtime()))
    service = SolidWorksTools(factory=factory)
    server = create_server(service)
    try:
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())
    finally:
        service.close()

if __name__ == '__main__':
    asyncio.run(main())
