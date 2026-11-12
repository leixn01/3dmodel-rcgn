import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

from cadkin.adapters.solidworks import SolidWorksAdapter
from cadkin.constraints.analysis import analyze_snapshot
from cadkin.errors import ToolFailure
from cadkin.tools.constraint_analysis import replay_analysis
from cadkin.tools.solidworks import SolidWorksTools
from tests.constraint_fakes import write_constraint_fixture
from tests.sw_fakes import runtime


class ConstraintTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.app,self.records,self.envelope=write_constraint_fixture(self.root)
        self.source={'path':'synthetic.json','sha256':'a'*64}
        self.factory=Mock(side_effect=AssertionError('offline called COM'))
        self.service=SolidWorksTools(self.root,factory=self.factory);self.addCleanup(self.service.close)

    def analyze(self,envelope=None):
        return analyze_snapshot(['base-1','carriage-1'],self.source,envelope or self.envelope,.1,.1)

    def test_revolute_pattern_is_target_derived_but_not_solved(self):
        result=self.analyze()
        self.assertEqual([c['kind'] for c in result['candidates']],['revolute'])
        self.assertEqual(result['state'],'supported_local_pattern')
        self.assertEqual(result['target_joint_kind'],'unknown');self.assertIsNone(result['target_degrees_of_freedom'])
        self.assertFalse(result['motion_tested'])
        self.assertEqual(len(result['constraint_facts']),2)
        self.assertTrue(all(c['evidence_ids'] for c in result['constraint_facts']))
        self.assertEqual(result['mate_evidence'][0]['entity_geometry'][0]['persistent_reference']['scope'],'active_root_assembly')

    def test_lock_rotation_combines_with_axial_stop(self):
        self.envelope['data']['mates'][0]['constraint_options']['concentric_lock_rotation']=True
        self.assertEqual(self.analyze()['candidates'][0]['kind'],'fixed')
        self.envelope['data']['mates']=self.envelope['data']['mates'][:1]
        self.assertEqual(self.analyze()['candidates'][0]['kind'],'prismatic')

    def test_unknown_rotation_never_defaults_to_free(self):
        self.envelope['data']['mates'][0].pop('constraint_options')
        result=self.analyze();self.assertEqual(result['candidates'],[])
        self.assertIn('CONCENTRIC_ROTATION_LOCK_UNKNOWN',[m['code'] for m in result['missing_evidence']])

    def test_missing_or_selection_type_geometry_does_not_infer(self):
        for record in self.envelope['data']['mates']:
            for e in record['entities']: e.pop('reference_geometry')
        result=self.analyze();self.assertEqual(result['candidates'],[])
        self.assertIn('MATE_REFERENCE_GEOMETRY_MISSING_OR_UNSUPPORTED',[x['code'] for x in result['missing_evidence']])

    def test_parallel_distinct_axes_and_duplicate_axis(self):
        first=self.envelope['data']['mates'][0];second=copy.deepcopy(first);second['feature_id']=101
        self.envelope['data']['mates']=[first,second]
        self.assertEqual(self.analyze()['candidates'],[])
        for entity in second['entities']:
            entity['entity_params_raw'][0]=.02
            g=entity['reference_geometry'];g['entity_params_raw'][0]=.02;g['point_root_m'][0]=.02
        self.assertEqual(self.analyze()['candidates'][0]['kind'],'prismatic')

    def test_conflicting_plane_geometry_is_not_revolute(self):
        e=self.envelope['data']['mates'][1]['entities'][1]
        e['entity_params_raw'][2]=.01;g=e['reference_geometry'];g['entity_params_raw'][2]=.01;g['point_root_m'][2]=.01
        result=self.analyze();self.assertEqual(result['candidates'],[])
        self.assertEqual(result['conflicts'][0]['code'],'MATE_GEOMETRY_OUTSIDE_TOLERANCE')

    def test_suppressed_or_broken_constraints_not_combined(self):
        self.envelope['data']['mates'][1]['activity'].update(suppressed=True,state='suppressed')
        self.assertEqual(self.analyze()['candidates'],[])
        self.envelope['data']['mates'][1]['activity'].update(suppressed=False,state='unsuppressed_feature_issue',feature_error_code=7)
        result=self.analyze();self.assertEqual(result['candidates'],[])
        self.assertIn('MATE_STATE_OR_REFERENCE_UNRESOLVED',[x['code'] for x in result['missing_evidence']])

    def test_multi_entity_and_boundary_remain_unresolved(self):
        record=self.envelope['data']['mates'][1]
        record['entities'].append({'entity_index':2,'reference_status':'root_or_unavailable'});record['entity_count']=3
        result=self.analyze();self.assertEqual(result['candidates'],[])
        self.assertEqual(len(result['boundary_evidence']),1)

    def test_invalid_provenance_and_forged_geometry_rejected(self):
        for mode in ('provenance','numeric','scope','type'):
            envelope=copy.deepcopy(self.envelope)
            entity=envelope['data']['mates'][0]['entities'][0]
            if mode=='provenance':envelope['data'].pop('reference_geometry_capture')
            elif mode=='numeric':entity['reference_geometry']['direction_root_unit']=[1,0,0]
            elif mode=='scope':entity['reference_geometry']['persistent_reference']['scope']='referenced_part_definition'
            else:envelope['data']['mates'][0]['type_name']='lock'
            with self.assertRaises(ToolFailure):self.analyze(envelope)

    def test_file_replay_no_com_source_immutability_and_budget(self):
        hashes={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*.json')}
        args=dict(target_graph_path='outputs/target.json',output_path='outputs/constraints.json',distance_tolerance_mm=.1,angle_tolerance_deg=.1)
        r=self.service.call('cad_analyze_constraints',args);self.assertEqual(r['status'],'ok',r)
        self.assertEqual(r['data']['coverage']['returned_pairs'],3)
        replayed,_=replay_analysis(self.root,args['output_path']);self.assertEqual(replayed['pairs'],r['data']['pairs'])
        r=self.service.call('cad_analyze_constraints',{**args,'output_path':'outputs/limited.json','max_pairs':1})
        self.assertEqual(r['status'],'partial');self.assertEqual(r['data']['coverage']['omitted_pairs'],2)
        self.assertEqual(self.service.call('cad_analyze_constraints',args)['errors'][0]['code'],'OUTPUT_EXISTS')
        self.assertTrue(all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in hashes.items()))
        self.factory.assert_not_called()
        path=self.root/'outputs/constraints.json';raw=json.loads(path.read_text());raw['pairs'][0]['target_joint_kind']='revolute';path.write_text(json.dumps(raw))
        with self.assertRaises(ToolFailure):replay_analysis(self.root,str(path))
        with (self.root/'constraint-mates.json').open('a') as stream:stream.write('\n')
        r=self.service.call('cad_analyze_constraints',{**args,'output_path':'outputs/tampered.json'})
        self.assertEqual(r['errors'][0]['code'],'EVIDENCE_MISMATCH');self.assertFalse((self.root/'outputs/tampered.json').exists())

    def test_capture_rechecks_rotation_and_geometry_and_does_not_edit(self):
        service=SolidWorksTools(self.root,factory=lambda:SolidWorksAdapter(app=self.app,runtime=runtime()));self.addCleanup(service.close)
        token=service.call('sw_active_document')['data']['document_token'];doc=self.app.ActiveDoc
        before=(doc.dirty,doc.rebuilt,list(doc.SelectionManager.selected))
        args={'expected_document_token':token,'include_reference_geometry':True}
        result=service.call('sw_mate_inventory',args);self.assertEqual(result['status'],'ok',result)
        self.assertEqual(before,(doc.dirty,doc.rebuilt,doc.SelectionManager.selected))
        from types import SimpleNamespace
        calls=[]
        def changed():calls.append(1);return SimpleNamespace(LockRotation=len(calls)>1)
        self.records[0].GetDefinition=changed
        self.assertEqual(service.call('sw_mate_inventory',args)['errors'][0]['code'],'MATE_STATE_CHANGED')

    def test_capture_failure_retains_unknown_not_false(self):
        self.records[0].GetDefinition=lambda:None
        service=SolidWorksTools(self.root,factory=lambda:SolidWorksAdapter(app=self.app,runtime=runtime()));self.addCleanup(service.close)
        token=service.call('sw_active_document')['data']['document_token']
        result=service.call('sw_mate_inventory',{'expected_document_token':token,'include_reference_geometry':True})
        self.assertEqual(result['status'],'partial',result)
        self.assertIsNone(result['data']['mates'][0]['constraint_options']['concentric_lock_rotation'])

    def test_cli_and_invalid_arguments(self):
        run=subprocess.run([sys.executable,'-m','cadkin','analyze-constraints','outputs/target.json','--distance-tolerance-mm','.1',
            '--angle-tolerance-deg','.1','--output','outputs/cli.json'],cwd=self.root,capture_output=True,text=True,timeout=30)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        for key,value in [('max_pairs',0),('distance_tolerance_mm',0),('angle_tolerance_deg',6)]:
            args=dict(target_graph_path='outputs/target.json',output_path='outputs/bad.json',distance_tolerance_mm=.1,angle_tolerance_deg=.1)
            args[key]=value;self.assertEqual(self.service.call('cad_analyze_constraints',args)['errors'][0]['code'],'INVALID_ARGUMENTS')

    def test_separate_snapshots_and_geometry_only_cannot_supply_constraints(self):
        from cadkin.constraints.analysis import analyze
        target=json.loads((self.root/'outputs/target.json').read_text())
        a=copy.deepcopy(self.envelope);a['data']['mates']=a['data']['mates'][:1]
        b=copy.deepcopy(self.envelope);b['data']['mates']=b['data']['mates'][1:]
        result=analyze(target,[(self.source,a),({**self.source,'sha256':'b'*64},b)],.1,.1)
        pair=next(p for p in result['pairs'] if p['occurrence_paths']==['base-1','carriage-1'])
        self.assertTrue(all(not s['candidates'] for s in pair['snapshots']))
        self.assertIn('MULTIPLE_MATE_SNAPSHOTS_NOT_COMBINED',[f['code'] for f in pair['flags']])
        empty=copy.deepcopy(self.envelope);empty['data']['mates']=[]
        result=analyze(target,[(self.source,empty)],.1,.1)
        self.assertTrue(all(not s['candidates'] for p in result['pairs'] for s in p['snapshots']))
        self.assertTrue(any(p['geometry_context']['axis_relations'] for p in result['pairs']))

    def test_unsupported_active_mates_and_lock_motion_conflict(self):
        extra=copy.deepcopy(self.envelope['data']['mates'][0]);extra.update(feature_id=102,type_code=17,type_name='screw')
        extra.pop('constraint_options');self.envelope['data']['mates'].append(extra)
        self.assertEqual(self.analyze()['candidates'][0]['status'],'conditional')
        lock=self.envelope['data']['mates'][0];lock.update(type_code=16,type_name='lock');lock.pop('constraint_options')
        result=self.analyze()
        self.assertEqual(result['candidates'][0]['status'],'opposed')
        self.assertIn('LOCK_WITH_MOTION_MATE',[x['code'] for x in result['conflicts']])

    def test_capture_identity_geometry_and_document_change_fatal(self):
        original=self.records[0].mate.entities[0].EntityParams
        # Recheck sees a changed raw plane/cylinder parameter, even if the COM object is unchanged.
        calls=[]
        def changing_size():
            calls.append(1)
            if len(calls)>2: original[0]=.5
            return len(original)
        self.records[0].mate.entities[0].GetEntityParamsSize=changing_size
        service=SolidWorksTools(self.root,factory=lambda:SolidWorksAdapter(app=self.app,runtime=runtime()));self.addCleanup(service.close)
        token=service.call('sw_active_document')['data']['document_token']
        result=service.call('sw_mate_inventory',{'expected_document_token':token,'include_reference_geometry':True})
        self.assertEqual(result['status'],'error',result)
        self.assertEqual(result['errors'][0]['code'],'GEOMETRY_CHANGED')

    def test_final_pose_guard_covers_optional_com_rechecks(self):
        from types import SimpleNamespace
        from tests.sw_fakes import pose
        calls=[]
        def moved_during_recheck():
            calls.append(1)
            if len(calls)>1:self.app.ActiveDoc.root.children[0].Transform2=pose(x=.5)
            return SimpleNamespace(LockRotation=False)
        self.records[0].GetDefinition=moved_during_recheck
        service=SolidWorksTools(self.root,factory=lambda:SolidWorksAdapter(app=self.app,runtime=runtime()));self.addCleanup(service.close)
        token=service.call('sw_active_document')['data']['document_token']
        result=service.call('sw_mate_inventory',{'expected_document_token':token,'include_reference_geometry':True})
        self.assertEqual(result['status'],'error',result)
        self.assertEqual(result['errors'][0]['code'],'COMPONENT_CHANGED')
