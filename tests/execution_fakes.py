"""Explicit test-only fixtures; never select a simulated backend in production."""
from cadkin.tools.solidworks import SolidWorksTools
from cadkin.adapters.solidworks import SolidWorksAdapter
from tests.chain_fakes import write_chain_fixture
from tests.sw_fakes import runtime


def write_execution_fixture(root, degraded=False, pattern_size=2, missing_distances=False, include_face_review=True):
    missing=('cylinder0.json','cylinder1.json','cylinder2.json','mates.json') if degraded else ()
    if missing_distances:missing+=('distance0.json','distance1.json','distance2.json')
    args,app=write_chain_fixture(root,with_lock=True,return_app=True,incomplete_sources=missing)
    if not include_face_review:
        args['evidence_paths'] = [p for p in args['evidence_paths'] if p != 'outputs/face-review.json']
    service=SolidWorksTools(root)
    try:
        for name,arguments in [
            ('cad_build_chain_evidence',args),
            ('cad_build_target_graph',{'chain_path':'outputs/chain.json','output_path':'outputs/target.json'}),
            ('cad_build_rigid_candidates',{'target_graph_path':'outputs/target.json','output_path':'outputs/rigid.json'}),
            ('cad_draft_joints',{'rigid_candidates_path':'outputs/rigid.json','output_path':'outputs/drafts.json',
                               'pattern_size':pattern_size,'template_ids':['gas_lift_bar_stool'] if pattern_size==2 else ['articulation_test_bench']}),
            ('cad_check_joint_draft',{'joint_draft_path':'outputs/drafts.json','output_path':'outputs/check.json'}),
            ('cad_plan_evidence_tasks',{'draft_check_path':'outputs/check.json','output_path':'outputs/plan.json'})]:
            result=service.call(name,arguments);assert result['status']!='error',result
    finally:service.close()
    return app


def live_service(root,app):
    return SolidWorksTools(root,factory=lambda:SolidWorksAdapter(app=app,runtime=runtime()))
