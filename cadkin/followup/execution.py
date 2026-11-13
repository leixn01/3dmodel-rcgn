"""Pure evaluation of read-only observations and execution dependencies."""
from cadkin.geometry import transform_from_sw
from cadkin.errors import ToolFailure

FATAL_CODES = {'TIMEOUT', 'OUTCOME_UNKNOWN', 'CLOSED', 'DOCUMENT_CHANGED', 'COMPONENT_CHANGED'}
DOCUMENT_FIELDS = ('document_token', 'path', 'title', 'document_type', 'configuration', 'dirty')


def document_matches(actual, expected):
    return (isinstance(actual, dict) and isinstance(expected, dict) and
            type(actual.get('dirty')) is bool and type(expected.get('dirty')) is bool and
            all(k in actual and k in expected and actual[k] == expected[k] for k in DOCUMENT_FIELDS))


def pose_matches(actual, expected, spatial=False):
    if not isinstance(actual, dict) or not isinstance(expected, dict): return False
    fields = {'occurrence_path':'id', 'file_path':'file_path',
              'parent_occurrence_path':'parent_id', 'referenced_configuration':'configuration'}
    if not all(k in actual and v in expected and actual[k] == expected[v] for k,v in fields.items()): return False
    if spatial and (actual.get('is_suppressed') is not False or actual.get('suppression_state') not in (2,3)): return False
    try:
        transform = actual['transform']
        matrix = transform_from_sw(transform['raw_array'])['to_root']
        return transform['to_root'] == matrix == expected['to_root_column_vectors_m']
    except (KeyError, TypeError, ToolFailure): return False


