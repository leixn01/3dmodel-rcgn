"""Match root mate references to saved part faces using live CAD object identity."""
from cadkin._vendor.sw_mcp import call, value
from cadkin.adapters.evidence import boolean, evidence_error, integer
from cadkin.adapters.face_identity import resolve_face, same_object
from cadkin.errors import ToolFailure, success
from cadkin.geometry import cylinder_from_sw, transform_from_sw


class FaceMatcher:
    def __init__(self, adapter, info, sources, max_candidate_faces, max_comparisons):
        self.adapter, self.info = adapter, info
        self.sources = {s['data']['occurrence_path']: s for s in sources}
        self.prepared, self.verifications, self.errors = {}, [], []
        self.comparisons, self.max_comparisons = 0, max_comparisons
        self.total_faces = sum(len(s['data']['cylinders']) for s in sources)
        self.selected, remaining = {}, max_candidate_faces
        for path, source in sorted(self.sources.items()):
            rows = sorted(source['data']['cylinders'], key=lambda r: (r['body_index'], r['face_index']))
            self.selected[path] = rows[:remaining]
            remaining -= len(self.selected[path])
            if not source['binding']['complete']:
                self.errors.append({'code': 'SOURCE_INCOMPLETE', 'message': 'Cylinder evidence is incomplete.',
                                    'occurrence_path': path, 'source_errors': source['binding']['errors']})
        self.truncated = self.total_faces > max_candidate_faces
        if self.truncated:
            self.errors.append({'code': 'CANDIDATE_FACE_LIMIT', 'message': 'Only the first bounded candidate faces are eligible for comparison.'})

    def _context(self, source, component):
        self.adapter._check_evidence_target(self.info, source['node'], component)
        current = transform_from_sw(value(value(component, 'Transform2'), 'ArrayData'))
        if current['raw_array'] != source['data']['transform']['raw_array']:
            raise ToolFailure('COMPONENT_CHANGED', 'Occurrence pose differs from the saved cylinder evidence.')
        loaded = value(component, 'GetModelDoc2')
        if loaded is None:
            raise ToolFailure('COMPONENT_MODEL_UNAVAILABLE', 'Referenced part is not loaded; no document was opened.')
        part_info = self.adapter._info(loaded)
        keys = ('document_token', 'path', 'title', 'configuration', 'document_type')
        if any(part_info[k] != source['data']['source_part'].get(k) for k in keys):
            raise ToolFailure('COMPONENT_CONFIGURATION_MISMATCH', 'Loaded part identity/configuration differs from the source.')
        return loaded

    def _geometry(self, source, face, row):
        surface = value(face, 'GetSurface')
        if surface is None or not boolean(value(surface, 'IsCylinder'), 'IsCylinder'):
            raise ToolFailure('FACE_GEOMETRY_MISMATCH', 'Resolved face is no longer an analytic cylinder.')
        current = cylinder_from_sw(value(surface, 'CylinderParams'), transform_from_sw(source['data']['transform']['raw_array']))
        # Conservative: even a reparameterization asks for recollection. Equal axes alone cannot identify a face.
        if current['raw_array'] != row['raw_array']:
            raise ToolFailure('FACE_GEOMETRY_MISMATCH', 'Resolved face cylinder parameters differ; recollect geometry and relations.')

    def _prepare(self, path, component):
        if path in self.prepared:
            return self.prepared[path]
        source = self.sources[path]
        part = self._context(source, component)
        faces, errors = [], []
        for row in self.selected[path]:
            self.adapter._check_current(self.info)
            try:
                face = resolve_face(part, row.get('face_reference'), self.adapter.runtime)
                self._geometry(source, face, row)
                assembly_face = call(component, 'GetCorrespondingEntity', face)
                if assembly_face is None:
                    raise ToolFailure('FACE_CORRESPONDENCE_UNAVAILABLE', 'No occurrence entity corresponds to this definition face.')
                faces.append((row, face, assembly_face))
            except Exception as exc:
                errors.append(evidence_error(exc, occurrence_path=path, body_index=row['body_index'], face_index=row['face_index']))
        result = {'component': component, 'part': part, 'faces': faces, 'errors': errors, 'compared': set()}
        self.prepared[path] = result
        return result

    def inspect(self, mate, entity, record):
        match = {'status': 'unknown', 'matches': [], 'compared_faces': 0}
        record['face_match'] = match
        if record.get('reference_status') != 'verified_root_occurrence':
            raise ToolFailure('FACE_REFERENCE_CONTEXT_UNAVAILABLE', 'Mate occurrence identity is not verified.')
        path = record['reference_occurrence_path']
        if path not in self.sources:
            match['status'] = 'outside_scope'
            return
        if record.get('reference_type_code') != 2:  # swSelFACES, never interpreted as cylinder geometry.
            match['status'] = 'not_face'
            return
        reference = value(entity, 'Reference')
        if reference is None:
            raise ToolFailure('MATE_FACE_UNAVAILABLE', 'Mate face reference is null.')
        component = value(entity, 'ReferenceComponent')
        prepared = self._prepare(path, component)
        errors = [dict(e) for e in prepared['errors']]
        for row, _, assembly_face in prepared['faces']:
            if self.comparisons >= self.max_comparisons:
                self.truncated = True
                errors.append({'code': 'FACE_COMPARISON_LIMIT', 'message': 'Mate-to-face comparison budget reached.'})
                break
            self.adapter._check_current(self.info)
            self.comparisons += 1
            try:
                same = same_object(self.adapter.app, reference, assembly_face)
                match['compared_faces'] += 1
                prepared['compared'].add((row['body_index'], row['face_index']))
                if same:
                    binding = self.sources[path]['binding']
                    match['matches'].append({'occurrence_path': path, 'body_index': row['body_index'], 'face_index': row['face_index'],
                                             'source_sha256': binding['source_sha256'], 'source_path': binding['source_path'],
                                             'identity_check': 'resolved_part_face_to_occurrence_IsSame'})
            except Exception as exc:
                errors.append(evidence_error(exc, body_index=row['body_index'], face_index=row['face_index']))
        match['eligible_faces'] = len(self.selected[path])
        match['source_faces'] = len(self.sources[path]['data']['cylinders'])
        match['status'] = 'partial' if errors or match['eligible_faces'] != match['source_faces'] else 'checked'
        if match['compared_faces']:
            self.verifications.append((mate, record['entity_index'], reference, component))
        record['errors'].extend({**error, 'field': 'face_match'} for error in errors)

    def finish(self):
        # Reject changes observed after the comparison, without claiming an atomic snapshot.
        for path, prepared in self.prepared.items():
            source = self.sources[path]
            part = self._context(source, prepared['component'])
            for row, face, assembly_face in prepared['faces']:
                if (row['body_index'], row['face_index']) not in prepared['compared']:
                    continue
                self.adapter._check_current(self.info)
                try:
                    latest = resolve_face(part, row['face_reference'], self.adapter.runtime)
                    self._geometry(source, latest, row)
                    corresponding = call(prepared['component'], 'GetCorrespondingEntity', latest)
                    if corresponding is None or not same_object(self.adapter.app, face, latest) or not same_object(self.adapter.app, assembly_face, corresponding):
                        raise ToolFailure('GEOMETRY_CHANGED', 'Face correspondence changed during capture.')
                except Exception as exc:
                    raise ToolFailure('GEOMETRY_CHANGED', 'Face identity/geometry could not be revalidated; discard mixed evidence.', reason=str(exc)) from exc
        for mate, index, reference, component in self.verifications:
            self.adapter._check_current(self.info)
            entity = call(mate, 'MateEntity', index)
            try:
                current_ref, current_component = value(entity, 'Reference'), value(entity, 'ReferenceComponent')
                if (integer(value(entity, 'ReferenceType2'), 'ReferenceType2') != 2 or current_ref is None or current_component is None or
                    not same_object(self.adapter.app, reference, current_ref) or not same_object(self.adapter.app, component, current_component)):
                    raise ValueError('Mate reference changed.')
            except Exception as exc:
                raise ToolFailure('MATE_REFERENCE_CHANGED', 'Mate entity could not be revalidated; discard mixed evidence.', reason=str(exc)) from exc
        self.adapter._check_current(self.info)


