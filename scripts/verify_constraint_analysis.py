"""0.22 acceptance: synthetic local constraints, live-adapter substitutes and offline replay."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cadkin.errors import ToolFailure
from cadkin.tools.constraint_analysis import replay_analysis
from cadkin.tools.solidworks import SolidWorksTools
from tests.constraint_fakes import write_constraint_fixture


def run(root,destination):
    root=root.resolve();dest=(root/destination).resolve()
    if not dest.is_relative_to(root/'outputs') or dest==root/'outputs': raise ValueError('Choose a new directory below outputs/.')
    dest.mkdir(parents=True,exist_ok=False)
    checks=[];calls=[]
    def check(name,ok):checks.append({'name':name,'passed':bool(ok)})
    for mode,kind in [('lock','fixed'),('revolute','revolute'),('prismatic','prismatic'),('fixed','fixed'),
                      ('parallel_axes','prismatic'),('duplicate_axis',None),('no_mates',None),('conflict',None),('legacy',None)]:
        base=dest/mode
        _,_,envelope=write_constraint_fixture(base,'revolute' if mode=='legacy' else mode,enriched=mode!='legacy')
        original={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in base.rglob('*.json')}
        service=SolidWorksTools(base,factory=lambda:(_ for _ in ()).throw(AssertionError('Offline analysis called CAD')))
        try:
            args=dict(target_graph_path='outputs/target.json',output_path='outputs/constraints.json',distance_tolerance_mm=.1,angle_tolerance_deg=.1)
            result=service.call('cad_analyze_constraints',args)
            (base/'response.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            calls.append({'mode':mode,'tool':'cad_analyze_constraints','arguments':args,'response_path':str(base/'response.json')})
            assert result['status']=='ok',result
            data=result['data'];pair=next(p for p in data['pairs'] if p['occurrence_paths']==['base-1','carriage-1']);snapshot=pair['snapshots'][0]
            check(mode+' expected local candidates',[c['kind'] for c in snapshot['candidates']]==([kind] if kind else []))
            check(mode+' no target truth or DOF transfer',all(p['target_joint_kind']=='unknown' and p['target_degrees_of_freedom'] is None for p in data['pairs']))
            check(mode+' replay and unchanged sources',replay_analysis(base,args['output_path'])[0]['pairs']==data['pairs'] and all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in original.items()))
            if mode=='revolute':
                check('direct root face identity and locators',all(len(r['entity_geometry'])==2 and all(g['persistent_reference']['scope']=='active_root_assembly' for g in r['entity_geometry']) for r in snapshot['mate_evidence']))
                check('rotation unlock is observed',snapshot['mate_evidence'][0]['concentric_lock_rotation'] is False)
                limited=service.call('cad_analyze_constraints',{**args,'output_path':'outputs/limited.json','max_pairs':1})
                check('omitted pair budget is explicit',limited['status']=='partial' and limited['data']['coverage']['omitted_pairs']==2)
                check('existing output not overwritten',service.call('cad_analyze_constraints',args)['errors'][0]['code']=='OUTPUT_EXISTS')
                raw=json.loads((base/args['output_path']).read_text());raw['pairs'][0]['target_joint_kind']='revolute'
                (base/'outputs/forged.json').write_text(json.dumps(raw),encoding='utf-8')
                try:replay_analysis(base,'outputs/forged.json');rejected=False
                except ToolFailure as exc:rejected=exc.code=='EVIDENCE_MISMATCH'
                check('forged target conclusion rejected',rejected)
            if mode=='no_mates':check('STEP-style missing mates preserve geometric context',bool(pair['geometry_context']['axis_relations']) and bool(snapshot['missing_evidence']))
            if mode=='conflict':check('inconsistent mate geometry retained',snapshot['state']=='conflicting_evidence' and snapshot['conflicts'][0]['code']=='MATE_GEOMETRY_OUTSIDE_TOLERANCE')
            if mode=='legacy':check('legacy source missing geometry remains explicit','MATE_REFERENCE_GEOMETRY_MISSING_OR_UNSUPPORTED' in [x['code'] for x in snapshot['missing_evidence']])
        finally:service.close()
    report={'version':'0.22.0','scope':'synthetic CAD adapter and real offline implementation; not installed SOLIDWORKS/lift validation',
            'passed':all(c['passed'] for c in checks),'checks':checks,'calls':calls}
    (dest/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'passed':report['passed'],'checks':len(checks),'report':str(dest/'report.json')}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    result=run(Path.cwd(),args.output);print(json.dumps(result,ensure_ascii=False));raise SystemExit(0 if result['passed'] else 1)