def assess(task, envelope, document):
    """Never accept claimed execution states; derive them from original envelopes."""
    if not isinstance(envelope, dict) or envelope.get('schema_version') != 1 or envelope.get('status') not in ('ok','partial','error') or not isinstance(envelope.get('errors'), list) or not all(isinstance(e,dict) for e in envelope['errors']):
        return 'failed', ['INVALID_ENVELOPE'], False
    codes = [e.get('code','INVALID_ERROR') for e in envelope['errors'] if isinstance(e,dict)]
    fatal = bool(set(codes) & FATAL_CODES)
    data = envelope.get('data')
    if envelope['status'] == 'error' or not isinstance(data,dict): return 'failed', codes or ['MISSING_DATA'], fatal
    actual_doc = data if task['tool']=='sw_active_document' else data.get('document')
    if not document_matches(actual_doc, document): return 'failed', codes+['DOCUMENT_CONTEXT_MISMATCH'], True
    if task['tool']=='sw_active_document':
        valid = envelope['status']=='ok' and not codes
    elif task['tool']=='sw_component_spatial':
        # A failed approximate bbox does not invalidate independently valid identity/pose.
        valid = pose_matches(data.get('component'),task['expected_context'],spatial=True)
    else:
        expected = {n['id']:n for n in task['expected_context']}
        name = task['tool']
        if name == 'sw_component_cylinders':
            node = expected.get(data.get('occurrence_path'))
            valid = (data.get('cylinder_schema_version')==1 and node is not None and
                     data.get('referenced_configuration')==node['configuration'] and
                     isinstance(data.get('transform'),dict) and
                     pose_matches({'occurrence_path':node['id'],'file_path':node['file_path'],
                         'parent_occurrence_path':node['parent_id'],'referenced_configuration':data.get('referenced_configuration'),
                         'transform':data['transform']},node) and
                     isinstance(data.get('source_part'),dict) and data['source_part'].get('document_type')=='part' and
                     data['source_part'].get('configuration')==node['configuration'])
        elif name == 'sw_component_constraints':
            node = expected.get(data.get('occurrence_path'))
            valid = data.get('constraint_schema_version')==1 and node is not None and data.get('parent_occurrence_path')==node['parent_id']
        elif name == 'sw_component_faces':
            target = data.get('target',{})
            valid = data.get('face_inventory_schema_version')==1 and pose_matches(target,expected.get(target.get('occurrence_path')))
        elif name == 'sw_component_distance':
            targets = data.get('targets',[])
            valid = (data.get('component_distance_schema_version')==1 and len(targets)==2 and
                     {t.get('occurrence_path') for t in targets}==set(expected) and
                     all(pose_matches(t,expected.get(t.get('occurrence_path'))) for t in targets))
        elif name in ('sw_sample_cylinder_face','sw_read_face_adjacency'):
            source=data.get('source')
            schema='cylinder_sample_schema_version' if name=='sw_sample_cylinder_face' else 'face_adjacency_schema_version'
            valid=(data.get(schema)==1 and isinstance(source,dict) and source==task.get('expected_inspection_source') and
                data.get('boundary_source')==task.get('expected_boundary_binding') and len(expected)==1 and
                pose_matches(source.get('target'),next(iter(expected.values()))) and
                data.get('parameters')=={k:v for k,v in task['arguments'].items() if k not in ('expected_document_token','boundary_path')} and
                data.get('physical_engagement_confirmed') is False)
        elif name == 'sw_read_face_boundary':
            source=data.get('source')
            valid=(data.get('face_boundary_schema_version')==1 and isinstance(source,dict) and source==task.get('expected_boundary_source') and
                len(expected)==1 and pose_matches(source.get('target'),next(iter(expected.values()))) and
                data.get('parameters')=={'max_edges':task['arguments']['max_edges']} and data.get('physical_engagement_confirmed') is False)
        elif name == 'sw_probe_face_pair':
            sources = data.get('sources')
            valid = (data.get('face_probe_schema_version') == 1 and sources == task.get('expected_face_sources') and
                     isinstance(sources, list) and len(sources) == 2 and
                     {s['target']['occurrence_path'] for s in sources} == set(expected) and
                     all(pose_matches(s['target'], expected.get(s['target']['occurrence_path'])) for s in sources) and
                     data.get('parameters') == {k: task['arguments'][k] for k in
                         ('seed_points_root_mm', 'max_iterations', 'convergence_tolerance_mm')} and
                     data.get('global_minimum_proven') is False and data.get('contact_confirmed') is False and
                     data.get('mechanical_relation_confirmed') is False)
        else:
            valid = (data.get('mate_inventory_schema_version')==1 and data.get('scope')=='active_root_assembly' and
                     isinstance(data.get('component_contexts'),list) and
                     all(isinstance(c,dict) and (c.get('occurrence_path') not in expected or
                         pose_matches(c,expected[c['occurrence_path']])) for c in data['component_contexts']))
        if valid:
            complete = envelope['status']=='ok' and not codes and data.get('complete') is True and not data.get('truncated',False)
            return ('passed' if complete else 'partial'), codes, fatal
    if not valid: return 'failed', codes+['CONTEXT_OR_SCHEMA_MISMATCH'], True
    return 'passed', codes, fatal


def skip_reason(task, records):
    if any(r.get('fatal') for r in records): return 'EXECUTION_HALTED'
    # Postflight must still run after nonfatal capture failures to bound the successful observations.
    if task['phase']=='postflight': return None
    by_id = {r['task_id']:r for r in records}
    if any(by_id[d]['state']!='passed' for d in task['depends_on']): return 'DEPENDENCY_NOT_PASSED'
    return None


def execution_state(plan, records):
    processed = len(records)
    complete = processed == len(plan['tasks'])
    guards = [r for r,t in zip(records,plan['tasks']) if t['phase']!='capture']
    guard_count = sum(t['phase']!='capture' for t in plan['tasks'])
    passed = complete and len(guards)==guard_count and all(r['state']=='passed' for r in guards)
    eligible = [r['task_id'] for r,t in zip(records,plan['tasks']) if t['phase']=='capture' and r['state']=='passed'] if passed else []
    return {'execution_complete':complete,'guards_passed':passed,'eligible_capture_ids':eligible,
            'next_task_id':None if complete else plan['tasks'][processed]['id'],
            'summary':{'processed_tasks':processed,'planned_tasks':len(plan['tasks']),
                       'calls_executed':sum(r['envelope_source'] is not None for r in records),
                       'passed':sum(r['state']=='passed' for r in records),
                       'partial':sum(r['state']=='partial' for r in records),
                       'failed':sum(r['state']=='failed' for r in records),
                       'skipped':sum(r['state']=='skipped' for r in records),
                       'eligible_captures':len(eligible)}}
