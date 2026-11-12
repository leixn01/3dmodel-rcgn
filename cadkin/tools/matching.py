"""Source replay and file boundaries for target adaptation and reference hypothesis search."""
from pathlib import Path
from cadkin.errors import success
from cadkin.tools.files import json_path, read_json
from cadkin.tools.proximity import write_result
from cadkin.tools.chain import build_chain
from cadkin.tools.chain_sources import ChainSources, require, check_fields
from cadkin.matching.target import adapt_target


def recheck(root,bindings):
    for b in bindings:
        require(read_json(json_path(root,b['path']))[1]==b['sha256'],'Source changed during graph processing.','EVIDENCE_MISMATCH')


def build_target(root,chain_path,relation_paths=None):
    path=json_path(root,chain_path);original,digest=read_json(path)
    require(isinstance(original,dict) and original.get('chain_dossier_schema_version')==1 and original.get('algorithm_version')==1,
            'Use an original base chain dossier.','INVALID_TARGET_SOURCE')
    params=original.get('parameters')
    require(isinstance(params,dict) and set(params)=={'inventory_path','occurrence_paths','chain_name','evidence_paths','grouping_path','grouping_review_path'},
            'Invalid chain parameters.','INVALID_TARGET_SOURCE')
    chain=build_chain(root,**params);check_fields(original,chain)
    reader=ChainSources(root,params['inventory_path'],params['grouping_review_path'])
    require(reader.spatial.get('units')=={'api_length':'m','display_length':'mm','matrix_translation':'m'},'Unsupported spatial units.','INVALID_TARGET_SOURCE')
    requested=[] if relation_paths is None else relation_paths
    require(isinstance(requested,list) and len(requested)<=20 and all(isinstance(p,str) and p for p in requested),'Use at most 20 relation files.','INVALID_ARGUMENTS')
    names={str(json_path(root,p)) for p in requested}
    for source in chain['sources']:
        if source['kind']=='connection':
            raw,_=reader.bound(source)
            names.add(str(json_path(root,raw['sources']['relations']['path'])))
    require(len(names)<=40,'Too many combined relation sources.','TARGET_SOURCE_LIMIT')
    relations=[];seen=set()
    for name in sorted(names):
        data,binding=reader.relations(name)
        if binding['sha256'] not in seen:relations.append((data,binding));seen.add(binding['sha256'])
    data=adapt_target(chain,reader.nodes,relations)
    by_path={b['path']:b for b in chain['input_files']}
    for b in reader.finish()+[{'path':str(path),'sha256':digest}]:
        require(b['path'] not in by_path or by_path[b['path']]==b,'Mixed evidence snapshots.','EVIDENCE_MISMATCH');by_path[b['path']]=b
    files=sorted(by_path.values(),key=lambda b:b['path'])
    require(len(files)<=256 and sum(Path(b['path']).stat().st_size for b in files)<=128*1024*1024,'Target source graph budget exceeded.','TARGET_SOURCE_LIMIT')
    data.update(parameters={'chain_path':str(path),'relation_paths':sorted(str(json_path(root,p)) for p in set(requested))},
                source_chain={'path':str(path),'sha256':digest},relation_sources=[b for _,b in relations],input_files=files)
    recheck(root,files)
    return data


def build_target_graph(root,chain_path,output_path,relation_paths=None):
    output=json_path(root,output_path,output=True)
    data=build_target(root,chain_path,relation_paths);write_result(output,data)
    return success({'output_path':str(output),'coverage':data['coverage'],'complete':data['complete'],
                    'requires_human_review':False,'solidworks_modified':False},data['errors'])


def match_templates(root,target_graph_path,output_path,template_ids=None,include_heldout=False,**parameters):
    from cadkin.templates.catalog import catalog,find_template
    from cadkin.templates.usd import read_template
    from cadkin.matching.search import match_patterns
    output=json_path(root,output_path,output=True);path=json_path(root,target_graph_path);original,digest=read_json(path)
    require(isinstance(original,dict) and original.get('target_graph_schema_version')==1 and original.get('algorithm_version')==1 and
            isinstance(original.get('parameters'),dict) and set(original['parameters'])=={'chain_path','relation_paths'},
            'Use an original target graph produced by cad_build_target_graph.','INVALID_TARGET_SOURCE')
    target=build_target(root,**original['parameters']);check_fields(original,target)
    ids=template_ids if template_ids is not None else [t['id'] for t in catalog()['templates'] if include_heldout or t['split']=='reference']
    require(isinstance(ids,list) and 1<=len(ids)<=8 and all(isinstance(x,str) and x for x in ids) and len(set(ids))==len(ids),'Choose 1–8 unique template IDs.','INVALID_ARGUMENTS')
    references=[];bindings=[]
    for template_id in sorted(ids):
        entry,asset=find_template(template_id)
        require(include_heldout or entry['split']!='heldout','Heldout templates require explicit include_heldout=true; record evaluation exposure.','HELDOUT_TEMPLATE')
        graph=read_template(asset)
        require(graph['source']['sha256']==entry['sha256'],'Template hash changed.','EVIDENCE_MISMATCH')
        references.append((entry,graph));bindings.append({'id':template_id,'sha256':entry['sha256'],'split':entry['split'],
            'source_revision':entry['source_revision'],'asset_url':entry['asset_url'],'risks':graph['risks'],'complete':graph['complete']})
    data=match_patterns(target,references,**parameters)
    data.update(target_source={'path':str(path),'sha256':digest},template_sources=bindings,
                heldout_exposed=any(b['split']=='heldout' for b in bindings))
    recheck(root,target['input_files']+[data['target_source']])
    for b in bindings:find_template(b['id'])
    write_result(output,data)
    errors=[]
    if not data['search_exhaustive']:errors.append({'code':'MATCH_SEARCH_LIMIT','message':'Search was bounded; omitted mappings are unknown.'})
    if not target['complete']:errors.append({'code':'SOURCE_INCOMPLETE','message':'Target source gaps remain in target_errors.'})
    if not data['candidates']:errors.append({'code':'NO_SUPPORTED_MATCH','message':'No supported candidate was found in the searched scope; not proof of absent mechanism.'})
    return success({'output_path':str(output),**data},errors)
