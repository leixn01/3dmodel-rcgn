"""Local closest-point probes on finite plane/cylinder faces, never global clearance proof."""
from datetime import datetime, timezone
import math

from cadkin._vendor.sw_mcp import call, value
from cadkin.adapters.evidence import evidence_error
from cadkin.adapters.faces import FaceContext, read_descriptor
from cadkin.adapters.face_identity import resolve_face, same_object
from cadkin.errors import ToolFailure, success
from cadkin.face_geometry import point, part_point, root_normal, pair_metrics, require
from cadkin.geometry import numbers
from cadkin.tools.relations import _document


class ProbeFace:
    def __init__(self, adapter, token, source):
        self.adapter, self.source = adapter, source
        self.context = FaceContext(adapter, token, source['target']['occurrence_path'])
        require(_document(self.context.info) == _document(source['document']) and self.context.data == source['target'],
                'Live occurrence differs from face source; recollect.', 'EVIDENCE_MISMATCH')
        self.transform = self.context.data['transform']
        self.face = resolve_face(self.context.part, source['face']['face_reference'], adapter.runtime)
        self.descriptor = read_descriptor(self.face)
        require(self.descriptor == source['face']['descriptor'], 'Face geometry differs from source.', 'FACE_GEOMETRY_MISMATCH')
        require(self.descriptor['surface_type'] in ('plane', 'cylinder'), 'This release probes only analytic plane/cylinder faces.', 'UNSUPPORTED_FACE_SURFACE')

    def check(self):
        self.context.check()
        latest = resolve_face(self.context.part, self.source['face']['face_reference'], self.adapter.runtime)
        require(same_object(self.adapter.app, self.face, latest) and read_descriptor(latest) == self.descriptor,
                'Face identity or geometry changed during probing.', 'GEOMETRY_CHANGED')

    def project(self, root_m):
        self.context.check()
        xyz = part_point(self.transform, root_m)
        raw = numbers(call(self.face, 'GetClosestPointOn', *xyz), 5, 'INVALID_FACE_POINT')
        return {'point_part_m': raw[:3], 'uv': raw[3:], 'point_root_m': point(self.transform['to_root'], raw[:3])}

    def normal(self, sample):
        raw = numbers(call(value(self.face, 'GetSurface'), 'EvaluateAtPoint', *sample['point_part_m']), 11, 'INVALID_FACE_NORMAL')
        return {'evaluation_part_raw': raw, 'face_in_surface_sense': self.descriptor['face_in_surface_sense'],
                'face_normal_root_unit': root_normal(self.transform, raw[:3], self.descriptor['face_in_surface_sense'])}


