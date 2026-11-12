"""Explicit synthetic fixture for guarded face-probe reintegration tests."""
from cadkin.tools.execution import run_plan
from cadkin.tools.files import read_json
from tests.execution_fakes import write_execution_fixture, live_service


def prepare(root, include_face_review=True):
    app = write_execution_fixture(root, include_face_review=include_face_review)
    service = live_service(root, app)
    try:
        assert run_plan(service, 'outputs/plan.json', 'outputs/bootstrap-run.json')['data']['guards_passed']
        for tool, args in [
            ('cad_index_evidence', dict(draft_check_path='outputs/check.json', execution_path='outputs/bootstrap-run.json', output_path='outputs/bootstrap-index.json')),
            ('cad_plan_face_probes', dict(draft_check_path='outputs/check.json', evidence_index_path='outputs/bootstrap-index.json',
                max_component_gap_mm=30, surface_tolerance_mm=.1, output_path='outputs/face-plan.json'))]:
            result = service.call(tool, args); assert result['status'] != 'error', result
        run = run_plan(service, 'outputs/face-plan.json', 'outputs/face-run.json')['data']
        assert run['execution_complete'] and run['guards_passed'], run
        probes = [r['envelope_source']['path'] for r in run['records'] if r['task_id'] in run['eligible_capture_ids']]
        result = service.call('cad_review_face_contacts', dict(probe_paths=probes, contact_tolerance_mm=.2,
            angle_tolerance_deg=7, output_path='outputs/supplied-review.json'))
        assert result['status'] != 'error', result
        captures = {}
        for record in run['records']:
            if record['task_id'] in run['eligible_capture_ids']:
                raw, _ = read_json(root/record['envelope_source']['path'])
                captures[record['task_id']] = {'tool': 'sw_probe_face_pair', 'data': raw['data'], 'source': record['envelope_source']}
        return app, run, captures
    finally: service.close()
