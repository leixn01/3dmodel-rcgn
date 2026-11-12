"""Explicit synthetic observations for matcher controls; never real SolidWorks measurements."""
import itertools


def toy_target():
    names=['a','b','c']
    pairs=[]
    for a,b in itertools.combinations(names,2):
        axis=[1,0,0] if (a,b)==('a','b') else [0,0,1] if (a,b)==('b','c') else None
        pairs.append({'id':a+b,'node_ids':[a,b],'link_support':1. if axis else 0.,'representative_axis_unit':axis,
                      'signals':[],'axis_relations':[],'flags':[]})
    return {'nodes':[{'id':n,'eligible':True} for n in names],'pairs':pairs,'coverage':{'nodes':3},'errors':[],'complete':True,'boundary_evidence':[]}


def toy_reference(parallel=False,kind='prismatic',name='reference'):
    ids=['r0','r1','r2'];joints=[]
    for index,(a,b,axis) in enumerate([('r0','r1',[1,0,0]),('r0','r2',[1,0,0] if parallel else [0,0,1])]):
        joints.append({'id':'j'+str(index),'kind':kind,'enabled':True,
                       'endpoints':[{'body_id':n,'frame_kind':'body','axis_world':axis} for n in (a,b)]})
    return ({'id':name,'sha256':'a'*64}, {'bodies':[{'id':n,'enabled':True} for n in ids],'joints':joints,'risks':[]})


def blinded_reference_window(entry,graph):
    """Hide labels/IDs in a reference-derived observation control; connectivity/axes are GIVEN.

    This is not independent recognition ground truth or geometry extracted from target CAD.
    """
    from cadkin.matching.search import reference_patterns
    patterns,_,_=reference_patterns([(entry,graph)],3)
    if not patterns:return None
    pattern=patterns[0];ids=pattern['body_ids'];rename={n:f'item-{i}' for i,n in enumerate(ids)}
    pairs=[]
    for a,b in itertools.combinations(ids,2):
        js=[j for j in pattern['joints'] if set(j['node_ids'])=={a,b}]
        axes=[j['axis_unit'] for j in js if j['axis_unit'] is not None]
        pairs.append({'id':rename[a]+'-'+rename[b],'node_ids':sorted([rename[a],rename[b]]),
                      'link_support':1. if js else 0.,'representative_axis_unit':axes[0] if len(axes)==1 else None,
                      'signals':[],'axis_relations':[],'flags':[]})
    return {'nodes':[{'id':n,'eligible':True} for n in rename.values()],'pairs':pairs,'coverage':{'nodes':3},
            'errors':[],'complete':True,'boundary_evidence':[],
            'control_scope':'Source-derived observed connectivity and axes are given; joint types/names/IDs hidden. Not CAD recognition accuracy.'}
