import importlib.util
import sys
import unittest


@unittest.skipUnless(importlib.util.find_spec('mcp'), 'Install .[solidworks] for protocol integration tests')
class McpTests(unittest.IsolatedAsyncioTestCase):
    async def test_face_identity_collection_and_review_over_real_stdio(self):
        import json
        from pathlib import Path
        import tempfile
        from anyio import fail_after
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from cadkin.adapters.solidworks import SolidWorksAdapter
        from cadkin.tools.solidworks import SolidWorksTools
        from tests.face_fakes import face_document
        from tests.sw_fakes import runtime
        from tests.test_face_matches import write_face_fixture
        root = Path.cwd()
        (root / 'outputs').mkdir(exist_ok=True)
        parameters = StdioServerParameters(command=sys.executable, args=['-m', 'tests.mcp_fixture', '--faces'])
        with tempfile.TemporaryDirectory(dir=root / 'outputs') as directory, fail_after(25):
            base = Path(directory)
            service = SolidWorksTools(root=base, factory=lambda: SolidWorksAdapter(app=face_document()[4], runtime=runtime()))
            try: args = write_face_fixture(base, service)
            finally: service.close()
            args['inventory_path'] = str(base / args['inventory_path'])
            args['cylinder_paths'] = [str(base / p) for p in args['cylinder_paths']]
            async with stdio_client(parameters) as (read, write):
                async with ClientSession(read, write) as session:
                    init = await session.initialize()
                    self.assertEqual(init.serverInfo.version, '0.9.0')
                    capture = await session.call_tool('sw_component_cylinders', {
                        'expected_document_token': args['expected_document_token'], 'occurrence_path': 'shaft-1', 'include_face_references': True})
                    self.assertFalse(capture.isError, capture)
                    self.assertEqual(capture.structuredContent['data']['cylinders'][0]['face_reference']['encoding'], 'base64')
                    result = await session.call_tool('sw_match_mate_faces', args)
                    self.assertFalse(result.isError, result)
                    self.assertEqual(result.structuredContent['status'], 'ok')
                    saved = base / 'mates.json'
                    saved.write_text(json.dumps(result.structuredContent), encoding='utf-8')
                    relations = await session.call_tool('cad_component_relations', {
                        'inventory_path': args['inventory_path'], 'cylinder_paths': args['cylinder_paths'],
                        'distance_tolerance_mm': 0.1, 'angle_tolerance_deg': 0.1, 'output_path': str(base / 'outputs/relations.json')})
                    self.assertFalse(relations.isError, relations)
                    review = await session.call_tool('cad_review_connections', {
                        'relations_path': str(base / 'outputs/relations.json'), 'mate_inventory_path': str(saved),
                        'output_path': str(base / 'outputs/review.json')})
                    self.assertFalse(review.isError, review)
                    self.assertEqual(review.structuredContent['data']['coverage']['face_matched_mate_records'], 3)
                    limited = await session.call_tool('sw_match_mate_faces', {**args, 'max_comparisons': 1})
                    self.assertFalse(limited.isError)
                    self.assertEqual(limited.structuredContent['status'], 'partial')
                    bad = await session.call_tool('sw_match_mate_faces', {**args, 'max_candidate_faces': 0})
                    self.assertTrue(bad.isError)
                    self.assertEqual(len((await session.list_tools()).tools), 23)

    async def test_production_offline_relations_over_real_stdio(self):
        import json
        from pathlib import Path
        import tempfile
        from anyio import fail_after
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from tests.test_relations import write_fixture
        root = Path.cwd()
        (root / 'outputs').mkdir(exist_ok=True)
        # Production transport, no simulated or real CAD connection needed by this tool.
        parameters = StdioServerParameters(command=sys.executable, args=['-m', 'cadkin.mcp_server'])
        with tempfile.TemporaryDirectory(dir=root / 'outputs') as directory, fail_after(20):
            base = Path(directory)
            args = write_fixture(base)
            for key in ('inventory_path', 'output_path', 'grouping_path'): args[key] = str(base / args[key])
            args['cylinder_paths'] = [str(base / p) for p in args['cylinder_paths']]
            async with stdio_client(parameters) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool('cad_component_relations', args)
                    self.assertFalse(result.isError, result)
                    self.assertEqual(result.structuredContent['data']['counts']['coaxial_candidate'], 1)
                    self.assertFalse(result.structuredContent['data']['solidworks_modified'])
                    stored = json.loads(Path(args['output_path']).read_text(encoding='utf-8'))
                    self.assertTrue(stored['requires_review'])
                    partial = await session.call_tool('cad_component_relations', {
                        **args, 'output_path': str(base / 'outputs/limited.json'), 'max_pairs': 1})
                    self.assertFalse(partial.isError)
                    self.assertEqual(partial.structuredContent['status'], 'partial')
                    self.assertTrue(partial.structuredContent['data']['truncated'])
                    bad = await session.call_tool('cad_component_relations', {
                        **args, 'output_path': str(base / 'outputs/bad.json'), 'angle_tolerance_deg': 0})
                    self.assertTrue(bad.isError)
                    self.assertFalse((base / 'outputs/bad.json').exists())
                    self.assertEqual(len((await session.list_tools()).tools), 23)

    async def test_real_stdio_handshake_schemas_success_and_tool_error(self):
        from anyio import fail_after
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        parameters = StdioServerParameters(command=sys.executable, args=['-m', 'tests.mcp_fixture'])
        with fail_after(20):
            async with stdio_client(parameters) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = (await session.list_tools()).tools
                    self.assertEqual(len(tools), 23)
                    self.assertFalse(any('script' in tool.name or 'save' in tool.name for tool in tools))
                    doc = await session.call_tool('sw_active_document')
                    self.assertFalse(doc.isError)
                    token = doc.structuredContent['data']['document_token']
                    spatial = await session.call_tool('sw_spatial_inventory', {'expected_document_token': token})
                    self.assertFalse(spatial.isError)
                    self.assertTrue(spatial.structuredContent['data']['complete'])
                    self.assertEqual(spatial.structuredContent['data']['component_count'], 4)
                    single = await session.call_tool('sw_component_spatial', {
                        'expected_document_token': token, 'occurrence_path': 'slide-1/block-1'})
                    self.assertFalse(single.isError)
                    self.assertEqual(single.structuredContent['data']['component'],
                                     spatial.structuredContent['data']['components'][3])
                    limited = await session.call_tool('sw_spatial_inventory', {
                        'expected_document_token': token, 'max_components': 1})
                    self.assertFalse(limited.isError)
                    self.assertEqual(limited.structuredContent['status'], 'partial')
                    self.assertTrue(limited.structuredContent['data']['truncated'])
                    missing = await session.call_tool('sw_component_spatial', {
                        'expected_document_token': token, 'occurrence_path': 'does-not-exist'})
                    self.assertTrue(missing.isError)
                    self.assertEqual(missing.structuredContent['errors'][0]['code'], 'COMPONENT_NOT_FOUND')
                    display = await session.call_tool('sw_get_display_state')
                    self.assertTrue(display.structuredContent['data']['visibility']['planes'])
                    hidden = await session.call_tool('sw_set_display_visibility', {
                        'expected_document_token': token, 'target': 'planes', 'visible': False})
                    self.assertFalse(hidden.isError)
                    self.assertFalse(hidden.structuredContent['data']['visible'])
                    display = await session.call_tool('sw_get_display_state')
                    self.assertFalse(display.structuredContent['data']['visibility']['planes'])
                    for name, extra in [('sw_zoom_to_fit', {}),
                                        ('sw_get_component_visibility', {'occurrence_path': 'rail-2'}),
                                        ('sw_set_component_visibility', {'occurrence_path': 'rail-2', 'visible': False})]:
                        result = await session.call_tool(name, {'expected_document_token': token, **extra})
                        self.assertFalse(result.isError, result)
                    selection = await session.call_tool('sw_select_component', {'expected_document_token': token, 'occurrence_path': 'rail-2'})
                    self.assertFalse(selection.isError)
                    self.assertEqual(selection.structuredContent['data']['selected_count'], 1)
                    bad = await session.call_tool('sw_rebuild', {'expected_document_token': '0' * 24})
                    self.assertTrue(bad.isError)
                    self.assertEqual(bad.structuredContent['errors'][0]['code'], 'DOCUMENT_CHANGED')
                    bad = await session.call_tool('sw_component_tree', {'max_depth': 0})
                    self.assertTrue(bad.isError)
                    bad = await session.call_tool('not_a_tool')
                    self.assertTrue(bad.isError)

    async def test_cold_start_then_open_and_reuse_over_real_stdio(self):
        from anyio import fail_after
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        parameters = StdioServerParameters(command=sys.executable, args=['-m', 'tests.mcp_fixture', '--cold-start'])
        with fail_after(20):
            async with stdio_client(parameters) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    before = await session.call_tool('sw_session_status')
                    self.assertFalse(before.structuredContent['data']['connected'])
                    started = await session.call_tool('sw_start_application')
                    self.assertFalse(started.isError, started)
                    self.assertTrue(started.structuredContent['data']['started'])
                    self.assertTrue(started.structuredContent['data']['startup_completed'])
                    self.assertFalse(started.structuredContent['data']['has_active_document'])
                    opened = await session.call_tool('sw_open_document', {'path': 'examples/three_servo_lift/3X Lift Assembly.STEP'})
                    self.assertFalse(opened.isError, opened)
                    again = await session.call_tool('sw_start_application')
                    self.assertFalse(again.isError)
                    self.assertFalse(again.structuredContent['data']['started'])
                    self.assertEqual(again.structuredContent['data']['process_id'], started.structuredContent['data']['process_id'])
                    doc = await session.call_tool('sw_active_document')
                    self.assertEqual(doc.structuredContent['data'], opened.structuredContent['data']['document'])
                    inventory = await session.call_tool('sw_spatial_inventory', {'expected_document_token': doc.structuredContent['data']['document_token']})
                    self.assertTrue(inventory.structuredContent['data']['complete'])

    @unittest.skipIf(sys.platform == 'win32', 'Non-Windows failure-path test')
    async def test_production_server_reports_platform_error_without_mock_fallback(self):
        from anyio import fail_after
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        parameters = StdioServerParameters(command=sys.executable, args=['-m', 'cadkin.mcp_server'])
        with fail_after(20):
            async with stdio_client(parameters) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool('sw_session_status')
                    self.assertTrue(result.isError)
                    self.assertEqual(result.structuredContent['errors'][0]['code'], 'UNSUPPORTED_PLATFORM')

    async def test_paging_and_offline_group_file_over_stdio(self):
        import json
        from pathlib import Path
        import tempfile
        from anyio import fail_after
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        root = Path.cwd()
        (root / 'outputs').mkdir(exist_ok=True)
        parameters = StdioServerParameters(command=sys.executable, args=['-m', 'tests.mcp_fixture'])
        with tempfile.TemporaryDirectory(dir=root / 'outputs') as directory, fail_after(20):
            async with stdio_client(parameters) as (read, write):
                async with ClientSession(read, write) as session:
                    init = await session.initialize()
                    self.assertEqual(init.serverInfo.version, '0.9.0')
                    doc = (await session.call_tool('sw_active_document')).structuredContent['data']
                    args = {'expected_document_token': doc['document_token'], 'page_size': 2}
                    page = (await session.call_tool('sw_spatial_inventory', args)).structuredContent
                    self.assertFalse(page['data']['collection_complete'])
                    next_page = (await session.call_tool('sw_spatial_inventory', {**args, 'offset': 2,
                        'expected_inventory_signature': page['data']['inventory_signature']})).structuredContent
                    self.assertFalse(next_page['data']['pagination']['has_more'])
                    self.assertFalse(next_page['data']['collection_complete'])
                    source = Path(directory) / 'page.json'
                    output = Path(directory) / 'groups.json'
                    source.write_text(json.dumps(page), encoding='utf-8')
                    rejected = await session.call_tool('cad_group_components', {'inventory_path': str(source), 'output_path': str(output)})
                    self.assertTrue(rejected.isError)
                    self.assertEqual(rejected.structuredContent['errors'][0]['code'], 'GROUPING_REQUIRES_COMPLETE_INVENTORY')
                    self.assertFalse(output.exists())
                    complete = (await session.call_tool('sw_spatial_inventory', {'expected_document_token': doc['document_token']})).structuredContent
                    source = Path(directory) / 'complete.json'
                    source.write_text(json.dumps(complete), encoding='utf-8')
                    grouped = await session.call_tool('cad_group_components', {'inventory_path': str(source), 'output_path': str(output)})
                    self.assertFalse(grouped.isError, grouped)
                    self.assertFalse(grouped.structuredContent['data']['solidworks_modified'])
                    self.assertEqual(grouped.structuredContent['data']['coverage']['scoped_leaf_occurrences'], 3)
                    self.assertTrue(output.is_file())
                    repeat = await session.call_tool('cad_group_components', {'inventory_path': str(source), 'output_path': str(output)})
                    self.assertTrue(repeat.isError)
                    still_alive = await session.call_tool('sw_active_document')
                    self.assertFalse(still_alive.isError)

    async def test_environment_python_and_new_evidence_tools_over_stdio(self):
        import json
        import os
        from pathlib import Path
        from anyio import fail_after
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        config = json.loads(Path('opencode.json').read_text(encoding='utf-8'))
        command = config['mcp']['solidworks']['command']
        self.assertEqual(command, ['python', '-m', 'cadkin.mcp_server'])
        # Exercise PATH-based Python resolution with a conda marker; not a claim of installing Conda.
        env = {'PATH': str(Path(sys.executable).parent) + os.pathsep + os.environ['PATH'], 'CONDA_PREFIX': sys.prefix}
        parameters = StdioServerParameters(command=command[0], args=['-m', 'tests.mcp_fixture'], env=env)
        with fail_after(20):
            async with stdio_client(parameters) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    status = (await session.call_tool('sw_session_status')).structuredContent
                    runtime = status['data']['runtime']
                    self.assertEqual(Path(runtime['python_executable']).resolve(), Path(sys.executable).resolve())
                    self.assertTrue(runtime['matches_conda_prefix'])
                    doc = (await session.call_tool('sw_active_document')).structuredContent['data']
                    args = {'expected_document_token': doc['document_token'], 'occurrence_path': 'rail-1'}
                    mates = await session.call_tool('sw_component_constraints', args)
                    self.assertFalse(mates.isError, mates)
                    self.assertTrue(mates.structuredContent['data']['fixed_state']['value'])
                    self.assertEqual(mates.structuredContent['data']['mates'][0]['type_name'], 'concentric')
                    cylinders = await session.call_tool('sw_component_cylinders', args)
                    self.assertFalse(cylinders.isError, cylinders)
                    self.assertEqual(cylinders.structuredContent['data']['cylinder_count'], 1)
                    self.assertEqual(cylinders.structuredContent['data']['cylinders'][0]['radius_root_mm'], 10)
                    limited = await session.call_tool('sw_component_cylinders', {**args, 'max_faces': 1})
                    self.assertFalse(limited.isError)
                    self.assertEqual(limited.structuredContent['status'], 'partial')
                    wrong = await session.call_tool('sw_component_cylinders', {**args, 'occurrence_path': 'slide-1'})
                    self.assertTrue(wrong.isError)
                    self.assertEqual(wrong.structuredContent['errors'][0]['code'], 'NOT_PART_COMPONENT')

    async def test_root_mate_inventory_over_stdio(self):
        from anyio import fail_after
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        parameters = StdioServerParameters(command=sys.executable, args=['-m', 'tests.mcp_fixture'])
        with fail_after(20):
            async with stdio_client(parameters) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    doc = (await session.call_tool('sw_active_document')).structuredContent['data']
                    args = {'expected_document_token': doc['document_token']}
                    result = await session.call_tool('sw_mate_inventory', args)
                    self.assertFalse(result.isError, result)
                    self.assertEqual(result.structuredContent['data']['mate_count'], 3)
                    self.assertEqual(result.structuredContent['data']['mates'][0]['activity']['state'], 'unsuppressed_no_feature_error')
                    limited = await session.call_tool('sw_mate_inventory', {**args, 'max_mates': 1})
                    self.assertEqual(limited.structuredContent['status'], 'partial')
                    bad = await session.call_tool('sw_mate_inventory', {**args, 'max_features': 0})
                    self.assertTrue(bad.isError)
                    self.assertFalse((await session.call_tool('sw_active_document')).isError)

    async def test_production_connection_review_over_stdio(self):
        from pathlib import Path
        import tempfile
        from anyio import fail_after
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from tests.test_mates import connection_fixture
        root = Path.cwd()
        (root / 'outputs').mkdir(exist_ok=True)
        parameters = StdioServerParameters(command=sys.executable, args=['-m', 'cadkin.mcp_server'])
        with tempfile.TemporaryDirectory(dir=root / 'outputs') as directory, fail_after(20):
            base = Path(directory)
            args = {k: str(base / v) for k, v in connection_fixture(base).items()}
            async with stdio_client(parameters) as (read, write):
                async with ClientSession(read, write) as session:
                    init = await session.initialize()
                    self.assertEqual(init.serverInfo.version, '0.9.0')
                    result = await session.call_tool('cad_review_connections', args)
                    self.assertFalse(result.isError, result)
                    self.assertEqual(result.structuredContent['data']['counts']['has_unsuppressed_mate_evidence'], 1)
                    repeated = await session.call_tool('cad_review_connections', args)
                    self.assertTrue(repeated.isError)
                    self.assertEqual(repeated.structuredContent['errors'][0]['code'], 'OUTPUT_EXISTS')
                    self.assertEqual(len((await session.list_tools()).tools), 23)
