import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import numpy as np

from cadkin.constraints.analysis import analyze
from cadkin.constraints.chain_motion import solve_chain
from cadkin.errors import ToolFailure
from cadkin.tools.chain_motion import replay_chain_solution
from cadkin.tools.solidworks import SolidWorksTools
from tests.constraint_fakes import write_constraint_followup_fixture


class ChainConstraintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)
        cls.fixtures={}
        for mode in ('chain_open','chain_closed','chain_redundant','chain_fixed','chain_hinges','no_mates','prismatic'):
            root=cls.root/mode;_,_,raw=write_constraint_followup_fixture(root,mode,enriched=True)
            cls.fixtures[mode]=(json.loads((root/'outputs/target.json').read_text()),raw)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def source(self,mode,raw=None,extra=None,max_pairs=200):
        target,original=self.fixtures[mode];snapshots=[({'path':'synthetic.json','sha256':'a'*64},raw or original)]
        if extra:snapshots.append(({'path':'another.json','sha256':'b'*64},extra))
        return analyze(target,snapshots,.1,.1,max_pairs)
    def solve(self,mode,**kwargs):
        analysis=kwargs.pop('analysis',None) or self.source(mode)
        return solve_chain(analysis,['base-1','carriage-1','rail-1'],kwargs.pop('reference','base-1'),100,**kwargs)
    def test_open_slides_and_closed_loop_remove_motion(self):
        opened=self.solve('chain_open')['snapshots'][0];closed=self.solve('chain_closed')['snapshots'][0]
        self.assertEqual(opened['modeled_chain_instantaneous_dof'],2,opened['unresolved_evidence'])
        self.assertEqual(opened['graph_cycle_count'],0)
        self.assertEqual(closed['modeled_chain_instantaneous_dof'],0,closed['unresolved_evidence'])
        self.assertEqual(closed['graph_cycle_count'],1);self.assertEqual(closed['spanning_forest_diagnostics']['additional_loop_rank'],2)
        self.assertTrue(opened['internal_boundary_mates_handled'])
        self.assertEqual(closed['linear_solution']['rank'],12)
    def test_redundant_loop_does_not_remove_extra_motion(self):
        s=self.solve('chain_redundant')['snapshots'][0]
        self.assertEqual(s['modeled_chain_instantaneous_dof'],2);self.assertEqual(s['graph_cycle_count'],1)
        self.assertEqual(s['spanning_forest_diagnostics']['additional_loop_rank'],0)
    def test_locks_and_reference_are_not_physical_grounding(self):
        for ref in ('base-1','carriage-1','rail-1'):
            s=self.solve('chain_fixed',reference=ref)['snapshots'][0]
            self.assertEqual(s['modeled_chain_instantaneous_dof'],0,s['source_conflicts'])
            self.assertFalse(s['reference_is_physical_ground']);self.assertIsNone(s['target_degrees_of_freedom'])
    def test_modes_obey_every_pair_at_common_origin(self):
        s=self.solve('chain_hinges')['snapshots'][0]
        self.assertEqual(s['modeled_chain_instantaneous_dof'],2)
        matrix=np.array([r['coefficients'] for r in s['rows']]);variables=s['variable_occurrence_order']
        origin=np.array(s['velocity_origin_root_m']);length=s['characteristic_length_m']
        for mode in s['motion_modes']:
            by_name={b['occurrence_path']:b['scaled_twist'] for b in mode['components']}
            x=np.concatenate([by_name[n] for n in variables]);np.testing.assert_allclose(matrix@x,0,atol=1e-10)
            self.assertEqual(by_name['base-1'],[0.]*6)
            for edge in s['edges']:
                a,b=edge['occurrence_paths'];difference=np.array(by_name[b])-np.array(by_name[a])
                point=np.array(edge['modeled_constraints'][0]['idealization_face']['point_root_m'])
                velocity=difference[:3]*length+np.cross(difference[3:],point-origin)
                np.testing.assert_allclose(velocity,0,atol=1e-10)
                np.testing.assert_allclose(difference[3:5],0,atol=1e-10)
        self.assertTrue(any(abs(b['scaled_twist'][1])>1e-6 for mode in s['motion_modes'] for b in mode['components']))
    def test_disconnected_and_empty_remain_unknown(self):
        s=self.solve('prismatic')['snapshots'][0];self.assertEqual(s['status'],'partial_constraint_model')
        self.assertIsNone(s['modeled_chain_instantaneous_dof']);self.assertEqual(s['known_constraint_nullity'],7)
        self.assertIn('DISCONNECTED_CONSTRAINT_GRAPH',[g['code'] for g in s['unresolved_evidence']])
        s=self.solve('no_mates')['snapshots'][0];self.assertIsNone(s['known_constraint_nullity']);self.assertEqual(s['motion_modes'],[])
    def test_unsupported_external_and_budget_are_not_complete(self):
        raw=copy.deepcopy(self.fixtures['chain_open'][1]);raw['data']['mates'][0]['type_code']=17;raw['data']['mates'][0]['type_name']='screw';raw['data']['mates'][0].pop('constraint_options')
        s=self.solve('chain_open',analysis=self.source('chain_open',raw))['snapshots'][0]
        self.assertIsNone(s['modeled_chain_instantaneous_dof']);self.assertIn('UNSUPPORTED_ACTIVE_CONSTRAINT',[m['code'] for m in s['unresolved_evidence']])
        raw=copy.deepcopy(self.fixtures['chain_open'][1]);raw['data']['mates'][0]['entities'][0]['reference_occurrence_path']='external-1'
        s=self.solve('chain_open',analysis=self.source('chain_open',raw))['snapshots'][0]
        self.assertIn('BOUNDARY_OR_UNRESOLVED_MATES',[m['code'] for m in s['unresolved_evidence']])
        s=self.solve('chain_closed',analysis=self.source('chain_closed',max_pairs=1))['snapshots'][0]
        self.assertIsNone(s['modeled_chain_instantaneous_dof']);self.assertIn('ANALYSIS_PAIR_LIMIT',[m['code'] for m in s['unresolved_evidence']])
    def test_source_snapshots_are_not_combined(self):
        a=self.source('chain_open',extra=self.fixtures['chain_closed'][1]);data=self.solve('chain_open',analysis=a)
        self.assertEqual([s['modeled_chain_instantaneous_dof'] for s in data['snapshots']],[2,0])
        self.assertFalse(data['assembly_dof_solved']);self.assertIsNone(data['target_degrees_of_freedom'])
    def test_scope_and_reference_validation(self):
        with self.assertRaises(ToolFailure):self.solve('chain_open',reference='outside')
        with self.assertRaises(ToolFailure):solve_chain(self.source('chain_open'),[str(i) for i in range(21)],'0',100)
    def test_geometry_conflict_partial_source_and_total_equation_cap(self):
        raw=copy.deepcopy(self.fixtures['chain_open'][1])
        entity=raw['data']['mates'][0]['entities'][1]
        entity['entity_params_raw'][0]=.02
        entity['reference_geometry']['entity_params_raw'][0]=.02
        entity['reference_geometry']['point_root_m'][0]=.02
        s=self.solve('chain_open',analysis=self.source('chain_open',raw))['snapshots'][0]
        self.assertEqual(s['status'],'conflicting_source');self.assertFalse(s['motion_modes']);self.assertIsNone(s['modeled_chain_instantaneous_dof'])
        raw=copy.deepcopy(self.fixtures['chain_open'][1]);raw['status']='partial';raw['data']['complete']=False
        s=self.solve('chain_open',analysis=self.source('chain_open',raw))['snapshots'][0]
        self.assertIsNone(s['modeled_chain_instantaneous_dof']);self.assertIn('MATE_SOURCE_INCOMPLETE',[m['code'] for m in s['unresolved_evidence']])
        from unittest.mock import patch
        with patch('cadkin.constraints.chain_motion.MAX_EQUATIONS',4),self.assertRaises(ToolFailure) as raised:self.solve('chain_open')
        self.assertEqual(raised.exception.code,'CHAIN_EQUATION_LIMIT')

    def test_compact_file_replay_tamper_rejection_and_cli(self):
        base=self.root/'chain_open';initial={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in base.rglob('*.json')}
        service=SolidWorksTools(base,factory=lambda:(_ for _ in ()).throw(AssertionError('Unexpected CAD')))
        try:
            args={'constraint_analysis_path':'outputs/constraints.json','reference_occurrence_path':'base-1','characteristic_length_mm':100,'output_path':'outputs/chain-solved.json'}
            r=service.call('cad_solve_chain_constraints',args);self.assertEqual(r['status'],'ok',r)
            self.assertNotIn('rows',r['data']['snapshots'][0]);self.assertTrue(r['data']['detail_saved'])
            replay_chain_solution(base,args['output_path']);path=base/args['output_path'];raw=json.loads(path.read_text())
            raw['snapshots'][0]['linear_solution']['rank']=0;path.write_text(json.dumps(raw))
            with self.assertRaises(ToolFailure):replay_chain_solution(base,args['output_path'])
            self.assertTrue(all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in initial.items()))
            p=subprocess.run([sys.executable,'-m','cadkin','solve-chain-constraints','outputs/constraints.json','--reference-occurrence-path','base-1',
                '--characteristic-length-mm','100','--output','outputs/cli-chain.json'],cwd=base,capture_output=True,text=True,timeout=90)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        finally:service.close()


if __name__=='__main__':unittest.main()
