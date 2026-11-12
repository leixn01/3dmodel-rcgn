"""Four-occurrence synthetic grouping controls; no real CAD observations."""
import itertools
from tests.matching_fakes import toy_target


def mate_signal(kind='lock', active=True):
    return {'kind': 'active_mate' if active else 'inactive_or_unknown_mate',
            'mate_type': kind, 'record_errors': [], 'source': {'evidence_id': 'synthetic-lock'}}


def axis_relation(left='a', right='b', direction=None, origin=None, kind='coaxial_candidate'):
    return {'kind': kind, 'source': {'path': 'synthetic.json', 'sha256': 'a'*64}, 'candidate_index': 0,
            'left': {'node_id': left, 'axis_unit': direction or [1,0,0], 'origin_m': origin or [0,0,0]},
            'right': {'node_id': right, 'axis_unit': direction or [1,0,0], 'origin_m': origin or [0,0,0]}}


def rigid_target():
    t = toy_target()
    t.update(document={'title': 'Synthetic only'}, chain_name='Synthetic rigid control',
             units={'length': 'm', 'angle': 'degree', 'frame': 'root_assembly'})
    t['nodes'].append({'id':'d', 'eligible': True})
    for a in ('a','b','c'):
        t['pairs'].append({'id':a+'d','node_ids':[a,'d'],'link_support':1. if a=='a' else 0.,
                          'representative_axis_unit':None, 'signals':[mate_signal()] if a=='a' else [],
                          'axis_relations':[], 'flags':[]})
    for p in t['pairs']:
        if p['representative_axis_unit']:
            p['axis_relations']=[axis_relation(*p['node_ids'],direction=p['representative_axis_unit'])]
    return t
