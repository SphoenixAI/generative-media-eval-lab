"""TEST-ONLY prerequisite contracts; retained corruption never passes through models."""
from copy import deepcopy
from collections import Counter
import json
import pytest
from eval_lab import lint_evidence as le, lint_prerequisites as lp
from eval_lab import lint_temporal_prerequisites as lt
from test_lint_prerequisites import adapter, row, ref, pin, exact_error

# Independent inventory: declarations, including presence, collection members and edge types.
EXPECTED = {
    'Evidence': 'media=ref:MediaAsset coverage=coverage timestamp_start=?seconds timestamp_end=?seconds sampling_manifest=sequence sampling_manifest.*=seconds',
    'MediaAsset': 'type=media_type duration=positive checksum=digest',
    'MediaIngestion': 'media=ref:MediaAsset source_sha256=digest metadata=mapping metadata.duration_seconds=positive metadata.frames=nonempty metadata.frames.*=mapping metadata.frames.*.index=index metadata.frames.*.seconds=seconds metadata.frames.*.pts=integer',
    'DerivativeManifest': 'media=ref:MediaAsset ingestion=ref:MediaIngestion source_sha256=digest frames=nonempty frames.*=mapping frames.*.frame_index=index frames.*.requested_seconds=seconds frames.*.actual_seconds=seconds frames.*.pts=integer',
    'PilotClip': 'media=ref:MediaAsset ingestion=ref:MediaIngestion',
    'PilotSubmission': 'frame_indices=sequence frame_indices.*=index artifact=ref:Evidence clip=ref:PilotClip derivative=?ref:DerivativeManifest',
    'TechnicalObservation': 'media=pin:MediaAsset dimension=dimension span=sequence span.*=seconds evidence=sequence evidence.*=pin:Evidence',
    'Hypothesis': 'supporting_evidence=sequence supporting_evidence.*=ref:Evidence',
    'HypothesisContext': 'hypothesis=pin:Hypothesis observation=pin:TechnicalObservation',
    'RelationClaim': 'predicate=predicate subject=refkind object=refkind',
    'RelationClaimV2': 'predicate=predicate subject=refkind object=refkind intent=pin:intent epistemic_purpose=epistemic operational_purpose=operational',
    'TestPlan': 'arms=nonempty arms.*=mapping arms.*.id=text arms.*.generation_plan_ref=?pin:GenerationPlan sample_design=?mapping sample_design.decision_rule=text sample_design.n_per_arm=?count sample_design.stopping_rule=?text',
}
ENUMERATIONS = ('MediaIngestion', 'PilotSubmission', 'HypothesisContext')
ALIASES = {'m': ('MediaAsset', 3), 'i': ('MediaIngestion', 5), 'e': ('Evidence', 7),
           'd': ('DerivativeManifest', 11), 'c': ('PilotClip', 13), 's': ('PilotSubmission', 17),
           'o': ('TechnicalObservation', 19), 'h': ('Hypothesis', 23), 'x': ('HypothesisContext', 29),
           'r': ('RelationClaimV2', 31), 't': ('TestPlan', 37), 'g': ('GenerationPlan', 41), 'v': ('IntentSpecV2', 43), 'l': ('RelationClaim', 83)}

def reference(alias):
    kind, revision = ALIASES[alias]
    return ref(kind, 'TEST-ONLY-' + alias, revision)

def fixture():
    R = reference
    return {
        'm': dict(type='video', duration=3.5, checksum='a'*64),
        'i': dict(media=R('m'), source_sha256='a'*64, metadata=dict(duration_seconds=3.5, frames=[
            dict(index=0, seconds=0, pts=101), dict(index=1, seconds=1.25, pts=211), dict(index=2, seconds=2.75, pts=337)])),
        'e': dict(media=R('m'), coverage='interval', timestamp_start=0, timestamp_end=3.5, sampling_manifest=[]),
        'd': dict(media=R('m'), ingestion=R('i'), source_sha256='a'*64, frames=[
            dict(frame_index=2, requested_seconds=2.5, actual_seconds=2.75, pts=337),
            dict(frame_index=0, requested_seconds=0, actual_seconds=0, pts=101),
            dict(frame_index=2, requested_seconds=2.6, actual_seconds=2.75, pts=337)]),
        'c': dict(media=R('m'), ingestion=R('i')),
        's': dict(artifact=R('e'), clip=R('c'), derivative=R('d'), frame_indices=[0, 2]),
        'o': dict(media={'PIN':'m'}, dimension='motion_plausibility', span=[0, 3.5], evidence=[{'PIN':'e'}]),
        'h': dict(supporting_evidence=[R('e')]),
        'x': dict(hypothesis={'PIN':'h'}, observation={'PIN':'o'}),
        'v': {}, 'g': {},
        'r': dict(predicate='supports', subject=R('e'), object=R('h'), intent={'PIN':'v'}, epistemic_purpose='EXPLAIN', operational_purpose='INVESTIGATE'),
        't': dict(frozen_at=None, frozen_digest=None, arms=[dict(id='TEST-ONLY-arm-A', generation_plan_ref={'PIN':'g'}),
            dict(id='TEST-ONLY-arm-B', generation_plan_ref=None)], sample_design=dict(n_per_arm=4, stopping_rule=None, decision_rule='TEST-ONLY compare')),
    }

def records(data):
    cache = {}
    def convert(value):
        if type(value) is dict:
            if set(value) == {'PIN'}: return pin(make(value['PIN']))
            return {k: convert(v) for k, v in value.items()}
        if type(value) is list: return [convert(v) for v in value]
        return value
    def make(alias):
        if alias not in cache: cache[alias] = row(reference(alias), **convert(data[alias]))
        return cache[alias]
    return [make(alias) for alias in data]

def run(adapter, data=None, root='s'):
    rows = records(fixture() if data is None else data)
    inventory = {k: [{p: r[p] for p in ('kind', 'id', 'revision')} for r in rows if r['kind'] == k] for k in ENUMERATIONS}
    return lt.prepare(adapter(rows, inventory), reference(root))

def change(data, alias, path, value):
    node = data[alias]
    for part in path[:-1]: node = node[part]
    if value is le._MISSING: del node[path[-1]]
    else: node[path[-1]] = value

def rejected(result, alias, path, state, reason):
    kind, revision = ALIASES[alias]
    expected = le.EvidenceResult(state, f'{kind}:TEST-ONLY-{alias}@{revision}', path, reason)
    assert expected in result.diagnostics, ('intended diagnostic', expected, result.diagnostics)
    exact_error(result.support, ValueError, 'unavailable prerequisite')

