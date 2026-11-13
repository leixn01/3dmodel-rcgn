"""Replay existing offline evidence derivations before using them in a chain dossier."""
from pathlib import Path

from cadkin.errors import ToolFailure
from cadkin.geometry import transform_from_sw
from cadkin.tools.files import json_path, read_json
from cadkin.tools.inventory import spatial_inventory
from cadkin.tools.grouping import group_inventory
from cadkin.tools.relations import relate_axes
from cadkin.tools.connections import review_connections, identity
from cadkin.tools.proximity_review import review_proximity
from cadkin.tools.face_contacts import review_probe


def require(condition, message, code='INVALID_CHAIN_SOURCE'):
    if not condition:
        raise ToolFailure(code, message)


def check_fields(actual, expected):
    require(isinstance(actual, dict), 'Expected an original result JSON.')
    for key, value in expected.items():
        if key not in ('captured_at_utc', 'limitations'):
            require(actual.get(key) == value, f'Derived source field differs: {key}.', 'EVIDENCE_MISMATCH')


class ChainSources:
    def __init__(self, root, inventory_path, grouping_review_path=None):
        self.root, self.cache, self.total_bytes = Path(root), {}, 0
        self.grouping_review_path = grouping_review_path
        self.inventory, self.inventory_binding = self.read(inventory_path)
        self.spatial, self.nodes = spatial_inventory(self.inventory)

    def read(self, name):
        require(isinstance(name, str) and bool(name), 'Missing source path.')
        path = json_path(self.root, name); key = str(path)
        if key not in self.cache:
            require(len(self.cache) < 256, 'Source graph exceeds 256 files.', 'CHAIN_SOURCE_LIMIT')
            try:
                size = path.stat().st_size
            except OSError as exc:
                raise ToolFailure('INVALID_INPUT', 'Source file is unavailable.', path=key) from exc
            require(self.total_bytes + size <= 128 * 1024 * 1024, 'Source graph exceeds 128 MiB.', 'CHAIN_SOURCE_LIMIT')
            data, digest = read_json(path)
            self.cache[key] = (data, {'path': key, 'sha256': digest})
            self.total_bytes += size
        return self.cache[key]

    def bound(self, binding):
        require(isinstance(binding, dict), 'Missing source binding.')
        data, actual = self.read(binding.get('path'))
        require(actual['sha256'] == binding.get('sha256'), 'Source file hash changed.', 'EVIDENCE_MISMATCH')
        return data, actual

    def inventory_match(self, binding):
        _, actual = self.bound(binding)
        require(actual['sha256'] == self.inventory_binding['sha256'], 'Different spatial inventory snapshot.', 'EVIDENCE_MISMATCH')

    def grouping(self, path):
        raw, binding = self.read(path)
        require(isinstance(raw, dict) and isinstance(raw.get('source'), dict), 'Invalid grouping file.')
        self.inventory_match({'path': raw['source'].get('inventory_path'), 'sha256': raw['source'].get('inventory_sha256')})
        review = None
        if raw.get('review_sha256') is not None:
            review_path = raw.get('review_path') or self.grouping_review_path
            require(review_path is not None, 'Supply grouping_review_path for older manually reviewed grouping files.', 'GROUPING_REVIEW_SOURCE_REQUIRED')
            review, rb = self.read(review_path)
            require(rb['sha256'] == raw['review_sha256'], 'Grouping manual review hash differs.', 'EVIDENCE_MISMATCH')
        expected = group_inventory(self.inventory, self.inventory_binding['sha256'], raw.get('scope_occurrence_path'), review)
        expected['source']['inventory_path'] = raw['source']['inventory_path']
        check_fields(raw, expected)
        return expected, binding

    def relations(self, path):
        raw, binding = self.read(path)
        require(isinstance(raw, dict) and isinstance(raw.get('sources'), list) and isinstance(raw.get('parameters'), dict), 'Invalid relation file.')
        self.inventory_match({'path': raw.get('inventory_path'), 'sha256': raw.get('inventory_sha256')})
        sources = []
        for source in raw['sources']:
            require(isinstance(source, dict), 'Invalid cylinder source binding.')
            envelope, b = self.bound({'path': source.get('source_path'), 'sha256': source.get('source_sha256')})
            sources.append((envelope, b['path'], b['sha256']))
        grouping = None
        if raw.get('grouping_source') is not None:
            _, gb = self.bound(raw['grouping_source']); grouping, _ = self.grouping(gb['path'])
        require(set(raw['parameters']) == {'distance_tolerance_mm', 'angle_tolerance_deg', 'max_pairs', 'max_candidates'}, 'Invalid relation parameters.')
        expected = relate_axes(self.inventory, self.inventory_binding['sha256'], sources, grouping=grouping, **raw['parameters'])
        check_fields(raw, expected)
        return expected, binding

    def connections(self, raw):
        sources = raw.get('sources'); require(isinstance(sources, dict), 'Missing connection sources.')
        self.inventory_match(sources.get('inventory'))
        if raw.get('connection_review_schema_version') == 2:
            require(set(sources) == {'inventory', 'mates'}, 'Root mate review cannot hide additional source families.')
            mates, mate_binding = self.bound(sources['mates'])
            expected = review_connections(None, mates, self.inventory, self.inventory_binding['sha256'])
            expected.update(sources=sources, geometry_candidates_evaluated=False, requires_human_review=False)
            check_fields(raw, expected)
            return 'connection', expected, {}, {'unmatched_mates': expected['unmatched_mates'],
                'coverage': expected['coverage'], 'original_review_coverage': expected['coverage'],
                'root_mate_source': mate_binding, 'replay_scope': 'verified_two_entity_root_mate_pairs'}
        _, rb = self.bound(sources.get('relations')); relations, _ = self.relations(rb['path'])
        mates, mate_binding = self.bound(sources.get('mates'))
        expected = review_connections(relations, mates, self.inventory, self.inventory_binding['sha256'])
        check_fields(raw, expected)
        # Replay exact mapped root-mate pairs as well, without inventing geometry candidates.
        extra = []
        for mate in mates['data']['mates']:
            paths = sorted({e['reference_occurrence_path'] for e in mate.get('entities') or [] if e.get('reference_status') == 'verified_root_occurrence'})
            if len(paths) == 2:
                extra.append(paths)
        expanded = review_connections(relations, mates, self.inventory, self.inventory_binding['sha256'], extra_occurrence_pairs=extra)
        return 'connection', expanded, {}, {'unmatched_mates': expanded['unmatched_mates'], 'coverage': expanded['coverage'],
            'original_review_coverage': expected['coverage'], 'root_mate_source': mate_binding,
            'replay_scope': 'axis_candidates_plus_verified_two_occurrence_root_mates'}

    def proximity(self, raw):
        sources = raw.get('sources'); require(isinstance(sources, dict), 'Missing proximity review sources.')
        self.inventory_match(sources.get('inventory'))
        worklist, _ = self.bound(sources.get('proximity'))
        require(isinstance(worklist, dict), 'Invalid proximity worklist.')
        self.inventory_match({'path': worklist.get('inventory_path'), 'sha256': worklist.get('inventory_sha256')})
        require(isinstance(raw.get('distance_sources'), list) and 1 <= len(raw['distance_sources']) <= 200, 'Missing distance sources.')
        distances = []
        for source in raw['distance_sources']:
            envelope, b = self.bound(source); distances.append((envelope, b['path'], b['sha256']))
        expected = review_proximity(worklist, self.inventory, self.inventory_binding['sha256'], distances, raw.get('contact_tolerance_mm'))
        check_fields(raw, expected)
        return 'component_proximity', expected, {'contact_tolerance_mm': expected['contact_tolerance_mm']}, {
            'unranked_occurrences': expected['unranked_occurrences'], 'coverage': expected['worklist_coverage']}

    def face_contacts(self, raw):
        require(isinstance(raw.get('pairs'), list) and 1 <= len(raw['pairs']) <= 100 and isinstance(raw.get('parameters'), dict), 'Invalid face contact review.')
        params = raw['parameters']; require(set(params) == {'contact_tolerance_mm', 'angle_tolerance_deg'}, 'Invalid face contact thresholds.')
        rows, errors, seen = [], [], set()
        for item in raw['pairs']:
            require(isinstance(item, dict), 'Invalid face contact pair.')
            probe, pb = self.bound({'path': item.get('probe_path'), 'sha256': item.get('probe_sha256')})
            require(isinstance(probe, dict) and isinstance(probe.get('data'), dict), 'Missing face probe data.')
            require(identity(probe['data'].get('document')) == identity(self.spatial['document']), 'Face probe document differs.', 'EVIDENCE_MISMATCH')
            sources = probe['data'].get('sources'); require(isinstance(sources, list) and len(sources) == 2, 'Missing probe sources.')
            for source in sources:
                require(isinstance(source, dict), 'Invalid face source.')
                self.bound(source)
                target = source.get('target'); require(isinstance(target, dict), 'Missing face target.')
                node = self.nodes.get(target.get('occurrence_path'))
                require(node is not None and all(target.get(k) == node.get(k) for k in ('file_path','referenced_configuration','parent_occurrence_path')),
                        'Face occurrence differs from inventory.', 'EVIDENCE_MISMATCH')
                require(isinstance(target.get('transform'), dict) and isinstance(node.get('transform'), dict), 'Missing face/spatial transform.')
                require(transform_from_sw(target['transform'].get('raw_array'))['raw_array'] == transform_from_sw(node['transform'].get('raw_array'))['raw_array'],
                        'Face occurrence pose differs from inventory.', 'EVIDENCE_MISMATCH')
            row, key = review_probe(self.root, probe, **params)
            require(key not in seen, 'Duplicate face probe pair.'); seen.add(key)
            rows.append({**row, 'probe_path': pb['path'], 'probe_sha256': pb['sha256']})
            if probe['status'] != 'ok':
                errors.append({'code':'SOURCE_INCOMPLETE','message':'Probe has partial/unknown evidence.','source_path':pb['path'],'source_errors':probe['errors']})
        counts = {state: sum(r['review_state'] == state for r in rows) for state in ('near_face_contact_candidate','near_points_orientation_unconfirmed','sample_gap_above_tolerance','unresolved')}
        expected = {'face_contact_review_schema_version':1, 'document':probe['data']['document'], 'parameters':params,
                    'scope':'provided_local_face_probes_only','pairs':rows,'counts':counts,'complete':not errors,'errors':errors,
                    'requires_review':True,'global_minimum_proven':False,'contact_confirmed':False,'mechanical_relation_confirmed':False,'solidworks_modified':False}
        check_fields(raw, expected)
        return 'face_contact', expected, params, {'scope': expected['scope']}

    def evidence(self, path):
        raw, binding = self.read(path); require(isinstance(raw, dict), 'Invalid evidence file.')
        schemas = [('connection_review_schema_version',self.connections),('proximity_review_schema_version',self.proximity),('face_contact_review_schema_version',self.face_contacts)]
        matches = [loader for key, loader in schemas if raw.get(key) == 1 or
                   (key == 'connection_review_schema_version' and raw.get(key) == 2)]
        require(len(matches) == 1, 'Use a supported connection/proximity/face-contact review result file.')
        return (*matches[0](raw), binding)

    def finish(self):
        for path, (_, binding) in self.cache.items():
            _, digest = read_json(Path(path))
            require(digest == binding['sha256'], 'Source changed while compiling the dossier.', 'EVIDENCE_MISMATCH')
        return [binding for _, binding in sorted(self.cache.values(), key=lambda item:item[1]['path'])]
