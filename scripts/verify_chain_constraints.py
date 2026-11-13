"""0.25 chain acceptance using source-bound synthetic mates, not the user's lift."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cadkin.errors import ToolFailure
from cadkin.tools.chain_motion import replay_chain_solution
from cadkin.tools.solidworks import SolidWorksTools
from tests.constraint_fakes import write_constraint_followup_fixture


def run(root,destination):
    root=root.resolve();dest=(root/destination).resolve()
    if not dest.is_relative_to(root/'outputs') or dest==root/'outputs':raise ValueError('Choose a new directory below outputs/.')
    dest.mkdir(parents=True,exist_ok=False);checks=[];calls=[]
    def check(name,ok):checks.append({'name':name,'passed':bool(ok)})
    for mode,dof,cycles in [('chain_open',2,0),('chain_closed',0,1),('chain_redundant',2,1),('chain_fixed',0,0),('chain_hinges',2,0),('no_mates',None,0),('prismatic',None,0)]:
        base=dest/mode;app,_,_=write_constraint_followup_fixture(base,mode,enriched=True)
        original={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in base.rglob('*.json')}
        service=SolidWorksTools(base,factory=lambda:(_ for _ in ()).throw(AssertionError('Unexpected CAD')))
        try:
            args={'constraint_analysis_path':'outputs/constraints.json','reference_occurrence_path':'base-1','characteristic_length_mm':100,'output_path':'outputs/chain-motion.json'}
            result=service.call('cad_solve_chain_constraints',args);assert result['status']!='error',result
            (base/'response.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');calls.append({'mode':mode,'tool':'cad_solve_chain_constraints','arguments':args,'response_path':str(base/'response.json')})
            data,_=replay_chain_solution(base,args['output_path']);s=data['snapshots'][0]
            check(mode+' local chain dimension',s['modeled_chain_instantaneous_dof']==dof)
            check(mode+' graph cycle accounting',s['graph_cycle_count']==cycles)
            check(mode+' target stays unverified',data['target_degrees_of_freedom'] is None and not data['assembly_dof_solved'] and not data['finite_motion_verified'])
            check(mode+' compact response preserves full file',result['data']['detail_saved'] and 'rows' not in result['data']['snapshots'][0] and 'rows' in s)
            check(mode+' input bytes unchanged',all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in original.items()))
            if mode=='chain_closed':check('closed loop removes two forest directions',s['spanning_forest_diagnostics']['additional_loop_rank']==2)
            if mode=='chain_redundant':check('redundant loop removes no additional direction',s['spanning_forest_diagnostics']['additional_loop_rank']==0)
            if mode=='no_mates':check('empty model not twelve verified freedoms',s['known_constraint_nullity'] is None and not s['motion_modes'])
            if mode=='prismatic':check('disconnected node keeps uncertainty',any(m['code']=='DISCONNECTED_CONSTRAINT_GRAPH' for m in s['unresolved_evidence']))
            if mode=='chain_hinges':check('coupled rotation carries origin velocity',any(abs(b['scaled_twist'][1])>1e-6 for m in s['motion_modes'] for b in m['components']))
            if mode=='chain_open':
                wrong=service.call('cad_solve_chain_constraints',{**args,'reference_occurrence_path':'outside','output_path':'outputs/rejected.json'});check('invalid reference rejected',wrong['errors'][0]['code']=='INVALID_ARGUMENTS')
                repeat=service.call('cad_solve_chain_constraints',args);check('output not overwritten',repeat['errors'][0]['code']=='OUTPUT_EXISTS')
                forged=base/'outputs/forged.json';data['snapshots'][0]['modeled_chain_instantaneous_dof']=99;forged.write_text(json.dumps(data),encoding='utf-8')
                try:replay_chain_solution(base,str(forged));rejected=False
                except ToolFailure as exc:rejected=exc.code=='EVIDENCE_MISMATCH'
                check('forged dimension rejected',rejected)
        finally:service.close()
    report={'version':'0.25.0','scope':'Synthetic source-bound chain equations; no real SolidWorks or lift validation','checks':checks,'calls':calls,'passed':all(c['passed'] for c in checks)}
    (dest/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'passed':report['passed'],'checks':len(checks),'report':str(dest/'report.json')}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args();r=run(Path.cwd(),args.output);print(json.dumps(r,ensure_ascii=False));raise SystemExit(0 if r['passed'] else 1)
