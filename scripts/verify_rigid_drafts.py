"""Offline 0.15 acceptance on explicit synthetic CAD sources; not lift recognition accuracy."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cadkin.tools.solidworks import SolidWorksTools
from cadkin.rigid.groups import candidate_partitions
from cadkin.rigid.joints import axis_draft
from tests.chain_fakes import write_chain_fixture
from tests.rigid_fakes import rigid_target, mate_signal, axis_relation


def run(root,destination):
    root=root.resolve();dest=(root/destination).resolve()
    if not dest.is_relative_to(root/'outputs') or dest==root/'outputs':raise ValueError('Choose a new directory below outputs/.')
    dest.mkdir(parents=True,exist_ok=False)
    checks=[];calls=[]
    def save(name,data):
        with (dest/name).open('x',encoding='utf-8') as stream:json.dump(data,stream,ensure_ascii=False,indent=2,allow_nan=False)
    def check(name,ok):checks.append({'name':name,'passed':bool(ok)})
    fixture=dest/'synthetic-cad';args=write_chain_fixture(fixture,with_lock=True)
    original={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in fixture.rglob('*.json')}
    def forbidden():raise AssertionError('Acceptance cannot connect SolidWorks')
    service=SolidWorksTools(fixture,factory=forbidden)
    def call(name,params,label):
        result=service.call(name,params);save(label+'.response.json',result)
        calls.append({'tool':name,'parameters':params,'status':result['status']});return result
    try:
        chain=call('cad_build_chain_evidence',args,'chain');check('synthetic chain compiles',chain['status']=='ok')
        target=call('cad_build_target_graph',{'chain_path':'outputs/chain.json','output_path':'outputs/target.json'},'target')
        check('target source replay succeeds',target['status']=='ok')
        params={'target_graph_path':'outputs/target.json','output_path':'outputs/rigid.json'}
        result=call('cad_build_rigid_candidates',params,'rigid');check('rigid candidates generated',result['status']=='ok')
        rigid=json.loads((fixture/'outputs/rigid.json').read_text(encoding='utf-8'))
        check('unmerged baseline retained',rigid['partitions'][0]['basis']=='unmerged_baseline')
        check('synthetic lock yields multi-occurrence group',any(len(g['member_occurrence_paths'])==2 for p in rigid['partitions'] for g in p['groups']))
        expected=sorted(args['occurrence_paths'])
        check('every partition preserves all occurrences once',all(sorted(n for g in p['groups'] for n in g['member_occurrence_paths'])==expected for p in rigid['partitions']))
        check('no rigidity or human confirmation manufactured',not rigid['rigidity_confirmed'] and not rigid['requires_human_review'])
        limited=call('cad_build_rigid_candidates',{**params,'output_path':'outputs/limited-groups.json','max_partitions':1},'limited-groups')
        check('partition cap disclosed',limited['status']=='partial' and limited['data']['output_truncated'])
        draft_args={'rigid_candidates_path':'outputs/rigid.json','output_path':'outputs/drafts.json','template_ids':['gas_lift_bar_stool'],'pattern_size':2}
        draft=call('cad_draft_joints',draft_args,'drafts');check('group-based matching succeeds',draft['status']=='ok')
        data=draft['data'];cs=[c for p in data['partition_results'] if p['match'] for c in p['match']['candidates']]
        check('reference body maps to multiple occurrences',any(len(m['member_occurrence_paths'])==2 for c in cs for m in c['mapping']))
        edges=[e for c in cs for e in c['joint_hypotheses']]
        check('limits pivot pitch remain unknown',all(e['limits'] is None and e['axis_origin_m'] is None and e['pitch_m_per_revolution'] is None for e in edges))
        check('joint degrees of freedom unverified',all(not e['dof_verified'] and not e['joint_axis_verified'] and not e['mechanical_relation_confirmed'] for e in edges))
        check('geometry comes with original pair provenance',all(e['source_occurrence_pair_ids'] for e in edges))
        check('search states share the total budget',data['summary']['evaluated_states']<=20000)
        limited=call('cad_draft_joints',{**draft_args,'output_path':'outputs/limited-drafts.json','max_states':1},'limited-drafts')
        check('search budget explicitly partial',limited['status']=='partial' and not limited['data']['search_exhaustive_within_retained_partitions'])
        empty=call('cad_draft_joints',{**draft_args,'output_path':'outputs/no-joints.json','template_ids':['gear_meshing_kit']},'no-joints')
        check('no joint reference creates no draft',empty['status']=='partial' and empty['data']['summary']['returned_candidates']==0)
        held=call('cad_draft_joints',{**draft_args,'output_path':'outputs/heldout.json','template_ids':['bar_clamp']},'heldout')
        check('heldout excluded by default',held['status']=='error' and held['errors'][0]['code']=='HELDOUT_TEMPLATE')
        bad=copy.deepcopy(rigid);bad['partitions'][0]['groups'][0]['rigidity_confirmed']=True
        (fixture/'outputs/tampered.json').write_text(json.dumps(bad),encoding='utf-8')
        rejected=call('cad_draft_joints',{**draft_args,'rigid_candidates_path':'outputs/tampered.json','output_path':'outputs/rejected.json'},'tampered')
        check('modified membership rejected',rejected['status']=='error' and rejected['errors'][0]['code']=='EVIDENCE_MISMATCH')
        check('service remains usable',call('cad_list_mechanism_templates',{},'recovery')['status']=='ok')
        check('original source hashes unchanged',all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==sha for p,sha in original.items()))
        t=rigid_target();t['pairs'][0]['signals']=[{'kind':'near_component'}]
        weak=candidate_partitions(t);save('contact-control.json',weak)
        check('contact grouping explicitly weak',any('CONTACT_DOES_NOT_PROVE_RIGIDITY' in p['risk_codes'] for p in weak['partitions']))
        t=rigid_target();t['pairs'][3]['signals'].append(mate_signal('slider'))
        blocked=candidate_partitions(t);save('motion-conflict-control.json',blocked)
        check('motion mate blocks lock merge',blocked['coverage']['blocked_proposals']==1 and len(blocked['partitions'])==1)
        pair=rigid_target()['pairs'][0];pair['axis_relations'].append(axis_relation(origin=[0,.005,0]))
        axis=axis_draft(pair,.1,1);save('multiple-axis-control.json',axis)
        check('offset axes remain alternatives',len(axis['geometric_line_candidates'])==2 and axis['axis_line_candidate'] is None)
        fixed=call('cad_draft_joints',{**draft_args,'output_path':'outputs/fixed-window.json','pattern_size':3},'fixed-window')
        check('window size not silently reduced',any(p['skip_reason']=='insufficient_eligible_groups' for p in fixed['data']['partition_results']))
    finally:service.close()
    report={'passed':all(c['passed'] for c in checks),'checks':checks,'calls':calls,'requires_human_review':False,
            'purpose':'Synthetic source replay and conditional rigid/joint workflow acceptance; not lift recognition accuracy.',
            'limitations':['No live SolidWorks connection or STEP modification. Lock/contact observations are explicit test fixtures.',
                           'No solved rigid groups, joint limits, kinematics, disassembly or independent recognition accuracy.']}
    save('report.json',report);return report,dest/'report.json'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True);args=parser.parse_args()
    try:
        report,path=run(Path.cwd(),args.output)
        print(json.dumps({'passed':report['passed'],'checks':len(report['checks']),'report':str(path)},ensure_ascii=False))
        sys.exit(0 if report['passed'] else 1)
    except (OSError,ValueError,KeyError) as exc:parser.exit(2,f'Acceptance could not finish: {exc}\n')
