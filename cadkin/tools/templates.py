"""Project file and MCP boundaries for independent reference-graph operations."""
import hashlib
from pathlib import Path
from cadkin.errors import ToolFailure, success
from cadkin.templates.catalog import find_template, list_templates
from cadkin.templates.usd import read_template
from cadkin.templates.compare import compare_graphs
from cadkin.tools.files import json_path, read_json
from cadkin.tools.proximity import write_result


def template_catalog(root, query='', include_heldout=False):
    return success(list_templates(query, include_heldout))


def extract_template(root, output_path, template_id=None, asset_path=None):
    output=json_path(root,output_path,output=True)
    if (template_id is None)==(asset_path is None):
        raise ToolFailure('INVALID_ARGUMENTS','Supply exactly one of template_id and asset_path.')
    entry=None
    if template_id is not None:
        entry,path=find_template(template_id)
    else:
        root=Path(root).resolve(); path=(root/asset_path).resolve()
        if not path.is_relative_to(root):
            raise ToolFailure('INVALID_PATH','USD input must be inside the project.')
    data=read_template(path)
    if entry:
        if data['source']['sha256']!=entry['sha256']:
            raise ToolFailure('EVIDENCE_MISMATCH','Bundled template changed during extraction.')
        data['reference_asset']={k:entry[k] for k in ('id','split','author','license','license_url','asset_url','source_revision','source_files','modifications')}
    write_result(output,data)
    errors=[] if data['complete'] else [{'code':'TEMPLATE_INCOMPLETE','message':'Extraction retains unsupported or missing mechanism information; see risks.','details':{}}]
    return success({'output_path':str(output), **data},errors)


def compare_templates(root, reference_path, candidate_path, correspondence_path, output_path):
    output=json_path(root,output_path,output=True)
    sources={}; payload={}
    for key,name in (('reference',reference_path),('candidate',candidate_path),('correspondence',correspondence_path)):
        path=json_path(root,name); obj,digest=read_json(path)
        sources[key]={'path':str(path),'sha256':digest};payload[key]=obj
    data=compare_graphs(payload['reference'],payload['candidate'],payload['correspondence'],sources['reference']['sha256'],sources['candidate']['sha256'])
    data['sources']=sources
    for item in sources.values():
        if hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()!=item['sha256']:
            raise ToolFailure('EVIDENCE_MISMATCH','Graph input changed during comparison.')
    write_result(output,data)
    errors=[{'code':'COMPARISON_PARTIAL','message':'Scores have incomplete evidence, excluded joints or body coverage; see risks.','details':{}}] if any(r['code'] in ('PARTIAL_INPUT','EXCLUDED_JOINTS','INCOMPLETE_BODY_CORRESPONDENCE','STALE_GRAPH_SUMMARY') for r in data['risks']) else []
    return success({'output_path':str(output),**data},errors)
