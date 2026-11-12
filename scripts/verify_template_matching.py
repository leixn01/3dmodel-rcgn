"""Automatic offline acceptance using explicit synthetic CAD data and reference-derived controls."""
import argparse
import copy
import json
from pathlib import Path
import sys

# The checkout supplies test fixtures; none are imported by production tools.
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cadkin.tools.solidworks import SolidWorksTools
from cadkin.templates.catalog import catalog,find_template
from cadkin.templates.usd import read_template
from cadkin.matching.search import match_patterns
from tests.chain_fakes import write_chain_fixture
from tests.matching_fakes import blinded_reference_window


def run(root,destination):
    root=root.resolve();dest=(root/destination).resolve()
    if not dest.is_relative_to(root/'outputs') or dest==root/'outputs':raise ValueError('Choose a new directory below outputs/.')
    dest.mkdir(parents=True,exist_ok=False)
    checks=[];calls=[]
    def save(name,data):
        with (dest/name).open('x',encoding='utf-8') as stream:json.dump(data,stream,ensure_ascii=False,indent=2,allow_nan=False)
    def check(name,ok):checks.append({'name':name,'passed':bool(ok)})
    fixture=dest/'synthetic-cad';args=write_chain_fixture(fixture)
    def forbidden():raise AssertionError('Acceptance must not initialize SolidWorks')
    service=SolidWorksTools(fixture,factory=forbidden)
    def call(name,params,label):
        result=service.call(name,params);save(label+'.response.json',result);calls.append({'tool':name,'parameters':params,'status':result['status']});return result
    try:
        chain=call('cad_build_chain_evidence',args,'chain');check('synthetic base chain compiles',chain['status']=='ok')
        target=call('cad_build_target_graph',{'chain_path':'outputs/chain.json','output_path':'outputs/target.json'},'target')
        check('target graph uses three separate occurrences',target.get('data',{}).get('coverage',{}).get('nodes')==3)
        graph=json.loads((fixture/'outputs/target.json').read_text(encoding='utf-8'))
        check('relations automatically recovered from connection source',len(graph['relation_sources'])==1)
        check('axis evidence available for three pairs',graph['coverage']['pairs_with_single_axis']==3)
        params={'target_graph_path':'outputs/target.json','template_ids':['gas_lift_bar_stool'],'output_path':'outputs/matches.json'}
        matches=call('cad_match_mechanism_templates',params,'matches');data=matches.get('data',{})
        check('reference subgraph candidates generated',bool(data.get('candidates')))
        check('automatic workflow has no human gate',data.get('requires_human_review') is False)
        check('joint hypotheses do not certify motion or copy limits',all(not e['mechanical_relation_confirmed'] and e['limits'] is None and not e['joint_axis_verified'] for c in data.get('candidates',[]) for e in c['joint_hypotheses']))
        check('target and template bindings recorded',bool(data.get('target_source',{}).get('sha256')) and bool(data.get('template_sources')))
        limited=call('cad_match_mechanism_templates',{**params,'max_states':1,'output_path':'outputs/limited.json'},'limited')
        check('search limit is partial',limited['status']=='partial')
        check('search limit is disclosed',limited.get('data',{}).get('search_exhaustive') is False)
        negative=call('cad_match_mechanism_templates',{**params,'template_ids':['gear_meshing_kit'],'output_path':'outputs/no-joints.json'},'no-joints')
        check('no joint template does not manufacture candidates',negative['status']=='partial' and not negative['data']['candidates'])
        heldout=call('cad_match_mechanism_templates',{**params,'template_ids':['bar_clamp'],'output_path':'outputs/heldout.json'},'heldout')
        check('heldout excluded without explicit opt-in',heldout['status']=='error' and heldout['errors'][0]['code']=='HELDOUT_TEMPLATE')
        tampered=copy.deepcopy(graph);tampered['pairs'][0]['link_support']=.123
        (fixture/'outputs/tampered.json').write_text(json.dumps(tampered),encoding='utf-8')
        bad=call('cad_match_mechanism_templates',{**params,'target_graph_path':'outputs/tampered.json','output_path':'outputs/bad.json'},'tampered')
        check('modified derived graph rejected',bad['status']=='error' and bad['errors'][0]['code']=='EVIDENCE_MISMATCH')
        recovered=call('cad_list_mechanism_templates',{},'recovered');check('service usable after errors',recovered['status']=='ok')
        for entry in catalog()['templates']:
            if entry['split']!='reference':continue
            reference=read_template(find_template(entry['id'])[1]);observation=blinded_reference_window(entry,reference)
            if observation is None:continue
            result=match_patterns(observation,[(entry,reference)],max_states=100000,beam_width=1000)
            save(entry['id']+'.given-observations.json',observation);save(entry['id']+'.control-result.json',result)
            check(entry['id']+' given-topology label-hidden control',bool(result['candidates']) and result['best_score']>=.7)
    finally:service.close()
    report={'purpose':'Offline adapter/search acceptance, not target STEP decomposition accuracy.',
            'passed':all(c['passed'] for c in checks),'checks':checks,'calls':calls,'requires_human_review':False,
            'limitations':['Synthetic CAD fixtures are explicit test data, not measurements from the lift.',
                           'Reference-derived controls are given connectivity/axes with labels hidden; they are not independent recognition evaluation.',
                           'Ranking scores are not probabilities. Joint kinds, axes, rigid groups and motion remain hypotheses.',
                           'No COM, CAD modification, heldout tuning or target STEP matching occurred.']}
    save('report.json',report);return report,dest/'report.json'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True);args=parser.parse_args()
    try:
        report,path=run(Path.cwd(),args.output)
        print(json.dumps({'passed':report['passed'],'checks':len(report['checks']),'report':str(path)},ensure_ascii=False))
        sys.exit(0 if report['passed'] else 1)
    except (OSError,ValueError,KeyError) as exc:parser.exit(2,f'Acceptance could not finish: {exc}\n')