# Each semantic row is an isolated guard and also its guard-deletion witness.
CASES = [
    ('duration correspondence', 'i', ('metadata','duration_seconds'), 4.5, 's'),
    ('source correspondence', 'i', ('source_sha256',), 'b'*64, 's'),
    ('timeline starts at zero', 'i', ('metadata','frames',0,'seconds'), .25, 's'),
    ('contiguous decoded indices', 'i', ('metadata','frames',1,'index'), 4, 's'),
    ('increasing decoded times', 'i', ('metadata','frames',1,'seconds'), 0, 's'),
    ('last frame below duration', 'i', ('metadata','frames',2,'seconds'), 3.5, 's'),
    ('paired timestamps', 'e', ('timestamp_start',), None, 'e'),
    ('ordered timestamps', 'e', ('timestamp_start',), 3.75, 'e'),
    ('sampled coverage requires samples', 'e', ('coverage',), 'sampled_frames', 'e'),
    ('unique selected indices', 's', ('frame_indices',), [0,0], 's'),
    ('selected index in manifest', 's', ('frame_indices',), [1], 's'),
    ('derivative media correspondence', 'd', ('media',), ref('MediaAsset','TEST-ONLY-other',47), 's'),
    ('derivative ingestion correspondence', 'd', ('ingestion',), ref('MediaIngestion','TEST-ONLY-other',53), 's'),
    ('derivative source correspondence', 'd', ('source_sha256',), 'c'*64, 's'),
    ('decoded index in timeline', 'd', ('frames',0,'frame_index'), 4, 's'),
    ('decoded PTS correspondence', 'd', ('frames',0,'pts'), 338, 's'),
    ('decoded time correspondence', 'd', ('frames',0,'actual_seconds'), 2.8, 's'),
    ('request precedes actual', 'd', ('frames',0,'requested_seconds'), 2.9, 's'),
    ('selected frame within interval', 'e', ('timestamp_end',), 2.6, 's'),
    ('two element span', 'o', ('span',), [0,1,2], 'o'),
    ('ordered span', 'o', ('span',), [2,1], 'o'),
    ('unique arm IDs', 't', ('arms',1,'id'), 'TEST-ONLY-arm-A', 't'),
    ('exclusive sample count or stopping rule', 't', ('sample_design','stopping_rule'), 'TEST-ONLY stop', 't'),
]
# Guard diagnostic locations are literals, independent of implementation paths.
LOCATIONS = {
    'duration correspondence': ('i', ('metadata','duration_seconds')), 'source correspondence': ('i', ('source_sha256',)),
    'timeline starts at zero': ('i', ('metadata','frames',0,'seconds')), 'contiguous decoded indices': ('i', ('metadata','frames',1,'index')),
    'increasing decoded times': ('i', ('metadata','frames',1,'seconds')), 'last frame below duration': ('i', ('metadata','frames',2,'seconds')),
    'paired timestamps': ('e', ('timestamp_start',)), 'ordered timestamps': ('e', ('timestamp_end',)),
    'sampled coverage requires samples': ('e', ('sampling_manifest',)), 'unique selected indices': ('s', ('frame_indices',)),
    'selected index in manifest': ('s', ('frame_indices',)), 'derivative media correspondence': ('d', ('media',)),
    'derivative ingestion correspondence': ('d', ('ingestion',)), 'derivative source correspondence': ('d', ('source_sha256',)),
    'decoded index in timeline': ('d', ('frames',0,'frame_index')), 'decoded PTS correspondence': ('d', ('frames',0,'pts')),
    'decoded time correspondence': ('d', ('frames',0,'actual_seconds')), 'request precedes actual': ('d', ('frames',0,'requested_seconds')),
    'selected frame within interval': ('s', ('frame_indices',)), 'two element span': ('o', ('span',)), 'ordered span': ('o', ('span',)),
    'unique arm IDs': ('t', ('arms',)), 'exclusive sample count or stopping rule': ('t', ('sample_design',)),
}

def semantic(adapter, case):
    reason, alias, path, value, root = case
    assert run(adapter, root=root).diagnostics == ()
    data = fixture(); change(data, alias, path, value)
    # Distinct exact targets exist with valid raw integrity, isolating correspondence.
    rows = records(data)
    if reason == 'derivative media correspondence': rows.append(row(value, **fixture()['m']))
    if reason == 'derivative ingestion correspondence': rows.append(row(value, **fixture()['i']))
    inventory = {k: [pin(r)['ref'] for r in rows if r['kind'] == k] for k in ENUMERATIONS}
    result = lt.prepare(adapter(rows, inventory), reference(root))
    subject, location = LOCATIONS[reason]
    rejected(result, subject, location, 'UNKNOWN' if reason=='paired timestamps' else 'INTEGRITY_FAILURE', reason)

@pytest.mark.parametrize('case', CASES, ids=[c[0] for c in CASES])
def test_semantic_guard(adapter, case): semantic(adapter, case)

def test_inventory_exact():
    assert lt.SPECS == EXPECTED
    assert lt.ENUMERATIONS == ENUMERATIONS

# Field matrix independent of production declarations. Optional fields are active here.
FIELDS = [
    ('m','type','video',42,'s'), ('m','duration',3.5,'3.5','s'), ('m','checksum','a'*64,False,'s'),
    ('i','media',reference('m'),[],'s'), ('i','source_sha256','a'*64,3,'s'), ('i','metadata',fixture()['i']['metadata'],[],'s'),
    ('i','metadata.duration_seconds',3.5,True,'s'), ('i','metadata.frames',fixture()['i']['metadata']['frames'],{},'s'),
    ('i','metadata.frames.0',fixture()['i']['metadata']['frames'][0],[],'s'), ('i','metadata.frames.0.index',0,False,'s'),
    ('i','metadata.frames.0.seconds',0,'0','s'), ('i','metadata.frames.0.pts',101,1.1,'s'),
    ('e','media',reference('m'),[],'e'), ('e','coverage','interval',8,'e'), ('e','timestamp_start',0,False,'e'),
    ('e','timestamp_end',3.5,'3.5','e'), ('e','sampling_manifest',[],{},'e'), ('e','sampling_manifest.0',.5,False,'e'),
    ('s','frame_indices',[0,2],{},'s'), ('s','frame_indices.0',0,True,'s'), ('s','artifact',reference('e'),[], 's'),
    ('s','clip',reference('c'),[], 's'), ('s','derivative',reference('d'),[], 's'),
    ('c','media',reference('m'),[],'s'), ('c','ingestion',reference('i'),[],'s'),
    ('d','media',reference('m'),[],'s'), ('d','ingestion',reference('i'),[],'s'), ('d','source_sha256','a'*64,9,'s'),
    ('d','frames',fixture()['d']['frames'],{},'s'), ('d','frames.0',fixture()['d']['frames'][0],[],'s'),
    ('d','frames.0.frame_index',2,'2','s'), ('d','frames.0.requested_seconds',2.5,True,'s'),
    ('d','frames.0.actual_seconds',2.75,'2.75','s'), ('d','frames.0.pts',337,False,'s'),
    ('o','dimension','motion_plausibility',7,'o'), ('o','media',{'PIN':'m'},[],'o'), ('o','span',[0,3.5],{},'o'),
    ('o','span.0',0,False,'o'), ('o','evidence',[{'PIN':'e'}],{},'o'), ('o','evidence.0',{'PIN':'e'},[], 'o'),
    ('h','supporting_evidence',[reference('e')],{},'h'), ('h','supporting_evidence.0',reference('e'),[], 'h'),
    ('x','hypothesis',{'PIN':'h'},[],'h'), ('x','observation',{'PIN':'o'},[],'h'),
    ('r','predicate','supports',4,'r'), ('r','subject',reference('e'),[], 'r'), ('r','object',reference('h'),[], 'r'),
    ('r','intent',{'PIN':'v'},[], 'r'), ('r','epistemic_purpose','EXPLAIN',4,'r'), ('r','operational_purpose','INVESTIGATE',False,'r'),
    ('t','arms',fixture()['t']['arms'],{},'t'), ('t','arms.0',fixture()['t']['arms'][0],[],'t'),
    ('t','arms.0.id','TEST-ONLY-arm-A',4,'t'), ('t','arms.0.generation_plan_ref',{'PIN':'g'},[],'t'),
    ('t','sample_design',fixture()['t']['sample_design'],[],'t'), ('t','sample_design.decision_rule','TEST-ONLY compare',4,'t'),
    ('t','sample_design.n_per_arm',4,True,'t'), ('t','sample_design.stopping_rule','TEST-ONLY stop',6,'t'),
]