class MateFaceOperations:
    def sw_match_mate_faces(self, expected_document_token, inventory_binding, sources, max_candidate_faces=100,
                           max_comparisons=2000, max_features=2000, max_mates=200, max_entities=16, max_depth=32):
        _, info = self._document(expected_document_token)
        if any(info[k] != inventory_binding['document'].get(k) for k in ('document_token', 'path', 'title', 'configuration', 'document_type')):
            raise ToolFailure('EVIDENCE_MISMATCH', 'Live document differs from the saved inventory.')
        matcher = FaceMatcher(self, info, sources, max_candidate_faces, max_comparisons)
        result = self._collect_mates(expected_document_token, max_features, max_mates, max_entities, max_depth, matcher.inspect)
        matcher.finish()
        data = result['data']
        errors = result['errors'] + matcher.errors
        if not inventory_binding['complete']:
            errors.append({'code': 'SOURCE_INCOMPLETE', 'message': 'Spatial evidence is incomplete.', 'source_errors': inventory_binding['errors']})
        data['face_matching'] = {'schema_version': 1, 'scope': 'provided_part_faces_and_active_root_mate_entities',
                                 'inventory_path': inventory_binding['path'], 'inventory_sha256': inventory_binding['sha256'],
                                 'cylinder_sources': [{k: s['binding'][k] for k in ('occurrence_path', 'source_path', 'source_sha256')} for s in sources],
                                 'requested_faces': matcher.total_faces, 'resolved_faces': sum(len(p['faces']) for p in matcher.prepared.values()),
                                 'comparisons': matcher.comparisons, 'max_candidate_faces': max_candidate_faces, 'max_comparisons': max_comparisons,
                                 'unvisited_occurrences': sorted(set(matcher.sources) - set(matcher.prepared)),
                                 'identity_method': 'GetObjectByPersistReference3 + IComponent2.GetCorrespondingEntity + ISldWorks.IsSame',
                                 'complete': not errors, 'truncated': matcher.truncated or data['truncated']}
        data['complete'], data['truncated'] = not errors, matcher.truncated or data['truncated']
        data['limitations'].extend([
            'Face identity applies only to supplied source hashes and successfully compared references. Unvisited/outside-scope/non-face entities remain untested.',
            'Body/face indices only locate a record inside the hashed source. Persistent ID bytes are resolved, never compared as identity.',
            'Matching faces do not prove finite contact, feature health, solved constraints, remaining DOFs or mechanical joints.',
            'Definition parameters are rechecked; assembly-level face geometry/cuts and topology history are not evaluated. Capture with no concurrent edits.'])
        return success(data, errors)
