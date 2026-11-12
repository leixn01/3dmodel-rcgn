"""Synthetic draft/plan fixtures; never evidence of real lift operation."""
from cadkin.rigid.groups import candidate_partitions
from cadkin.rigid.joints import draft_partitions
from tests.rigid_fakes import rigid_target
from tests.matching_fakes import toy_reference
from tests.chain_fakes import write_chain_fixture


def draft_fixture():
    target=rigid_target()
    target['document'].update(document_token='a'*24,configuration='Default',path='C:/synthetic.sldasm',document_type='assembly',dirty=False)
    for node in target['nodes']:
        node.update(file_path='C:/synthetic.sldprt',configuration='Default',parent_id=None,
                    to_root_column_vectors_m=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]])
    rigid=candidate_partitions(target)
    draft=draft_partitions(target,rigid,[toy_reference(),toy_reference(kind='revolute',name='other')],max_candidates=10)
    draft['heldout_exposed']=False
    return target,rigid,draft


def write_draft_fixture(root, service_factory):
    args,app=write_chain_fixture(root,with_lock=True,return_app=True)
    service=service_factory(root)
    try:
        calls=[('cad_build_chain_evidence',args),
               ('cad_build_target_graph',{'chain_path':'outputs/chain.json','output_path':'outputs/target.json'}),
               ('cad_build_rigid_candidates',{'target_graph_path':'outputs/target.json','output_path':'outputs/rigid.json'}),
               ('cad_draft_joints',{'rigid_candidates_path':'outputs/rigid.json','output_path':'outputs/drafts.json',
                                    'template_ids':['gas_lift_bar_stool'],'pattern_size':2})]
        for name,arguments in calls:
            result=service.call(name,arguments);assert result['status']=='ok',result
    finally:service.close()
    return app
