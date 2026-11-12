import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from cadkin.tools.solidworks import SolidWorksTools
from cadkin.tools.chain import build_chain, review_flags
from tests.chain_fakes import write_chain_fixture


class ChainTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.args=write_chain_fixture(self.root)
        def forbidden():raise AssertionError('Offline chain operation started CAD')
        self.service=SolidWorksTools(root=self.root,factory=forbidden);self.addCleanup(self.service.close)
    def read(self,path):return json.loads((self.root/path).read_text(encoding='utf-8'))
    def save(self,path,data):
        file=self.root/path;file.parent.mkdir(parents=True,exist_ok=True);file.write_text(json.dumps(data),encoding='utf-8');return path
    def build(self,**kwargs):return self.service.call('cad_build_chain_evidence',{**self.args,**kwargs})
    def decision(self,chain='outputs/chain.json',decision='confirmed',**kwargs):
        data=self.read(chain);pair=data['pairs'][0]
        item={'pair_id':pair['pair_id'],'decision':decision,'relation_type':'rigid_connection' if decision=='confirmed' else None,
              'reason':'Synthetic reviewer declaration for test only.','evidence_ids':[e['evidence_id'] for e in pair['evidence']],**kwargs}
        review={'chain_review_input_schema_version':1,'chain_sha256':hashlib.sha256((self.root/chain).read_bytes()).hexdigest(),
                'reviewer':'Fixture reviewer','reviewed_at':'2026-11-12T10:00:00+08:00','decisions':[item]}
        return review
    def apply(self,review,**kwargs):
        self.save('review.json',review)
        return self.service.call('cad_apply_chain_review',{'chain_path':'outputs/chain.json','review_path':'review.json','output_path':'outputs/reviewed.json',**kwargs})

    def test_compiles_all_evidence_roles_and_no_cad(self):
        result=self.build();self.assertEqual(result['status'],'ok',result)
        data=self.read('outputs/chain.json');self.assertEqual(len(data['pairs']),3);self.assertEqual(data['coverage']['unknown_pairs'],0)
        self.assertEqual({s['kind'] for s in data['sources']},{'connection','component_proximity','face_contact'})
        self.assertEqual({m['role']['role'] for m in data['members']},{'fixed_base','moving_platform','transmission_related'})
        self.assertTrue(all(p['review_state']=='pending' for p in data['pairs']))
        self.assertFalse(data['mechanical_relation_confirmed']);self.assertGreater(len(data['input_files']),10)
        for b in data['input_files']:self.assertEqual(hashlib.sha256(Path(b['path']).read_bytes()).hexdigest(),b['sha256'])

    def test_unknown_pairs_and_optional_sources_retained(self):
        result=self.build(evidence_paths=[],grouping_path=None)
        self.assertEqual(result['status'],'error') # Schema omits optional fields, never null.
        args={k:v for k,v in self.args.items() if k not in ('grouping_path','evidence_paths')}
        result=self.service.call('cad_build_chain_evidence',args);self.assertEqual(result['status'],'partial',result)
        data=self.read('outputs/chain.json');self.assertEqual(data['coverage']['unknown_pairs'],3)
        self.assertTrue(all(p['evidence_status']=='unknown' for p in data['pairs']))
        self.assertTrue(all(m['role']['role']=='pending' for m in data['members']))

    def test_face_only_does_not_fill_unmeasured_pairs(self):
        result=self.build(evidence_paths=['outputs/face-review.json']);self.assertEqual(result['status'],'partial',result)
        data=self.read('outputs/chain.json');self.assertEqual(data['coverage']['unknown_pairs'],2)
        self.assertEqual(sum(len(p['evidence']) for p in data['pairs']),1)

    def test_scope_keeps_boundary_links_and_skipped_counts(self):
        result=self.build(occurrence_paths=['base-1','carriage-1']);self.assertEqual(result['status'],'ok',result)
        data=self.read('outputs/chain.json');self.assertEqual(len(data['pairs']),1);self.assertEqual(len(data['boundary_evidence']),4)
        self.assertTrue(all('rail-1' in b['occurrence_paths'] for b in data['boundary_evidence']))

    def test_duplicate_unknown_and_container_scope_rejected(self):
        for paths in (['base-1','base-1'],['base-1','missing'],['base-1']):self.assertEqual(self.build(occurrence_paths=paths)['status'],'error')
        source=self.read('inventory.json');source['data']['components'][1]['parent_occurrence_path']='base-1'
        self.save('container.json',source)
        self.assertEqual(self.build(inventory_path='container.json',evidence_paths=[])['status'],'error')
        self.assertFalse((self.root/'outputs/chain.json').exists())

    def test_duplicate_content_and_source_path_rejected(self):
        self.save('copy.json',self.read('outputs/face-review.json'))
        # Byte-identical copy, not merely semantically equal JSON.
        (self.root/'copy.json').write_bytes((self.root/'outputs/face-review.json').read_bytes())
        result=self.build(evidence_paths=['outputs/face-review.json','copy.json'])
        self.assertEqual(result['errors'][0]['code'],'DUPLICATE_CHAIN_SOURCE')

    def test_tampered_relations_and_review_derivations_rejected(self):
        for file,mutate in [
            ('outputs/relations.json',lambda d:d['candidates'][0].update(kind='parallel_candidate')),
            ('outputs/connections.json',lambda d:d['pairs'][0].update(review_state='geometry_only')),
            ('outputs/proximity-review.json',lambda d:d['pairs'][0].update(review_state='unmeasured')),
            ('outputs/face-review.json',lambda d:d['pairs'][0]['metrics'].update(gap_mm=0))]:
            original=(self.root/file).read_bytes();data=self.read(file);mutate(data);self.save(file,data)
            result=self.build();self.assertEqual(result['status'],'error',(file,result))
            self.assertFalse((self.root/'outputs/chain.json').exists());(self.root/file).write_bytes(original)

    def test_transitive_source_edit_is_rejected(self):
        data=self.read('cylinder0.json');data['data']['captured_at_utc']='changed';self.save('cylinder0.json',data)
        result=self.build();self.assertEqual(result['errors'][0]['code'],'EVIDENCE_MISMATCH')

    def test_grouping_edit_and_manual_review_bound(self):
        original=(self.root/'outputs/groups.json').read_bytes()
        data=self.read('outputs/groups.json');data['groups'][0]['members'][0]['role_status']='manual_confirmed';self.save('outputs/groups.json',data)
        self.assertEqual(self.build()['errors'][0]['code'],'EVIDENCE_MISMATCH')
        (self.root/'outputs/groups.json').write_bytes(original)
        digest=hashlib.sha256((self.root/'inventory.json').read_bytes()).hexdigest()
        self.save('role-review.json',{'inventory_sha256':digest,'assignments':[{'occurrence_path':'base-1','role':'fixed_base','decision':'confirmed','reason':'Fixture manual role'}]})
        result=self.service.call('cad_group_components',{'inventory_path':'inventory.json','review_path':'role-review.json','output_path':'outputs/manual-groups.json'})
        self.assertEqual(result['status'],'ok')
        result=self.build(grouping_path='outputs/manual-groups.json',evidence_paths=[]);self.assertEqual(result['status'],'partial',result)
        member=next(m for m in self.read('outputs/chain.json')['members'] if m['occurrence_path']=='base-1')
        self.assertEqual(member['role']['role_status'],'manual_confirmed')

    def test_legacy_manual_group_requires_exact_review_file(self):
        digest=hashlib.sha256((self.root/'inventory.json').read_bytes()).hexdigest()
        self.save('role-review.json',{'inventory_sha256':digest,'assignments':[]})
        self.service.call('cad_group_components',{'inventory_path':'inventory.json','review_path':'role-review.json','output_path':'outputs/legacy.json'})
        data=self.read('outputs/legacy.json');data.pop('review_path');self.save('outputs/legacy.json',data)
        self.assertEqual(self.build(grouping_path='outputs/legacy.json',evidence_paths=[])['errors'][0]['code'],'GROUPING_REVIEW_SOURCE_REQUIRED')
        self.assertEqual(self.build(grouping_path='outputs/legacy.json',grouping_review_path='role-review.json',evidence_paths=[])['status'],'partial')

    def test_source_partial_and_unmatched_mates_remain_visible(self):
        mates=self.read('mates.json');mates['status']='partial';mates['data']['complete']=False;mates['errors']=[{'code':'FIXTURE_PARTIAL','message':'Synthetic partial source'}]
        self.save('partial-mates.json',mates)
        result=self.service.call('cad_review_connections',{'relations_path':'outputs/relations.json','mate_inventory_path':'partial-mates.json','output_path':'outputs/partial-connections.json'})
        self.assertEqual(result['status'],'partial')
        result=self.build(evidence_paths=['outputs/partial-connections.json']);self.assertEqual(result['status'],'partial',result)
        data=self.read('outputs/chain.json');self.assertIn('unmatched_mates',data['sources'][0]['coverage'])
        self.assertTrue(data['sources'][0]['errors'])

    def test_distance_scope_disagreement_flag_preserves_both_sources(self):
        distance=self.read('distance0.json');m=distance['data']['measurement'];m['distance_m']=.0002;m['distance_mm']=.2;m['point_right_m']=[.0002,0,0];m['point_right_mm']=[.2,0,0];m['point_separation_m']=.0002
        self.save('alternate-distance.json',distance)
        result=self.service.call('cad_review_proximity',{'proximity_path':'outputs/proximity.json','distance_paths':['alternate-distance.json','distance1.json','distance2.json'],'output_path':'outputs/alternate-proximity.json','contact_tolerance_mm':.1})
        self.assertEqual(result['status'],'ok',result)
        self.assertEqual(self.build(evidence_paths=self.args['evidence_paths']+['outputs/alternate-proximity.json'])['status'],'ok')
        data=self.read('outputs/chain.json');p=data['pairs'][0];codes={f['code'] for f in p['review_flags']}
        self.assertIn('DISTANCE_CLASSIFICATION_DISAGREEMENT',codes);self.assertIn('GEOMETRY_SCOPE_REQUIRES_REVIEW',codes)
        self.assertEqual(p['evidence_status'],'needs_reconciliation');self.assertEqual(len(p['evidence']),4)
        review=self.decision();self.assertEqual(self.apply(review)['errors'][0]['code'],'UNACKNOWLEDGED_CHAIN_FLAGS')
        review['decisions'][0]['acknowledged_flags']=sorted(codes)
        result=self.apply(review);self.assertEqual(result['status'],'ok',result)
        self.assertFalse(self.read('outputs/reviewed.json')['pairs'][0]['human_review']['cad_verified'])

    def test_human_declarations_are_separate_and_unspecified_stays_pending(self):
        self.assertEqual(self.build()['status'],'ok')
        review=self.decision();review['chain_sha256']=review['chain_sha256'].upper() # PowerShell Get-FileHash uses uppercase hex.
        result=self.apply(review);self.assertEqual(result['status'],'ok',result)
        data=self.read('outputs/reviewed.json');self.assertEqual(data['review_counts'],{'confirmed':1,'rejected':0,'pending':2,'conflict':0})
        self.assertTrue(data['pairs'][0]['human_review']['human_confirmed']);self.assertFalse(data['pairs'][0]['mechanical_relation_confirmed'])
        self.assertFalse(data['human_review_complete']);self.assertTrue(data['requires_review'])
        self.assertTrue(all(p['review_state']=='pending' for p in self.read('outputs/chain.json')['pairs']))

    def test_reject_pending_conflict_and_complete_review_counts(self):
        self.build();review=self.decision();pairs=self.read('outputs/chain.json')['pairs']
        for decision in ('rejected','pending','conflict'):
            review['decisions']=[{'pair_id':p['pair_id'],'decision':decision,'relation_type':None,'reason':'Fixture declaration','evidence_ids':[]} for p in pairs]
            result=self.apply(review,output_path=f'outputs/{decision}.json');self.assertEqual(result['status'],'ok',result)
            self.assertEqual(result['data']['review_counts'][decision],3)
            self.assertEqual(result['data']['human_review_complete'],decision=='rejected')

    def test_stale_dossier_hash_no_carryover(self):
        self.build();review=self.decision();review['chain_sha256']='0'*64
        self.assertEqual(self.apply(review)['errors'][0]['code'],'INVALID_CHAIN_REVIEW')
        self.assertFalse((self.root/'outputs/reviewed.json').exists())

    def test_tampered_dossier_and_source_replay_on_review(self):
        self.build();data=self.read('outputs/chain.json');data['pairs'][0]['evidence']=[];self.save('outputs/chain.json',data)
        self.assertEqual(self.apply(self.decision())['errors'][0]['code'],'EVIDENCE_MISMATCH')

    def test_invalid_human_attribution_relation_and_evidence_ids(self):
        self.build();original=self.decision()
        for mutate in (lambda r:r.update(reviewer=''),lambda r:r.update(reviewed_at='2026-11-12'),lambda r:r.update(reviewed_at='bad'),
                       lambda r:r['decisions'][0].update(reason=''),lambda r:r['decisions'][0].update(pair_id='missing'),
                       lambda r:r['decisions'][0].update(pair_id=[]),
                       lambda r:r['decisions'][0].update(evidence_ids=['other-pair-evidence']),lambda r:r['decisions'][0].update(relation_type=None),
                       lambda r:r['decisions'].append(r['decisions'][0])):
            review=copy.deepcopy(original);mutate(review);result=self.apply(review)
            self.assertEqual(result['status'],'error',result);self.assertEqual(result['errors'][0]['code'],'INVALID_CHAIN_REVIEW',result)
            self.assertFalse((self.root/'outputs/reviewed.json').exists())

    def test_review_does_not_clear_source_partial(self):
        self.build(evidence_paths=[])
        review=self.decision();review['decisions']=[{**review['decisions'][0],'pair_id':p['pair_id'],'evidence_ids':[]} for p in self.read('outputs/chain.json')['pairs']]
        result=self.apply(review);self.assertEqual(result['status'],'partial',result)
        self.assertTrue(result['data']['human_review_complete']);self.assertFalse(result['data']['complete'])
        self.assertFalse(result['data']['mechanical_relation_confirmed'])

    def test_root_mates_without_axis_candidates_are_not_dropped(self):
        # A valid replay with no geometric candidates: replace both source cylinder lists by empty captures.
        files=[]
        for i in range(3):
            raw=self.read(f'cylinder{i}.json');raw['data']['cylinders']=[];raw['data']['cylinder_count']=0
            files.append(self.save(f'empty-cylinder{i}.json',raw))
        result=self.service.call('cad_component_relations',{'inventory_path':'inventory.json','cylinder_paths':files,
            'output_path':'outputs/empty-relations.json','distance_tolerance_mm':.1,'angle_tolerance_deg':.1})
        self.assertEqual(result['status'],'ok',result)
        result=self.service.call('cad_review_connections',{'relations_path':'outputs/empty-relations.json','mate_inventory_path':'mates.json','output_path':'outputs/mates-only.json'})
        self.assertEqual(result['status'],'ok',result);self.assertEqual(self.read('outputs/mates-only.json')['pairs'],[])
        result=self.build(evidence_paths=['outputs/mates-only.json']);self.assertEqual(result['status'],'partial',result)
        data=self.read('outputs/chain.json');self.assertEqual(data['coverage']['pairs_with_observations'],2)
        pair=data['pairs'][0];record=pair['evidence'][0]['record']
        self.assertEqual(record['geometric_candidate_indices'],[]);self.assertTrue(record['mate_evidence'])

    def test_face_inventory_pose_must_match_chain_spatial_source(self):
        inventory=self.read('inventory.json');node=inventory['data']['components'][0]
        node['transform']['raw_array'][9]+=1
        self.save('moved-inventory.json',inventory)
        result=self.build(inventory_path='moved-inventory.json',evidence_paths=['outputs/face-review.json'],grouping_path=None)
        self.assertEqual(result['status'],'error')
        args={**self.args,'inventory_path':'moved-inventory.json','evidence_paths':['outputs/face-review.json']};args.pop('grouping_path')
        result=self.service.call('cad_build_chain_evidence',args)
        self.assertEqual(result['errors'][0]['code'],'EVIDENCE_MISMATCH')

    def test_unmeasured_distance_records_remain_unknown(self):
        result=self.service.call('cad_review_proximity',{'proximity_path':'outputs/proximity.json','distance_paths':['distance0.json'],
            'output_path':'outputs/one-distance.json','contact_tolerance_mm':.1})
        self.assertEqual(result['status'],'partial')
        result=self.build(evidence_paths=['outputs/one-distance.json']);self.assertEqual(result['status'],'partial')
        data=self.read('outputs/chain.json');self.assertEqual(data['coverage']['unknown_pairs'],2)
        unknown=[p for p in data['pairs'] if p['evidence_status']=='unknown']
        self.assertTrue(all(p['evidence'][0]['record']['review_state']=='unmeasured' for p in unknown))

    def test_file_protection_and_cli_roundtrip(self):
        result=self.build();self.assertEqual(result['status'],'ok')
        self.assertEqual(self.build()['errors'][0]['code'],'OUTPUT_EXISTS')
        self.assertEqual(self.build(output_path='../outside.json')['errors'][0]['code'],'INVALID_PATH')
        self.save('review.json',self.decision())
        run=subprocess.run([sys.executable,'-m','cadkin','review-chain','outputs/chain.json','review.json','--output','outputs/cli-reviewed.json'],cwd=self.root,text=True,capture_output=True)
        self.assertEqual(run.returncode,0,run.stderr+run.stdout)
        run=subprocess.run([sys.executable,'-m','cadkin','chain-evidence','inventory.json','--occurrences','base-1','carriage-1','--name','CLI chain','--output','outputs/cli-chain.json'],cwd=self.root,text=True,capture_output=True)
        self.assertEqual(run.returncode,0,run.stderr+run.stdout);self.assertEqual(self.read('outputs/cli-chain.json')['coverage']['unknown_pairs'],1)
