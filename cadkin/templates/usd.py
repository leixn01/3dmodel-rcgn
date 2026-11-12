"""Read bounded, standalone OpenUSD mechanism graphs using the official USD schemas."""
import hashlib
import math
from pathlib import Path

from cadkin.errors import ToolFailure


def require(ok, message, code='INVALID_TEMPLATE'):
    if not ok:
        raise ToolFailure(code, message)


def usd_modules():
    try:
        from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics
    except ImportError as exc:
        raise ToolFailure('USD_DEPENDENCY_MISSING', 'Install the templates extra with the current Conda Python: python -m pip install -e ".[solidworks,templates]"') from exc
    return Gf, Sdf, Usd, UsdGeom, UsdPhysics


def vector(value):
    result = [float(v) for v in value]
    require(all(math.isfinite(v) for v in result), 'Non-finite USD vector.')
    return result


def matrix(value):
    # USD uses row vectors. Preserve that convention explicitly, unlike the CAD column matrix.
    return [vector(row) for row in value]


def read_template(path, max_prims=20000):
    Gf, Sdf, Usd, UsdGeom, UsdPhysics = usd_modules()
    path = Path(path).resolve()
    require(path.suffix.lower() in ('.usd', '.usda', '.usdc'), 'Use a standalone USD/USDA/USDC file.', 'INVALID_PATH')
    try:
        raw = path.read_bytes() if path.stat().st_size <= 64 * 1024 * 1024 else None
    except OSError as exc:
        raise ToolFailure('INVALID_INPUT', 'Cannot read USD input.', reason=str(exc)) from exc
    require(raw is not None, 'USD input exceeds 64 MiB.', 'TEMPLATE_LIMIT')
    digest = hashlib.sha256(raw).hexdigest()
    # Anonymous copies prevent cached layers hiding source edits. No external layer is opened.
    try:
        layer = Sdf.Layer.OpenAsAnonymous(str(path))
    except Exception as exc:
        raise ToolFailure('INVALID_TEMPLATE', 'Cannot parse USD input.', reason=str(exc)) from exc
    require(layer is not None, 'Cannot parse USD input.')
    require(not layer.GetCompositionAssetDependencies(), 'Flatten references, payloads and sublayers before extraction; external composition is not read.', 'USD_COMPOSITION_UNSUPPORTED')
    stage = Usd.Stage.Open(layer, Usd.Stage.LoadNone)
    require(stage is not None, 'Cannot open USD stage.')
    prims = []
    for index, prim in enumerate(stage.TraverseAll()):
        require(index < max_prims, 'USD prim budget exceeded.', 'TEMPLATE_LIMIT')
        require(not prim.GetVariantSets().GetNames() and not prim.IsInstance() and not prim.HasAuthoredInherits() and not prim.HasAuthoredSpecializes(),
                'Select variants and flatten instances/inherits/specializes before extraction.', 'USD_COMPOSITION_UNSUPPORTED')
        if prim.IsActive() and prim.IsDefined():
            prims.append(prim)
    mpu = float(UsdGeom.GetStageMetersPerUnit(stage))
    require(math.isfinite(mpu) and mpu > 0, 'Invalid metersPerUnit.')
    risks = []
    def risk(code, message, **context):
        risks.append({'code': code, 'message': message, **context})
    if not stage.HasAuthoredMetadata('metersPerUnit'):
        risk('DEFAULT_UNITS', 'metersPerUnit is not authored; USD default 0.01 was applied.')
    if not stage.HasAuthoredMetadata('upAxis'):
        risk('DEFAULT_UP_AXIS', 'upAxis is not authored; USD default was applied.')
    cache = UsdGeom.XformCache(Usd.TimeCode.Default())
    bodies = {}
    for prim in prims:
        if not prim.HasAPI(UsdPhysics.RigidBodyAPI):
            continue
        rb = UsdPhysics.RigidBodyAPI(prim)
        if not UsdGeom.Xformable(prim):
            risk('NON_XFORMABLE_BODY', 'Rigid body has no Xformable frame.', path=str(prim.GetPath()))
            continue
        mat = cache.GetLocalToWorldTransform(prim)
        body = {'id': str(prim.GetPath()), 'label': prim.GetName(), 'enabled': bool(rb.GetRigidBodyEnabledAttr().Get()),
                'kinematic': bool(rb.GetKinematicEnabledAttr().Get()), 'world_matrix_row_vectors_stage_units': matrix(mat),
                'origin_m': vector(mat.ExtractTranslation() * mpu), 'geometry_members': [], 'collider_count': 0}
        stored = prim.GetCustomDataByKey('cadkin:sourceGeometryMembers')
        if stored is not None:
            body['geometry_members'] = list(stored)
            body['collider_count'] = int(prim.GetCustomDataByKey('cadkin:sourceColliderCount') or 0)
            body['geometry_scope'] = 'source_paths_only_geometry_omitted'
        else:
            body['geometry_scope'] = 'stage_geometry'
        bodies[body['id']] = body
    def owner(prim):
        while prim and not prim.IsPseudoRoot():
            if str(prim.GetPath()) in bodies:
                return str(prim.GetPath())
            prim = prim.GetParent()
        return None
    for prim in prims:
        bid = owner(prim)
        if bid:
            if prim.HasAPI(UsdPhysics.CollisionAPI):
                bodies[bid]['collider_count'] += 1
            elif prim.IsA(UsdGeom.Boundable):
                bodies[bid]['geometry_members'].append(str(prim.GetPath()))
        if any(a.GetNumTimeSamples() for a in prim.GetAttributes()):
            risk('ANIMATED_SOURCE', 'Only default-time values are read; authored animation is not evaluated.', path=str(prim.GetPath()))
    joints = []
    for prim in prims:
        typ = prim.GetTypeName()
        if not prim.IsA(UsdPhysics.Joint) and not ('Joint' in typ and typ.startswith(('Physics', 'Physx'))):
            continue
        joint = UsdPhysics.Joint(prim)
        kind = {'PhysicsFixedJoint': 'fixed', 'PhysicsPrismaticJoint': 'prismatic', 'PhysicsRevoluteJoint': 'revolute'}.get(typ, 'unsupported')
        jid = str(prim.GetPath())
        if kind == 'unsupported':
            risk('UNSUPPORTED_JOINT', 'Joint is retained without reducing it to a supported joint type.', path=jid, usd_type=typ)
        endpoints = []
        for side in (0, 1):
            rel = prim.GetRelationship(f'physics:body{side}')
            targets = list(rel.GetTargets()) if rel else []
            require(len(targets) <= 1, 'A joint endpoint has multiple targets.')
            target = stage.GetPrimAtPath(targets[0]) if targets else None
            if targets and not target:
                risk('UNRESOLVED_BODY_TARGET', 'Joint target is missing.', path=jid, target=str(targets[0]))
            bid = owner(target) if target else None
            valid_frame = bool(target and UsdGeom.Xformable(target)) or not targets
            if target and not UsdGeom.Xformable(target):
                risk('INVALID_TARGET_FRAME', 'Joint target is not Xformable; anchor and axis remain unknown.', path=jid)
            if targets and target and bid is None:
                risk('STATIC_XFORM_ENDPOINT', 'Joint endpoint is a static Xform, not a dynamic rigid body.', path=jid, target=str(targets[0]))
            position_attr = prim.GetAttribute(f'physics:localPos{side}')
            rotation_attr = prim.GetAttribute(f'physics:localRot{side}')
            pos = position_attr.Get() if position_attr else None
            rot = rotation_attr.Get() if rotation_attr else None
            local = vector(pos) if pos is not None else [0., 0., 0.]
            rot = Gf.Quatd(rot) if rot is not None else Gf.Quatd(1)
            q = [float(rot.GetReal()), *vector(rot.GetImaginary())]
            require(math.isfinite(q[0]) and abs(sum(v*v for v in q)-1) < 1e-4, 'Invalid joint quaternion.')
            transform = cache.GetLocalToWorldTransform(target) if target and UsdGeom.Xformable(target) else Gf.Matrix4d(1)
            axis_attr = prim.GetAttribute('physics:axis'); axis_name = axis_attr.Get() if axis_attr else None
            axis = None
            if kind in ('revolute', 'prismatic'):
                require(axis_name in ('X', 'Y', 'Z'), 'Invalid joint axis.')
                directions = {'X': Gf.Vec3d(1,0,0), 'Y': Gf.Vec3d(0,1,0), 'Z': Gf.Vec3d(0,0,1)}
                axes = [transform.TransformDir(directions[c]) for c in ('X','Y','Z')]
                lengths = [v.GetLength() for v in axes]
                valid = all(abs(l-1) < 1e-6 for l in lengths) and all(abs(Gf.Dot(axes[a],axes[b])) < 1e-6 for a,b in ((0,1),(0,2),(1,2))) and transform.GetDeterminant()>0
                if valid:
                    axis = vector(transform.TransformDir(rot.Transform(directions[axis_name])).GetNormalized())
                else:
                    risk('NON_RIGID_FRAME', 'Scaled, mirrored or sheared joint frame; world axis remains unknown.', path=jid, side=side)
            endpoints.append({'target_path':str(targets[0]) if targets else None, 'body_id':bid if valid_frame else None,
                              'frame_kind':'unresolved' if not valid_frame else 'body' if bid else 'static_xform' if target else 'world',
                              'local_position_stage_units':local, 'local_rotation_wxyz':q,
                              'anchor_m':vector(transform.Transform(Gf.Vec3d(*local)) * mpu) if valid_frame else None,
                              'axis_world':axis if valid_frame else None})
        limits = {}
        for key in ('lower', 'upper'):
            attr = prim.GetAttribute(f'physics:{key}Limit'); value = attr.Get() if attr else None
            limits[key] = (float(value) * (mpu if kind == 'prismatic' else 1)) if value is not None and math.isfinite(float(value)) else None
        limits['unit'] = 'm' if kind == 'prismatic' else 'degree' if kind == 'revolute' else None
        if limits['lower'] is not None and limits['upper'] is not None and limits['lower'] > limits['upper']:
            risk('INVALID_LIMIT_ORDER', 'Joint lower limit exceeds upper limit.', path=jid)
        extra = []
        for name in prim.GetAppliedSchemas():
            if any(word in name.lower() for word in ('mimic', 'gear', 'rack', 'tendon')):
                extra.append(name)
        if extra or kind == 'unsupported':
            risk('COUPLING_NOT_EVALUATED', 'Runtime-specific coupling is preserved as metadata, not solved.', path=jid)
        extension_properties = {}
        for prop in prim.GetProperties():
            if any(word in prop.GetName().lower() for word in ('mimic', 'gear', 'rack', 'tendon')):
                extension_properties[prop.GetName()] = str(prop.GetTargets() if hasattr(prop,'GetTargets') else prop.Get())
        if extension_properties and not extra and kind != 'unsupported':
            risk('COUPLING_NOT_EVALUATED', 'Coupling properties are preserved, not solved.', path=jid)
        joints.append({'id':jid, 'label':prim.GetName(), 'kind':kind, 'usd_type':typ,
                       'enabled':bool(joint.GetJointEnabledAttr().Get()) if joint else None,
                       'endpoints':endpoints, 'limits':limits, 'coupling_schemas':extra, 'coupling_properties':extension_properties})
    require(bodies, 'No authored rigid bodies found; visual parts alone are not mechanism labels.', 'NO_RIGID_BODIES')
    if not joints:
        risk('NO_JOINTS', 'No authored joints; this is a rigid-body-only reference.')
    require(hashlib.sha256(path.read_bytes()).hexdigest() == digest, 'USD source changed during extraction.', 'EVIDENCE_MISMATCH')
    kinds = {kind:sum(j['kind']==kind for j in joints) for kind in sorted({j['kind'] for j in joints})}
    return {'mechanism_template_schema_version':1, 'source':{'path':str(path),'sha256':digest},
            'representation':'authored_usd_rigid_bodies_and_joints', 'source_meters_per_unit':mpu,
            'source_up_axis':str(UsdGeom.GetStageUpAxis(stage)), 'time':'default',
            'bodies':list(bodies.values()), 'joints':joints,
            'summary':{'body_count':len(bodies),'joint_count':len(joints),'joint_types':kinds},
            'complete':not any(r['code'] in ('UNRESOLVED_BODY_TARGET','NON_XFORMABLE_BODY','NON_RIGID_FRAME','UNSUPPORTED_JOINT','ANIMATED_SOURCE','INVALID_LIMIT_ORDER','INVALID_TARGET_FRAME','COUPLING_NOT_EVALUATED','NO_JOINTS') for r in risks),
            'requires_human_review':False, 'risks':risks,
            'limitations':['These are reference-asset annotations, not recovered SolidWorks mechanisms or measured physical truth.',
                           'Default-time kinematic graph only; no simulation, automatic body merging or transfer of source dimensions to target parts.']}