class FaceProbeOperations:
    def sw_probe_face_pair(self, expected_document_token, sources, seed_points_root_mm, max_iterations=20, convergence_tolerance_mm=0.001):
        require(type(max_iterations) is int and 1 <= max_iterations <= 50, 'Use 1–50 iterations.', 'INVALID_ARGUMENTS')
        tolerance = numbers([convergence_tolerance_mm], 1, 'INVALID_ARGUMENTS')[0]
        require(0 < tolerance <= 1, 'Convergence tolerance must be in (0, 1] mm.', 'INVALID_ARGUMENTS')
        require(isinstance(seed_points_root_mm, list) and 1 <= len(seed_points_root_mm) <= 8, 'Use 1–8 explicit root-frame seeds.', 'INVALID_ARGUMENTS')
        seeds = [numbers(seed, 3, 'INVALID_ARGUMENTS') for seed in seed_points_root_mm]
        faces = [ProbeFace(self, expected_document_token, source) for source in sources]
        errors, samples = [], []
        for side, face in enumerate(faces):
            errors.extend(face.context.errors)
            if not sources[side]['complete']:
                errors.append({'code': 'SOURCE_INCOMPLETE', 'message': 'Face source has incomplete coverage/errors.', 'side': side, 'source_errors': sources[side]['errors']})
        for index, seed in enumerate(seeds):
            row = {'seed_index': index, 'seed_root_mm': seed, 'iterations': 0, 'converged': False,
                   'left': None, 'right': None, 'normal_left': None, 'normal_right': None, 'metrics': None, 'errors': []}
            try:
                previous, current = None, [x / 1000 for x in seed]
                for iteration in range(max_iterations):
                    left = faces[0].project(current)
                    right = faces[1].project(left['point_root_m'])
                    row['iterations'] = iteration + 1
                    latest = (left['point_root_m'], right['point_root_m'])
                    if previous is not None and max(math.dist(a, b) for a, b in zip(latest, previous)) <= tolerance / 1000:
                        row['converged'] = True
                        break
                    previous, current = latest, right['point_root_m']
                # Reproject to the SAME finite faces: axes, extended surfaces or stale coordinates
                # must not be silently accepted as on-face points.
                for face, sample in zip(faces, (left, right)):
                    verified = face.project(sample['point_root_m'])
                    require(math.dist(verified['point_root_m'], sample['point_root_m']) <= 1e-8,
                            'Closest-point output failed same-face point revalidation.', 'FACE_POINT_NOT_ON_FACE')
                row['left'], row['right'] = left, right
                if not row['converged']:
                    row['errors'].append({'code': 'FACE_PROBE_ITERATION_LIMIT', 'message': 'Point iteration did not stabilize; valid sampled points are retained, not a minimum proof.'})
                for name, face, sample in zip(('normal_left', 'normal_right'), faces, (left, right)):
                    try:
                        row[name] = face.normal(sample)
                    except Exception as exc:
                        row['errors'].append(evidence_error(exc, field=name))
                row['metrics'] = pair_metrics(left['point_root_m'], right['point_root_m'],
                    None if row['normal_left'] is None else row['normal_left']['face_normal_root_unit'],
                    None if row['normal_right'] is None else row['normal_right']['face_normal_root_unit'])
            except Exception as exc:
                row['errors'].append(evidence_error(exc))
            samples.append(row)
            errors.extend({**error, 'seed_index': index} for error in row['errors'])
        # Refuse an entire mixed snapshot, including changes observed after a failed probe.
        for face in faces:
            face.check()
        usable = [row for row in samples if row['metrics'] is not None]
        best = min(usable, key=lambda row: (row['metrics']['gap_mm'], row['seed_index'])) if usable else None
        return success({'face_probe_schema_version': 1, 'document': faces[0].context.info,
                        'captured_at_utc': datetime.now(timezone.utc).isoformat(), 'snapshot_atomic': False,
                        'geometry_scope': 'placed_part_definition_faces', 'assembly_instance_features_evaluated': False,
                        'method': 'bounded_alternating_IFace2.GetClosestPointOn', 'sources': sources,
                        'parameters': {'seed_points_root_mm': seeds, 'max_iterations': max_iterations, 'convergence_tolerance_mm': tolerance},
                        'samples': samples, 'best_seed_index': None if best is None else best['seed_index'],
                        'measurement_status': 'unavailable' if best is None else 'sampled', 'complete': not errors,
                        'global_minimum_proven': False, 'contact_confirmed': False, 'mechanical_relation_confirmed': False,
                        'solidworks_modified': False,
                        'limitations': ['Finite face closest-point queries from explicit seeds; only sampled point-pair gaps are measured, not a certified global minimum.',
                                        'Convergence does not prove a minimum; a large sampled gap cannot exclude nearby points elsewhere.',
                                        'Part-definition faces are placed once by occurrence transforms; assembly-level cuts/features are NOT evaluated.',
                                        'Normals are local face normals, reversed when FaceInSurfaceSense is true; sheet orientation does not establish an outward solid normal.',
                                        'Near/opposing points are candidates only: no contact patch, interference, penetration, fit, rigid body or motion joint is inferred.',
                                        'UV/area/parameters and persistent identity are conservative change checks, not a complete topology hash or atomic snapshot.']}, errors)
