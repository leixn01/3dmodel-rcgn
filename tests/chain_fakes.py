"""Three-part synthetic source graph for offline dossier tests, not a lift analysis."""
import json
import math
from pathlib import Path

from cadkin.adapters.solidworks import SolidWorksAdapter
from cadkin.tools.solidworks import SolidWorksTools
from cadkin.tools.spatial import collect_spatial
from tests.face_probe_fakes import probe_document
from tests.mate_fakes import attach_features
from tests.sw_fakes import Component, pose, runtime


def write_chain_fixture(root, with_lock=False, return_app=False):
    root = Path(root);root.mkdir(parents=True,exist_ok=True)
    doc,part,app=probe_document()
    doc.root.children[0].Name2='base-1';doc.root.children[1].Name2='carriage-1'
    third=Component('rail-1');third.model_doc=part;third.Transform2=pose(x=.02)
    doc.root.children.append(third);_, mate_records = attach_features(doc)
    if with_lock:
        mate_records[0].mate.Type = 16
        mate_records[0].Name = 'SyntheticLock'
    def closest(a,b,p,q):
        p.value=tuple(a.Transform2.ArrayData[9:12]);q.value=tuple(b.Transform2.ArrayData[9:12]);return math.dist(p.value,q.value)
    doc.ClosestDistance=closest
    service=SolidWorksTools(root=root,factory=lambda:SolidWorksAdapter(app=app,runtime=runtime()))
    def save(name,data):
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data),encoding='utf-8');return name
    def call(name,args):
        result=service.call(name,args);assert result['status']=='ok',result;return result
    try:
        inventory=collect_spatial(service);save('inventory.json',inventory);token=inventory['data']['document']['document_token']
        call('cad_group_components',{'inventory_path':'inventory.json','output_path':'outputs/groups.json'})
        cylinders=[]
        for i,path in enumerate(('base-1','carriage-1','rail-1')):
            cylinders.append(save(f'cylinder{i}.json',call('sw_component_cylinders',{'expected_document_token':token,'occurrence_path':path})))
        call('cad_component_relations',{'inventory_path':'inventory.json','cylinder_paths':cylinders,'output_path':'outputs/relations.json',
            'distance_tolerance_mm':.1,'angle_tolerance_deg':.1,'grouping_path':'outputs/groups.json'})
        save('mates.json',call('sw_mate_inventory',{'expected_document_token':token}))
        call('cad_review_connections',{'relations_path':'outputs/relations.json','mate_inventory_path':'mates.json','output_path':'outputs/connections.json'})
        call('cad_proximity_candidates',{'inventory_path':'inventory.json','output_path':'outputs/proximity.json','max_box_gap_mm':30})
        distances=[]
        for i,(a,b) in enumerate((('base-1','carriage-1'),('base-1','rail-1'),('carriage-1','rail-1'))):
            distances.append(save(f'distance{i}.json',call('sw_component_distance',{'expected_document_token':token,'left_occurrence_path':a,'right_occurrence_path':b})))
        call('cad_review_proximity',{'proximity_path':'outputs/proximity.json','distance_paths':distances,'output_path':'outputs/proximity-review.json','contact_tolerance_mm':.1})
        for i,path in enumerate(('base-1','carriage-1')):
            save(f'faces{i}.json',call('sw_component_faces',{'expected_document_token':token,'occurrence_path':path}))
        save('probe.json',call('sw_probe_face_pair',{'expected_document_token':token,
            'left':{'face_inventory_path':'faces0.json','body_index':0,'face_index':0},
            'right':{'face_inventory_path':'faces1.json','body_index':0,'face_index':1},'seed_points_root_mm':[[0,500,500]]}))
        call('cad_review_face_contacts',{'probe_paths':['probe.json'],'output_path':'outputs/face-review.json','contact_tolerance_mm':.1,'angle_tolerance_deg':5})
    finally:service.close()
    arguments = {'inventory_path':'inventory.json','occurrence_paths':['base-1','carriage-1','rail-1'],'chain_name':'Synthetic lift chain',
            'grouping_path':'outputs/groups.json','evidence_paths':['outputs/connections.json','outputs/proximity-review.json','outputs/face-review.json'],
            'output_path':'outputs/chain.json'}
    return (arguments, app) if return_app else arguments
