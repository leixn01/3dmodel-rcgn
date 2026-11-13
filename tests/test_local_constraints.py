import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import numpy as np

from cadkin.constraints.analysis import analyze_snapshot
from cadkin.constraints.motion import model_snapshot
from cadkin.constraints.linear import decompose
from cadkin.errors import ToolFailure
from cadkin.tools.local_motion import replay_solution
from cadkin.tools.solidworks import SolidWorksTools
from cadkin.tools.execution import run_plan
from tests.constraint_fakes import write_constraint_followup_fixture
from tests.execution_fakes import live_service


class LocalConstraintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)
        cls.app,_,cls.envelope=write_constraint_followup_fixture(cls.root,enriched=True)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def setUp(self):
        self.raw=copy.deepcopy(self.envelope)
        self.source={'path':'synthetic.json','sha256':'a'*64}
    def equation(self,kind,point=(0,0,0),direction=(0,0,1),locked=False):
        record=copy.deepcopy(self.envelope['data']['mates'][0 if kind=='axis' else 1])
        for entity in record['entities']:
            raw=list(point)+list(direction)+([.01] if kind=='axis' else [])
            entity['entity_params_raw']=raw
            entity['reference_geometry'].update(entity_params_raw=raw,point_root_m=list(point),direction_root_unit=list(direction))
        if kind=='axis':record['constraint_options']['concentric_lock_rotation']=locked
        return record
    def model(self,records=None,length=.1,tolerance=1e-8,limit=200):
        if records is not None:self.raw['data']['mates']=records
        for i,r in enumerate(self.raw['data']['mates']):r['feature_id']=100+i
        snapshot=analyze_snapshot(['base-1','carriage-1'],self.source,self.raw,.1,.1)
        return model_snapshot(['base-1','carriage-1'],snapshot,length,tolerance,limit,[])
    def assert_solution(self,model,dof,translations):
        self.assertEqual(model['modeled_instantaneous_dof'],dof,model)
        self.assertEqual(model['pure_translation_dimension'],translations)
        self.assertEqual(model['linear_solution']['rank'],6-dof)
        self.assertLess(model['linear_solution']['max_nullspace_residual'],1e-9)
        self.assertEqual(len(model['motion_modes']),dof)
        self.assertEqual(model['target_joint_kind'],'unknown');self.assertIsNone(model['target_degrees_of_freedom'])

    def test_classic_axis_plane_and_lock_models(self):
        self.assert_solution(self.model([self.equation('axis')]),2,1)
        self.assert_solution(self.model([self.equation('axis',locked=True)]),1,1)
        self.assert_solution(self.model([self.equation('plane')]),3,2)
        self.assert_solution(self.model([self.equation('axis'),self.equation('plane')]),1,0)
        self.assert_solution(self.model([self.equation('axis',locked=True),self.equation('plane')]),0,0)
        lock=copy.deepcopy(self.envelope['data']['mates'][0]);lock.update(type_code=16,type_name='lock');lock.pop('constraint_options')
        self.assert_solution(self.model([lock]),0,0)

    def test_parallel_axes_dependence_and_nonparallel_axes(self):
        axis=self.equation('axis')
        duplicated=self.model([axis,copy.deepcopy(axis)])
        self.assert_solution(duplicated,2,1);self.assertEqual(duplicated['dependent_linear_equations'],4)
        self.assert_solution(self.model([self.equation('axis'),self.equation('axis',point=(.02,0,0))]),1,1)
        nonparallel=self.model([self.equation('axis'),self.equation('axis',direction=(1,0,0))])
        self.assert_solution(nonparallel,0,0)
        self.assertIn('NONPARALLEL_AXIS_COMBINATION_NOT_IMPLEMENTED',[m['code'] for m in nonparallel['pattern_gaps_addressed']])

    def test_oblique_plane_and_plane_combinations(self):
        self.assert_solution(self.model([self.equation('axis'),self.equation('plane',direction=(1,0,0))]),1,1)
        v=[math.sqrt(.5),0,math.sqrt(.5)]
        oblique=self.model([self.equation('axis'),self.equation('plane',direction=v)])
        self.assert_solution(oblique,0,0)
        self.assertIn('OBLIQUE_PLANE_COMBINATION_NOT_IMPLEMENTED',[m['code'] for m in oblique['pattern_gaps_addressed']])
        self.assert_solution(self.model([self.equation('plane'),self.equation('plane',direction=(1,0,0))]),1,1)
        self.assert_solution(self.model([self.equation('plane'),self.equation('plane',direction=(1,0,0)),self.equation('plane',direction=(0,1,0))]),0,0)

    def test_suppressed_missing_unsupported_and_partial_are_not_free_dof(self):
        self.raw['data']['mates']=[]
        result=self.model();self.assertIsNone(result['known_constraint_nullity']);self.assertIsNone(result['modeled_instantaneous_dof']);self.assertEqual(result['motion_modes'],[])
        axis=self.equation('axis');axis['activity'].update(suppressed=True,state='suppressed')
        self.assertIsNone(self.model([axis])['modeled_instantaneous_dof'])
        axis=self.equation('axis');axis.pop('constraint_options')
        result=self.model([axis]);self.assertEqual(result['known_constraint_nullity'],2);self.assertIsNone(result['modeled_instantaneous_dof'])
        screw=self.equation('axis');screw.update(type_code=17,type_name='screw');screw.pop('constraint_options')
        result=self.model([self.equation('axis'),screw]);self.assertEqual(result['status'],'partial_constraint_model')
        self.raw['status']='partial';self.raw['data']['complete']=False
        result=self.model([self.equation('axis')]);self.assertIsNone(result['modeled_instantaneous_dof'])
        self.assertIn('MATE_SOURCE_INCOMPLETE',[m['code'] for m in result['unresolved_evidence']])

    def test_conflicting_geometry_suppresses_motion_claim(self):
        entity=self.raw['data']['mates'][1]['entities'][1]
        entity['entity_params_raw'][2]=.02;g=entity['reference_geometry'];g['entity_params_raw'][2]=.02;g['point_root_m'][2]=.02
        result=self.model();self.assertEqual(result['status'],'conflicting_source')
        self.assertEqual(result['known_constraint_nullity'],2);self.assertIsNone(result['modeled_instantaneous_dof']);self.assertEqual(result['motion_modes'],[])

    def test_boundaries_and_constraint_budget_keep_partial_model(self):
        axis=self.equation('axis');boundary=self.equation('plane')
        boundary['entities'][1]['reference_occurrence_path']='rail-1'
        result=self.model([axis,boundary]);self.assertEqual(result['known_constraint_nullity'],2);self.assertIsNone(result['modeled_instantaneous_dof'])
        result=self.model([self.equation('axis'),self.equation('plane')],limit=1)
        self.assertEqual(result['coverage']['omitted_constraints'],1);self.assertIsNone(result['modeled_instantaneous_dof'])

    def test_entity_order_and_global_translation_do_not_change_modes(self):
        first=self.model()
        for record in self.raw['data']['mates']:record['entities'].reverse()
        second=self.model();self.assertEqual(first,second)
        offset=np.array([100.,-55.,23.])
        for r in self.raw['data']['mates']:
            for e in r['entities']:
                point=(np.array(e['entity_params_raw'][:3])+offset).tolist()
                e['entity_params_raw'][:3]=point;g=e['reference_geometry'];g['entity_params_raw'][:3]=point;g['point_root_m']=point
        shifted=self.model();self.assert_solution(shifted,1,0)
        np.testing.assert_allclose(shifted['linear_solution']['nullspace_projector'],first['linear_solution']['nullspace_projector'],atol=1e-10)
        np.testing.assert_allclose(shifted['velocity_origin_root_m'],offset,atol=1e-12)

    def test_rotation_and_scale_covariance(self):
        axis=np.array([1.,2.,3.]);axis/=np.linalg.norm(axis)
        rotation=np.eye(3)*math.cos(.73)+(1-math.cos(.73))*np.outer(axis,axis)+math.sin(.73)*np.array([[0,-axis[2],axis[1]],[axis[2],0,-axis[0]],[-axis[1],axis[0],0]])
        first=self.model([self.equation('axis'),self.equation('plane',point=(.03,0,0))])
        changed=[]
        for r in copy.deepcopy(self.raw['data']['mates']):
            for e in r['entities']:
                p=(rotation@np.array(e['entity_params_raw'][:3])*1000).tolist();d=(rotation@np.array(e['entity_params_raw'][3:6])).tolist()
                e['entity_params_raw'][:6]=p+d;g=e['reference_geometry'];g.update(entity_params_raw=e['entity_params_raw'],point_root_m=p,direction_root_unit=d)
                # Reconstruct normalized direction exactly as the source parser expects.
                from cadkin.face_geometry import unit
                g['direction_root_unit']=unit(d)
            changed.append(r)
        transformed=self.model(changed,length=100.)
        self.assert_solution(transformed,1,0)
        transform=np.zeros((6,6));transform[:3,:3]=rotation;transform[3:,3:]=rotation
        expected=transform@np.array(first['linear_solution']['nullspace_projector'])@transform.T
        np.testing.assert_allclose(transformed['linear_solution']['nullspace_projector'],expected,atol=1e-10)

    def test_jacobian_rows_match_independent_finite_difference(self):
        # Point velocity is independently measured from a small Rodrigues rigid transform.
        from cadkin.constraints.motion import cross
        model=self.model([self.equation('axis'),self.equation('plane',point=(.03,0,0))])
        origin=np.array(model['velocity_origin_root_m']);length=model['characteristic_length_m']
        velocity=np.array([.2,-.4,.3,.7,.1,-.3]);omega=velocity[3:];speed=np.linalg.norm(omega)
        k=np.array([[0,-omega[2],omega[1]],[omega[2],0,-omega[0]],[-omega[1],omega[0],0]])/speed
        dt=1e-7;rotation=np.eye(3)+math.sin(speed*dt)*k+(1-math.cos(speed*dt))*(k@k)
        for statement in model['modeled_constraints']:
            g=statement['idealization_face'];p=np.array(g['point_root_m']);direction=np.array(g['direction_root_unit'])
            point_derivative=(origin+rotation@(p-origin)+velocity[:3]*length*dt-p)/dt/length
            angular_derivative=(rotation@direction-direction)/dt
            for index in statement['row_indices']:
                row=model['rows'][index];coeff=np.array(row['coefficients'])*row['normalization_norm']
                if row['equation']=='parallel_direction_velocity':
                    derivative=np.dot(cross(coeff[3:],direction),angular_derivative)
                else:derivative=np.dot(coeff[:3],point_derivative)
                self.assertAlmostEqual(np.dot(coeff,velocity),derivative,places=6)

    def test_rank_sensitivity_is_explicit(self):
        result=decompose(np.diag([1,1,1,1,1e-8,0]),6,1e-8)
        self.assertFalse(result['rank_stable']);self.assertEqual(result['rank_range'],[4,5])
        model=self.model([self.equation('axis'),self.equation('axis',point=(2e-9,0,0))])
        self.assertEqual(model['status'],'numerically_sensitive');self.assertIsNone(model['modeled_instantaneous_dof']);self.assertEqual(model['motion_modes'],[])

    def test_canonical_nullspace_and_svd_failure(self):
        rows=[[0,0,1,0,0,0],[0,0,0,1,0,0],[0,0,0,0,1,0]]
        first=decompose(rows,6,1e-8);np.testing.assert_allclose(np.array(first['basis'])@np.array(first['basis']).T,np.eye(3),atol=1e-10)
        with patch('numpy.linalg.svd',side_effect=np.linalg.LinAlgError('synthetic')):
            with self.assertRaises(ToolFailure) as e:decompose(rows,6,1e-8)
        self.assertEqual(e.exception.code,'NUMERICAL_SOLUTION_INVALID')


class LocalConstraintFileTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.app,_,_=write_constraint_followup_fixture(self.root,enriched=True)
        self.factory=Mock(side_effect=AssertionError('Offline connected to CAD'))
        self.service=SolidWorksTools(self.root,factory=self.factory);self.addCleanup(self.service.close)
        self.args=dict(constraint_analysis_path='outputs/constraints.json',output_path='outputs/local.json',characteristic_length_mm=100)
    def test_replay_and_source_immutability(self):
        original={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*.json')}
        result=self.service.call('cad_solve_local_constraints',self.args);self.assertEqual(result['status'],'ok',result)
        data,_=replay_solution(self.root,'outputs/local.json');self.assertEqual(data['pairs'],result['data']['pairs'])
        self.assertTrue(all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in original.items()))
        self.assertEqual(self.service.call('cad_solve_local_constraints',self.args)['errors'][0]['code'],'OUTPUT_EXISTS');self.factory.assert_not_called()
    def test_forged_numeric_and_target_conclusions_rejected(self):
        self.service.call('cad_solve_local_constraints',self.args);path=self.root/'outputs/local.json';raw=json.loads(path.read_text())
        for key in ('number','target','source'):
            changed=copy.deepcopy(raw)
            if key=='number':changed['pairs'][0]['snapshots'][0]['linear_solution']['basis'][0][0]+=.01
            elif key=='target':changed['pairs'][0]['target_joint_kind']='revolute'
            else:changed['pairs'][0]['snapshots'][0]['velocity_origin_root_m'][0]+=.001
            path.write_text(json.dumps(changed),encoding='utf-8')
            with self.subTest(key=key),self.assertRaises(ToolFailure):replay_solution(self.root,str(path))
        # Numeric replay tolerates insignificant LAPACK roundoff, not changed rank or source inputs.
        raw['pairs'][0]['snapshots'][0]['linear_solution']['singular_values'][0]+=1e-12
        path.write_text(json.dumps(raw),encoding='utf-8');replay_solution(self.root,str(path))
    def test_invalid_parameters_limits_and_source_changes(self):
        for key,value in [('characteristic_length_mm',0),('relative_rank_tolerance',1e-20),('max_pairs',0),('max_constraints_per_snapshot',0)]:
            result=self.service.call('cad_solve_local_constraints',{**self.args,key:value});self.assertEqual(result['errors'][0]['code'],'INVALID_ARGUMENTS')
        result=self.service.call('cad_solve_local_constraints',{**self.args,'max_pairs':1,'max_constraints_per_snapshot':1})
        self.assertEqual(result['status'],'partial');self.assertEqual(result['data']['coverage']['omitted_pairs'],2);self.assertEqual(result['data']['coverage']['omitted_constraints'],1)
        with (self.root/'constraint-mates.json').open('a') as stream:stream.write('\n')
        result=self.service.call('cad_solve_local_constraints',{**self.args,'output_path':'outputs/changed.json'})
        self.assertEqual(result['errors'][0]['code'],'EVIDENCE_MISMATCH');self.assertFalse((self.root/'outputs/changed.json').exists())
    def test_cli_and_inherited_followup_history(self):
        process=subprocess.run([sys.executable,'-m','cadkin','solve-local-constraints','outputs/constraints.json','--characteristic-length-mm','100',
            '--output','outputs/cli.json'],cwd=self.root,capture_output=True,text=True,timeout=60)
        self.assertEqual(process.returncode,0,process.stdout+process.stderr)
        root=self.root/'followup';app,_,_=write_constraint_followup_fixture(root)
        live=live_service(root,app)
        try:
            run_plan(live,'outputs/plan.json','outputs/run.json')
            updated=live.call('cad_reintegrate_evidence',{'execution_path':'outputs/run.json','output_path':'outputs/updated.json'})['data']
            result=live.call('cad_solve_local_constraints',{**self.args,'constraint_analysis_path':updated['after_constraint_analysis_source']['path']})
            self.assertEqual(result['status'],'ok',result);data=result['data']
            self.assertEqual(data['rounds_completed'],1);self.assertEqual(data['evidence_index_source'],updated['after_evidence_index_source'])
            replay_solution(root,data['output_path'])
        finally:live.close()


if __name__=='__main__':unittest.main()