def parts(text): return tuple(int(p) if p.isdigit() else p for p in text.split('.'))

@pytest.mark.parametrize('entry', FIELDS, ids=[x[0]+'.'+x[1] for x in FIELDS])
@pytest.mark.parametrize('variant', ['missing','null','malformed','valid'])
def test_declared_field_contract(adapter, entry, variant):
    alias, text, valid, bad, root = entry; path = parts(text); data = fixture()
    if text == 'sampling_manifest.0': data['e']['sampling_manifest'] = [.5]
    if text == 'sample_design.stopping_rule': data['t']['sample_design']['n_per_arm'] = None
    change(data, alias, path, valid)
    if variant == 'missing' and type(path[-1]) is int:
        parent=data[alias]
        for part in path[:-1]: parent=parent[part]
        del parent[path[-1]:]  # Arrays cannot contain holes; query the now-unavailable exact element.
        record=adapter(records(data),{}).read(reference(alias))
        assert record.field(path,le.MAPPING)==le.EvidenceResult('UNKNOWN',record.subject,path,'missing required field')
        return
    change(data, alias, path, le._MISSING if variant == 'missing' else None if variant == 'null' else bad if variant == 'malformed' else valid)
    result = run(adapter, data, root)
    if variant == 'valid': assert result.diagnostics == (); result.support()
    elif variant == 'null' and text in ('timestamp_start','timestamp_end'):
        rejected(result, 'e', ('timestamp_start',), 'UNKNOWN', 'paired timestamps')
    elif variant == 'null' and text in ('arms.0.generation_plan_ref','sample_design.n_per_arm','sample_design.stopping_rule'):
        if text == 'arms.0.generation_plan_ref': assert result.diagnostics == ()
        else: rejected(result, 't', ('sample_design',), 'INTEGRITY_FAILURE', 'exclusive sample count or stopping rule')
    else: rejected(result, alias, path, 'INTEGRITY_FAILURE' if variant == 'malformed' else 'UNKNOWN',
                   'wrong type' if variant == 'malformed' else 'missing required field' if variant == 'missing' else 'null required field')

@pytest.mark.parametrize('value', [None, le._MISSING])
def test_frame_attachment_requires_derivative(adapter, value):
    data = fixture(); data['s']['frame_indices'] = [0]; change(data,'s',('derivative',),value)
    rejected(run(adapter,data), 's', ('derivative',), 'UNKNOWN', 'null required field' if value is None else 'missing required field')
    assert run(adapter).diagnostics == ()

@pytest.mark.parametrize('coverage', ['full_clip','sampled_frames'])
@pytest.mark.parametrize('alias,path,value,state,reason', [
    ('o',('dimension',),None,'UNKNOWN','null required field'), ('o',('dimension',),'bogus','INTEGRITY_FAILURE','unsupported value'),
    ('i',('metadata','duration_seconds'),None,'UNKNOWN','null required field'), ('i',('metadata','duration_seconds'),0,'INTEGRITY_FAILURE','below minimum'),
    ('e',('coverage',),'unknown','UNKNOWN','explicitly unavailable'), ('e',('coverage',),'bogus','INTEGRITY_FAILURE','unsupported value')])
def test_motion_and_full_clip_contract(adapter, coverage, alias,path,value,state,reason):
    data=fixture(); data['e'].update(coverage=coverage, timestamp_start=None, timestamp_end=None, sampling_manifest=[.5])
    data['s'].update(frame_indices=[], derivative=None)
    assert run(adapter,data,'o').diagnostics == ()
    change(data,alias,path,value); rejected(run(adapter,data,'o'),alias,path,state,reason)

@pytest.mark.parametrize('branch', ['image','nonmotion','empty-support','no-attachment','present-empty-attachment',
    'stopping','nongeneration','nongeneration-design','outside-end','inclusive-end','legacy'])
def test_valid_branches(adapter, branch):
    data=fixture(); root='o'
    if branch=='image': data['m']['type']='image'; data['m'].pop('duration'); data['s'].update(frame_indices=[],derivative=None)
    if branch=='nonmotion': data['o']['dimension']='composition'
    if branch=='empty-support': data['o']['evidence']=[]; data['h']['supporting_evidence']=[]; root='h'
    if branch=='no-attachment': data['s'].update(frame_indices=[],derivative=None); root='e'
    if branch=='present-empty-attachment': data['s']['frame_indices']=[]; root='s'
    if branch=='outside-end': data['e']['timestamp_end']=4.5; data['o']['span']=[0,4.75]
    if branch=='inclusive-end': root='e'
    if branch in ('stopping','nongeneration','nongeneration-design'):
        root='t'
        if branch=='stopping': data['t']['sample_design'].update(n_per_arm=None,stopping_rule='TEST-ONLY stop')
        else:
            for arm in data['t']['arms']: arm['generation_plan_ref']=None
            if branch=='nongeneration': data['t']['sample_design']=None
    if branch=='legacy':
        rows=records(data); legacy=row(ref('RelationClaim','TEST-ONLY-legacy',59),predicate='supports',subject=reference('e'),object=reference('h'))
        result=lt.prepare(adapter(rows+[legacy],{}),pin(legacy)['ref'])
        assert result.compatibility == ('UNSPECIFIED','UNSPECIFIED')
    else: result=run(adapter,data,root)
    assert result.diagnostics == (); result.support()
    if branch=='outside-end':
        assert 4.5 in [v.value for v in result.support()] and 3.5 in [v.value for v in result.support()]

