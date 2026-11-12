"""Rebuild small structural derivatives from pinned ForgeCAD source files.

Usage: python scripts/build_reference_templates.py outputs/reference-download
The source directory must contain the four files recorded per asset in catalog.json.
No CAD data, downloads or simulation are performed by runtime tools.
"""
import argparse
import hashlib
import json
from pathlib import Path
from pxr import Sdf, Usd, UsdGeom, UsdPhysics, Vt

REVISION = 'b94ea770666b6c0f82e09a78e9fcb375b223e3b1'
ASSETS = [
    ('articulation_test_bench', ['prismatic', 'revolute', 'test_fixture'], 'reference'),
    ('bench_vise', ['clamping', 'linear_motion', 'screw_candidate'], 'reference'),
    ('bearing_pulley_shaft_kit', ['shaft', 'bearing', 'pulley'], 'reference'),
    ('toggle_clamp_fixture_plate', ['clamping', 'linkage'], 'reference'),
    ('gas_lift_bar_stool', ['lifting', 'linear_motion'], 'reference'),
    ('gear_meshing_kit', ['gear', 'rotation'], 'reference'),
    ('planetary_gearbox', ['gear', 'rotation'], 'heldout'),
    ('bar_clamp', ['clamping', 'linear_motion'], 'heldout'),
]
DEST = Path(__file__).resolve().parents[1] / 'cadkin/resources/mechanisms'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(source):
    DEST.mkdir(parents=True, exist_ok=True)
    previous = json.loads((DEST / 'catalog.json').read_text(encoding='utf-8')) if (DEST / 'catalog.json').exists() else None
    entries = []
    for name, tags, split in ASSETS:
        rels = [f'{name}/simready_usd/{name}.usda', f'{name}/simready_usd/forgecad/physics.usda',
                f'{name}/simready_usd/forgecad/geometry.usda', f'{name}/com.nvidia.simready.packaging.json']
        files = [{'path':r, 'sha256':sha(source/r), 'size_bytes':(source/r).stat().st_size,
                  'url':f'https://huggingface.co/datasets/ForgeCAD/simready-assets/resolve/{REVISION}/{r}'} for r in rels]
        if previous:
            old = next(e for e in previous['templates'] if e['id'] == name)
            assert files == old['source_files'], f'{name}: source bytes differ from pinned catalog'
        assert json.loads((source/rels[3]).read_text())['license'] == 'cc-by-4.0'
        root = Sdf.Layer.FindOrOpen(str((source/rels[0]).resolve()))
        root_spec = root.GetPrimAtPath('/Model')
        assert not any(a.name.startswith('xformOp') for a in root_spec.attributes), 'Root transform needs explicit support'
        layer = Sdf.Layer.CreateAnonymous()
        layer.subLayerPaths = [str((source/r).resolve()) for r in rels[1:3]]
        stage = Usd.Stage.Open(layer)
        UsdGeom.Xform.Define(stage, '/Model')  # Source root supplies this def; both sublayers are overs.
        for key in ('metersPerUnit', 'upAxis'):
            stage.SetMetadata(key, root.pseudoRoot.GetInfo(key))
        cache = UsdGeom.XformCache()
        prims = list(stage.Traverse())
        bodies = [p for p in prims if p.HasAPI(UsdPhysics.RigidBodyAPI)]
        joints = [p for p in prims if p.IsA(UsdPhysics.Joint) or ('Joint' in p.GetTypeName() and p.GetTypeName().startswith(('Physics','Physx')))]
        assert bodies, name
        body_paths = {p.GetPath() for p in bodies}
        def owner(p):
            while p and not p.IsPseudoRoot():
                if p.GetPath() in body_paths:
                    return p.GetPath()
                p = p.GetParent()
        members = {p:[] for p in body_paths}; colliders = {p:0 for p in body_paths}
        for p in prims:
            bid = owner(p)
            if bid:
                if p.HasAPI(UsdPhysics.CollisionAPI):
                    colliders[bid] += 1
                elif p.IsA(UsdGeom.Boundable):
                    members[bid].append(str(p.GetPath()))
        out = Usd.Stage.CreateInMemory()
        for key in ('metersPerUnit', 'upAxis'):
            out.SetMetadata(key, stage.GetMetadata(key))
        out.SetMetadata('documentation', 'Structure-only derivative of ForgeCAD/simready-assets; CC BY 4.0. See catalog.json and ATTRIBUTION.md. Visual meshes, collisions, materials, animation and simulation are omitted; source default world frames are retained.')
        out.SetDefaultPrim(UsdGeom.Xform.Define(out, '/Model').GetPrim())
        frame_paths = set(body_paths)
        for j in joints:
            for side in (0,1):
                frame_paths.update(j.GetRelationship(f'physics:body{side}').GetTargets())
        for path in sorted(frame_paths, key=lambda p:(p.pathElementCount,str(p))):
            orig = stage.GetPrimAtPath(path)
            assert orig and UsdGeom.Xformable(orig), f'Unresolved frame {path}'
            dst = UsdGeom.Xform.Define(out, path)
            dst.AddTransformOp().Set(cache.GetLocalToWorldTransform(orig))
            dst.SetResetXformStack(True)
            if path in body_paths:
                api = UsdPhysics.RigidBodyAPI.Apply(dst.GetPrim()); src = UsdPhysics.RigidBodyAPI(orig)
                api.CreateRigidBodyEnabledAttr(src.GetRigidBodyEnabledAttr().Get())
                api.CreateKinematicEnabledAttr(src.GetKinematicEnabledAttr().Get())
                dst.GetPrim().SetCustomDataByKey('cadkin:sourceGeometryMembers', Vt.StringArray(members[path]))
                dst.GetPrim().SetCustomDataByKey('cadkin:sourceColliderCount', colliders[path])
        flat = stage.Flatten()
        for joint in joints:
            # Copy the whole joint specification, including extension properties; no children/meshes.
            out.DefinePrim(joint.GetPath().GetParentPath(), 'Scope')
            assert Sdf.CopySpec(flat, joint.GetPath(), out.GetRootLayer(), joint.GetPath())
        # Verify the derivative against the composed original before writing it.
        out_cache = UsdGeom.XformCache()
        for frame_path in frame_paths:
            original_matrix = cache.GetLocalToWorldTransform(stage.GetPrimAtPath(frame_path))
            excerpt_matrix = out_cache.GetLocalToWorldTransform(out.GetPrimAtPath(frame_path))
            assert all(abs(original_matrix[i][k]-excerpt_matrix[i][k])<1e-10 for i in range(4) for k in range(4)), frame_path
        for joint in joints:
            copied = out.GetPrimAtPath(joint.GetPath())
            assert copied.GetTypeName() == joint.GetTypeName()
            for attr in joint.GetAuthoredAttributes():
                assert copied.GetAttribute(attr.GetName()).Get() == attr.Get(), (name,attr.GetPath())
            for rel in joint.GetRelationships():
                assert copied.GetRelationship(rel.GetName()).GetTargets() == rel.GetTargets(), (name,rel.GetPath())
        path = DEST / f'{name}.usda'
        out.GetRootLayer().Export(str(path))
        path.write_bytes(path.read_bytes().replace(b'\r\n',b'\n').rstrip()+b'\n')
        entries.append({'id':name, 'label':name.replace('_',' '), 'tags':tags, 'split':split,
            'file':path.name, 'sha256':sha(path), 'author':'ForgeCAD', 'license':'CC-BY-4.0',
            'license_url':'https://creativecommons.org/licenses/by/4.0/',
            'asset_url':f'https://huggingface.co/datasets/ForgeCAD/simready-assets/tree/{REVISION}/{name}',
            'source_revision':REVISION, 'source_files':files,
            'modifications':'Structure-only derivative: default world frames baked with resetXformStack; source joints preserved; meshes/collision geometry/materials/animation omitted; geometry paths and collider counts retained as source metadata.',
            'expected':{'body_count':len(bodies),'joint_count':len(joints),
                        'joint_types':{t:sum(p.GetTypeName()==t for p in joints) for t in sorted({p.GetTypeName() for p in joints})}}})
        print(name, entries[-1]['expected'], path.stat().st_size)
    (DEST/'catalog.json').write_text(json.dumps({'catalog_schema_version':1,'templates':entries},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('source',type=Path)
    build(parser.parse_args().source.resolve())
