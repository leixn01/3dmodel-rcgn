"""Offline acceptance of reference parsing and scoring, not target CAD recognition accuracy."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
from cadkin.tools.solidworks import SolidWorksTools
from cadkin.templates.catalog import catalog


def run(root, destination):
    root=root.resolve();dest=(root/destination).resolve()
    if not dest.is_relative_to(root/'outputs') or dest==root/'outputs':
        raise ValueError('Choose a new directory below outputs/.')
    dest.mkdir(parents=True,exist_ok=False)
    checks=[];calls=[]
    def save(path,obj):
        with path.open('x',encoding='utf-8') as stream:json.dump(obj,stream,ensure_ascii=False,indent=2,allow_nan=False)
    service=SolidWorksTools(root)
    def call(name,args,label):
        result=service.call(name,args);save(dest/f'{label}.response.json',result);calls.append({'tool':name,'arguments':args,'status':result['status']});return result
    def check(name,ok):checks.append({'name':name,'passed':bool(ok)})
    try:
        result=call('cad_list_mechanism_templates',{},'catalog')
        check('reference retrieval excludes heldout',result['status']=='ok' and result['data']['count']==6)
        for entry in catalog()['templates']:
            result=call('cad_extract_mechanism_template',{'template_id':entry['id'],'output_path':str(dest/(entry['id']+'.json'))},entry['id'])
            data=result.get('data') or {}
            check(entry['id']+' authored counts',data.get('summary',{}).get('body_count')==entry['expected']['body_count'] and data.get('summary',{}).get('joint_count')==entry['expected']['joint_count'])
            if entry['expected']['joint_count']==0:
                check(entry['id']+' remains incomplete',result['status']=='partial' and not data.get('complete',True) and 'NO_JOINTS' in [r['code'] for r in data.get('risks',[])])
        reference=dest/'bench_vise.json';ref=json.loads(reference.read_text(encoding='utf-8'));refhash=hashlib.sha256(reference.read_bytes()).hexdigest()
        for label,change in [('identity',None),('missing_joint','remove'),('wrong_joint_type','type'),('missing_body_map','map')]:
            candidate=copy.deepcopy(ref)
            if change=='remove':candidate['joints'].pop()
            if change=='type':candidate['joints'][0]['kind']='prismatic' if candidate['joints'][0]['kind']!='prismatic' else 'revolute'
            path=dest/(label+'.candidate.json');save(path,candidate)
            body_map=[{'candidate_body':b['id'],'reference_body':b['id']} for b in ref['bodies']]
            if change=='map':body_map.pop()
            correspondence={'body_correspondence_schema_version':1,'reference_sha256':refhash,'candidate_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'body_map':body_map}
            map_path=dest/(label+'.map.json');save(map_path,correspondence)
            args={'reference_path':str(reference),'candidate_path':str(path),'correspondence_path':str(map_path),'output_path':str(dest/(label+'.score.json'))}
            result=call('cad_compare_mechanism_graphs',args,label);data=result.get('data') or {};typed=data.get('typed_joints',{})
            if change is None:check('identity parser/scorer control',typed.get('recall')==1 and typed.get('precision')==1)
            elif change=='remove':check('missing joint reduces recall',typed.get('true_positive')==6 and typed.get('expected')==7 and len(data.get('missing_typed_joints',[]))==1)
            elif change=='type':check('wrong type preserves connections but lowers type recall',data.get('connections',{}).get('recall')==1 and typed.get('true_positive')==6)
            else:check('incomplete body correspondence retained',result['status']=='partial' and len(data.get('body_coverage',{}).get('unmapped_candidate',[]))==1)
        bad=call('cad_extract_mechanism_template',{'template_id':'no-such-template','output_path':str(dest/'bad.json')},'unknown')
        check('unknown ID is explicit error',bad['status']=='error' and bad['errors'][0]['code']=='TEMPLATE_NOT_FOUND')
        recovered=call('cad_list_mechanism_templates',{},'recovery');check('service remains usable',recovered['status']=='ok')
    finally:service.close()
    report={'purpose':'Reference parser and synthetic scoring controls only; no SolidWorks/model recognition accuracy claim.',
            'passed':all(c['passed'] for c in checks),'checks':checks,'calls':calls,'requires_human_review':False,
            'limitations':['Body correspondence in synthetic controls is known by construction.',
                           'Source joint definitions are authored references, not independent physical measurements.',
                           'No COM, CAD modification, simulation or target STEP mechanism matching was performed.']}
    save(dest/'report.json',report)
    return report,dest/'report.json'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    args=parser.parse_args()
    try:
        report,path=run(Path.cwd(),args.output)
        print(json.dumps({'passed':report['passed'],'checks':len(report['checks']),'report':str(path)},ensure_ascii=False))
        sys.exit(0 if report['passed'] else 1)
    except (OSError,ValueError,KeyError) as exc:
        parser.exit(2,f'Acceptance could not finish: {exc}\n')
