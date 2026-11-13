import importlib.util
import sys
import unittest


@unittest.skipUnless(importlib.util.find_spec('mcp'), 'Install .[solidworks] for protocol integration tests')
class McpTests(unittest.IsolatedAsyncioTestCase):
    async def test_geometry_analysis_capture_and_stop_over_stdio(self):
        from pathlib import Path
        import tempfile
        from anyio import fail_after
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from cadkin.tools.geometric_connections import replay_geometry_analysis
        with tempfile.TemporaryDirectory() as directory, fail_after(180):
            root=Path(directory)
            fixture=StdioServerParameters(command=sys.executable,args=['-m','tests.geometry_mcp_fixture','--root',str(root)])
            async with stdio_client(fixture) as (read,write):
                async with ClientSession(read,write) as session:
                    await session.initialize()
                    self.assertEqual(len((await session.list_tools()).tools),52)
                    args={'target_graph_path':'outputs/target.json','distance_tolerance_mm':.1,'angle_tolerance_deg':.1,'output_path':'outputs/geometry.json'}
                    analyzed=await session.call_tool('cad_analyze_geometric_connections',args)
                    self.assertFalse(analyzed.isError,analyzed);self.assertNotIn('pairs',analyzed.structuredContent['data'])
                    plan=await session.call_tool('cad_plan_evidence_tasks',{'draft_check_path':'outputs/check.json',
                        'geometry_analysis_path':'outputs/geometry.json','output_path':'outputs/geometry-plan.json'})
                    self.assertFalse(plan.isError,plan);self.assertEqual(plan.structuredContent['data']['algorithm_version'],6)
                    previous=None
                    for n in range(7):
                        batch={'plan_path':'outputs/geometry-plan.json','output_path':f'outputs/batch-{n}.json','time_budget_seconds':60}
                        if previous:batch['previous_execution_path']=previous
                        result=await session.call_tool('sw_execute_evidence_batch',batch)
                        self.assertFalse(result.isError,result);d=result.structuredContent['data'];previous=d['execution_source']['path']
                        if d['execution_complete']:break
                    self.assertTrue(d['execution_complete']);self.assertTrue(d['guards_passed'])
            production=StdioServerParameters(command=sys.executable,args=['-m','cadkin.mcp_server','--root',str(root)])
            async with stdio_client(production) as (read,write):
                async with ClientSession(read,write) as session:
                    await session.initialize()
                    indexed=await session.call_tool('cad_index_evidence',{'draft_check_path':'outputs/check.json',
                        'execution_path':previous,'output_path':'outputs/index.json'})
                    self.assertFalse(indexed.isError,indexed)
                    after=await session.call_tool('cad_analyze_geometric_connections',{**args,'evidence_index_path':'outputs/index.json','output_path':'outputs/after.json'})
                    self.assertFalse(after.isError,after)
                    data,_=replay_geometry_analysis(root,'outputs/after.json')
                    self.assertEqual(data['rounds_completed'],1);self.assertEqual(data['pairs'][0]['target_joint_kind'],'unknown')
                    self.assertEqual(len(data['pairs'][0]['distance_observations']),1)
                    stopped=await session.call_tool('cad_plan_evidence_tasks',{'draft_check_path':'outputs/check.json',
                        'geometry_analysis_path':'outputs/after.json','output_path':'outputs/stop.json'})
                    self.assertFalse(stopped.isError,stopped);self.assertEqual(stopped.structuredContent['data']['tasks'],[])
                    rejected=await session.call_tool('cad_solve_chain_constraints',{'constraint_analysis_path':'outputs/after.json',
                        'reference_occurrence_path':'base-1','characteristic_length_mm':100,'output_path':'outputs/invalid-solution.json'})
                    self.assertTrue(rejected.isError)
                    self.assertEqual(rejected.structuredContent['errors'][0]['code'],'INVALID_CONSTRAINT_SOURCE')

    async def test_root_mates_without_cylinders_over_production_stdio(self):
        from pathlib import Path
        import tempfile
        import json
        from anyio import fail_after
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from tests.constraint_fakes import write_constraint_fixture
        from cadkin.tools.chain_motion import replay_chain_solution
        with tempfile.TemporaryDirectory() as directory, fail_after(120):
            root = Path(directory)
            write_constraint_fixture(root, mode='chain_closed', enriched=True)
            # Only the original spatial and mate envelopes exist for the production server.
            for path in root.rglob('*.json'):
                if path not in (root/'inventory.json', root/'constraint-mates.json'): path.unlink()
            server = StdioServerParameters(command=sys.executable, args=['-m', 'cadkin.mcp_server', '--root', str(root)])
            async with stdio_client(server) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    listed = (await session.list_tools()).tools
                    self.assertEqual(len(listed), 52)
                    schema = next(t for t in listed if t.name == 'cad_review_root_mates').inputSchema
                    self.assertEqual(set(schema['required']), {'inventory_path', 'mate_inventory_path', 'output_path'})
                    for tool, args in [
                        ('cad_review_root_mates', {'inventory_path': 'inventory.json', 'mate_inventory_path': 'constraint-mates.json', 'output_path': 'outputs/native.json'}),
                        ('cad_build_chain_evidence', {'inventory_path': 'inventory.json', 'occurrence_paths': ['base-1', 'carriage-1', 'rail-1'],
                            'chain_name': 'Synthetic mate-only chain', 'evidence_paths': ['outputs/native.json'], 'output_path': 'outputs/native-chain.json'}),
                        ('cad_build_target_graph', {'chain_path': 'outputs/native-chain.json', 'output_path': 'outputs/native-target.json'}),
                        ('cad_analyze_constraints', {'target_graph_path': 'outputs/native-target.json', 'distance_tolerance_mm': .1,
                            'angle_tolerance_deg': .1, 'output_path': 'outputs/native-analysis.json'}),
                        ('cad_solve_chain_constraints', {'constraint_analysis_path': 'outputs/native-analysis.json', 'reference_occurrence_path': 'base-1',
                            'characteristic_length_mm': 100, 'output_path': 'outputs/native-solution.json'})]:
                        result = await session.call_tool(tool, args)
                        self.assertFalse(result.isError, result)
                    solution, _ = replay_chain_solution(root, 'outputs/native-solution.json')
                    self.assertEqual(solution['snapshots'][0]['modeled_chain_instantaneous_dof'], 0)
                    self.assertFalse(solution['finite_motion_verified'])
                    target = json.loads((root/'outputs/native-target.json').read_text(encoding='utf-8'))
                    self.assertEqual(target['relation_sources'], [])
                    repeated = await session.call_tool('cad_review_root_mates', {'inventory_path': 'inventory.json',
                        'mate_inventory_path': 'constraint-mates.json', 'output_path': 'outputs/native.json'})
                    self.assertTrue(repeated.isError)
                    self.assertEqual(repeated.structuredContent['errors'][0]['code'], 'OUTPUT_EXISTS')

    async def test_first_chain_baseline_over_production_stdio(self):
        from pathlib import Path
        import tempfile
        import json
        from anyio import fail_after
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from tests.chain_session_fakes import session_fixture
        from cadkin.tools.chain_session import run_chain_session
        from cadkin.tools.observation_index import replay_index
        with tempfile.TemporaryDirectory() as directory, fail_after(120):
            root = Path(directory)
            service, _, _, _ = session_fixture(root)
            try:
                result = run_chain_session(service, 'config.json', 'outputs/session.json')
                self.assertEqual(result['status'], 'ok', result)
            finally: service.close()
            baseline = json.loads(Path(result['data']['handoffs']['baseline']['path']).read_text(encoding='utf-8'))
            server = StdioServerParameters(command=sys.executable, args=['-m', 'cadkin.mcp_server', '--root', str(root)])
            async with stdio_client(server) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    args = {'execution_path': baseline['execution_source']['path'], 'output_path': 'outputs/offline-baseline.json',
                            'distance_tolerance_mm': .1, 'angle_tolerance_deg': .1}
                    created = await session.call_tool('cad_create_chain_baseline', args)
                    self.assertFalse(created.isError, created)
                    data = created.structuredContent['data']; self.assertTrue(data['baseline_created'])
                    index, _ = replay_index(root, data['outputs']['index']['path'])
                    self.assertEqual(index['rounds_completed'], 1)
                    stopped = await session.call_tool('cad_create_chain_baseline', args)
                    self.assertTrue(stopped.isError)
                    self.assertEqual(len((await session.list_tools()).tools), 52)

    async def test_batched_capture_and_chain_solution_over_stdio(self):
        from pathlib import Path
        import tempfile
        from anyio import fail_after
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from cadkin.tools.chain_motion import replay_chain_solution
        with tempfile.TemporaryDirectory() as directory, fail_after(180):
            root=Path(directory)
            fixture=StdioServerParameters(command=sys.executable,args=['-m','tests.constraint_followup_mcp_fixture','--root',str(root)])
            async with stdio_client(fixture) as (read,write):
                async with ClientSession(read,write) as session:
                    await session.initialize()
                    first=await session.call_tool('sw_execute_evidence_batch',{'plan_path':'outputs/plan.json','output_path':'outputs/first.json','max_steps':3})
                    self.assertFalse(first.isError,first);self.assertFalse(first.structuredContent['data']['guards_passed'])
                    second=await session.call_tool('sw_execute_evidence_batch',{'plan_path':'outputs/plan.json','output_path':'outputs/second.json',
                        'previous_execution_path':first.structuredContent['data']['execution_source']['path'],'time_budget_seconds':60})
                    self.assertFalse(second.isError,second);self.assertTrue(second.structuredContent['data']['guards_passed'])
                    execution=second.structuredContent['data']['execution_source']['path']
            server=StdioServerParameters(command=sys.executable,args=['-m','cadkin.mcp_server','--root',str(root)])
            async with stdio_client(server) as (read,write):
                async with ClientSession(read,write) as session:
                    await session.initialize()
                    updated=await session.call_tool('cad_reintegrate_evidence',{'execution_path':execution,'output_path':'outputs/updated.json'})
                    self.assertFalse(updated.isError,updated)
                    args={'constraint_analysis_path':updated.structuredContent['data']['after_constraint_analysis_source']['path'],
                        'reference_occurrence_path':'base-1','characteristic_length_mm':100,'output_path':'outputs/chain-motion.json'}
                    solved=await session.call_tool('cad_solve_chain_constraints',args)
                    self.assertFalse(solved.isError,solved);data=solved.structuredContent['data']
                    self.assertEqual(data['rounds_completed'],1);self.assertEqual(data['snapshots'][0]['status'],'partial_constraint_model')
                    self.assertIsNone(data['snapshots'][0]['modeled_chain_instantaneous_dof'])
                    replay_chain_solution(root,data['output_path'])
                    bad=await session.call_tool('cad_solve_chain_constraints',{**args,'reference_occurrence_path':'absent'})
                    self.assertTrue(bad.isError)
                    self.assertEqual(len((await session.list_tools()).tools),52)

    async def test_local_constraint_solution_over_production_stdio(self):
        from pathlib import Path
        import tempfile
        from anyio import fail_after
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from tests.constraint_fakes import write_constraint_followup_fixture
        from cadkin.tools.local_motion import replay_solution
        with tempfile.TemporaryDirectory() as directory, fail_after(120):
            root=Path(directory);write_constraint_followup_fixture(root,enriched=True)
            server=StdioServerParameters(command=sys.executable,args=['-m','cadkin.mcp_server','--root',str(root)])
            async with stdio_client(server) as (read,write):
                async with ClientSession(read,write) as session:
                    await session.initialize()
                    listed=(await session.list_tools()).tools
                    self.assertEqual(len(listed),52)
                    schema=next(t for t in listed if t.name=='cad_solve_local_constraints').inputSchema
                    self.assertIn('characteristic_length_mm',schema['required'])
                    args={'constraint_analysis_path':'outputs/constraints.json','characteristic_length_mm':100,'output_path':'outputs/local.json'}
                    result=await session.call_tool('cad_solve_local_constraints',args)
                    self.assertFalse(result.isError,result)
                    data=result.structuredContent['data']
                    pair=next(p for p in data['pairs'] if p['occurrence_paths']==['base-1','carriage-1'])
                    self.assertEqual(pair['snapshots'][0]['modeled_instantaneous_dof'],1)
                    self.assertEqual(pair['target_joint_kind'],'unknown');self.assertFalse(data['assembly_dof_solved'])
                    replay_solution(root,'outputs/local.json')
                    failed=await session.call_tool('cad_solve_local_constraints',{**args,'characteristic_length_mm':0})
                    self.assertTrue(failed.isError)
                    repeated=await session.call_tool('cad_solve_local_constraints',args)
                    self.assertEqual(repeated.structuredContent['errors'][0]['code'],'OUTPUT_EXISTS')
                    recovered=await session.call_tool('cad_solve_local_constraints',{**args,'output_path':'outputs/recovered.json'})
                    self.assertFalse(recovered.isError,recovered)

    async def test_constraint_followup_capture_reintegration_and_stop_over_stdio(self):
        from pathlib import Path
        import tempfile
        from anyio import fail_after
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        with tempfile.TemporaryDirectory() as directory, fail_after(180):
            root = Path(directory)
            fixture = StdioServerParameters(command=sys.executable, args=['-m','tests.constraint_followup_mcp_fixture','--root',str(root)])
            async with stdio_client(fixture) as (read,write):
                async with ClientSession(read,write) as session:
                    await session.initialize()
                    plan = await session.call_tool('cad_plan_evidence_tasks', {'draft_check_path':'outputs/check.json',
                        'constraint_analysis_path':'outputs/constraints.json','output_path':'outputs/protocol-plan.json'})
                    self.assertFalse(plan.isError,plan); self.assertEqual(plan.structuredContent['data']['algorithm_version'],4)
                    previous = None
                    for number in range(9):
                        args = {'plan_path':'outputs/protocol-plan.json','output_path':f'outputs/step-{number}.json'}
                        if previous: args['previous_execution_path'] = previous
                        result = await session.call_tool('sw_execute_evidence_task', args)
                        self.assertFalse(result.isError,result); previous = result.structuredContent['data']['output_path']
                    self.assertTrue(result.structuredContent['data']['guards_passed'])
                    self.assertEqual(len(result.structuredContent['data']['eligible_capture_ids']),1)
            # Reintegrate and resume using the production server, without a CAD backend.
            server = StdioServerParameters(command=sys.executable,args=['-m','cadkin.mcp_server','--root',str(root)])
            async with stdio_client(server) as (read,write):
                async with ClientSession(read,write) as session:
                    await session.initialize()
                    result = await session.call_tool('cad_reintegrate_evidence', {'execution_path':previous,'output_path':'outputs/updated.json'})
                    self.assertFalse(result.isError,result); update = result.structuredContent['data']
                    self.assertTrue(update['recomputation_complete']); self.assertEqual(update['algorithm_version'],3)
                    plan = await session.call_tool('cad_plan_evidence_tasks', {'draft_check_path':update['after_check_source']['path'],
                        'constraint_analysis_path':update['after_constraint_analysis_source']['path'],'output_path':'outputs/stop.json'})
                    self.assertFalse(plan.isError,plan); data = plan.structuredContent['data']
                    self.assertEqual(data['tasks'],[]); self.assertEqual(data['continuation']['rounds_completed'],1)
                    self.assertEqual(data['evidence_index_source'], update['after_evidence_index_source'])
                    stopped = await session.call_tool('sw_execute_evidence_task', {'plan_path':'outputs/stop.json','output_path':'outputs/blocked.json'})
                    self.assertTrue(stopped.isError); self.assertEqual(stopped.structuredContent['errors'][0]['code'],'NO_CAPTURE_TASKS')
                    self.assertEqual(len((await session.list_tools()).tools),52)

    async def test_constraint_analysis_over_production_stdio(self):
        from pathlib import Path
        import tempfile
        from anyio import fail_after
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from tests.constraint_fakes import write_constraint_fixture
        with tempfile.TemporaryDirectory() as directory, fail_after(120):
            root=Path(directory);write_constraint_fixture(root)
            server=StdioServerParameters(command=sys.executable,args=['-m','cadkin.mcp_server','--root',str(root)])
            async with stdio_client(server) as (read,write):
                async with ClientSession(read,write) as session:
                    await session.initialize()
                    tools=(await session.list_tools()).tools
                    self.assertEqual(len(tools),52)
                    schema=next(t for t in tools if t.name=='sw_mate_inventory').inputSchema
                    self.assertIn('include_reference_geometry',schema['properties'])
                    args=dict(target_graph_path='outputs/target.json',output_path='outputs/constraints.json',
                              distance_tolerance_mm=.1,angle_tolerance_deg=.1)
                    result=await session.call_tool('cad_analyze_constraints',args)
                    self.assertFalse(result.isError,result)
                    pairs=result.structuredContent['data']['pairs']
                    pair=next(p for p in pairs if p['occurrence_paths']==['base-1','carriage-1'])
                    self.assertEqual(pair['snapshots'][0]['candidates'][0]['kind'],'revolute')
                    self.assertEqual(pair['target_joint_kind'],'unknown')
                    failed=await session.call_tool('cad_analyze_constraints',{**args,'max_pairs':0})
                    self.assertTrue(failed.isError)
                    limited=await session.call_tool('cad_analyze_constraints',{**args,'output_path':'outputs/limited.json','max_pairs':1})
                    self.assertFalse(limited.isError)
                    self.assertEqual(limited.structuredContent['status'],'partial')
                    self.assertEqual(len((await session.list_tools()).tools),52)

    async def test_template_free_target_draft_and_plan_over_stdio(self):
        from pathlib import Path
        import tempfile
        from anyio import fail_after
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from tests.chain_fakes import write_chain_fixture
        with tempfile.TemporaryDirectory() as directory, fail_after(120):
            root = Path(directory); args = write_chain_fixture(root, with_lock=True)
            server = StdioServerParameters(command=sys.executable, args=['-m', 'cadkin.mcp_server', '--root', str(root)])
            async with stdio_client(server) as (read, write):
                async with ClientSession(read, write) as session:
                    initialized = await session.initialize(); self.assertEqual(initialized.serverInfo.version, '0.28.0')
                    for name, arguments in [
                        ('cad_build_chain_evidence', args),
                        ('cad_build_target_graph', dict(chain_path='outputs/chain.json', output_path='outputs/target.json')),
                        ('cad_build_rigid_candidates', dict(target_graph_path='outputs/target.json', output_path='outputs/rigid.json')),
                        ('cad_draft_joints', dict(rigid_candidates_path='outputs/rigid.json', output_path='outputs/draft.json'))]:
                        result = await session.call_tool(name, arguments); self.assertFalse(result.isError, result)
                    draft = result.structuredContent['data']
                    self.assertEqual(draft['template_sources'], []); self.assertGreater(draft['summary']['target_pairs_returned'], 0)
                    self.assertTrue(all(p['target_joint_kind'] == 'unknown' and p['target_degrees_of_freedom'] is None
                        for run in draft['partition_results'] for p in run['connection_candidates']))
                    checked = await session.call_tool('cad_check_joint_draft', dict(joint_draft_path='outputs/draft.json', output_path='outputs/check.json'))
                    self.assertFalse(checked.isError, checked)
                    planned = await session.call_tool('cad_plan_evidence_tasks', dict(draft_check_path='outputs/check.json', output_path='outputs/plan.json'))
                    self.assertFalse(planned.isError, planned)
                    self.assertEqual(len((await session.list_tools()).tools), 52)

    @unittest.skipUnless(importlib.util.find_spec('pxr'), 'Install .[templates] for face planning protocol tests')
    async def test_face_planning_execution_index_and_stop_over_stdio(self):
        from pathlib import Path
        import tempfile
        from anyio import fail_after
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        with tempfile.TemporaryDirectory() as directory, fail_after(300):
            root = Path(directory)
            server = StdioServerParameters(command=sys.executable, args=['-m', 'tests.face_planning_mcp_fixture', '--root', str(root)])
            async with stdio_client(server) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    index_path = 'outputs/bootstrap-index.json'
                    for round_number, expected_tool in ((2, 'sw_component_faces'), (3, 'sw_probe_face_pair')):
                        args = {'draft_check_path': 'outputs/check.json', 'evidence_index_path': index_path,
                            'output_path': f'outputs/face-plan-{round_number}.json', 'max_component_gap_mm': 30, 'surface_tolerance_mm': .1}
                        r = await session.call_tool('cad_plan_face_probes', args)
                        self.assertFalse(r.isError, r); plan = r.structuredContent['data']
                        self.assertEqual({t['tool'] for t in plan['tasks'] if t['phase'] == 'capture'}, {expected_tool})
                        previous = None
                        for step in range(len(plan['tasks'])):
                            arguments = {'plan_path': args['output_path'], 'output_path': f'outputs/face-{round_number}-step-{step}.json'}
                            if previous: arguments['previous_execution_path'] = previous
                            r = await session.call_tool('sw_execute_evidence_task', arguments)
                            self.assertFalse(r.isError, r); execution = r.structuredContent['data']; previous = execution['output_path']
                            if execution['execution_complete']: break
                        self.assertTrue(execution['guards_passed'])
                        index_path = f'outputs/face-index-{round_number}.json'
                        r = await session.call_tool('cad_index_evidence', {'draft_check_path': 'outputs/check.json',
                            'execution_path': previous, 'output_path': index_path})
                        self.assertFalse(r.isError, r)
                        self.assertEqual(r.structuredContent['data']['rounds_completed'], round_number)
                    probes = [o['source']['path'] for o in r.structuredContent['data']['observations'] if o['family'] == 'face_probes']
                    self.assertEqual(len(probes), 12)
            # Offline calls now use the production entrypoint with no fake backend.
            server = StdioServerParameters(command=sys.executable, args=['-m', 'cadkin.mcp_server', '--root', str(root)])
            async with stdio_client(server) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    r = await session.call_tool('cad_plan_face_probes', {**args, 'evidence_index_path': index_path, 'output_path': 'outputs/stopped.json'})
                    self.assertFalse(r.isError, r); self.assertEqual(r.structuredContent['data']['tasks'], [])
                    r = await session.call_tool('cad_review_face_contacts', {'probe_paths': probes, 'output_path': 'outputs/probe-review.json',
                        'contact_tolerance_mm': .1, 'angle_tolerance_deg': 5})
                    self.assertFalse(r.isError, r); self.assertFalse(r.structuredContent['data']['contact_confirmed'])
                    r = await session.call_tool('cad_reintegrate_evidence', {'execution_path': previous,
                        'face_review_path': 'outputs/probe-review.json', 'output_path': 'outputs/face-updated.json'})
                    self.assertFalse(r.isError, r); update = r.structuredContent['data']
                    self.assertTrue(update['recomputation_complete']); self.assertEqual(len(update['applied_capture_ids']), 12)
                    r = await session.call_tool('cad_compare_draft_checks', {'before_check_path': 'outputs/check.json',
                        'after_check_path': update['after_check_source']['path'], 'output_path': 'outputs/face-comparison.json'})
                    self.assertFalse(r.isError, r); self.assertEqual(r.structuredContent['data']['face_evidence']['summary']['newly_observed_ids'], 12)
                    r = await session.call_tool('cad_index_evidence', {'draft_check_path': update['after_check_source']['path'],
                        'execution_path': previous, 'output_path': 'outputs/updated-index.json'})
                    self.assertFalse(r.isError, r); self.assertEqual(r.structuredContent['data']['rounds_completed'], 3)
                    r = await session.call_tool('cad_plan_face_probes', {**args, 'draft_check_path': update['after_check_source']['path'],
                        'evidence_index_path': 'outputs/updated-index.json', 'output_path': 'outputs/updated-stop.json'})
                    self.assertFalse(r.isError, r); self.assertEqual(r.structuredContent['data']['tasks'], [])
                    r = await session.call_tool('sw_execute_evidence_task', {'plan_path': 'outputs/stopped.json', 'output_path': 'outputs/rejected.json'})
                    self.assertTrue(r.isError); self.assertEqual(r.structuredContent['errors'][0]['code'], 'NO_CAPTURE_TASKS')
                    self.assertFalse((root/'outputs/rejected.json').exists())
                    self.assertEqual(len((await session.list_tools()).tools), 52)

    @unittest.skipUnless(importlib.util.find_spec('pxr'), 'Install .[templates] for execution protocol tests')
    async def test_guarded_execution_and_offline_reintegration_over_stdio(self):
        import json
        from pathlib import Path
        import tempfile
        from anyio import fail_after
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        with tempfile.TemporaryDirectory() as directory, fail_after(120):
            root=Path(directory)
            fixture=StdioServerParameters(command=sys.executable,args=['-m','tests.execution_mcp_fixture','--root',str(root)])
            async with stdio_client(fixture) as (read,write):
                async with ClientSession(read,write) as session:
                    init=await session.initialize();self.assertEqual(init.serverInfo.version,'0.28.0')
                    previous=None
                    for index in range(20):
                        args={'plan_path':'outputs/plan.json','output_path':f'outputs/protocol-step-{index}.json'}
                        if previous is not None:args['previous_execution_path']=previous
                        result=await session.call_tool('sw_execute_evidence_task',args)
                        self.assertFalse(result.isError,result);data=result.structuredContent['data']
                        self.assertEqual(data['summary']['calls_executed'],index+1)
                        previous=data['output_path']
                        if data['execution_complete']:break
                    self.assertTrue(data['execution_complete']);self.assertTrue(data['guards_passed'])
                    self.assertGreater(len(data['eligible_capture_ids']),0)
            # Reopen the production server with no fake CAD factory; all further operations are offline.
            server=StdioServerParameters(command=sys.executable,args=['-m','cadkin.mcp_server','--root',str(root)])
            async with stdio_client(server) as (read,write):
                async with ClientSession(read,write) as session:
                    await session.initialize()
                    updated=await session.call_tool('cad_reintegrate_evidence',{'execution_path':previous,'output_path':'outputs/reintegrated.json'})
                    self.assertFalse(updated.isError,updated);d=updated.structuredContent['data']
                    self.assertTrue(d['recomputation_complete']);self.assertTrue(d['applied_capture_ids'])
                    compared=await session.call_tool('cad_compare_draft_checks',{'before_check_path':'outputs/check.json',
                        'after_check_path':d['after_check_source']['path'],'output_path':'outputs/compared.json'})
                    self.assertFalse(compared.isError,compared);self.assertFalse(compared.structuredContent['data']['resolved_findings_asserted'])
                    indexed=await session.call_tool('cad_index_evidence',{'draft_check_path':d['after_check_source']['path'],
                        'execution_path':previous,'output_path':'outputs/observations.json'})
                    self.assertFalse(indexed.isError,indexed)
                    planned=await session.call_tool('cad_plan_evidence_tasks',{'draft_check_path':d['after_check_source']['path'],
                        'evidence_index_path':'outputs/observations.json','output_path':'outputs/next-plan.json'})
                    self.assertFalse(planned.isError,planned);self.assertEqual(planned.structuredContent['data']['continuation']['action'],'collect')
                    # Recovered cylinders expose ambiguous target axes beyond the reference window.
                    # Only the missing rail catalog is new; completed first-round scans are reused.
                    captures = [t for t in planned.structuredContent['data']['tasks'] if t['phase']=='capture']
                    self.assertEqual([(t['tool'], t['arguments'].get('occurrence_path')) for t in captures], [('sw_component_faces', 'rail-1')])
                    bounded=await session.call_tool('cad_plan_evidence_tasks',{'draft_check_path':d['after_check_source']['path'],
                        'evidence_index_path':'outputs/observations.json','max_tasks':3,'output_path':'outputs/budget-stop.json'})
                    self.assertFalse(bounded.isError,bounded);self.assertEqual(bounded.structuredContent['data']['continuation']['action'],'stop')
                    stopped=await session.call_tool('sw_execute_evidence_task',{'plan_path':'outputs/budget-stop.json','output_path':'outputs/no-call.json'})
                    self.assertTrue(stopped.isError);self.assertEqual(stopped.structuredContent['errors'][0]['code'],'NO_CAPTURE_TASKS')
                    receipt=json.loads(Path(previous).read_text(encoding='utf-8'));receipt['guards_passed']=False
                    tampered=root/'outputs/tampered-execution.json';tampered.write_text(json.dumps(receipt),encoding='utf-8')
                    bad=await session.call_tool('cad_reintegrate_evidence',{'execution_path':str(tampered),'output_path':'outputs/rejected.json'})
                    self.assertTrue(bad.isError);self.assertEqual(bad.structuredContent['errors'][0]['code'],'EVIDENCE_MISMATCH')
                    self.assertEqual(len((await session.list_tools()).tools),52)

    @unittest.skipUnless(importlib.util.find_spec('pxr'), 'Install .[templates] for evidence planning tests')
    async def test_production_draft_check_and_task_plan_over_stdio(self):
        import json
        from pathlib import Path
        import tempfile
        from anyio import fail_after
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from tests.followup_fakes import write_draft_fixture
        from cadkin.tools.solidworks import SolidWorksTools
        with tempfile.TemporaryDirectory() as directory, fail_after(40):
            root=Path(directory);write_draft_fixture(root,lambda r:SolidWorksTools(r))
            server=StdioServerParameters(command=sys.executable,args=['-m','cadkin.mcp_server','--root',str(root)])
            async with stdio_client(server) as (read,write):
                async with ClientSession(read,write) as session:
                    init=await session.initialize();self.assertEqual(init.serverInfo.version,'0.28.0')
                    checked=await session.call_tool('cad_check_joint_draft',{'joint_draft_path':'outputs/drafts.json','output_path':'outputs/check.json'})
                    self.assertFalse(checked.isError);self.assertEqual(checked.structuredContent['status'],'partial')
                    args={'draft_check_path':'outputs/check.json','output_path':'outputs/plan.json'}
                    plan=await session.call_tool('cad_plan_evidence_tasks',args)
                    self.assertFalse(plan.isError);data=plan.structuredContent['data'];self.assertFalse(data['executed'])
                    self.assertGreater(data['summary']['planned_capture_tasks'],0)
                    self.assertTrue(all(not Path(t['save_envelope_path']).exists() for t in data['tasks']))
                    small=await session.call_tool('cad_plan_evidence_tasks',{**args,'output_path':'outputs/small-plan.json','max_tasks':3})
                    self.assertEqual(small.structuredContent['status'],'partial')
                    raw=json.loads((root/'outputs/check.json').read_text(encoding='utf-8'));raw['findings']=[]
                    (root/'outputs/check.json').write_text(json.dumps(raw),encoding='utf-8')
                    bad=await session.call_tool('cad_plan_evidence_tasks',{**args,'output_path':'outputs/bad-plan.json'})
                    self.assertTrue(bad.isError);self.assertEqual(bad.structuredContent['errors'][0]['code'],'EVIDENCE_MISMATCH')
                    self.assertEqual(len((await session.list_tools()).tools),52)

    @unittest.skipUnless(importlib.util.find_spec('pxr'), 'Install .[templates] for joint draft protocol tests')
    async def test_production_rigid_and_joint_drafts_over_stdio(self):
        import json
        from pathlib import Path
        import tempfile
        from anyio import fail_after
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from tests.chain_fakes import write_chain_fixture
        with tempfile.TemporaryDirectory() as directory, fail_after(40):
            root=Path(directory);chain_args=write_chain_fixture(root,with_lock=True)
            server=StdioServerParameters(command=sys.executable,args=['-m','cadkin.mcp_server','--root',str(root)])
            async with stdio_client(server) as (read,write):
                async with ClientSession(read,write) as session:
                    await session.initialize()
                    for name,args in [('cad_build_chain_evidence',chain_args),
                        ('cad_build_target_graph',{'chain_path':'outputs/chain.json','output_path':'outputs/target.json'}),
                        ('cad_build_rigid_candidates',{'target_graph_path':'outputs/target.json','output_path':'outputs/rigid.json'})]:
                        result=await session.call_tool(name,args);self.assertFalse(result.isError)
                    args={'rigid_candidates_path':'outputs/rigid.json','output_path':'outputs/drafts.json',
                          'template_ids':['gas_lift_bar_stool'],'pattern_size':2}
                    result=await session.call_tool('cad_draft_joints',args)
                    self.assertFalse(result.isError)
                    data=result.structuredContent['data'];self.assertGreater(data['summary']['returned_candidates'],0)
                    self.assertTrue(any(len(m['member_occurrence_paths'])==2 for p in data['partition_results'] for c in p['match']['candidates'] for m in c['mapping']))
                    limited=await session.call_tool('cad_draft_joints',{**args,'output_path':'outputs/limited.json','max_states':1})
                    self.assertEqual(limited.structuredContent['status'],'partial')
                    raw=json.loads((root/'outputs/rigid.json').read_text(encoding='utf-8'));raw['partitions'][0]['groups'][0]['rigidity_confirmed']=True
                    (root/'outputs/rigid.json').write_text(json.dumps(raw),encoding='utf-8')
                    bad=await session.call_tool('cad_draft_joints',{**args,'output_path':'outputs/bad.json'})
                    self.assertTrue(bad.isError);self.assertEqual(bad.structuredContent['errors'][0]['code'],'EVIDENCE_MISMATCH')
                    self.assertEqual(len((await session.list_tools()).tools),52)

    @unittest.skipUnless(importlib.util.find_spec('pxr'), 'Install .[templates] for matching protocol tests')
    async def test_production_target_and_matching_tools_over_stdio(self):
        import json
        from pathlib import Path
        import tempfile
        from anyio import fail_after
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from tests.chain_fakes import write_chain_fixture
        with tempfile.TemporaryDirectory() as directory, fail_after(40):
            root=Path(directory);chain_args=write_chain_fixture(root)
            parameters=StdioServerParameters(command=sys.executable,args=['-m','cadkin.mcp_server','--root',str(root)])
            async with stdio_client(parameters) as (read,write):
                async with ClientSession(read,write) as session:
                    init=await session.initialize();self.assertEqual(init.serverInfo.version,'0.28.0')
                    chain=await session.call_tool('cad_build_chain_evidence',chain_args)
                    self.assertFalse(chain.isError)
                    target=await session.call_tool('cad_build_target_graph',{'chain_path':'outputs/chain.json','output_path':'outputs/target.json'})
                    self.assertFalse(target.isError);self.assertEqual(target.structuredContent['data']['coverage']['nodes'],3)
                    args={'target_graph_path':'outputs/target.json','template_ids':['gas_lift_bar_stool'],'output_path':'outputs/matches.json'}
                    result=await session.call_tool('cad_match_mechanism_templates',args)
                    self.assertFalse(result.isError);self.assertTrue(result.structuredContent['data']['candidates'])
                    self.assertFalse(result.structuredContent['data']['mechanical_relation_confirmed'])
                    budget=await session.call_tool('cad_match_mechanism_templates',{**args,'max_states':1,'output_path':'outputs/limited.json'})
                    self.assertEqual(budget.structuredContent['status'],'partial');self.assertFalse(budget.structuredContent['data']['search_exhaustive'])
                    raw=json.loads((root/'outputs/target.json').read_text(encoding='utf-8'));raw['pairs'][0]['link_support']=.123
                    (root/'outputs/target.json').write_text(json.dumps(raw),encoding='utf-8')
                    bad=await session.call_tool('cad_match_mechanism_templates',{**args,'output_path':'outputs/bad.json'})
                    self.assertTrue(bad.isError);self.assertEqual(bad.structuredContent['errors'][0]['code'],'EVIDENCE_MISMATCH')
                    self.assertEqual(len((await session.list_tools()).tools),52)

    @unittest.skipUnless(importlib.util.find_spec('pxr'), 'Install .[templates] for USD protocol tests')
    async def test_production_reference_tools_and_recovery_over_stdio(self):
        import hashlib
        import json
        from pathlib import Path
        import tempfile
        from anyio import fail_after
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        with tempfile.TemporaryDirectory() as directory, fail_after(25):
            base=Path(directory)
            parameters=StdioServerParameters(command=sys.executable,args=['-m','cadkin.mcp_server','--root',str(base)])
            async with stdio_client(parameters) as (read,write):
                async with ClientSession(read,write) as session:
                    init=await session.initialize();self.assertEqual(init.serverInfo.version,'0.28.0')
                    listed=await session.call_tool('cad_list_mechanism_templates',{})
                    self.assertEqual(listed.structuredContent['data']['count'],6)
                    extracted=await session.call_tool('cad_extract_mechanism_template',{'template_id':'bench_vise','output_path':'outputs/graph.json'})
                    self.assertFalse(extracted.isError);self.assertEqual(extracted.structuredContent['data']['summary']['joint_count'],7)
                    p=base/'outputs/graph.json';g=json.loads(p.read_text(encoding='utf-8'));digest=hashlib.sha256(p.read_bytes()).hexdigest()
                    m={'body_correspondence_schema_version':1,'reference_sha256':digest,'candidate_sha256':digest,
                       'body_map':[{'candidate_body':b['id'],'reference_body':b['id']} for b in g['bodies']]}
                    (base/'map.json').write_text(json.dumps(m),encoding='utf-8')
                    compared=await session.call_tool('cad_compare_mechanism_graphs',{'reference_path':'outputs/graph.json','candidate_path':'outputs/graph.json','correspondence_path':'map.json','output_path':'outputs/score.json'})
                    self.assertFalse(compared.isError);self.assertEqual(compared.structuredContent['data']['typed_joints']['recall'],1)
                    negative=await session.call_tool('cad_extract_mechanism_template',{'template_id':'gear_meshing_kit','output_path':'outputs/no-joints.json'})
                    self.assertEqual(negative.structuredContent['status'],'partial');self.assertFalse(negative.structuredContent['data']['complete'])
                    bad=await session.call_tool('cad_extract_mechanism_template',{'template_id':'missing','output_path':'outputs/bad.json'})
                    self.assertTrue(bad.isError);self.assertEqual(bad.structuredContent['errors'][0]['code'],'TEMPLATE_NOT_FOUND')
                    self.assertEqual(len((await session.list_tools()).tools),52)

    async def test_production_chain_compile_review_and_errors_over_stdio(self):
        import hashlib
        import json
        from pathlib import Path
        import tempfile
        from anyio import fail_after
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from tests.chain_fakes import write_chain_fixture
        root = Path.cwd(); (root / 'outputs').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root / 'outputs') as directory, fail_after(25):
            base = Path(directory); args = write_chain_fixture(base)
            parameters = StdioServerParameters(command=sys.executable, args=['-m', 'cadkin.mcp_server', '--root', str(base)])
            async with stdio_client(parameters) as (read, write):
                async with ClientSession(read, write) as session:
                    init = await session.initialize(); self.assertEqual(init.serverInfo.version, '0.28.0')
                    result = await session.call_tool('cad_build_chain_evidence', args)
                    self.assertEqual(result.structuredContent['status'], 'ok', result)
                    self.assertEqual(result.structuredContent['data']['coverage']['possible_pairs'], 3)
                    dossier = json.loads((base / 'outputs/chain.json').read_text(encoding='utf-8'))
                    review = {'chain_review_input_schema_version': 1,
                        'chain_sha256': hashlib.sha256((base / 'outputs/chain.json').read_bytes()).hexdigest(),
                        'reviewer': 'Protocol fixture reviewer', 'reviewed_at': '2026-11-12T00:00:00Z',
                        'decisions': [{'pair_id': dossier['pairs'][0]['pair_id'], 'decision': 'pending', 'relation_type': None,
                                       'reason': 'Synthetic pending decision', 'evidence_ids': []}]}
                    (base / 'review.json').write_text(json.dumps(review), encoding='utf-8')
                    result = await session.call_tool('cad_apply_chain_review', {'chain_path': 'outputs/chain.json', 'review_path': 'review.json', 'output_path': 'outputs/reviewed.json'})
                    self.assertFalse(result.isError); self.assertEqual(result.structuredContent['data']['review_counts']['pending'], 3)
                    bad = await session.call_tool('cad_build_chain_evidence', {**args, 'output_path': 'outputs/bad.json', 'occurrence_paths': ['base-1', 'missing']})
                    self.assertTrue(bad.isError); self.assertEqual(bad.structuredContent['errors'][0]['code'], 'INVALID_CHAIN_SCOPE')
                    self.assertEqual(len((await session.list_tools()).tools), 52)

    async def test_face_catalog_probe_review_and_recovery_over_real_stdio(self):
        import json
        from pathlib import Path
        import tempfile
        from anyio import fail_after
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        root = Path.cwd(); (root / 'outputs').mkdir(exist_ok=True)
        parameters = StdioServerParameters(command=sys.executable, args=['-m', 'tests.mcp_fixture', '--face-probe'])
        with tempfile.TemporaryDirectory(dir=root / 'outputs') as directory, fail_after(25):
            base = Path(directory)
            async with stdio_client(parameters) as (read, write):
                async with ClientSession(read, write) as session:
                    init = await session.initialize()
                    self.assertEqual(init.serverInfo.version, '0.28.0')
                    token = (await session.call_tool('sw_active_document')).structuredContent['data']['document_token']
                    selections = []
                    for i, occurrence in enumerate(('plate-1', 'plate-2')):
                        catalog = await session.call_tool('sw_component_faces', {'expected_document_token': token, 'occurrence_path': occurrence})
                        self.assertEqual(catalog.structuredContent['status'], 'ok', catalog)
                        path = base / f'faces-{i}.json'; path.write_text(json.dumps(catalog.structuredContent), encoding='utf-8')
                        selections.append({'face_inventory_path': str(path), 'body_index': 0, 'face_index': i})
                    args = {'expected_document_token': token, 'left': selections[0], 'right': selections[1], 'seed_points_root_mm': [[0, 500, 500]]}
                    probe = await session.call_tool('sw_probe_face_pair', args)
                    self.assertEqual(probe.structuredContent['status'], 'ok', probe)
                    self.assertAlmostEqual(probe.structuredContent['data']['samples'][0]['metrics']['gap_mm'], .05)
                    source = base / 'probe.json'; source.write_text(json.dumps(probe.structuredContent), encoding='utf-8')
                    review = await session.call_tool('cad_review_face_contacts', {'probe_paths': [str(source)], 'output_path': str(base / 'review.json'),
                        'contact_tolerance_mm': .1, 'angle_tolerance_deg': 5})
                    self.assertEqual(review.structuredContent['data']['counts']['near_face_contact_candidate'], 1)
                    self.assertFalse(review.structuredContent['data']['global_minimum_proven'])
                    limited = await session.call_tool('sw_probe_face_pair', {**args, 'max_iterations': 1})
                    self.assertEqual(limited.structuredContent['status'], 'partial')
                    bad = await session.call_tool('sw_probe_face_pair', {**args, 'expected_document_token': '0' * 24})
                    self.assertTrue(bad.isError)
                    self.assertEqual(bad.structuredContent['errors'][0]['code'], 'EVIDENCE_MISMATCH')
                    self.assertEqual(len((await session.list_tools()).tools), 52)

    async def test_proximity_distance_review_and_errors_over_real_stdio(self):
        import json
        from pathlib import Path
        import tempfile
        from anyio import fail_after
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        root = Path.cwd(); (root / 'outputs').mkdir(exist_ok=True)
        parameters = StdioServerParameters(command=sys.executable, args=['-m', 'tests.mcp_fixture', '--distance'])
        with tempfile.TemporaryDirectory(dir=root / 'outputs') as directory, fail_after(25):
            base = Path(directory)
            async with stdio_client(parameters) as (read, write):
                async with ClientSession(read, write) as session:
                    init = await session.initialize()
                    self.assertEqual(init.serverInfo.version, '0.28.0')
                    active = await session.call_tool('sw_active_document')
                    token = active.structuredContent['data']['document_token']
                    spatial = await session.call_tool('sw_spatial_inventory', {'expected_document_token': token})
                    self.assertFalse(spatial.isError, spatial)
                    self.assertTrue(spatial.structuredContent['data']['collection_complete'])
                    (base / 'inventory.json').write_text(json.dumps(spatial.structuredContent), encoding='utf-8')
                    args = {'inventory_path': str(base / 'inventory.json'), 'output_path': str(base / 'proximity.json'), 'max_box_gap_mm': 30}
                    proximity = await session.call_tool('cad_proximity_candidates', args)
                    self.assertFalse(proximity.isError, proximity)
                    self.assertEqual(proximity.structuredContent['data']['coverage']['returned_candidates'], 2)
                    paths = []
                    for i, pair in enumerate((('base-1', 'slider-1'), ('shaft-1', 'slider-1'))):
                        distance = await session.call_tool('sw_component_distance', {'expected_document_token': token,
                            'left_occurrence_path': pair[0], 'right_occurrence_path': pair[1]})
                        self.assertFalse(distance.isError, distance)
                        self.assertEqual(distance.structuredContent['status'], 'ok')
                        paths.append(str(base / f'distance-{i}.json'))
                        Path(paths[-1]).write_text(json.dumps(distance.structuredContent), encoding='utf-8')
                    review = await session.call_tool('cad_review_proximity', {'proximity_path': args['output_path'], 'distance_paths': paths,
                        'contact_tolerance_mm': .1, 'output_path': str(base / 'review.json')})
                    self.assertFalse(review.isError, review)
                    self.assertEqual(review.structuredContent['data']['counts']['near_contact_candidate'], 1)
                    self.assertFalse(review.structuredContent['data']['contact_confirmed'])
                    limited = await session.call_tool('cad_proximity_candidates', {**args, 'max_candidates': 1, 'output_path': str(base / 'limited.json')})
                    self.assertEqual(limited.structuredContent['status'], 'partial')
                    missing = await session.call_tool('cad_review_proximity', {'proximity_path': args['output_path'], 'distance_paths': paths[:1],
                        'contact_tolerance_mm': .1, 'output_path': str(base / 'unmeasured.json')})
                    self.assertEqual(missing.structuredContent['status'], 'partial')
                    self.assertEqual(missing.structuredContent['data']['counts']['unmeasured'], 1)
                    bad = await session.call_tool('sw_component_distance', {'expected_document_token': '0' * 24,
                        'left_occurrence_path': 'base-1', 'right_occurrence_path': 'slider-1'})
                    self.assertTrue(bad.isError)
                    self.assertEqual(bad.structuredContent['errors'][0]['code'], 'DOCUMENT_CHANGED')
                    self.assertEqual(len((await session.list_tools()).tools), 52)

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
                    self.assertEqual(init.serverInfo.version, '0.28.0')
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
                    self.assertEqual(len((await session.list_tools()).tools), 52)

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
                    self.assertEqual(len((await session.list_tools()).tools), 52)

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
                    self.assertEqual(len(tools), 52)
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
                    self.assertEqual(init.serverInfo.version, '0.28.0')
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
                    self.assertEqual(init.serverInfo.version, '0.28.0')
                    result = await session.call_tool('cad_review_connections', args)
                    self.assertFalse(result.isError, result)
                    self.assertEqual(result.structuredContent['data']['counts']['has_unsuppressed_mate_evidence'], 1)
                    repeated = await session.call_tool('cad_review_connections', args)
                    self.assertTrue(repeated.isError)
                    self.assertEqual(repeated.structuredContent['errors'][0]['code'], 'OUTPUT_EXISTS')
                    self.assertEqual(len((await session.list_tools()).tools), 52)
