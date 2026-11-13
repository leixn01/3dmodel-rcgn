"""Explicit synthetic root-face mates; never used by the production adapter."""
import json
from types import SimpleNamespace
from pathlib import Path

from cadkin.adapters.solidworks import SolidWorksAdapter
from cadkin.tools.solidworks import SolidWorksTools
from tests.chain_fakes import write_chain_fixture
from tests.evidence_fakes import Mate, MateEntity
from tests.mate_fakes import Feature
from tests.sw_fakes import runtime


def attach_constraint_mates(app, mode='revolute'):
    doc = app.ActiveDoc
    a, b = doc.root.children[:2]
    refs, records = {}, []
    def add(kind, surface='cylinder', origin=(0.,0.,0.), direction=(0.,0.,1.), rotation=False):
        entities = []
        for component in (a,b):
            entity = MateEntity(component)
            face = SimpleNamespace(GetSurface=lambda: SimpleNamespace(IsPlane=lambda:surface=='plane', IsCylinder=lambda:surface=='cylinder'))
            key = bytes((len(refs)+1,)); refs[key] = face
            entity.Reference = face
            entity.EntityParams = list(origin)+list(direction)+([.01] if surface=='cylinder' else [])
            entities.append(entity)
        mate = Mate(entities); mate.Type = kind
        feature = Feature(100+len(records), 'TargetConstraint'+str(len(records)), 'MateConcentric' if kind==1 else 'MateCoincident', mate)
        feature.GetDefinition = lambda: SimpleNamespace(LockRotation=rotation)
        records.append(feature)
    if mode == 'no_mates': pass
    elif mode == 'lock': add(16)
    else:
        add(1, rotation=mode in ('prismatic','fixed'))
        if mode in ('revolute','fixed','conflict'): add(0, 'plane', origin=(0,0,0 if mode!='conflict' else .01))
        if mode == 'parallel_axes': add(1, origin=(.02,0,0))
        if mode == 'duplicate_axis': add(1)
    if mode == 'conflict': records[-1].mate.entities[1].EntityParams[2] = .02
    group = Feature(99, 'Mates', 'MateGroup', children=records)
    doc.FirstFeature = lambda: group
    class Extension:
        def GetPersistReference3(self, face): return next((k for k,v in refs.items() if v is face),None)
        def GetObjectByPersistReference3(self, encoded, state):
            state.value=0; return refs.get(bytes(encoded.value))
    doc.Extension = Extension()
    return records


def write_constraint_fixture(root, mode='revolute', enriched=True):
    root=Path(root).resolve()
    args, app=write_chain_fixture(root, return_app=True)
    records=attach_constraint_mates(app,mode)
    live=SolidWorksTools(root, factory=lambda:SolidWorksAdapter(app=app,runtime=runtime()))
    try:
        token=live.call('sw_active_document')['data']['document_token']
        envelope=live.call('sw_mate_inventory',{'expected_document_token':token,'include_reference_geometry':enriched})
        assert envelope['status']=='ok',envelope
    finally:live.close()
    path=root/'constraint-mates.json';path.write_text(json.dumps(envelope),encoding='utf-8')
    offline=SolidWorksTools(root)
    try:
        r=offline.call('cad_review_connections',{'relations_path':'outputs/relations.json','mate_inventory_path':str(path),'output_path':'outputs/constraint-connections.json'});assert r['status']=='ok',r
        args['evidence_paths'][0]='outputs/constraint-connections.json'
        r=offline.call('cad_build_chain_evidence',args);assert r['status']=='ok',r
        r=offline.call('cad_build_target_graph',{'chain_path':args['output_path'],'output_path':'outputs/target.json'});assert r['status']=='ok',r
    finally:offline.close()
    return app, records, envelope


def write_constraint_followup_fixture(root, mode='revolute', enriched=False):
    app, records, envelope = write_constraint_fixture(root, mode, enriched)
    service = SolidWorksTools(root)
    try:
        for name, args in [
            ('cad_build_rigid_candidates', {'target_graph_path': 'outputs/target.json', 'output_path': 'outputs/rigid.json'}),
            ('cad_draft_joints', {'rigid_candidates_path': 'outputs/rigid.json', 'output_path': 'outputs/drafts.json'}),
            ('cad_check_joint_draft', {'joint_draft_path': 'outputs/drafts.json', 'output_path': 'outputs/check.json'}),
            ('cad_analyze_constraints', {'target_graph_path': 'outputs/target.json', 'output_path': 'outputs/constraints.json',
                'distance_tolerance_mm': .1, 'angle_tolerance_deg': .1}),
            ('cad_plan_evidence_tasks', {'draft_check_path': 'outputs/check.json', 'constraint_analysis_path': 'outputs/constraints.json',
                'output_path': 'outputs/plan.json'})]:
            result = service.call(name, args)
            assert result['status'] != 'error', result
    finally:
        service.close()
    return app, records, envelope