@pytest.mark.parametrize('predicate,left,right', [('supports','Evidence','Hypothesis'),('contradicts','Evidence','Hypothesis'),
    ('motivated_by','Hypothesis','IntentSpec'),('fulfills','Evidence','IntentSpecV2'),('violates','Evidence','IntentSpecV2'),
    ('alternative_to','Hypothesis','Hypothesis'),('compatible_with','Hypothesis','Hypothesis'),('refines','Hypothesis','Hypothesis')])
@pytest.mark.parametrize('side', ['subject','object'])
def test_relation_vocabulary_contract(adapter,predicate,left,right,side):
    for alias,target in [('r',right),('l','IntentSpec' if right=='IntentSpecV2' else right)]:
        data=fixture(); data[alias]=dict(data['r'] if alias=='r' else {},predicate=predicate,subject=ref(left,'TEST-ONLY-left',61),object=ref(target,'TEST-ONLY-right',67))
        rows=records(data)+[row(ref(left,'TEST-ONLY-left',61)),row(ref(target,'TEST-ONLY-right',67))]
        control=lt.prepare(adapter(rows,{}),reference(alias)); assert control.diagnostics == (); control.support()
        data[alias][side]=reference('m')
        result=lt.prepare(adapter(records(data)+rows[-2:],{}),reference(alias))
        rejected(result,alias,(side,),'INTEGRITY_FAILURE','relation endpoint kind')
        assert len(result.diagnostics)==1

@pytest.mark.parametrize('field,value,reason', [('predicate','bogus','unsupported value'),('epistemic_purpose','UNSPECIFIED','unsupported value'),
    ('operational_purpose','UNSPECIFIED','unsupported value'),('sample_design.n_per_arm',0,'below minimum'),
    ('sample_design.n_per_arm',-1,'below minimum'),('sample_design.stopping_rule',' ','empty value'),
    ('sample_design.decision_rule',' ','empty value'),('frame_indices.0',-1,'below minimum')])
def test_vocabulary_and_numeric_boundaries(adapter,field,value,reason):
    alias='r' if field in ('predicate','epistemic_purpose','operational_purpose') else 't' if field.startswith('sample') else 's'
    data=fixture()
    if field=='sample_design.stopping_rule': data['t']['sample_design']['n_per_arm']=None
    change(data,alias,parts(field),value); rejected(run(adapter,data,alias),alias,parts(field),'INTEGRITY_FAILURE',reason)

@pytest.mark.parametrize('case', ['parent-null','parent-malformed','missing','absent','present','required-null'])
def test_optional_branch_contract(case):
    raw={'slot':None if case in ('absent','required-null') else 8}
    if case=='parent-null': raw=None
    if case=='parent-malformed': raw=[]
    if case=='missing': raw={}
    record=le.RawRecord('TEST-ONLY presence',(),raw)
    result=record.field(('slot',),le.REVISION) if case=='required-null' else record.presence(('slot',))
    expected={'parent-null':('UNKNOWN','null required field',None), 'parent-malformed':('INTEGRITY_FAILURE','wrong type',None),
        'missing':('UNKNOWN','missing required field',None), 'absent':('AVAILABLE','',False),
        'present':('AVAILABLE','',True), 'required-null':('UNKNOWN','null required field',None)}[case]
    assert (result.state,result.reason,result.value)==expected

@pytest.mark.parametrize('kind', ENUMERATIONS)
@pytest.mark.parametrize('variant', ['missing','null','malformed','empty','valid'])
def test_collection_contract(adapter,kind,variant):
    rows=records(fixture()); inv={k:[pin(r)['ref'] for r in rows if r['kind']==k] for k in ENUMERATIONS}
    if variant!='valid':
        if variant=='missing': del inv[kind]
        else: inv[kind]=None if variant=='null' else {} if variant=='malformed' else []
    reader=adapter(rows,inv)
    if not isinstance(reader,lp.DirectRecords):
        original=reader.rows
        if variant!='valid': reader.rows=lambda: le.EvidenceResult('INTEGRITY_FAILURE' if variant=='malformed' else 'UNKNOWN','universe',(), 'TEST-ONLY unavailable enumeration')
    result=lt.prepare(reader,reference('h' if kind=='HypothesisContext' else 'e'))
    if variant=='valid': assert result.diagnostics==()
    else:
        assert result.diagnostics
        exact_error(result.support,ValueError,'unavailable prerequisite')
        if isinstance(reader,lp.DirectRecords):
            state,reason=('INTEGRITY_FAILURE','inventory membership mismatch') if variant=='empty' else ('INTEGRITY_FAILURE','wrong type') if variant=='malformed' else ('UNKNOWN','null required field' if variant=='null' else 'missing required field')
            assert le.EvidenceResult(state,'inventory',(kind,),reason) in result.diagnostics
        else: assert le.EvidenceResult('INTEGRITY_FAILURE' if variant=='malformed' else 'UNKNOWN','universe',(),'TEST-ONLY unavailable enumeration') in result.diagnostics

@pytest.mark.parametrize('case', ['no-context','wrong-context-revision','no-ingestion','support-media','clip-media','evidence-media','interval-required','lower-bound','neither-count'])
def test_context_and_correspondence(adapter,case):
    data=fixture(); root='h'; extras=[]
    if case=='no-context': del data['x']
    if case=='wrong-context-revision':
        old=reference('h')|{'revision':22}; data['x']['hypothesis']={'ref':old,'sha256':row(old,supporting_evidence=[])['sha256']}; extras=[row(old,supporting_evidence=[])]
    if case=='no-ingestion': del data['i']; data.pop('s'); data.pop('d'); data.pop('c'); root='e'
    if case in ('support-media','clip-media','evidence-media'):
        other=ref('MediaAsset','TEST-ONLY-other',71); extras=[row(other,**data['m'])]
        alias='e' if case!='clip-media' else 'c'; data[alias]['media']=other
        root='o' if case=='support-media' else 's'
    if case=='interval-required': data['e'].update(coverage='full_clip',timestamp_start=None,timestamp_end=None); root='s'
    if case=='lower-bound': data['e']['timestamp_start']=.1; root='s'
    if case=='neither-count': data['t']['sample_design']['n_per_arm']=None; root='t'
    rows=records(data)+extras; inv={k:[pin(r)['ref'] for r in rows if r['kind']==k] for k in ENUMERATIONS}
    result=lt.prepare(adapter(rows,inv),reference(root))
    expected={'no-context':('h',('supporting_evidence',),'UNKNOWN','hypothesis context unavailable'),
        'wrong-context-revision':('h',('supporting_evidence',),'UNKNOWN','hypothesis context unavailable'),
        'no-ingestion':('e',('media',),'UNKNOWN','decoded ingestion unavailable'),
        'support-media':('e',('media',),'INTEGRITY_FAILURE','support media correspondence'),
        'clip-media':('i',('media',),'INTEGRITY_FAILURE','ingestion media correspondence'),
        'evidence-media':('e',('media',),'INTEGRITY_FAILURE','attachment media correspondence'),
        'interval-required':('e',('timestamp_start',),'UNKNOWN','null required field'),
        'lower-bound':('s',('frame_indices',),'INTEGRITY_FAILURE','selected frame within interval'),
        'neither-count':('t',('sample_design',),'INTEGRITY_FAILURE','exclusive sample count or stopping rule')}[case]
    rejected(result,*expected)

