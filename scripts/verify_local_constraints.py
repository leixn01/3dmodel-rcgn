"""0.24 acceptance: source-bound instantaneous pair constraints, never real CAD motion."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cadkin.errors import ToolFailure
from cadkin.tools.local_motion import replay_solution
from cadkin.tools.solidworks import SolidWorksTools
from tests.constraint_fakes import write_constraint_fixture


def run(root, destination):
    root=root.resolve();dest=(root/destination).resolve()
    if not dest.is_relative_to(root/'outputs') or dest==root/'outputs':raise ValueError('Choose a new directory below outputs/.')
    dest.mkdir(parents=True,exist_ok=False)
    checks,calls=[],[]
    def check(name,passed):checks.append({'name':name,'passed':bool(passed)})
    cases={'revolute':(1,0),'prismatic':(1,1),'fixed':(0,0),'lock':(0,0),'parallel_axes':(1,1),
        'duplicate_axis':(2,1),'nonparallel_axes':(0,0),'plane':(3,2),'oblique_plane':(0,0),
        'near_parallel_axes':(None,None),'no_mates':(None,None),'conflict':(None,None),'basic':(None,None)}
    for mode,(dof,translations) in cases.items():
        base=dest/mode
        app,_,_=write_constraint_fixture(base,'revolute' if mode=='basic' else mode,enriched=mode!='basic')
        original={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in base.rglob('*.json')}
        cad_before=(app.ActiveDoc.dirty,app.ActiveDoc.rebuilt,list(app.ActiveDoc.SelectionManager.selected))
        service=SolidWorksTools(base,factory=lambda:(_ for _ in ()).throw(AssertionError('Offline tool connected to CAD')))
        def call(name,**args):
            result=service.call(name,args)
            path=base/f'response-{len(calls):03d}.json';path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            calls.append({'case':mode,'tool':name,'arguments':args,'response_path':str(path)})
            return result
        try:
            analyzed=call('cad_analyze_constraints',target_graph_path='outputs/target.json',output_path='outputs/constraints.json',
                distance_tolerance_mm=.1,angle_tolerance_deg=.1)
            assert analyzed['status']!='error',analyzed
            args={'constraint_analysis_path':'outputs/constraints.json','characteristic_length_mm':100,'output_path':'outputs/local.json'}
            result=call('cad_solve_local_constraints',**args);assert result['status']!='error',result
            data=result['data'];pair=next(p for p in data['pairs'] if p['occurrence_paths']==['base-1','carriage-1'])
            snapshot=pair['snapshots'][0]
            check(mode+' modeled count and pure translation dimension',snapshot['modeled_instantaneous_dof']==dof and snapshot['pure_translation_dimension']==translations)
            check(mode+' target and finite motion stay unknown',pair['target_joint_kind']=='unknown' and pair['target_degrees_of_freedom'] is None and
                not data['assembly_dof_solved'] and not data['finite_motion_verified'] and not data['requires_human_review'])
            replay_solution(base,'outputs/local.json');check(mode+' source-bound numeric replay',True)
            check(mode+' source bytes and CAD unchanged',all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in original.items()) and
                cad_before==(app.ActiveDoc.dirty,app.ActiveDoc.rebuilt,app.ActiveDoc.SelectionManager.selected))
            if mode=='duplicate_axis':check('duplicate equations do not remove extra motion',snapshot['dependent_linear_equations']==4)
            if mode in ('nonparallel_axes','oblique_plane'):check(mode+' solves prior pattern gap',bool(snapshot['pattern_gaps_addressed']))
            if mode=='near_parallel_axes':check('sensitive rank suppresses modes',snapshot['status']=='numerically_sensitive' and not snapshot['motion_modes'] and result['status']=='partial')
            if mode=='conflict':check('conflict retains evidence and suppresses modes',snapshot['source_conflicts'] and not snapshot['motion_modes'])
            if mode in ('no_mates','basic'):check(mode+' absence is not six free motions',snapshot['known_constraint_nullity'] is None and not snapshot['motion_modes'])
            if mode=='revolute':
                bad=call('cad_solve_local_constraints',**{**args,'characteristic_length_mm':0})
                check('invalid scaling rejected',bad['errors'][0]['code']=='INVALID_ARGUMENTS')
                repeated=call('cad_solve_local_constraints',**args);check('output never overwritten',repeated['errors'][0]['code']=='OUTPUT_EXISTS')
                limited=call('cad_solve_local_constraints',**{**args,'output_path':'outputs/limited.json','max_pairs':1,'max_constraints_per_snapshot':1})
                check('budget preserves omissions',limited['status']=='partial' and limited['data']['coverage']['omitted_pairs']==2 and limited['data']['coverage']['omitted_constraints']==1)
                path=base/'outputs/local.json';raw=json.loads(path.read_text(encoding='utf-8'));raw['pairs'][0]['snapshots'][0]['linear_solution']['rank']=0
                forged=base/'outputs/forged.json';forged.write_text(json.dumps(raw),encoding='utf-8')
                try:replay_solution(base,str(forged));rejected=False
                except ToolFailure as exc:rejected=exc.code=='EVIDENCE_MISMATCH'
                check('forged rank rejected',rejected)
        finally:service.close()
    report={'version':'0.24.0','scope':'Synthetic root-face mate records and real offline solver; no installed SolidWorks or lift validation',
        'passed':all(c['passed'] for c in checks),'checks':checks,'calls':calls}
    (dest/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'passed':report['passed'],'checks':len(checks),'report':str(dest/'report.json')}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    result=run(Path.cwd(),args.output);print(json.dumps(result,ensure_ascii=False));raise SystemExit(0 if result['passed'] else 1)
