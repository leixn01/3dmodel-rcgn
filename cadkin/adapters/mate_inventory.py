"""Read mate features owned by the active root assembly; never activate subassemblies."""
from datetime import datetime, timezone

from cadkin._vendor.sw_mcp import call, value
from cadkin.adapters.evidence import boolean, evidence_error, integer
from cadkin.adapters.mate_records import read_mate
from cadkin.errors import ToolFailure, success
from cadkin.geometry import transform_from_sw


class MateInventoryOperations:
    def _mate_feature_state(self, feature):
        pythoncom, client = self.runtime
        empty = client.VARIANT(pythoncom.VT_EMPTY, None)
        states = call(feature, 'IsSuppressed2', 1, empty)  # swThisConfiguration=1
        if not isinstance(states, (tuple, list)) or len(states) != 1:
            raise ToolFailure('MATE_STATE_UNAVAILABLE', 'Expected one suppression Boolean for the active configuration.')
        suppressed = boolean(states[0], 'IsSuppressed2')
        warning = client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_BOOL, False)
        code = integer(call(feature, 'GetErrorCode2', warning), 'GetErrorCode2', 0)
        is_warning = boolean(warning.value, 'IsWarning') if code else None
        rolled_back = boolean(value(feature, 'IsRolledBack'), 'IsRolledBack')
        state = 'suppressed' if suppressed else ('rolled_back' if rolled_back else (
            'unsuppressed_feature_issue' if code else 'unsuppressed_no_feature_error'))
        return {'suppressed': suppressed, 'rolled_back': rolled_back, 'feature_error_code': code,
                'error_is_warning': is_warning, 'state': state, 'solver_validity': 'not_evaluated'}

    def sw_mate_inventory(self, expected_document_token, max_features=2000, max_mates=200, max_entities=16, max_depth=32):
        return self._collect_mates(expected_document_token, max_features, max_mates, max_entities, max_depth)

    def _collect_mates(self, expected_document_token, max_features=2000, max_mates=200, max_entities=16, max_depth=32,
                       inspect_entity=None):
        doc, info, nodes, errors, objects = self._spatial_tree(expected_document_token, 20000, 128)
        structural = {'COMPONENT_LIMIT', 'DEPTH_LIMIT', 'CHILDREN_READ_FAILED', 'INVALID_INSTANCE_NAME'}
        if any(e['code'] in structural or (e['code'] == 'COMPONENT_READ_FAILED' and e.get('field') == 'name') for e in errors):
            raise ToolFailure('COMPONENT_LOOKUP_INCOMPLETE', 'A unique root occurrence map is required.', traversal_errors=errors)
        by_path = {n['occurrence_path']: n for n in nodes}
        contexts = {}

        def resolve_reference(reference, name):
            if name not in objects or integer(call(self.app, 'IsSame', reference, objects[name]), 'IsSame') != 1:
                raise ToolFailure('MATE_REFERENCE_UNRESOLVED', 'Reference was not verified as the named root occurrence; no basename matching.')
            node, component = by_path[name], objects[name]
            if node['suppression_state'] not in (2, 3) or node['is_suppressed']:
                raise ToolFailure('UNRESOLVED_COMPONENT', 'Mate reference occurrence is not resolved.')
            transform = transform_from_sw(value(value(component, 'Transform2'), 'ArrayData'))
            context = {k: node[k] for k in ('occurrence_path', 'parent_occurrence_path', 'file_path', 'referenced_configuration')}
            context['transform'] = transform
            if name in contexts and contexts[name] != context:
                raise ToolFailure('COMPONENT_CHANGED', 'Referenced occurrence changed during mate capture.')
            contexts[name] = context
            return {'reference_occurrence_path': name, 'reference_status': 'verified_root_occurrence',
                    'identity_check': 'ISldWorks.IsSame=swObjectSame'}

        mates, verification, seen = [], [], set()
        scanned, groups, truncated = 0, 0, False
        # Stack entries are one sibling chain, its ancestor IDs, and root-MateGroup ownership.
        stack = [(value(doc, 'FirstFeature'), 'GetNextFeature', (), False)]
        while stack:
            feature, next_member, ancestors, in_group = stack.pop()
            if feature is None:
                continue
            self._check_current(info)
            if scanned >= max_features:
                truncated = True
                errors.append({'code': 'FEATURE_LIMIT', 'message': 'Feature traversal budget reached.'})
                break
            scanned += 1
            try:
                fid = integer(value(feature, 'GetID'), 'GetID', 0)
                name, kind = value(feature, 'Name'), value(feature, 'GetTypeName2')
                if not isinstance(name, str) or not name or not isinstance(kind, str) or not kind:
                    raise ToolFailure('INVALID_FEATURE', 'Feature name/type is unreadable.')
                if fid in seen:
                    raise ToolFailure('FEATURE_REVISIT', 'Repeated feature ID; traversal branch stopped instead of looping or duplicating evidence.')
                seen.add(fid)
            except Exception as exc:
                errors.append(evidence_error(exc, field='feature_identity'))
                continue  # Next cannot be trusted when identity/cycle checks fail.
            try:
                stack.append((value(feature, next_member), next_member, ancestors, in_group))
            except Exception as exc:
                errors.append(evidence_error(exc, feature_id=fid, field='next_feature'))
            is_group = kind == 'MateGroup'
            if is_group and not in_group:
                groups += 1
            is_mate = in_group and kind.startswith('Mate') and not is_group
            if is_mate:
                if len(mates) >= max_mates:
                    truncated = True
                    errors.append({'code': 'MATE_LIMIT', 'message': 'Mate record budget reached.'})
                    break
                state_errors = []
                try:
                    activity = self._mate_feature_state(feature)
                except Exception as exc:
                    activity = {'suppressed': None, 'rolled_back': None, 'feature_error_code': None,
                                'error_is_warning': None, 'state': 'unknown', 'solver_validity': 'not_evaluated'}
                    state_errors.append(evidence_error(exc, feature_id=fid, field='feature_state'))
                try:
                    mate = value(feature, 'GetSpecificFeature2')
                    if mate is None:
                        raise ToolFailure('MATE_INTERFACE_UNAVAILABLE', 'Mate feature has no readable specific interface.')
                    record, limited = read_mate(mate, len(mates), max_entities,
                                               lambda: self._check_current(info), resolve_reference, inspect_entity)
                    truncated = truncated or limited
                except ToolFailure as exc:
                    if exc.code in {'DOCUMENT_CHANGED', 'COMPONENT_CHANGED'}:
                        raise
                    record = {'mate_index': len(mates), 'type_code': None, 'type_name': None, 'alignment_code': None,
                              'entity_count': None, 'entities': None, 'errors': [evidence_error(exc, field='mate_interface')]}
                except Exception as exc:
                    record = {'mate_index': len(mates), 'type_code': None, 'type_name': None, 'alignment_code': None,
                              'entity_count': None, 'entities': None, 'errors': [evidence_error(exc, field='mate_interface')]}
                record.pop('constraint_activity', None)
                record.update(feature_id=fid, feature_name=name, feature_type=kind, activity=activity,
                              owning_assembly='active_root_assembly', entity_params_frame='root_assembly',
                              owner_configuration=info['configuration'])
                record['errors'].extend(state_errors)
                # Context changes must never be downgraded into usable mixed snapshots.
                for error in record['errors']:
                    if error['code'] in {'DOCUMENT_CHANGED', 'COMPONENT_CHANGED', 'GEOMETRY_CHANGED', 'COMPONENT_CONFIGURATION_MISMATCH'}:
                        raise ToolFailure(error['code'], 'Source context changed during mate capture; discard mixed evidence.')
                record['read_status'] = 'partial' if record['errors'] else 'ok'
                errors.extend(record['errors'])
                mates.append(record)
                verification.append((feature, fid, name, activity))
            elif is_group or in_group:
                try:
                    child = value(feature, 'GetFirstSubFeature')
                    if child is not None:
                        if len(ancestors) + 1 >= max_depth:
                            truncated = True
                            errors.append({'code': 'FEATURE_DEPTH_LIMIT', 'message': 'Mate subtree depth limit reached.', 'feature_id': fid})
                        else:
                            stack.append((child, 'GetNextSubFeature', ancestors + (fid,), True))
                except Exception as exc:
                    errors.append(evidence_error(exc, feature_id=fid, field='subfeatures'))
        self._check_current(info)
        for feature, fid, name, activity in verification:
            self._check_current(info)
            if value(feature, 'GetID') != fid or value(feature, 'Name') != name:
                raise ToolFailure('MATE_STATE_CHANGED', 'Mate identity changed during capture; discard mixed evidence.')
            if activity['state'] != 'unknown':
                try:
                    current = self._mate_feature_state(feature)
                except Exception as exc:
                    raise ToolFailure('MATE_STATE_CHANGED', 'Mate state could not be rechecked.', reason=str(exc)) from exc
                if current != activity:
                    raise ToolFailure('MATE_STATE_CHANGED', 'Mate suppression/error/rollback state changed during capture.')
        for path, context in contexts.items():
            self._check_evidence_target(info, by_path[path], objects[path])
            latest = transform_from_sw(value(value(objects[path], 'Transform2'), 'ArrayData'))
            if latest['raw_array'] != context['transform']['raw_array']:
                raise ToolFailure('COMPONENT_CHANGED', 'Referenced component transform changed during capture.')
        self._check_current(info)
        return success({'mate_inventory_schema_version': 1, 'document': info,
                        'captured_at_utc': datetime.now(timezone.utc).isoformat(), 'snapshot_atomic': False,
                        'scope': 'active_root_assembly', 'subassembly_internal_mates_included': False,
                        'mates': mates, 'mate_count': len(mates), 'root_mate_groups': groups,
                        'scanned_feature_count': scanned, 'component_contexts': list(contexts.values()),
                        'complete': not errors, 'truncated': truncated,
                        'parameters': {'max_features': max_features, 'max_mates': max_mates, 'max_entities': max_entities, 'max_depth': max_depth},
                        'limitations': ['Only mate features below active-root MateGroup are included; internal subassembly mates are excluded, even for nested reference components.',
                                        'Unsuppressed with no reported feature error is not proof of solved/independent/active constraints or mechanical connection.',
                                        'Root-frame EntityParams stay raw; selection reference type does not classify cylinder/plane geometry or identify a particular face.',
                                        'IsSame verifies occurrence identity, not entity geometry. Null/unmapped references remain unknown.',
                                        'No mates does not prove free motion. No solving, rebuild, configuration switch, motion inference or model modification.']}, errors)
