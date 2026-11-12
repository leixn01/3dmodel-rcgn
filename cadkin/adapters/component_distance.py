"""Read a single pair's component-context distance without changing selection."""
from datetime import datetime, timezone

from cadkin._vendor.sw_mcp import call, value
from cadkin.adapters.evidence import boolean, evidence_error
from cadkin.distance import distance_result
from cadkin.errors import ToolFailure, success
from cadkin.geometry import transform_from_sw


class ComponentDistanceOperations:
    def sw_component_distance(self, expected_document_token, left_occurrence_path, right_occurrence_path):
        if left_occurrence_path == right_occurrence_path:
            raise ToolFailure('INVALID_ARGUMENTS', 'Choose two distinct occurrences, including repeated-part instances if needed.')
        doc, info, nodes, errors, objects = self._spatial_tree(expected_document_token, 20000, 128)
        structural = {'COMPONENT_LIMIT', 'DEPTH_LIMIT', 'CHILDREN_READ_FAILED', 'INVALID_INSTANCE_NAME'}
        if any(e['code'] in structural or e['code'] == 'COMPONENT_READ_FAILED' and e.get('field') == 'name' for e in errors):
            raise ToolFailure('COMPONENT_LOOKUP_INCOMPLETE', 'A complete unambiguous occurrence lookup is required.', traversal_errors=errors)
        by_path = {node['occurrence_path']: node for node in nodes}
        parents = {node['parent_occurrence_path'] for node in nodes}

        def check_document():
            self._check_current(info)
            if not boolean(value(doc, 'IsEditingSelf'), 'IsEditingSelf'):
                raise ToolFailure('IN_CONTEXT_EDIT_ACTIVE', 'Exit component in-context editing before assembly measurements; no edit mode was changed.')

        def context(path):
            check_document()
            if path not in objects:
                raise ToolFailure('COMPONENT_NOT_FOUND', 'Use full occurrence paths from the current component tree.', occurrence_path=path)
            node, component = by_path[path], objects[path]
            if node['is_suppressed'] is not False or node['suppression_state'] not in (2, 3):
                raise ToolFailure('UNRESOLVED_COMPONENT', 'Both targets must be resolved; no component was loaded or resolved.', occurrence_path=path)
            self._check_evidence_target(info, node, component)
            if path in parents:
                raise ToolFailure('NOT_PART_COMPONENT', 'Measure leaf part occurrences, not multipart subassemblies.')
            part = value(component, 'GetModelDoc2')
            if part is None:
                raise ToolFailure('COMPONENT_MODEL_UNAVAILABLE', 'Target part is not loaded; no document was opened.')
            part_info = self._info(part)
            if part_info['document_type'] != 'part':
                raise ToolFailure('NOT_PART_COMPONENT', 'ClosestDistance component inputs are limited to part occurrences.')
            if not node['referenced_configuration'] or part_info['configuration'] != node['referenced_configuration']:
                raise ToolFailure('COMPONENT_CONFIGURATION_MISMATCH', 'Loaded part configuration differs from the occurrence reference.')
            if value(component, 'GetPathName') != node['file_path']:
                raise ToolFailure('COMPONENT_CHANGED', 'Target file changed during the read.')
            transform = transform_from_sw(value(value(component, 'Transform2'), 'ArrayData'))
            return {**{k: node[k] for k in ('occurrence_path', 'parent_occurrence_path', 'file_path', 'referenced_configuration')},
                    'transform': transform, 'source_part': part_info}

        paths = [left_occurrence_path, right_occurrence_path]
        contexts = [context(path) for path in paths]
        measurement = None
        try:
            pythoncom, client = self.runtime
            left_point = client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_VARIANT, None)
            right_point = client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_VARIANT, None)
            # Pass occurrence objects to the root document. No face/axis approximation, part-body
            # copies, selection, or extra component transform is applied to these output points.
            distance = call(doc, 'ClosestDistance', objects[paths[0]], objects[paths[1]], left_point, right_point)
            measurement = distance_result(distance, left_point.value, right_point.value)
        except Exception as exc:
            errors.append(evidence_error(exc, field='measurement'))
        for path, before in zip(paths, contexts):
            if context(path) != before:
                raise ToolFailure('COMPONENT_CHANGED', 'Target context changed during measurement; mixed evidence was discarded.')
        check_document()
        return success({'component_distance_schema_version': 1, 'document': info,
                        'captured_at_utc': datetime.now(timezone.utc).isoformat(), 'snapshot_atomic': False,
                        'scope': 'two_resolved_part_occurrences', 'targets': contexts,
                        'method': 'IModelDoc2.ClosestDistance(IComponent2,IComponent2)',
                        'geometry_scope': 'assembly_component_context',
                        'measurement': measurement, 'measurement_status': 'ok' if measurement is not None else 'unavailable',
                        'units': {'api_length': 'm', 'display_length': 'mm'}, 'complete': not errors,
                        'solidworks_modified': False, 'contact_confirmed': False, 'mechanical_relation_confirmed': False,
                        'limitations': ['One current component-pair minimum-distance result; no mate data is required or inferred.',
                                        'A zero/small distance does not distinguish touching, intersecting or contained solids and is not contact/fit/joint confirmation.',
                                        'Witness points are API output in the active assembly model frame, not persistent face IDs or a contact patch.',
                                        'Part instances may include multiple bodies; internal subassembly aggregate inputs are rejected. Validate supported geometry on the target SOLIDWORKS version.',
                                        'No atomic geometry revision is available. Keep geometry/configuration/pose unchanged; presentation/exploded display positions are not evaluated.']}, errors)