@pytest.mark.parametrize('broken', [False,True])
def test_preservation_and_subset(adapter,broken):
    data=fixture()
    if broken: data['s']['derivative']=None
    rows=records(data); before=deepcopy(rows); inv={k:[pin(r)['ref'] for r in rows if r['kind']==k] for k in ENUMERATIONS}
    reader=adapter(rows,inv); retained=not isinstance(reader,lp.DirectRecords)
    raw=(reader.root/'pilot.sqlite').read_bytes() if retained else None
    a=lt.prepare(reader,reference('h')); b=lt.prepare(reader,reference('h'))
    c=lt.prepare(adapter(list(reversed(rows)),inv),reference('h'))
    assert a==b==c and rows==before
    if retained: assert (reader.root/'pilot.sqlite').read_bytes()==raw
    assert a.groups==('E3','W1') and not hasattr(a,'ready')
    if broken: exact_error(a.support,ValueError,'unavailable prerequisite')
    else: assert a.support()

@pytest.mark.parametrize('case', CASES, ids=[c[0] for c in CASES])
def test_guard_deletion(adapter,monkeypatch,case):
    original=lt._Preparation.guard
    def removed(self,reason,condition,record,path,state='INTEGRITY_FAILURE'):
        if reason!=case[0]: return original(self,reason,condition,record,path,state)
    monkeypatch.setattr(lt._Preparation,'guard',removed)
    exact_error(lambda: semantic(adapter,case),AssertionError,'intended diagnostic')

# Independent literal multiplicities. Each timeline is accessed again under its own obligation.
def expected_access(root):
    counts=Counter()
    def add(alias, paths, n=1):
        for text in paths.split(): counts[(alias,parts(text.rstrip('?')),'presence' if text.endswith('?') else 'value')]+=n
    def timeline(n):
        add('m','duration checksum',n); add('i','media source_sha256 metadata metadata.duration_seconds metadata.frames',n)
        for i in range(3): add('i',f'metadata.frames.{i} metadata.frames.{i}.index metadata.frames.{i}.seconds metadata.frames.{i}.pts',n)
    def evidence(n):
        add('m','type',n); add('i','media',n); timeline(n)
        add('e','media coverage timestamp_start? timestamp_end? timestamp_start timestamp_end sampling_manifest',n)
    def attachment(n):
        add('s','frame_indices frame_indices.0 frame_indices.1 derivative? derivative artifact clip',n)
        add('c','media ingestion',n); add('m','type',n); timeline(n); evidence(n)
        add('e','media timestamp_start timestamp_end',n); add('i','source_sha256',n)
        add('d','media ingestion source_sha256 frames',n)
        for i in range(3): add('d',f'frames.{i} frames.{i}.frame_index frames.{i}.requested_seconds frames.{i}.actual_seconds frames.{i}.pts',n)
    if root in ('s','e','o','h'):
        attachment(2 if root=='h' else 1)
        if root!='s': evidence(2 if root=='h' else 1); add('s','artifact',2 if root=='h' else 1)
        if root in ('o','h'):
            add('o','dimension media span span.0 span.1 evidence evidence.0'); add('m','type'); add('i','media'); timeline(1)
            add('e','media',2 if root=='h' else 1)
        if root=='h': add('x','hypothesis observation'); add('h','supporting_evidence supporting_evidence.0')
    if root=='r': add('r','predicate intent epistemic_purpose operational_purpose subject object')
    if root=='t':
        add('t','arms arms.0 arms.1 arms.0.id arms.1.id arms.0.generation_plan_ref? arms.1.generation_plan_ref? arms.0.generation_plan_ref sample_design? sample_design sample_design.decision_rule sample_design.n_per_arm? sample_design.stopping_rule? sample_design.n_per_arm')
    return counts

@pytest.mark.parametrize('root',['s','e','o','h','r','t'])
def test_boundary_consumption(adapter,monkeypatch,root):
    observed=Counter(); original=le.RawRecord.field
    def trace(record,path,contract):
        observed[(record.subject,path,contract)]+=1
        return original(record,path,contract)
    monkeypatch.setattr(le.RawRecord,'field',trace)
    result=run(adapter,root=root); assert result.diagnostics==()
    actual=Counter((o[3],o[4],o[2]) for o in result.obligations if o[0]!='@collection')
    expected=Counter(); fields=Counter()
    contracts={'mapping':le.MAPPING,'sequence':le.SEQUENCE,'text':le.TEXT,'digest':le.DIGEST,
        'index':le.Contract((int,),minimum=0),'integer':le.Contract((int,)), 'seconds':le.Contract((int,float),minimum=0),
        'positive':le.Contract((int,float),minimum=0,exclusive=True),'count':le.Contract((int,),minimum=1),
        'nonempty':le.Contract((list,tuple),nonempty=True),'dimension':le.Contract((str,),choices=('prompt_adherence','subject_consistency','semantic_consistency','temporal_consistency','temporal_geometry','motion_plausibility','occlusion_consistency','lighting_continuity','camera_language','composition','artifacting','aesthetic_quality','editability')),
        'media_type':le.Contract((str,),choices=('image','video')),'coverage':le.Contract((str,),choices=('interval','full_clip','sampled_frames','unknown'),unavailable=('unknown',)),
        'predicate':le.Contract((str,),choices=('supports','contradicts','motivated_by','fulfills','violates','alternative_to','compatible_with','refines')),
        'epistemic':le.Contract((str,),choices=('SUPPORT','RULE_OUT','DISCRIMINATE','LOCALIZE','EXPLAIN','QUALIFY','SCOPE','OPERATIONALIZE')),
        'operational':le.Contract((str,),choices=('SHIP','REPAIR','REGENERATE','REVISE_RUBRIC','ADD_GOLD','RETRAIN_SIGNAL','INVESTIGATE'))}
    obligations=Counter()
    for (alias,path,mode),n in expected_access(root).items():
        kind,revision=ALIASES[alias]; subject=f'{kind}:TEST-ONLY-{alias}@{revision}'; expected[(subject,path,mode)]+=n
        template='.'.join('*' if type(p) is int else p for p in path)
        token=dict(x.split('=') for x in EXPECTED[kind].split())[template].lstrip('?')
        contract=le.BOOLEAN if mode=='presence' else le.MAPPING if token.startswith(('ref','pin:')) else contracts[token]
        obligations[(kind,template,mode,subject,path,contract)]+=n
        fields[(subject,path[:-1] if mode=='presence' else path,le.MAPPING if mode=='presence' else contract)]+=n
    assert actual==expected, 'active field multiplicity'
    assert Counter(o for o in result.obligations if o[0]!='@collection')==obligations, 'declaration contract identity'
    assert observed==fields, 'actual shared boundary consumption'
    enumerations={'s':{'MediaIngestion':1},'e':{'MediaIngestion':2,'PilotSubmission':1},
        'o':{'MediaIngestion':3,'PilotSubmission':1},'h':{'MediaIngestion':5,'PilotSubmission':2,'HypothesisContext':1},'r':{},'t':{}}
    assert Counter(o[1] for o in result.obligations if o[0]=='@collection')==enumerations[root], 'enumeration obligations'

