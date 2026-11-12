"""Packaged, pinned reference metadata; no network, CAD or USD dependency."""
import hashlib
import json
from pathlib import Path
from cadkin.errors import ToolFailure

ROOT = Path(__file__).resolve().parents[1] / 'resources' / 'mechanisms'


def catalog():
    return json.loads((ROOT/'catalog.json').read_text(encoding='utf-8'))


def find_template(template_id):
    entry = next((x for x in catalog()['templates'] if x['id'] == template_id), None)
    if entry is None:
        raise ToolFailure('TEMPLATE_NOT_FOUND', 'Unknown bundled template ID.', template_id=template_id)
    path = ROOT / entry['file']
    if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
        raise ToolFailure('EVIDENCE_MISMATCH', 'Bundled template hash differs from catalog.')
    return entry, path


def list_templates(query='', include_heldout=False):
    entries = []
    for item in catalog()['templates']:
        if not include_heldout and item['split'] == 'heldout':
            continue
        if query and query.casefold() not in ' '.join([item['id'], item['label'], *item['tags']]).casefold():
            continue
        entries.append({k:item[k] for k in ('id','label','tags','split','author','license','asset_url','expected')})
    return {'catalog_schema_version':1, 'templates':entries, 'count':len(entries),
            'scope':'Small pinned structural excerpts, not complete visual models or guaranteed physical ground truth.',
            'split_policy':'Heldout assets are excluded from reference retrieval by default. Viewing/using them for tuning invalidates an unseen-test claim.',
            'requires_human_review':False}
