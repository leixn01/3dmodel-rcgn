"""Explicit synthetic setup for the official SDK; no production backend switch."""
import argparse
import asyncio
from pathlib import Path
from mcp.server.stdio import stdio_server
from cadkin.mcp_server import create_server
from cadkin.tools.execution import run_plan
from tests.execution_fakes import write_execution_fixture, live_service


async def main(root):
    app = write_execution_fixture(root, include_face_review=False)
    service = live_service(root, app)
    try:
        r = service.call('cad_plan_evidence_tasks', {'draft_check_path': 'outputs/check.json', 'output_path': 'outputs/bootstrap-plan.json', 'max_tasks': 9})
        assert r['status'] != 'error', r
        r = run_plan(service, 'outputs/bootstrap-plan.json', 'outputs/bootstrap-run.json')
        assert r['data']['guards_passed'], r
        r = service.call('cad_index_evidence', {'draft_check_path': 'outputs/check.json', 'execution_path': 'outputs/bootstrap-run.json', 'output_path': 'outputs/bootstrap-index.json'})
        assert r['status'] != 'error', r
        server = create_server(service)
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())
    finally: service.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--root', type=Path, required=True)
    asyncio.run(main(parser.parse_args().root))