@pytest.mark.parametrize('entry',FIELDS,ids=[e[0]+'.'+e[1] for e in FIELDS])
def test_field_consumption_deletion(adapter,monkeypatch,entry):
    original=le.RawRecord.field; alias,text,valid,bad,root=entry; target=f'{ALIASES[alias][0]}:TEST-ONLY-{alias}@{ALIASES[alias][1]}'
    def removed(record,path,contract):
        if record.subject==target and path==parts(text): return le.EvidenceResult('AVAILABLE',target,path,value=valid)
        return original(record,path,contract)
    monkeypatch.setattr(le.RawRecord,'field',removed)
    exact_error(lambda:test_declared_field_contract(adapter,entry,'malformed'),AssertionError,'intended diagnostic')

@pytest.mark.parametrize('entry',[e for e in FIELDS if e[1] in ('media','artifact','clip','derivative','ingestion','evidence.0','supporting_evidence.0','hypothesis','observation','intent','arms.0.generation_plan_ref')],ids=lambda e:e[0]+e[1])
@pytest.mark.parametrize('damage',['missing-target','wrong-kind','bad-pin','revision'])
def test_exact_dependency_contract(adapter,entry,damage):
    alias,text,valid,bad,root=entry; data=fixture(); path=parts(text)
    pinned=type(valid) is dict and 'PIN' in valid
    if damage=='bad-pin' and not pinned:
        record=adapter(records(data),{}).read(valid|{'sha256':'f'*64})
        assert le.EvidenceResult('INTEGRITY_FAILURE','reference',(),'unexpected reference keys') in record.diagnostics
        return  # A digest on a Ref is malformed; it must never silently become a Pin.
    rows=records(data); original=next(r for r in rows if r['id']=='TEST-ONLY-'+alias); raw=json.loads(original['payload'])
    target=raw
    for part in path: target=target[part]
    request=target['ref'] if pinned else target; target_id=request['id']; target_kind=request['kind']; target_revision=request['revision']
    if damage=='bad-pin': target['sha256']='f'*64
    elif damage=='revision': request['revision']=97
    elif damage=='wrong-kind':
        other=next(r for r in rows if r['kind']=='GenerationPlan' and r['id']!=target_id) if target_kind!='GenerationPlan' else next(r for r in rows if r['kind']=='MediaAsset')
        target.clear(); target.update(pin(other) if pinned else pin(other)['ref'])
    else: rows=[r for r in rows if (r['kind'],r['id'])!=(target_kind,target_id)]
    replacement=row(reference(alias),**{k:v for k,v in raw.items() if k not in ('id','revision','schema_version')})
    rows=[replacement if r['id']=='TEST-ONLY-'+alias else r for r in rows]
    inv={k:[pin(r)['ref'] for r in rows if r['kind']==k] for k in ENUMERATIONS}
    # Read this edge directly to isolate its target guard from dependents' changed pin digests.
    p=lt._Preparation(adapter(rows,inv)); owner=p.read(reference(alias),(ALIASES[alias][0],))
    caught=None
    try: p.edge(owner,path)
    except lt._Unavailable as error: caught=error
    assert type(caught) is lt._Unavailable and 'unavailable prerequisite' in str(caught), 'dependency rejection required'
    if damage=='wrong-kind': assert le.EvidenceResult('INTEGRITY_FAILURE','reference',('kind',),'unsupported value') in p.diagnostics
    else:
        state='INTEGRITY_FAILURE' if damage=='bad-pin' else 'UNKNOWN'
        reason='pin digest mismatch' if damage=='bad-pin' else 'missing exact target'
        assert le.EvidenceResult(state,f'{target_kind}:{target_id}@{97 if damage=="revision" else target_revision}',('sha256',) if damage=='bad-pin' else (),reason) in p.diagnostics
        assert le.EvidenceResult(state,f'{ALIASES[alias][0]}:TEST-ONLY-{alias}@{ALIASES[alias][1]}',path,'dependency unavailable') in p.diagnostics, 'dependency unavailable diagnostic'

@pytest.mark.parametrize('guard,case',[('support media correspondence','support-media'),('ingestion media correspondence','clip-media'),
    ('attachment media correspondence','evidence-media'),('hypothesis context unavailable','no-context'),('decoded ingestion unavailable','no-ingestion')])
def test_context_guard_deletion(adapter,monkeypatch,guard,case):
    original=lt._Preparation.guard
    monkeypatch.setattr(lt._Preparation,'guard',lambda self,reason,*args: None if reason==guard else original(self,reason,*args))
    exact_error(lambda:test_context_and_correspondence(adapter,case),AssertionError,'intended diagnostic')

@pytest.mark.parametrize('coverage',['interval','full_clip','sampled_frames'])
def test_required_coordinates_are_unknown(adapter,coverage):
    data=fixture(); data['e'].update(coverage=coverage,sampling_manifest=[.5]); data['s'].update(frame_indices=[],derivative=None)
    data['e']['timestamp_start']=None
    result=run(adapter,data,'e')
    rejected(result,'e',('timestamp_start',),'UNKNOWN','null required field')

