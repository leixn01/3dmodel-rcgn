"""Explicit geometry-only source fixtures, never production CAD replacements."""
from pathlib import Path
from tests.chain_fakes import write_chain_fixture
from tests.execution_fakes import live_service


def geometry_fixture(root, distances=False, faces=False, scope=None):
    root=Path(root);args,app=write_chain_fixture(root,return_app=True)
    args.pop('grouping_path',None)
    args.update(occurrence_paths=scope or ['base-1','carriage-1'],
        evidence_paths=(['outputs/proximity-review.json'] if distances else [])+(['outputs/face-review.json'] if faces else []))
    service=live_service(root,app)
    for name,arguments in [
        ('cad_build_chain_evidence',args),
        ('cad_build_target_graph',{'chain_path':'outputs/chain.json','relation_paths':['outputs/relations.json'],'output_path':'outputs/target.json'}),
        ('cad_build_rigid_candidates',{'target_graph_path':'outputs/target.json','output_path':'outputs/rigid.json'}),
        ('cad_draft_joints',{'rigid_candidates_path':'outputs/rigid.json','output_path':'outputs/draft.json'}),
        ('cad_check_joint_draft',{'joint_draft_path':'outputs/draft.json','output_path':'outputs/check.json'})]:
        r=service.call(name,arguments);assert r['status']!='error',r
    return service,app


def run_batch(service, plan, prefix):
    previous=None
    for i in range(30):
        args={'plan_path':plan,'output_path':f'outputs/{prefix}-batch-{i:02d}.json','max_steps':20,'time_budget_seconds':60}
        if previous:args['previous_execution_path']=previous
        result=service.call('sw_execute_evidence_batch',args)
        assert result['status']!='error',result
        previous=result['data']['execution_source']['path']
        if result['data']['execution_complete']:
            assert result['data']['guards_passed'],result
            return previous
    raise AssertionError('Synthetic batch did not finish')
