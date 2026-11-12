"""Bounded part-definition face capture and stable target contexts."""
from datetime import datetime, timezone

from cadkin._vendor.sw_mcp import call, value
from cadkin.adapters.evidence import boolean, integer, sequence, evidence_error
from cadkin.adapters.face_identity import capture_face_reference
from cadkin.errors import ToolFailure, success
from cadkin.face_geometry import descriptor
from cadkin.geometry import transform_from_sw


def read_descriptor(face):
    surface = value(face, 'GetSurface')
    if surface is None:
        raise ToolFailure('SURFACE_UNAVAILABLE', 'Face has no readable surface.')
    kind, params = 'other', None
    if boolean(value(surface, 'IsPlane'), 'IsPlane'):
        kind, params = 'plane', value(surface, 'PlaneParams')
    elif boolean(value(surface, 'IsCylinder'), 'IsCylinder'):
        kind, params = 'cylinder', value(surface, 'CylinderParams')
    return descriptor({'surface_type': kind, 'surface_parameters_part': params,
                       'area_part_m2': value(face, 'GetArea'), 'uv_bounds': value(face, 'GetUVBounds'),
                       'body_type': integer(value(value(face, 'GetBody'), 'GetType'), 'body type'),
                       'face_in_surface_sense': boolean(value(face, 'FaceInSurfaceSense'), 'FaceInSurfaceSense')})


class FaceContext:
    def __init__(self, adapter, token, path):
        self.adapter = adapter
        self.doc, self.info, self.node, self.component, self.errors = adapter._evidence_target(token, path)
        self.part, self.data = self.current()

    def current(self):
        a, node, component = self.adapter, self.node, self.component
        a._check_evidence_target(self.info, node, component)
        if not boolean(value(self.doc, 'IsEditingSelf'), 'IsEditingSelf'):
            raise ToolFailure('IN_CONTEXT_EDIT_ACTIVE', 'Use the assembly edit context; no edit mode was changed.')
        part = value(component, 'GetModelDoc2')
        if part is None:
            raise ToolFailure('COMPONENT_MODEL_UNAVAILABLE', 'Target definition is not loaded.')
        info = a._info(part)
        if info['document_type'] != 'part':
            raise ToolFailure('NOT_PART_COMPONENT', 'Choose a resolved leaf part occurrence.')
        if not node['referenced_configuration'] or info['configuration'] != node['referenced_configuration']:
            raise ToolFailure('COMPONENT_CONFIGURATION_MISMATCH', 'Part configuration differs from the occurrence.')
        if value(component, 'GetPathName') != node['file_path']:
            raise ToolFailure('COMPONENT_CHANGED', 'Target file changed.')
        transform = transform_from_sw(value(value(component, 'Transform2'), 'ArrayData'))
        return part, {**{k: node[k] for k in ('occurrence_path', 'parent_occurrence_path', 'file_path', 'referenced_configuration')},
                      'source_part': info, 'transform': transform}

    def check(self):
        _, latest = self.current()
        if latest != self.data:
            raise ToolFailure('COMPONENT_CHANGED', 'Target context changed; discard mixed face evidence.')


class FaceOperations:
    def sw_component_faces(self, expected_document_token, occurrence_path, max_bodies=20, max_faces=200):
        context = FaceContext(self, expected_document_token, occurrence_path)
        errors, rows = list(context.errors), []
        bodies = sequence(call(context.part, 'GetBodies2', -1, False), 'GetBodies2')
        truncated, inspected = len(bodies) > max_bodies, 0
        if truncated:
            errors.append({'code': 'BODY_LIMIT', 'message': 'Face source includes only the bounded body prefix.'})
        for bi, body in enumerate(bodies[:max_bodies]):
            context.check(); inspected += 1
            try:
                face = value(body, 'GetFirstFace')
            except Exception as exc:
                errors.append(evidence_error(exc, body_index=bi)); continue
            fi = 0
            while face is not None:
                if len(rows) >= max_faces:
                    truncated = True
                    errors.append({'code': 'FACE_LIMIT', 'message': 'Stopped at global face budget.'}); break
                context.check()
                row = {'body_index': bi, 'face_index': fi, 'descriptor': None, 'face_reference': None, 'errors': []}
                for field, read in (('descriptor', lambda: read_descriptor(face)),
                                    ('face_reference', lambda: capture_face_reference(context.part, face, self.app, self.runtime))):
                    try:
                        row[field] = read()
                    except Exception as exc:
                        error = evidence_error(exc, body_index=bi, face_index=fi, field=field)
                        row['errors'].append(error); errors.append(error)
                rows.append(row)
                try:
                    face = value(face, 'GetNextFace')
                except Exception as exc:
                    errors.append(evidence_error(exc, body_index=bi, face_index=fi, field='next_face')); break
                fi += 1
            if len(rows) >= max_faces and truncated:
                break
        context.check()
        return success({'face_inventory_schema_version': 1, 'document': context.info, 'target': context.data,
                        'captured_at_utc': datetime.now(timezone.utc).isoformat(), 'snapshot_atomic': False,
                        'geometry_scope': 'referenced_part_definition', 'assembly_instance_features_evaluated': False,
                        'faces': rows, 'face_count': len(rows), 'reported_body_count': len(bodies), 'inspected_body_count': inspected,
                        'complete': not errors, 'truncated': truncated, 'solidworks_modified': False,
                        'limitations': ['Face indices only locate this hashed snapshot; persistent IDs must be resolved and verified.',
                                        'UV bounds and surface parameters are not the trimmed face boundary or a tessellation.',
                                        'Definition geometry excludes assembly-level cuts/features; unsupported surfaces remain catalogued, not probed.',
                                        'No atomic geometry revision or full topology fingerprint is claimed.']}, errors)