@pytest.mark.parametrize('value',[float('nan'),float('inf'),-.5])
def test_nonfinite_and_negative_times(adapter,value):
    data=fixture(); data['i']['metadata']['duration_seconds']=value
    result=run(adapter,data,'o')
    if value<0: rejected(result,'i',('metadata','duration_seconds'),'INTEGRITY_FAILURE','below minimum')
    else: rejected(result,'i',('payload',),'INTEGRITY_FAILURE','nonfinite number')

@pytest.mark.parametrize('design',[None,dict(n_per_arm=2,decision_rule='TEST-ONLY count'),dict(stopping_rule='TEST-ONLY stop',decision_rule='TEST-ONLY decide')])
def test_admitted_representatives(adapter,design):
    from eval_lab.persistence import Repository
    from eval_lab import domain as d, pilot_domain as pd, generation as g, evidence_roles as er, test_plans as tp
    from test_relation_v2 import seed,edge
    from test_competing_sets import competing,relation
    from test_test_plans import form
    from test_assessments import observation
    from test_generation import PLAN
    from contextlib import closing
    with closing(Repository()) as repo:
        x=seed(repo); v2=edge(x); repo.put(v2); legacy=relation(x.hs); repo.put(legacy)
        registration=x.r.model_copy(update=dict(id='TEST-ONLY-admitted-ingestion',metadata=x.r.metadata.model_copy(update=dict(frames=(
            x.r.metadata.frames[0],pd.FrameTime(index=1,pts=5,seconds=.5,source_seconds=.5)))))); repo.put(registration)
        clip=pd.PilotClip(id='TEST-ONLY-admitted-clip',media=x.m.ref,ingestion=registration.ref,selected_by='TEST-ONLY selector',label='TEST-ONLY attachment'); repo.put(clip)
        ev=x.e.model_copy(update=dict(id='TEST-ONLY-admitted-evidence',source='human_observation',coverage='interval',timestamp_start=0.,timestamp_end=1.)); repo.put(ev)
        tool=pd.ToolIdentity(name='ffmpeg',version='TEST-ONLY tool',executable_sha256='d'*64)
        frames=tuple(pd.ExtractedFrame(frame_index=i,requested_seconds=t,actual_seconds=a,pts=p,relative_path='TEST-ONLY-frame-'+str(n),sha256=str(n+5)*64,width=16,height=16)
            for n,(i,t,a,p) in enumerate(((1,.4,.5,5),(0,0,0,0),(1,.45,.5,5))))
        derivative=pd.DerivativeManifest(id='TEST-ONLY-admitted-derivative',media=x.m.ref,ingestion=registration.ref,source_sha256=x.m.checksum,tool=tool,command_template=('TEST-ONLY',),frames=frames); repo.put(derivative)
        submission=pd.PilotSubmission(id='TEST-ONLY-admitted-submission',clip=clip.ref,artifact=ev.ref,author=ev.author,derivative=derivative.ref,frame_indices=(0,1)); repo.put(submission)
        obs=observation(x.m,ev,created_at=x.hs[0].created_at); repo.put(obs)
        repo.put(er.HypothesisContext(id='TEST-ONLY-admitted-context',author='TEST-ONLY author',hypothesis=g.pin(x.hs[0]),observation=g.pin(obs)))
        group=competing(x.hs[:2]); repo.put(group); generation=g.record_plan(repo,PLAN)
        plan=tp.TestPlan(**form(group,sample_design=design,arms=[dict(id='TEST-ONLY-generation-arm',description='TEST-ONLY description',generation_plan_ref=g.pin(generation) if design else None)])); repo.put(plan)
        objects=[item for kind in le.ARTIFACT_TYPES for item in repo.all(kind)]
        rows=[row(item.ref.model_dump(),**item.model_dump(mode='json',exclude={'id','revision','schema_version'})) for item in objects]
        inventory={kind:[pin(r)['ref'] for r in rows if r['kind']==kind] for kind in ENUMERATIONS}
        for item in (ev,submission,obs,x.hs[0],v2,legacy,plan):
            result=lt.prepare(adapter(rows,inventory),item.ref.model_dump())
            assert result.diagnostics==(); assert result.support()

@pytest.mark.parametrize('case',['empty-derivative','nongeneration-design','wrong-version','same-id-media-revision','legacy-null'])
def test_optional_and_exact_branches(adapter,case):
    data=fixture(); root='s'
    if case=='empty-derivative': data['s']['frame_indices']=[]; data['d']['frames'][0]['pts']=339
    if case=='nongeneration-design':
        root='t'
        for arm in data['t']['arms']: arm['generation_plan_ref']=None
        data['t']['sample_design']['decision_rule']=None
    if case=='same-id-media-revision': data['d']['media']['revision']=2
    rows=records(data)
    if case=='same-id-media-revision': rows.append(row(reference('m')|{'revision':2},**data['m']))
    if case in ('wrong-version','legacy-null'):
        legacy=ref('RelationClaim','TEST-ONLY-legacy',59)
        record=row(legacy,predicate=None if case=='legacy-null' else 'supports',subject=reference('e'),object=reference('h'))
        if case=='wrong-version':
            payload=json.loads(record['payload']); payload['schema_version']=2
            from hashlib import sha256
            record['payload']=json.dumps(payload,sort_keys=True,separators=(',',':')); record['sha256']=sha256(record['payload'].encode()).hexdigest()
        result=lt.prepare(adapter(rows+[record],{}),legacy)
        assert le.EvidenceResult('UNKNOWN' if case=='legacy-null' else 'INTEGRITY_FAILURE','RelationClaim:TEST-ONLY-legacy@59',('predicate',) if case=='legacy-null' else ('schema_version',),'null required field' if case=='legacy-null' else 'unsupported value') in result.diagnostics
        exact_error(result.support,ValueError,'unavailable prerequisite'); return
    inv={k:[pin(r)['ref'] for r in rows if r['kind']==k] for k in ENUMERATIONS}; result=lt.prepare(adapter(rows,inv),reference(root))
    expected={'empty-derivative':('d',('frames',0,'pts'),'INTEGRITY_FAILURE','decoded PTS correspondence'),
        'nongeneration-design':('t',('sample_design','decision_rule'),'UNKNOWN','null required field'),
        'same-id-media-revision':('d',('media',),'INTEGRITY_FAILURE','derivative media correspondence')}[case]
    rejected(result,*expected)

MUTANTS=[('if not indices and not present: return','if not present: return','derivative'),
    ('if not indices and not present: return','if not indices: return','empty-derivative'),
    ('if not generation and not present: return','if not present: return','design'),
    ('if not generation and not present: return','if not generation: return','nongeneration-design'),
    ('if sorted(checked)!=sorted(expected):','if False:','inventory'),
    ("self.diagnostics.append(le.EvidenceResult(state, owner[2].subject, path, 'dependency unavailable'))",'pass','dependency'),
    ('if presence and not spec.startswith','if False and not spec.startswith','undeclared')]
