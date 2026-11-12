"""Opt-in root mate face geometry and concentric options; never edits a feature."""
from cadkin._vendor.sw_mcp import call, value
from cadkin.adapters.evidence import boolean, integer, evidence_error
from cadkin.adapters.face_identity import capture_face_reference, resolve_face, same_object
from cadkin.errors import ToolFailure
from cadkin.geometry import numbers
from cadkin.face_geometry import unit


def geometry(entity, reference):
    surface = value(reference, 'GetSurface')
    if surface is None:
        raise ToolFailure('MATE_SURFACE_UNAVAILABLE', 'Mate face has no surface.')
    kind = ('plane' if boolean(value(surface, 'IsPlane'), 'IsPlane') else
            'cylinder' if boolean(value(surface, 'IsCylinder'), 'IsCylinder') else 'other')
    size = integer(value(entity, 'GetEntityParamsSize'), 'GetEntityParamsSize', 0)
    if size > 64:
        raise ToolFailure('INVALID_MATE_PARAMS', 'Mate parameter array is too large.')
    raw = numbers(value(entity, 'EntityParams'), size, 'INVALID_MATE_PARAMS')
    data = {'surface_type': kind, 'entity_params_raw': raw, 'frame': 'root_assembly',
            'point_root_m': None, 'direction_root_unit': None, 'radius_m': None}
    if kind in ('plane', 'cylinder'):
        if size < (7 if kind == 'cylinder' else 6):
            raise ToolFailure('INVALID_MATE_PARAMS', 'Insufficient analytic mate entity parameters.')
        data.update(point_root_m=raw[:3], direction_root_unit=unit(raw[3:6]))
        if kind == 'cylinder':
            if raw[6] <= 0:
                raise ToolFailure('INVALID_MATE_PARAMS', 'Cylinder radius must be positive.')
            data['radius_m'] = raw[6]
    return data


def options(feature, code):
    if code != 1:
        return {'concentric_lock_rotation': None, 'status': 'not_applicable'}
    definition = value(feature, 'GetDefinition')
    if definition is None:
        raise ToolFailure('MATE_OPTIONS_UNAVAILABLE', 'Concentric feature definition is unavailable.')
    return {'concentric_lock_rotation': boolean(value(definition, 'LockRotation'), 'LockRotation'),
            'status': 'read', 'api': 'IConcentricMateFeatureData.LockRotation'}


class MateGeometryCapture:
    def __init__(self, adapter, token):
        self.adapter = adapter
        self.doc, self.info = adapter._document(token)
        self.entities, self.features = [], []

    def inspect(self, mate, entity, record):
        record['reference_geometry'] = {'status': 'unavailable'}
        if record.get('reference_status') != 'verified_root_occurrence':
            return
        if record.get('reference_type_code') != 2:
            record['reference_geometry'] = {'status': 'unsupported_reference_type'}
            return
        reference = value(entity, 'Reference')
        if reference is None:
            raise ToolFailure('MATE_FACE_UNAVAILABLE', 'Mate face reference is null.')
        data = geometry(entity, reference)
        if data['entity_params_raw'] != record['entity_params_raw']:
            raise ToolFailure('GEOMETRY_CHANGED', 'Mate parameters changed during capture.')
        pid = capture_face_reference(self.doc, reference, self.adapter.app, self.adapter.runtime, 'active_root_assembly')
        record['reference_geometry'] = {'status': 'read', **data, 'persistent_reference': pid,
            'identity_method': 'root_persistent_reference_roundtrip_IsSame',
            'catalog_face_match': False}
        self.entities.append((mate, record['entity_index'], reference, value(entity, 'ReferenceComponent'), record))

    def feature(self, feature, mate, record):
        try:
            record['constraint_options'] = options(feature, record['type_code'])
        except Exception as exc:
            record['constraint_options'] = {'status': 'unavailable', 'concentric_lock_rotation': None}
            record['errors'].append(evidence_error(exc, field='constraint_options'))
        self.features.append((feature, mate, record))

    def finish(self):
        a = self.adapter
        for feature, mate, record in self.features:
            a._check_current(self.info)
            for member, key in (('Type', 'type_code'), ('Alignment', 'alignment_code')):
                if record[key] is None: continue  # The initial failure is already retained as partial.
                try:
                    current = value(mate, member)
                except Exception as exc:
                    raise ToolFailure('MATE_STATE_CHANGED', 'Mate state could not be rechecked.') from exc
                if current != record[key]:
                    raise ToolFailure('MATE_STATE_CHANGED', 'Mate type/alignment changed during capture.')
            if record['constraint_options']['status'] == 'read':
                try:
                    current = options(feature, record['type_code'])
                except Exception as exc:
                    raise ToolFailure('MATE_STATE_CHANGED', 'Concentric rotation lock could not be rechecked.') from exc
                if current != record['constraint_options']:
                    raise ToolFailure('MATE_STATE_CHANGED', 'Concentric rotation lock changed during capture.')
        for mate, index, reference, component, record in self.entities:
            a._check_current(self.info)
            entity = call(mate, 'MateEntity', index)
            latest = value(entity, 'Reference')
            if (value(entity, 'ReferenceType2') != 2 or not same_object(a.app, component, value(entity, 'ReferenceComponent')) or
                    not same_object(a.app, reference, latest)):
                raise ToolFailure('GEOMETRY_CHANGED', 'Mate entity reference changed during capture.')
            saved = record['reference_geometry']
            resolved = resolve_face(self.doc, saved['persistent_reference'], a.runtime, 'active_root_assembly')
            current = geometry(entity, latest)
            if not same_object(a.app, latest, resolved) or current != {k: saved[k] for k in current}:
                raise ToolFailure('GEOMETRY_CHANGED', 'Mate face identity/geometry changed during capture.')
        a._check_current(self.info)
