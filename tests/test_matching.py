import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from cadkin.errors import ToolFailure
from cadkin.matching.search import match_patterns
from cadkin.matching.target import adapt_target
from cadkin.tools.solidworks import SolidWorksTools
from cadkin.tools.matching import build_target
from tests.matching_fakes import toy_target, toy_reference, blinded_reference_window
from tests.chain_fakes import write_chain_fixture

HAS_USD=importlib.util.find_spec('pxr') is not None


class SearchTests(unittest.TestCase):
    def run_search(self,target=None,refs=None,**kwargs):
        return match_patterns(target or toy_target(), refs or [toy_reference()],**kwargs)

    def test_supported_connected_match_and_symmetric_alternatives(self):
        data=self.run_search();self.assertEqual(data['best_score'],1)
        self.assertEqual(data['best_score_ties_found'],2);self.assertTrue(data['ambiguous']);self.assertTrue(data['search_exhaustive'])
        for c in data['candidates']:
            self.assertEqual(next(m['occurrence_path'] for m in c['mapping'] if m['template_body_id']=='r0'),'b')
            self.assertFalse(c['mechanical_relation_confirmed'])
            self.assertTrue(all(e['limits'] is None and e['axis_origin_m'] is None and not e['joint_axis_verified'] for e in c['joint_hypotheses']))

    def test_relative_axes_prefer_consistent_reference(self):
        d=self.run_search(refs=[toy_reference(True,name='parallel'),toy_reference(False,name='orthogonal')])
        self.assertEqual(d['candidates'][0]['template_id'],'orthogonal')
        self.assertGreater(d['best_score'],next(c['score'] for c in d['candidates'] if c['template_id']=='parallel'))

    def test_rotation_sign_and_name_do_not_change_score(self):
        t=toy_target()
        for p in t['pairs']:
            a=p['representative_axis_unit']
            if a:p['representative_axis_unit']=[a[2],-a[1],-a[0]]
        for n in t['nodes']:n['role_context']={'role':'fixed_base','label':'servo lead screw'}
        self.assertEqual(self.run_search(t)['best_score'],1)

    def test_no_evidence_names_cannot_invent_matches(self):
        t=toy_target()
        for p in t['pairs']:p['link_support']=0.
        t['nodes'][0]['name']='gas_lift_bar_stool'
        d=self.run_search(t);self.assertEqual(d['candidates'],[]);self.assertIsNone(d['best_score'])

    def test_unobserved_third_node_is_not_arbitrarily_filled(self):
        t=toy_target();t['pairs'][2]['link_support']=0.
        self.assertEqual(self.run_search(t)['candidates'],[])

    def test_extra_support_and_unknown_triangle_edge_retained(self):
        t=toy_target();t['pairs'][1]['link_support']=.5
        d=self.run_search(t);self.assertTrue(d['candidates'][0]['extra_supported_pairs']);self.assertLess(d['best_score'],1)
        entry,g=toy_reference();edge=copy.deepcopy(g['joints'][0]);edge['id']='j2';edge['endpoints'][0]['body_id']='r1';edge['endpoints'][1]['body_id']='r2';g['joints'].append(edge)
        d=self.run_search(refs=[(entry,g)]);self.assertTrue(d['candidates']);self.assertTrue(d['candidates'][0]['unsupported_template_joint_ids'])

    def test_joint_types_remain_unscored_hypotheses(self):
        a=self.run_search(refs=[toy_reference(kind='prismatic')]);b=self.run_search(refs=[toy_reference(kind='revolute')])
        self.assertEqual(a['best_score'],b['best_score'])
        self.assertEqual(a['candidates'][0]['joint_hypotheses'][0]['kind_basis'],'reference_template_only')

    def test_unknown_axes_reduce_coverage_not_silently_align(self):
        t=toy_target();t['pairs'][0]['representative_axis_unit']=None
        d=self.run_search(t);self.assertAlmostEqual(d['best_score'],.7)
        self.assertEqual(d['candidates'][0]['coverage']['completed_axis_checks'],0)
        self.assertEqual(d['candidates'][0]['coverage']['possible_axis_checks'],1)

    def test_budget_beam_and_output_truncation_are_separate(self):
        d=self.run_search(max_states=1);self.assertFalse(d['search_exhaustive']);self.assertEqual(d['search']['evaluated_states'],1)
        d=self.run_search(beam_width=1);self.assertFalse(d['search_exhaustive'])
        d=self.run_search(max_candidates=1);self.assertTrue(d['search_exhaustive']);self.assertTrue(d['output_truncated']);self.assertEqual(d['best_score_ties_found'],2)

    def test_budget_is_distributed_between_templates(self):
        d=self.run_search(refs=[toy_reference(name='a'),toy_reference(name='b')],max_states=7)
        self.assertEqual(d['search']['evaluated_states'],7)
        self.assertEqual([p['state_budget'] for p in d['search']['patterns']],[4,3])

    def test_disabled_targets_and_effective_pattern_size(self):
        t=toy_target();t['nodes'][2]['eligible']=False
        d=self.run_search(t);self.assertEqual(d['effective_pattern_size'],2)
        self.assertTrue(all(m['occurrence_path']!='c' for c in d['candidates'] for m in c['mapping']))
        t['nodes'][1]['eligible']=False;self.assertFalse(self.run_search(t)['candidates'])

    def test_reference_missing_joints_ground_disabled_and_boundary(self):
        entry,g=toy_reference();ground=copy.deepcopy(g['joints'][0]);ground['id']='ground';ground['endpoints'][0].update(body_id=None,frame_kind='world');g['joints'].append(ground)
        d=self.run_search(refs=[(entry,g)]);self.assertIn('ground',d['reference_coverage'][0]['excluded_joint_ids'])
        self.assertIn('ground',d['candidates'][0]['unmatched_reference_boundary_joint_ids'])
        g['joints']=[];d=self.run_search(refs=[(entry,g)]);self.assertFalse(d['candidates']);self.assertEqual(d['reference_coverage'][0]['pattern_count'],0)

    def test_reference_unknown_axis_is_in_denominator(self):
        entry,g=toy_reference();g['joints'][0]['endpoints'][0]['axis_world']=None
        d=self.run_search(refs=[(entry,g)])
        self.assertAlmostEqual(d['best_score'],.7)
        self.assertEqual(d['candidates'][0]['coverage']['possible_axis_checks'],1)
        self.assertEqual(d['candidates'][0]['coverage']['completed_axis_checks'],0)

    def test_template_rankings_keep_alternatives_when_output_is_capped(self):
        d=self.run_search(refs=[toy_reference(name='a'),toy_reference(name='b')],max_candidates=1)
        self.assertEqual(d['returned_candidates'],1)
        self.assertEqual(len(d['template_rankings']),2)
        self.assertTrue(all(r['best_score_found']==1 and r['supported_candidates_found'] for r in d['template_rankings']))

    def test_parameters_reject_nonfinite_and_bool(self):
        for args in ({'max_states':True},{'angle_tolerance_deg':float('nan')},{'pattern_size':7},{'beam_width':0}):
            with self.subTest(args=args),self.assertRaises(ToolFailure):self.run_search(**args)

    def test_order_permutation_preserves_best_score(self):
        t=toy_target();t['nodes'].reverse();t['pairs'].reverse()
        self.assertEqual(self.run_search(t),self.run_search())


class TargetTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.args=write_chain_fixture(self.root)
        self.service=SolidWorksTools(self.root,factory=lambda:self.fail('Offline tools must not initialize COM'));self.addCleanup(self.service.close)
        result=self.service.call('cad_build_chain_evidence',self.args);self.assertEqual(result['status'],'ok')
    def read(self,path):return json.loads((self.root/path).read_text(encoding='utf-8'))
    def save(self,path,obj):return (self.root/path).write_text(json.dumps(obj),encoding='utf-8')
    def build(self,**kwargs):return self.service.call('cad_build_target_graph',{'chain_path':'outputs/chain.json','output_path':'outputs/target.json',**kwargs})
    def match(self,**kwargs):return self.service.call('cad_match_mechanism_templates',{'target_graph_path':'outputs/target.json','output_path':'outputs/match.json',**kwargs})

    def test_replays_auto_relations_and_preserves_occurrences_and_units(self):
        d=build_target(self.root,'outputs/chain.json');self.assertEqual(len(d['nodes']),3);self.assertEqual(len(d['pairs']),3)
        self.assertEqual(len(d['relation_sources']),1);self.assertTrue(d['complete'])
        self.assertEqual(d['coverage']['pairs_with_single_axis'],3)
        n=next(n for n in d['nodes'] if n['id']=='rail-1');self.assertEqual(n['origin_m'],[.02,0,0])
        self.assertFalse(d['requires_human_review']);self.assertFalse(d['solidworks_modified'])
        self.assertTrue(all(p['axis_relations'] for p in d['pairs']))
        self.assertGreater(len(d['input_files']),10)

    def test_unknown_chain_can_adapt_without_forcing_collection(self):
        args={k:v for k,v in self.args.items() if k not in ('grouping_path','evidence_paths')};args['output_path']='outputs/empty-chain.json'
        self.service.call('cad_build_chain_evidence',args)
        result=self.build(chain_path='outputs/empty-chain.json');self.assertEqual(result['status'],'partial')
        self.assertEqual(result['data']['coverage']['pairs_with_positive_support'],0)

    def test_additional_standalone_axes_and_duplicate_content_do_not_inflate(self):
        d=build_target(self.root,'outputs/chain.json',['outputs/relations.json'])
        original=build_target(self.root,'outputs/chain.json')
        self.assertEqual([p['link_support'] for p in d['pairs']],[p['link_support'] for p in original['pairs']])
        self.assertEqual(len(d['relation_sources']),1)

    def test_modified_chain_and_source_are_rejected(self):
        chain=self.read('outputs/chain.json');chain['pairs'][0]['evidence_status']='confirmed';self.save('outputs/chain.json',chain)
        self.assertEqual(self.build()['errors'][0]['code'],'EVIDENCE_MISMATCH')

    def test_source_file_change_and_outputs_protected(self):
        self.build();self.assertEqual(self.build()['errors'][0]['code'],'OUTPUT_EXISTS')
        p=self.root/'cylinder0.json';p.write_bytes(p.read_bytes()+b'\n')
        self.assertEqual(self.build(output_path='outputs/new.json')['errors'][0]['code'],'EVIDENCE_MISMATCH')

    def test_flags_reduce_support_and_keep_conflicting_sources(self):
        from cadkin.tools.chain import build_chain
        from cadkin.tools.chain_sources import ChainSources
        params={k:v for k,v in self.args.items() if k!='output_path'}
        chain=build_chain(self.root,**params);chain['pairs'][0]['review_flags']=[{'code':'SCOPE_DIFFERENCE'}]
        reader=ChainSources(self.root,'inventory.json');d=adapt_target(chain,reader.nodes,[])
        self.assertEqual(d['pairs'][0]['link_support'],.5);self.assertEqual(d['coverage']['pairs_with_flags'],1)

    def test_multiple_axes_and_axis_budget_stay_unknown(self):
        from cadkin.tools.chain import build_chain
        from cadkin.tools.chain_sources import ChainSources
        params={k:v for k,v in self.args.items() if k!='output_path'};chain=build_chain(self.root,**params)
        reader=ChainSources(self.root,'inventory.json');rel,binding=reader.relations('outputs/relations.json')
        row=copy.deepcopy(rel['candidates'][0]);row['left']['axis_root_unit']=[1,0,0];rel['candidates'].append(row)
        d=adapt_target(chain,reader.nodes,[(rel,binding)]);pair=next(p for p in d['pairs'] if p['axis_direction_count']>1)
        self.assertIsNone(pair['representative_axis_unit'])
        rel['candidates']=rel['candidates'][:1]*33;d=adapt_target(chain,reader.nodes,[(rel,binding)])
        pair=next(p for p in d['pairs'] if p['axes_truncated']);self.assertEqual(len(pair['axis_relations']),32);self.assertIsNone(pair['representative_axis_unit']);self.assertFalse(d['complete'])

    def test_multiple_thresholds_and_mate_record_errors_preserve_risks(self):
        from cadkin.tools.chain import build_chain
        from cadkin.tools.chain_sources import ChainSources
        params={k:v for k,v in self.args.items() if k!='output_path'};chain=build_chain(self.root,**params)
        reader=ChainSources(self.root,'inventory.json');rel,binding=reader.relations('outputs/relations.json')
        other=copy.deepcopy(rel);other['parameters']['angle_tolerance_deg']=.2
        d=adapt_target(chain,reader.nodes,[(rel,binding),(other,{**binding,'sha256':'b'*64})])
        self.assertTrue(all(any(f['code']=='MULTIPLE_AXIS_THRESHOLDS' for f in p['flags']) for p in d['pairs']))
        pair=next(p for p in chain['pairs'] if any(e['kind']=='connection' and e['record']['mate_evidence'] for e in p['evidence']))
        evidence=next(e for e in pair['evidence'] if e['kind']=='connection' and e['record']['mate_evidence'])
        evidence['record']['mate_evidence'][0]['record_errors']=[{'code':'FIXTURE_ERROR'}]
        d=adapt_target(chain,reader.nodes,[])
        self.assertTrue(any(any(f['code']=='MATE_RECORD_INCOMPLETE' for f in p['flags']) for p in d['pairs']))

    @unittest.skipUnless(HAS_USD,'Install .[templates]')
    def test_production_matcher_replays_target_and_defaults_exclude_heldout(self):
        self.build();r=self.match();self.assertIn(r['status'],('ok','partial'))
        d=r['data'];self.assertTrue(d['candidates']);self.assertFalse(d['heldout_exposed']);self.assertEqual(len(d['template_sources']),6)
        self.assertFalse(d['requires_human_review']);self.assertFalse(d['mechanical_relation_confirmed'])
        t=self.read('outputs/target.json');t['pairs'][0]['link_support']=.99;self.save('outputs/target.json',t)
        self.assertEqual(self.match(output_path='outputs/forged.json')['errors'][0]['code'],'EVIDENCE_MISMATCH')

    @unittest.skipUnless(HAS_USD,'Install .[templates]')
    def test_heldout_requires_explicit_selection_and_marks_exposure(self):
        self.build();self.assertEqual(self.match(template_ids=['bar_clamp'])['errors'][0]['code'],'HELDOUT_TEMPLATE')
        r=self.match(template_ids=['bar_clamp'],include_heldout=True);self.assertTrue(r['data']['heldout_exposed'])

    @unittest.skipUnless(HAS_USD,'Install .[templates]')
    def test_no_reference_joint_and_no_target_support_stay_partial(self):
        self.build();r=self.match(template_ids=['gear_meshing_kit']);self.assertEqual(r['status'],'partial');self.assertFalse(r['data']['candidates'])
        args={k:v for k,v in self.args.items() if k not in ('grouping_path','evidence_paths')};args['output_path']='outputs/empty-chain.json'
        self.service.call('cad_build_chain_evidence',args);self.build(chain_path='outputs/empty-chain.json',output_path='outputs/empty-target.json')
        r=self.match(target_graph_path='outputs/empty-target.json',output_path='outputs/empty-match.json',template_ids=['gas_lift_bar_stool'])
        self.assertFalse(r['data']['candidates']);self.assertEqual(r['status'],'partial');self.assertTrue(r['data']['target_errors'])

    @unittest.skipUnless(HAS_USD,'Install .[templates]')
    def test_cli_and_budget_recovery(self):
        p=subprocess.run([sys.executable,'-m','cadkin','target-graph','outputs/chain.json','--output','outputs/target.json'],cwd=self.root,capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
        p=subprocess.run([sys.executable,'-m','cadkin','match-templates','outputs/target.json','--template-ids','gas_lift_bar_stool','--max-states','1','--output','outputs/budget.json'],cwd=self.root,capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr);d=json.loads(p.stdout);self.assertEqual(d['status'],'partial');self.assertFalse(d['data']['search_exhaustive'])
        self.assertEqual(self.service.call('cad_list_mechanism_templates')['status'],'ok')


@unittest.skipUnless(HAS_USD,'Install .[templates]')
class RealReferenceControlTests(unittest.TestCase):
    def test_reference_derived_label_hidden_controls_not_accuracy(self):
        from cadkin.templates.catalog import catalog,find_template
        from cadkin.templates.usd import read_template
        controls=0
        for entry in catalog()['templates']:
            if entry['split']=='heldout':continue
            g=read_template(find_template(entry['id'])[1]);target=blinded_reference_window(entry,g)
            if target is None:continue
            controls+=1;d=match_patterns(target,[(entry,g)],max_states=100000,beam_width=1000)
            self.assertTrue(d['candidates'],entry['id']);self.assertGreaterEqual(d['best_score'],.7)
            self.assertTrue(all('hypothesis_kind' not in p for p in target['pairs']))
        self.assertEqual(controls,4)


if __name__=='__main__':unittest.main()