@pytest.mark.parametrize('old,new,case',MUTANTS)
def test_branch_guard_deletion(adapter,monkeypatch,old,new,case):
    from pathlib import Path
    source=Path(lt.__file__).read_text(); assert source.count(old)==1
    namespace=dict(lt.__dict__); exec(compile(source.replace(old,new),lt.__file__,'exec'),namespace)
    namespace['_Unavailable']=lt._Unavailable
    monkeypatch.setattr(lt,'_Preparation',namespace['_Preparation'])
    if case=='derivative': action=lambda:test_frame_attachment_requires_derivative(adapter,None)
    elif case=='design': action=lambda:test_declared_field_contract(adapter,next(e for e in FIELDS if e[1]=='sample_design'),'null')
    elif case=='inventory':
        reader=lp.DirectRecords(records(fixture()),{k:[] for k in ENUMERATIONS})
        action=lambda:assert_collection(reader)
    elif case=='dependency': action=lambda:test_exact_dependency_contract(adapter,FIELDS[3],'missing-target')
    elif case=='undeclared': action=lambda:test_undeclared_presence(adapter)
    else: action=lambda:test_optional_and_exact_branches(adapter,case)
    fragment={'inventory':'inventory membership diagnostic','dependency':'dependency unavailable diagnostic','undeclared':''}.get(case,'intended diagnostic')
    exact_error(action,AssertionError,fragment)

def assert_collection(reader):
    result=lt.prepare(reader,reference('e'))
    assert le.EvidenceResult('INTEGRITY_FAILURE','inventory',('MediaIngestion',),'inventory membership mismatch') in result.diagnostics, 'inventory membership diagnostic'

def test_undeclared_presence(adapter):
    p=lt._Preparation(adapter(records(fixture()),{})); record=p.read(reference('m'),('MediaAsset',))
    exact_error(lambda:p.value(record,('type',),True),KeyError,'undeclared presence')

@pytest.mark.parametrize('kind',list(EXPECTED))
def test_deleted_declaration(monkeypatch,kind):
    monkeypatch.delitem(lt.SPECS,kind)
    exact_error(test_inventory_exact,AssertionError,'')

@pytest.mark.parametrize('field',['predicate','subject','object'])
@pytest.mark.parametrize('value,state,reason',[(le._MISSING,'UNKNOWN','missing required field'),(None,'UNKNOWN','null required field'),(4,'INTEGRITY_FAILURE','wrong type')])
def test_legacy_field_contract(adapter,field,value,state,reason):
    data=dict(predicate='supports',subject=reference('e'),object=reference('h'))
    if value is le._MISSING: del data[field]
    else: data[field]=value
    legacy=ref('RelationClaim','TEST-ONLY-legacy-fields',79)
    result=lt.prepare(adapter(records(fixture())+[row(legacy,**data)],{}),legacy)
    assert le.EvidenceResult(state,'RelationClaim:TEST-ONLY-legacy-fields@79',(field,),reason) in result.diagnostics
    exact_error(result.support,ValueError,'unavailable prerequisite')

@pytest.mark.parametrize('case',['relation','legacy-subject','legacy-object','target-kind','presence-missing','presence-parent','boundary-bypass'])
def test_remaining_guard_deletion(adapter,monkeypatch,case):
    if case in ('relation','legacy-subject','legacy-object'):
        original=lt._Preparation.guard
        monkeypatch.setattr(lt._Preparation,'guard',lambda self,reason,*a:None
            if reason=='relation endpoint kind' and (case=='relation' or a[1][0]=='RelationClaim') else original(self,reason,*a))
        action=lambda:test_relation_vocabulary_contract(adapter,'supports','Evidence','Hypothesis','object' if case=='legacy-object' else 'subject')
    elif case=='target-kind':
        original=lt._Preparation.read
        monkeypatch.setattr(lt._Preparation,'read',lambda self,request,kinds,*a,**kw: original(self,request,tuple(le.ARTIFACT_TYPES),*a,**kw))
        action=lambda:test_exact_dependency_contract(adapter,FIELDS[3],'wrong-kind')
    elif case.startswith('presence'):
        original=le.RawRecord.presence
        monkeypatch.setattr(le.RawRecord,'presence',lambda record,path:le.EvidenceResult('AVAILABLE',record.subject,path,value=False))
        action=lambda:test_optional_branch_contract('missing' if case=='presence-missing' else 'parent-malformed')
    else:
        monkeypatch.setattr(le.RawRecord,'field',lambda record,path,contract:le.field(record.diagnostic_raw,path,contract,subject=record.subject))
        # A path/contract trace must detect replacing the actual record boundary with raw inspection.
        original=lt._Preparation.value
        def bypass(self,record,path,presence=False):
            old=record[2].field
            object.__setattr__(record[2],'field',lambda p,c:le.field(record[2].diagnostic_raw,p,c,subject=record[2].subject))
            try:return original(self,record,path,presence)
            finally:object.__setattr__(record[2],'field',old)
        monkeypatch.setattr(lt._Preparation,'value',bypass)
        action=lambda:test_boundary_consumption(adapter,monkeypatch,'s')
    exact_error(action,AssertionError,'intended diagnostic' if case in ('relation','legacy-subject','legacy-object') else '')

@pytest.mark.parametrize('alias,text,value,reason,root',[
    ('i','metadata.frames',[],'empty value','s'),('d','frames',[],'empty value','s'),('t','arms',[],'empty value','t'),
    ('t','arms.0.id',' ','empty value','t'),('m','type','unknown','unsupported value','s'),
    ('i','metadata.frames.0.index',-1,'below minimum','s'),('i','metadata.frames.0.seconds',-.1,'below minimum','s'),
    ('d','frames.0.frame_index',-1,'below minimum','s'),('d','frames.0.requested_seconds',-.2,'below minimum','s'),
    ('d','frames.0.actual_seconds',-.3,'below minimum','s'),('e','timestamp_start',-.4,'below minimum','e'),
    ('e','timestamp_end',-.5,'below minimum','e'),('e','sampling_manifest',[-.6],'below minimum','e'),
    ('o','span.0',-.7,'below minimum','o'),('m','duration',0,'below minimum','o')])
def test_field_constraints(adapter,alias,text,value,reason,root):
    data=fixture(); change(data,alias,parts(text),value)
    path=parts(text)+(0,) if text=='sampling_manifest' else parts(text)
    rejected(run(adapter,data,root),alias,path,'INTEGRITY_FAILURE',reason)
    assert run(adapter,root=root).diagnostics==()
