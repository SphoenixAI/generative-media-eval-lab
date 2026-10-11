"""TEST-ONLY warrant/provenance/override controls, with independent literal oracles."""
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
import pytest
from eval_lab import lint_evidence as le, lint_prerequisites as lp, lint_temporal_prerequisites as lt
from eval_lab import lint_warrant_prerequisites as lw
from test_lint_prerequisites import adapter, row, ref, pin, exact_error

EXPECTED = {
    'MediaAsset': 'checksum=digest',
    'MediaIngestion': 'media=ref:MediaAsset source_sha256=digest created_at=instant',
    'PilotClip': 'media=ref:MediaAsset ingestion=ref:MediaIngestion intent=?ref:IntentSpec',
    'IntentSpecV2': 'criteria=nonempty criteria.*=mapping criteria.*.id=text criteria.*.dimension=dimension criteria.*.priority=priority expected_deviations=sequence expected_deviations.*=mapping expected_deviations.*.criterion_id=text expected_deviations.*.dimension=dimension',
    'IntentBinding': 'intent=pin:intent media=pin:MediaAsset registration=pin:MediaIngestion registered_at=instant origin=origin declaration=?declaration seal=?mapping seal.intent=pin:intent seal.sealed_at=instant plan=?mapping plan.intents=nonempty plan.intents.*=pin:intent plan.registration=pin:MediaIngestion plan.planned_at=instant first_view_at=?instant',
    'BindingContext': 'binding=pin:IntentBinding origin=?pin:ClipOrigin seal=?pin:SealRecord view=?pin:FirstView',
    'ClipOrigin': 'clip=pin:PilotClip origin=origin_kind plan=?pin:GenerationPlan',
    'FirstView': 'media=pin:MediaAsset registration=pin:MediaIngestion created_at=instant',
    'GenerationPlan': 'intent_revision_ids=sequence intent_revision_ids.*=pin:intent planned_at=instant created_at=instant',
    'SealRecord': 'intent=pin:intent canonical_source=text file_sha256=digest canonicalization=canonicalization number_profile=profile sealed_at=instant created_at=instant',
    'TechnicalObservation': 'media=pin:MediaAsset dimension=dimension deviation=deviation',
    'CriterionAssessment': 'media=pin:MediaAsset intent=pin:IntentSpecV2 binding=pin:IntentBinding criterion_id=text status=status observations=sequence observations.*=pin:TechnicalObservation flags=sequence flags.*=flag',
    'TerminalVerdict': 'media=pin:MediaAsset clip=pin:PilotClip intent=pin:IntentSpecV2 binding=pin:IntentBinding assessments=sequence assessments.*=pin:CriterionAssessment observations=sequence observations.*=pin:TechnicalObservation override=?mapping override.reason=text override.author=text override.action=action',
    'RelationClaim': 'predicate=predicate subject=refkind object=refkind intent=ref:IntentSpec evidence=sequence evidence.*=ref:Evidence',
    'RelationClaimV2': 'predicate=predicate subject=refkind object=refkind intent=pin:intent evidence=sequence evidence.*=ref:Evidence epistemic_purpose=epistemic operational_purpose=operational creative_anchor=sequence creative_anchor.*=text warrant=?text',
    'Evidence': 'media=ref:MediaAsset', 'Hypothesis': 'intent=refkind',
    'ModelRun': 'media=ref:MediaAsset prompt=ref:PromptSpec', 'PromptSpec': 'intent=ref:IntentSpec',
}
ENUMERATIONS = ('BindingContext', 'IntentBinding', 'RelationClaim', 'RelationClaimV2', 'PilotClip', 'ModelRun')
ALIASES = dict(m='MediaAsset', n='MediaAsset', i='MediaIngestion', j='MediaIngestion', k='MediaIngestion',
    c='PilotClip', d='PilotClip', v='IntentSpecV2', u='IntentSpecV2', z='IntentSpec', z2='IntentSpec', b='IntentBinding',
    x='BindingContext', y='ClipOrigin', w='FirstView', g='GenerationPlan', s='SealRecord',
    o='TechnicalObservation', q='TechnicalObservation', a='CriterionAssessment', f='CriterionAssessment',
    t='TerminalVerdict', r='RelationClaimV2', l='RelationClaim', e='Evidence', h='Hypothesis',
    el='Evidence', hl='Hypothesis', mr='ModelRun', pr='PromptSpec')
TIMES = ('2026-10-01T00:00:00Z', '2026-10-01T00:00:01Z', '2026-10-01T00:00:02Z', '2026-10-01T00:00:03Z')
def R(alias): return ref(ALIASES[alias], 'TEST-ONLY-warrant-'+alias, 1)
def P(alias): return {'PIN': alias}
def fixture():
    criterion = dict(id='TEST-ONLY-motion', dimension='motion_plausibility', priority='MUST', acceptance='TEST-ONLY accept', rejection='TEST-ONLY reject', tolerance='TEST-ONLY tolerate')
    legacy=dict(owner='TEST-ONLY owner',objective='TEST-ONLY legacy',audience='TEST-ONLY audience',context='TEST-ONLY context',authority='agent_proposed',created_at=TIMES[0],
        criteria=[dict(dimension='composition',rationale='TEST-ONLY rationale',acceptance='TEST-ONLY acceptance')])
    return dict(
        m=dict(checksum='a'*64), n=dict(checksum='b'*64),
        i=dict(media=R('m'), source_sha256='a'*64, created_at=TIMES[2]), j=dict(media=R('n'), source_sha256='b'*64, created_at=TIMES[2]),
        k=dict(media=R('m'), source_sha256='a'*64, created_at=TIMES[2]),
        c=dict(media=R('m'), ingestion=R('i'), intent=None), d=dict(media=R('n'), ingestion=R('j'), intent=R('z')),
        v=dict(created_at=TIMES[0], owner='TEST-ONLY owner', objective='TEST-ONLY objective', revision_reason='CLARIFICATION', predecessor=None,
            use_context=dict(surface='TEST-ONLY surface', audience='TEST-ONLY audience', viewing_profile='FEED'),
            criteria=[criterion, criterion | dict(id='TEST-ONLY-light', dimension='composition', priority='SHOULD')],
            expected_deviations=[dict(criterion_id='TEST-ONLY-motion', dimension='motion_plausibility', description='TEST-ONLY deviation')]),
        u=dict(created_at=TIMES[0], owner='TEST-ONLY other', objective='TEST-ONLY other objective', revision_reason='CORRECTION', predecessor=None,
            use_context=dict(surface='TEST-ONLY second surface', audience='TEST-ONLY second audience', viewing_profile='STUDIO'),
            criteria=[criterion | dict(id='TEST-ONLY-other', priority='COULD')], expected_deviations=[]), z=legacy, z2=legacy | dict(owner='TEST-ONLY second owner',objective='TEST-ONLY distinct legacy'),
        b=dict(intent=P('v'), media=P('m'), registration=P('i'), registered_at=TIMES[2], origin='GENERATED', declaration=None,
            seal=dict(intent=P('v'), sealed_at=TIMES[0]), plan=dict(intents=[P('v'), P('u')], registration=P('i'), planned_at=TIMES[1]), first_view_at=TIMES[3]),
        x=dict(binding=P('b'), origin=P('y'), seal=P('s'), view=P('w')),
        y=dict(clip=P('c'), origin='PLANNED', plan=P('g')),
        w=dict(media=P('m'), registration=P('i'), created_at=TIMES[3]),
        g=dict(intent_revision_ids=[P('v'), P('u')], planned_at=TIMES[1], created_at=TIMES[1]),
        s=dict(intent=P('v'), canonical_source={'SOURCE':'v'}, file_sha256={'FILE':'v'}, canonicalization='RFC8785', number_profile='safe-integer-tokens-v1', sealed_at=TIMES[0], created_at=TIMES[0]),
        o=dict(media=P('m'), dimension='motion_plausibility', deviation='MATERIAL'), q=dict(media=P('m'), dimension='composition', deviation='MINOR'),
        a=dict(media=P('m'), intent=P('v'), binding=P('b'), criterion_id='TEST-ONLY-motion', status='VIOLATED', observations=[P('o')], flags=['CONTEMPORANEOUS_INTENT']),
        f=dict(media=P('m'), intent=P('v'), binding=P('b'), criterion_id='TEST-ONLY-light', status='NOT_APPLICABLE', observations=[P('q')], flags=[]),
        t=dict(media=P('m'), clip=P('c'), intent=P('v'), binding=P('b'), assessments=[P('a'),P('f')], observations=[P('o'),P('q')],
            override=dict(reason='  TEST-ONLY reason  ', author='TEST-ONLY author', action='HOLD'), decision={'TEST-ONLY-retained':'SHIP'}),
        r=dict(predicate='supports', subject=R('e'), object=R('h'), intent=P('v'), evidence=[R('e')], creative_anchor=['TEST-ONLY-motion'], warrant='TEST-ONLY warrant', epistemic_purpose='EXPLAIN', operational_purpose='INVESTIGATE'),
        l=dict(predicate='supports', subject=R('el'), object=R('hl'), intent=R('z'), evidence=[R('el')]),
        e=dict(media=R('m')), h=dict(intent=R('v')), el=dict(media=R('n')), hl=dict(intent=R('z')),
        mr=dict(media=R('n'), prompt=R('pr')), pr=dict(intent=R('z')))

def records(data):
    cache = {}
    def convert(value):
        if type(value) is dict:
            if set(value)=={'PIN'}: return pin(make(value['PIN']))
            if set(value) in ({'SOURCE'}, {'FILE'}):
                payload=make(next(iter(value.values())))['payload']
                return payload if 'SOURCE' in value else sha256(payload.encode()).hexdigest()
            return {k:convert(v) for k,v in value.items()}
        if type(value) is list: return [convert(v) for v in value]
        return value
    def make(alias):
        if alias not in cache: cache[alias]=row(R(alias), **convert(data[alias]))
        return cache[alias]
    return [make(alias) for alias in data]
def reader(adapter, data):
    rows=records(data)
    return adapter(rows,{kind:[pin(r)['ref'] for r in rows if r['kind']==kind] for kind in ENUMERATIONS})
def run(adapter,data=None,root='b'): return lw.prepare(reader(adapter,fixture() if data is None else data),R(root))
def change(data,alias,path,value):
    node=data[alias]
    for key in path[:-1]: node=node[key]
    if value is le._MISSING and type(node) is list: del node[path[-1]:]
    elif value is le._MISSING: del node[path[-1]]
    else: node[path[-1]]=value

def rejected(result,alias,path,state,reason):
    assert le.EvidenceResult(state,ALIASES[alias]+':TEST-ONLY-warrant-'+alias+'@1',path,reason) in result.diagnostics, ('intended diagnostic',result.diagnostics)
    exact_error(result.support,ValueError,'unavailable prerequisite')

def test_warrant_inventory_exact():
    assert lw.SPECS==EXPECTED, 'full declaration inventory'
    assert lw.ENUMERATIONS==ENUMERATIONS, 'full enumeration inventory'

# reason, changed owner/path/value, root, diagnostic owner/path: each row is a deletion witness.
CASES = [
    ('unique criterion IDs','v',('criteria',1,'id'),'TEST-ONLY-motion','b','v',('criteria',)),
    ('expected criterion membership','v',('expected_deviations',0,'criterion_id'),'TEST-ONLY-absent','b','v',('expected_deviations',0,'criterion_id')),
    ('expected dimension correspondence','v',('expected_deviations',0,'dimension'),'composition','b','v',('expected_deviations',0,'dimension')),
    ('registration media correspondence','i',('media',),R('n'),'b','i',('media',)),
    ('registration source correspondence','i',('source_sha256',),'c'*64,'b','i',('source_sha256',)),
    ('registration instant correspondence','b',('registered_at',),TIMES[1],'b','b',('registered_at',)),
    ('prompt declaration origin correspondence','b',('declaration',),'PROMPT_ONLY','b','b',('declaration',)),
    ('origin media correspondence','c',('media',),R('n'),'b','c',('media',)),
    ('origin registration correspondence','c',('ingestion',),R('k'),'b','c',('ingestion',)),
    ('origin plan presence','y',('origin',),'FOUND','b','y',('plan',)),
    ('origin category correspondence','b',('origin',),'FOUND','b','b',('origin',)),
    ('plan support presence','b',('plan',),None,'b','b',('plan',)),
    ('unique plan intents','g',('intent_revision_ids',),[P('v'),P('v')],'b','g',('intent_revision_ids',)),
    ('plan event instant correspondence','g',('created_at',),TIMES[2],'b','g',('created_at',)),
    ('retained plan intent correspondence','b',('plan','intents'),[P('u'),P('v')],'b','b',('plan','intents')),
    ('retained plan registration correspondence','b',('plan','registration'),P('k'),'b','b',('plan','registration')),
    ('embedded plan instant correspondence','b',('plan','planned_at'),TIMES[2],'b','b',('plan','planned_at')),
    ('seal support presence','x',('seal',),None,'b','b',('seal',)),
    ('binding seal intent correspondence','s',('intent',),P('u'),'b','s',('intent',)),
    ('canonical source correspondence','s',('canonical_source',),'{} ','b','s',('canonical_source',)),
    ('canonical file correspondence','s',('file_sha256',),'d'*64,'b','s',('file_sha256',)),
    ('canonical intent correspondence','s',('canonical_source',),{'SOURCE':'u'},'b','s',('intent',)),
    ('seal event instant correspondence','s',('created_at',),TIMES[1],'b','s',('created_at',)),
    ('embedded seal intent correspondence','b',('seal','intent'),P('u'),'b','b',('seal','intent')),
    ('embedded seal instant correspondence','b',('seal','sealed_at'),TIMES[1],'b','b',('seal','sealed_at')),
    ('view support presence','x',('view',),None,'b','b',('first_view_at',)),
    ('embedded view instant correspondence','b',('first_view_at',),TIMES[2],'b','b',('first_view_at',)),
    ('assessment intent correspondence','a',('intent',),P('u'),'a','a',('intent',)),
    ('assessment media correspondence','a',('media',),P('n'),'a','a',('media',)),
    ('pinned criterion membership','a',('criterion_id',),'TEST-ONLY-absent','a','a',('criterion_id',)),
    ('observation support unavailable','a',('observations',),[],'a','a',('observations',)),
    ('observation media correspondence','o',('media',),P('n'),'a','o',('media',)),
    ('observation dimension correspondence','o',('dimension',),'composition','a','o',('dimension',)),
    ('clip media correspondence','t',('clip',),P('d'),'t','t',('clip',)),
    ('verdict binding intent correspondence','t',('intent',),P('u'),'t','t',('binding',)),
    ('verdict binding media correspondence','t',('media',),P('n'),'t','t',('binding',)),
    ('unique selected criterion','t',('assessments',),[P('a'),P('a')],'t','t',('assessments',)),
    ('unique selected observation','t',('observations',),[P('o'),P('o'),P('q')],'t','t',('observations',)),
    ('assessment support subset correspondence','t',('observations',),[P('q')],'t','a',('observations',)),
    ('unique anchor IDs','r',('creative_anchor',),['TEST-ONLY-motion','TEST-ONLY-motion'],'r','r',('creative_anchor',)),
    ('anchor membership','r',('creative_anchor',),['TEST-ONLY-absent'],'r','r',('creative_anchor',)),
    ('relation binding unavailable','e',('media',),R('n'),'r','e',('media',)),
    ('relation hypothesis correspondence','h',('intent',),R('u'),'r','h',('intent',)),
    ('relation hypothesis correspondence','hl',('intent',),R('z2'),'l','hl',('intent',)),
    ('relation intent endpoint correspondence','l',('object',),R('z2'),'l','l',('object',)),
    ('relation intent endpoint correspondence','r',('object',),R('u'),'r','r',('object',)),
]

def semantic(adapter,case):
    reason,alias,path,value,root,owner,location=case
    data=fixture()
    if reason=='relation intent endpoint correspondence': data[root].update(predicate='fulfills',object=R('z' if root=='l' else 'v'))
    valid=run(adapter,data,root); assert valid.diagnostics==(), 'valid counterpart'; assert valid.support()
    change(data,alias,path,value)
    if reason=='canonical source correspondence': data['s']['canonical_source']=json.loads(next(r for r in records(fixture()) if r['kind']=='SealRecord')['payload'])['canonical_source']+' '
    if reason=='canonical intent correspondence': data['s']['file_sha256']={'FILE':'u'}
    if reason=='verdict binding media correspondence': data['t']['clip']=P('d')
    result=run(adapter,data,root)
    if reason in ('relation hypothesis correspondence','relation intent endpoint correspondence'): assert result.diagnostics==(le.EvidenceResult('INTEGRITY_FAILURE',ALIASES[owner]+':TEST-ONLY-warrant-'+owner+'@1',location,reason),), 'intended diagnostic'
    rejected(result,owner,location,'UNKNOWN' if reason in ('observation support unavailable','relation binding unavailable') else 'INTEGRITY_FAILURE',reason)
@pytest.mark.parametrize('case',CASES,ids=[c[4]+'/'+c[0] for c in CASES])
def test_warrant_context_correspondence(adapter,case): semantic(adapter,case)
@pytest.mark.parametrize('case',CASES,ids=[c[4]+'/'+c[0] for c in CASES])
def test_warrant_guard_deletion(adapter,monkeypatch,case):
    original=lw._Preparation.guard
    reads=[]; original_read=lw._Preparation.read
    def read(self,*args,**kwargs):
        record=original_read(self,*args,**kwargs)
        reads.append((record[1],tuple(self.obligations))); return record
    monkeypatch.setattr(lw._Preparation,'read',read)
    monkeypatch.setattr(lw._Preparation,'guard',lambda self,reason,condition,record,*args:None if reason==case[0] and record[1][1]==R(case[5])['id'] else original(self,reason,condition,record,*args))
    exact_error(lambda:semantic(adapter,case),AssertionError,'intended diagnostic')
    if case[0] in ('relation hypothesis correspondence','relation intent endpoint correspondence'):
        selected=[(identity,ops) for identity,ops in reads if ops and ops[-1][3:5]==(ALIASES[case[1]]+':TEST-ONLY-warrant-'+case[1]+'@1',case[2])]; n=1 if case[5] in ('h','hl') else 2
        assert len(selected)==2*n and [ops for _,ops in selected[:n]]==[ops for _,ops in selected[n:]] and [identity for identity,_ in selected[n:]]==[tuple(case[3].values())]*n, 'exact target reads and obligation prefixes'

# Expand a separately authored inventory over literal TEST-ONLY payloads, never production declarations.
def field_cases():
    result=[]
    for kind,specs in EXPECTED.items():
        alias=next(a for a,k in ALIASES.items() if k==kind)
        for spec in specs.split():
            text,token=spec.split('='); path=tuple(0 if p=='*' else p for p in text.split('.'))
            result.append((alias,path,token))
    return result
FIELDS=field_cases()
@pytest.mark.parametrize('entry',FIELDS,ids=lambda e:e[0]+'.'+'.'.join(map(str,e[1])))
@pytest.mark.parametrize('damage,state,reason',[('missing','UNKNOWN','missing required field'),('null','UNKNOWN','null required field'),('malformed','INTEGRITY_FAILURE','wrong type'),('valid','AVAILABLE','')])
def test_warrant_field_contract(adapter,entry,damage,state,reason):
    alias,path,token=entry; data=fixture(); data['b']['declaration']='PROMPT_ONLY'; data['c']['intent']=R('z')
    if damage!='valid': change(data,alias,path,le._MISSING if damage=='missing' else None if damage=='null' else 123)
    p=lw._Preparation(reader(adapter,data)); record=p.read(R(alias),(ALIASES[alias],))
    if damage=='valid': p.value(record,path); assert p.diagnostics==[]
    else:
        error=None
        try: p.value(record,path)
        except lt._Unavailable as caught: error=caught
        assert le.EvidenceResult(state,ALIASES[alias]+':TEST-ONLY-warrant-'+alias+'@1',path,reason) in p.diagnostics, 'intended diagnostic'
        assert type(error) is lt._Unavailable and 'unavailable prerequisite' in str(error)
@pytest.mark.parametrize('entry',FIELDS,ids=lambda e:e[0]+str(e[1]))
def test_warrant_field_deletion(adapter,monkeypatch,entry):
    original=le.RawRecord.field; alias,path,_=entry
    monkeypatch.setattr(le.RawRecord,'field',lambda record,p,c:le.EvidenceResult('AVAILABLE',record.subject,p,value='TEST-ONLY bypass')
        if record.subject==ALIASES[alias]+':TEST-ONLY-warrant-'+alias+'@1' and p==path else original(record,p,c))
    exact_error(lambda:test_warrant_field_contract(adapter,entry,'malformed','INTEGRITY_FAILURE','wrong type'),AssertionError,'intended diagnostic')

@pytest.mark.parametrize('owner,path',[('b',('registered_at',)),('w',('created_at',)),('s',('created_at',)),('s',('sealed_at',)),('g',('created_at',)),('g',('planned_at',)),('b',('seal','sealed_at')),('b',('plan','planned_at')),('b',('first_view_at',)),('i',('created_at',))])
@pytest.mark.parametrize('stamp',['not a timestamp','2026-10-01T00:00:01','2026-02-30T00:00:01Z'])
def test_required_chronology_contract(adapter,owner,path,stamp):
    data=fixture(); change(data,owner,path,stamp)
    rejected(run(adapter,data),owner,path,'INTEGRITY_FAILURE','invalid timezone timestamp')
@pytest.mark.parametrize('owner,path,stamp',[('i',('created_at',),'2026-09-30T17:00:02-07:00'),('b',('registered_at',),'2026-09-30T17:00:02-07:00'),
    ('w',('created_at',),'2026-09-30T17:00:03-07:00'),('s',('created_at',),'2026-09-30T17:00:00-07:00'),('s',('sealed_at',),'2026-09-30T17:00:00-07:00'),
    ('g',('created_at',),'2026-09-30T17:00:01-07:00'),('g',('planned_at',),'2026-09-30T17:00:01-07:00'),('b',('plan','planned_at'),'2026-09-30T17:00:01-07:00'),
    ('b',('seal','sealed_at'),'2026-09-30T17:00:00-07:00'),('b',('first_view_at',),'2026-09-30T17:00:03-07:00')])
def test_binding_timestamp_instants(adapter,owner,path,stamp):
    data=fixture(); change(data,owner,path,stamp); before=deepcopy(data); source=reader(adapter,data)
    result=lw.prepare(source,R('b')); assert result.diagnostics==(); assert result.support(); assert data==before
    assert source.read(R(owner)).diagnostic_raw==json.loads(next(r for r in records(data) if r['id']==R(owner)['id'])['payload'])

@pytest.mark.parametrize('different',[False,True])
def test_first_view_content_correspondence(adapter,different):
    data=fixture(); data['w'].update(media=P('n') if different else P('m'),registration=P('j') if different else P('k'))
    # Equalize every chronology operand. No timing difference can mask identity rejection.
    for alias,path,_ in [('b',('registered_at',),0),('i',('created_at',),0),('j',('created_at',),0),('k',('created_at',),0),('w',('created_at',),0),('s',('created_at',),0),('s',('sealed_at',),0),('g',('created_at',),0),('g',('planned_at',),0),('b',('plan','planned_at'),0),('b',('seal','sealed_at'),0),('b',('first_view_at',),0)]: change(data,alias,path,TIMES[1])
    result=run(adapter,data)
    if different: rejected(result,'w',('media',),'INTEGRITY_FAILURE','FirstView content correspondence')
    else: assert result.diagnostics==(); assert result.chronology==((False,False,False),)
def test_first_view_deletion(adapter,monkeypatch):
    original=lw._Preparation.guard
    monkeypatch.setattr(lw._Preparation,'guard',lambda self,reason,*args:None if reason=='FirstView content correspondence' else original(self,reason,*args))
    exact_error(lambda:test_first_view_content_correspondence(adapter,True),AssertionError,'intended diagnostic')

@pytest.mark.parametrize('slot',('seal','plan','first_view_at','declaration'))
def test_binding_absence_branches(adapter,slot):
    data=fixture(); data['b'][slot]=None
    if slot=='seal': data['x']['seal']=None
    if slot=='first_view_at': data['x']['view']=None
    if slot=='plan': data['g']['intent_revision_ids']=[]
    result=run(adapter,data); assert result.diagnostics==(); assert result.support()
@pytest.mark.parametrize('declaration',[None,'PROMPT_ONLY'])
def test_found_and_legacy_branches(adapter,declaration):
    data=fixture(); data['b'].update(origin='FOUND',declaration=declaration,seal=None,plan=None,first_view_at=None)
    data['x'].update(seal=None,view=None); data['y'].update(origin='FOUND',plan=None)
    assert run(adapter,data).diagnostics==()
    if declaration is None: data['b']['intent']=P('z'); assert run(adapter,data).diagnostics==()
@pytest.mark.parametrize('root',('b','a','t','r','l','x'))
def test_warrant_partial_support(adapter,root):
    result=run(adapter,root=root); assert result.diagnostics==(); assert result.support()
    assert result.group=='partial prerequisites'
    if root=='l': assert result.compatibility==('UNSPECIFIED','UNSPECIFIED','legacy intent: no v2 criterion IDs'), 'legacy compatibility operands'
    assert not any(hasattr(result,key) for key in ('ready','complete','verdict','decision'))
@pytest.mark.parametrize('field,value,state,reason',[
    ('override',le._MISSING,'UNKNOWN','missing required field'),('override',42,'INTEGRITY_FAILURE','wrong type'),
    ('reason',None,'UNKNOWN','null required field'),('reason',le._MISSING,'UNKNOWN','missing required field'),('reason',' ','INTEGRITY_FAILURE','empty value'),
    ('author',None,'UNKNOWN','null required field'),('author',' ','INTEGRITY_FAILURE','empty value'),('action','COMPLETE','INTEGRITY_FAILURE','unsupported value')])
def test_override_prerequisite_contract(adapter,field,value,state,reason):
    data=fixture(); path=('override',) if field=='override' else ('override',field); change(data,'t',path,value)
    rejected(run(adapter,data,'t'),'t',path,state,reason)
def test_override_does_not_rewrite_decision(adapter):
    data=fixture(); assert run(adapter,data,'t').diagnostics==()
    assert data['t']['decision']=={'TEST-ONLY-retained':'SHIP'}
    data['t']['override']=None; assert run(adapter,data,'t').diagnostics==()

# Independently counted consumption, including repeated contracts/subjects and presence.
CRITERIA={'v':'criteria criteria.0 criteria.0.id criteria.0.dimension criteria.0.priority criteria.1 criteria.1.id criteria.1.dimension criteria.1.priority expected_deviations expected_deviations.0 expected_deviations.0.criterion_id expected_deviations.0.dimension'}
BINDING=CRITERIA | {
    'b':'intent media registration registered_at origin ?declaration ?plan plan plan.intents plan.intents.0 plan.intents.1 plan.registration plan.planned_at ?seal seal seal.intent seal.sealed_at ?first_view_at first_view_at',
    'm':'checksum*2', 'i':'media*2 source_sha256*2 created_at',
    'x':'binding*2 ?origin origin ?seal seal ?view view', 'y':'clip origin ?plan plan', 'c':'media ingestion',
    'g':'intent_revision_ids intent_revision_ids.0 intent_revision_ids.1 planned_at created_at',
    's':'intent*2 canonicalization number_profile canonical_source file_sha256 sealed_at created_at', 'w':'media registration created_at'}
RELATION=CRITERIA | {'r':'predicate*2 subject*2 object*2 intent*2 epistemic_purpose operational_purpose creative_anchor creative_anchor.0 ?warrant warrant evidence evidence.0',
    'h':'intent','e':'media*2','b':'media*2 intent*2'}
ASSESSMENT={'a':'media intent binding criterion_id status flags flags.0 observations observations.0', 'o':'media dimension deviation'}
LEGACY={'l':'predicate subject*2 object*2 intent evidence evidence.0', 'hl':'intent', 'el':'media*2', 'c':'media*2 ?intent*2',
    'd':'media*2 ?intent*2 intent*2', 'mr':'media*2 prompt*2', 'pr':'intent*2'}
def footprint(table):
    result=Counter()
    for alias,words in table.items():
        for word in words.split():
            word,_,count=word.partition('*'); presence=word.startswith('?')
            path=tuple(int(s) if s.isdigit() else s for s in word.lstrip('?').split('.'))
            result[(alias,path,presence)]+=int(count or 1)
    return result
@pytest.mark.parametrize('root',['b','a','t','r','l','x'])
def test_warrant_boundary_consumption(adapter,monkeypatch,root):
    observed=Counter(); original=le.RawRecord.field
    def spy(record,path,contract):
        observed[(record.subject,path,contract)]+=1
        return original(record,path,contract)
    monkeypatch.setattr(le.RawRecord,'field',spy)
    expected=footprint(RELATION if root=='r' else LEGACY if root=='l' else BINDING)
    collections={'r':{'IntentBinding':2},'l':{'PilotClip':2,'ModelRun':2},'b':{'BindingContext':1},'a':{'BindingContext':1},'x':{'BindingContext':1},
        't':{'BindingContext':3,'IntentBinding':2,'RelationClaim':1,'RelationClaimV2':1}}[root]
    if root=='a': expected+=footprint(ASSESSMENT)
    if root=='x': expected+=footprint({'x':'binding'})
    if root=='t':
        expected=footprint(BINDING)+footprint(BINDING)+footprint(BINDING)+footprint(RELATION)+footprint(ASSESSMENT)
        expected+=footprint({'f':'media intent binding criterion_id status flags observations observations.0', 'q':'media*2 dimension*2 deviation*2',
            'o':'media dimension deviation', 'c':'media', 'l':'intent', 'r':'intent',
            't':'media intent binding clip observations observations.0 observations.1 assessments assessments.0 assessments.1 ?override override override.reason override.author override.action'})
    result=run(adapter,root=root); assert result.diagnostics==()
    actual=Counter(); obligations=Counter(); fields=Counter()
    # Contracts are authored independently, with explicit vocabulary identity.
    contracts=lt.CONTRACTS | dict(instant=lw.Instant((str,)),priority=le.Contract((str,),choices=('MUST','SHOULD','COULD','WONT')),
        origin=le.Contract((str,),choices=('GENERATED','FOUND')),origin_kind=le.Contract((str,),choices=('PLANNED','FOUND')),
        declaration=le.Contract((str,),choices=('PROMPT_ONLY',)),canonicalization=le.Contract((str,),choices=('RFC8785',)),profile=le.Contract((str,),choices=('safe-integer-tokens-v1',)),
        flag=le.Contract((str,),choices=('CONTEMPORANEOUS_INTENT',)),deviation=le.Contract((str,),choices=('NONE','MINOR','MATERIAL','SEVERE','CATASTROPHIC','UNKNOWN'),unavailable=('UNKNOWN',)),
        status=le.Contract((str,),choices=('SATISFIED','VIOLATED','NOT_APPLICABLE','UNKNOWN'),unavailable=('UNKNOWN',)),action=le.Contract((str,),choices=('SHIP','HOLD','REPAIR','REGENERATE','INVESTIGATE')))
    for (alias,path,presence),count in expected.items():
        kind=ALIASES[alias]; subject=kind+':TEST-ONLY-warrant-'+alias+'@1'; template='.'.join('*' if type(s) is int else s for s in path)
        token=dict(w.split('=') for w in EXPECTED[kind].split())[template].lstrip('?')
        contract=le.BOOLEAN if presence else le.MAPPING if token.startswith(('ref','pin:')) else contracts[token]
        obligations[(kind,template,'presence' if presence else 'value',subject,path,contract)]+=count
        fields[(subject,path[:-1] if presence else path,le.MAPPING if presence else contract)]+=count
    assert Counter(o for o in result.obligations if o[0]!='@collection')==obligations, 'active obligation multiplicity'
    assert observed==fields, 'shared boundary consumption'
    assert Counter(o[1] for o in result.obligations if o[0]=='@collection')==collections, 'collection obligations'
    assert result.consumed==result.declared

@pytest.mark.parametrize('entry',[e for e in FIELDS if e[2].startswith('?')])
@pytest.mark.parametrize('damage',['missing','null','malformed','valid'])
def test_presence_contract(adapter,entry,damage):
    alias,path,token=entry; data=fixture(); data['c']['intent']=R('z'); data['b']['declaration']='PROMPT_ONLY'
    if damage!='valid': change(data,alias,path,le._MISSING if damage=='missing' else None if damage=='null' else 123)
    p=lw._Preparation(reader(adapter,data)); owner=p.read(R(alias),(ALIASES[alias],))
    if damage=='missing':
        exact_error(lambda:p.value(owner,path,True),lt._Unavailable,'unavailable prerequisite')
        assert le.EvidenceResult('UNKNOWN',owner[2].subject,path,'missing required field') in p.diagnostics
    else: assert p.value(owner,path,True)==(damage!='null')

@pytest.mark.parametrize('entry',[e for e in FIELDS if e[2].lstrip('?').startswith(('ref','pin:'))])
@pytest.mark.parametrize('damage',['missing','revision','digest','kind'])
def test_warrant_dependency_diagnostic(adapter,entry,damage):
    alias,path,token=entry; data=fixture(); data['c']['intent']=R('z'); rows=records(data)
    owner=next(r for r in rows if r['id']==R(alias)['id']); raw=json.loads(owner['payload']); request=raw
    for part in path: request=request[part]
    pinned=token.lstrip('?').startswith('pin:'); target=request['ref'] if pinned else request; target_id=target['id']; target_kind=target['kind']
    if damage=='missing': rows=[r for r in rows if r['id']!=target_id]
    elif damage=='revision': target['revision']=97
    elif damage=='digest': request['sha256']='f'*64
    else:
        alternate=next(r for r in rows if r['kind']=='MediaAsset' if r['id']!=target_id) if target_kind!='MediaAsset' else next(r for r in rows if r['kind']=='PilotClip')
        request.clear(); request.update(pin(alternate) if pinned else pin(alternate)['ref'])
    replacement=row(R(alias),**{k:v for k,v in raw.items() if k not in ('id','revision','schema_version')})
    rows=[replacement if r['id']==R(alias)['id'] else r for r in rows]
    p=lw._Preparation(adapter(rows,{})); record=p.read(R(alias),(ALIASES[alias],)); error=None
    try: p.edge(record,path)
    except lt._Unavailable as caught: error=caught
    if damage=='kind' and token.lstrip('?')=='refkind': assert error is None; return  # Semantic endpoint guards own this vocabulary.
    state='UNKNOWN' if damage in ('missing','revision') else 'INTEGRITY_FAILURE'
    if damage=='kind': expected=le.EvidenceResult(state,'reference',('kind',),'unsupported value')
    elif damage=='digest' and not pinned: expected=le.EvidenceResult(state,'reference',(),'unexpected reference keys')
    else: expected=le.EvidenceResult(state,target_kind+':'+target_id+'@'+('97' if damage=='revision' else '1'),('sha256',) if damage=='digest' else (), 'pin digest mismatch' if damage=='digest' else 'missing exact target')
    assert expected in p.diagnostics, 'target diagnostic'
    if damage!='kind': assert le.EvidenceResult(state,record[2].subject,path,'dependency unavailable') in p.diagnostics, 'dependency unavailable diagnostic'
    assert type(error) is lt._Unavailable and 'unavailable prerequisite' in str(error)

@pytest.mark.parametrize('root',['b','a','t','r','l'])
def test_warrant_inputs_preserved(adapter,root):
    data=fixture(); source=reader(adapter,data); rows=records(data); before=deepcopy(data)
    result=lw.prepare(source,R(root)); assert result.diagnostics==()
    assert lw.prepare(source,R(root))==result
    assert lw.prepare(adapter(list(reversed(rows)),{k:[pin(r)['ref'] for r in reversed(rows) if r['kind']==k] for k in ENUMERATIONS}),R(root))==result
    assert data==before
    for original in rows:
        read=source.read(pin(original),pinned=True); assert read.diagnostics==()
        assert read.diagnostic_raw==json.loads(original['payload'])

@pytest.mark.parametrize('alias,field,value',[('a','status','UNKNOWN'),('o','deviation','UNKNOWN')])
def test_excuse_unknown_operands(adapter,alias,field,value):
    data=fixture();data[alias][field]=value
    rejected(run(adapter,data,'a'),alias,(field,),'UNKNOWN','explicitly unavailable')
@pytest.mark.parametrize('label',['NONE','MINOR','MATERIAL','SEVERE','CATASTROPHIC'])
@pytest.mark.parametrize('status',['SATISFIED','VIOLATED','NOT_APPLICABLE'])
def test_excuse_operand_labels(adapter,label,status):
    data=fixture();data['o']['deviation']=label;data['a']['status']=status
    assert run(adapter,data,'a').diagnostics==()  # No acceptability judgment is made here.

@pytest.mark.parametrize('case',['missing','duplicate','wrong-context','media-revision','registration-revision','clip-revision','legacy-anchor','intent-endpoint','view-media','view-source','reverse-seal','reverse-view','reverse-plan','no-origin','parse-source'])
def test_remaining_correspondence(adapter,case):
    data=fixture(); root='b'; expected=None
    if case=='missing': del data['x']; expected=('b',(),'UNKNOWN','binding context unavailable')
    elif case=='duplicate':
        rows=records(data); x=next(r for r in rows if r['kind']=='BindingContext'); raw=json.loads(x['payload'])
        rows.append(row(ref('BindingContext','TEST-ONLY-second-context',1),**{k:v for k,v in raw.items() if k not in ('id','revision','schema_version')}))
        source=adapter(rows,{k:[pin(r)['ref'] for r in rows if r['kind']==k] for k in ENUMERATIONS})
        rejected(lw.prepare(source,R('b')),'b',(),'INTEGRITY_FAILURE','duplicate exact context'); return
    elif case=='wrong-context':
        p=lw._Preparation(reader(adapter,data)); b=p.read(R('b'),('IntentBinding',))
        # A separately retained binding with a distinct exact identity, all dependencies intact.
        raw=json.loads(next(r for r in records(data) if r['id']==R('b')['id'])['payload']); raw['id']='TEST-ONLY-other-binding'
        b2=row(ref('IntentBinding',raw['id'],1),**{k:v for k,v in raw.items() if k not in ('id','revision','schema_version')})
        wrong=row(ref('BindingContext','TEST-ONLY-wrong-context',1),binding=pin(b2),origin=None,seal=None,view=None)
        p.source=adapter(records(data)+[b2,wrong],{'BindingContext':[R('x'),pin(wrong)['ref']]})
        context=p.read(pin(wrong)['ref'],('BindingContext',)); error=None
        try:p.binding(b,context)
        except lt._Unavailable as caught:error=caught
        assert le.EvidenceResult('INTEGRITY_FAILURE','BindingContext:TEST-ONLY-wrong-context@1',('binding',),'exact context binding correspondence') in p.diagnostics, 'intended diagnostic'
        assert type(error) is lt._Unavailable and 'unavailable prerequisite' in str(error); return
    elif case.endswith('-revision'):
        alias,owner,field,label={'media-revision':('m','b','media','original media anchor'),'registration-revision':('i','b','registration','original registration anchor'),'clip-revision':('c','y','clip','original clip anchor')}[case]
        rows=records(data); old=next(r for r in rows if r['id']==R(alias)['id']); raw=json.loads(old['payload'])
        revised=row(R(alias)|{'revision':2},**{k:v for k,v in raw.items() if k not in ('id','revision','schema_version')})
        data[owner][field]=pin(revised)
        if alias=='m': data['i']['media']=pin(revised)['ref']
        rows=records(data)+[revised]; source=adapter(rows,{'BindingContext':[R('x')]})
        rejected(lw.prepare(source,R('b')),owner,(field,),'INTEGRITY_FAILURE',label); return
    elif case=='legacy-anchor': data['r'].update(intent=P('z'),subject=R('el'),object=R('hl'),evidence=[R('el')]);root='r';expected=('r',('creative_anchor',),'INTEGRITY_FAILURE','anchor membership')
    elif case=='intent-endpoint':data['r'].update(predicate='fulfills',object=R('u'));root='r';expected=('r',('object',),'INTEGRITY_FAILURE','relation intent endpoint correspondence')
    elif case=='view-media':data['w']['registration']=P('j');expected=('j',('media',),'INTEGRITY_FAILURE','registration media correspondence')
    elif case=='view-source':data['k']['source_sha256']='e'*64;data['w']['registration']=P('k');expected=('k',('source_sha256',),'INTEGRITY_FAILURE','registration source correspondence')
    elif case=='reverse-seal':data['b']['seal']=None;expected=('b',('seal',),'INTEGRITY_FAILURE','seal support presence')
    elif case=='reverse-view':data['b']['first_view_at']=None;expected=('b',('first_view_at',),'INTEGRITY_FAILURE','view support presence')
    elif case=='reverse-plan':data['g']['intent_revision_ids']=[];expected=('b',('plan',),'INTEGRITY_FAILURE','plan support presence')
    elif case=='no-origin':data['x']['origin']=None;expected=('b',('plan',),'INTEGRITY_FAILURE','plan support presence')
    else:data['s']['canonical_source']='not json';expected=('s',('canonical_source',),'INTEGRITY_FAILURE','canonical source correspondence')
    rejected(run(adapter,data,root),*expected)

REMAINING=[('missing','binding context unavailable'),('duplicate','duplicate exact context'),('wrong-context','exact context binding correspondence'),
    ('media-revision','original media anchor'),('registration-revision','original registration anchor'),('clip-revision','original clip anchor'),
    ('legacy-anchor','anchor membership'),('intent-endpoint','relation intent endpoint correspondence'),('view-media','registration media correspondence'),
    ('view-source','registration source correspondence'),('reverse-seal','seal support presence'),('reverse-view','view support presence'),
    ('reverse-plan','plan support presence'),('no-origin','plan support presence'),('parse-source','canonical source correspondence')]
@pytest.mark.parametrize('case,guard',REMAINING)
def test_remaining_guard_deletion(adapter,monkeypatch,case,guard):
    original=lw._Preparation.guard
    monkeypatch.setattr(lw._Preparation,'guard',lambda self,reason,*args:None if reason==guard else original(self,reason,*args))
    exact_error(lambda:test_remaining_correspondence(adapter,case),AssertionError,'intended diagnostic')

@pytest.mark.parametrize('field',['intent','media','binding'])
def test_verdict_assessment_context(adapter,field):
    data=fixture(); b=deepcopy(data['b']); b.update(origin='FOUND',seal=None,plan=None,first_view_at=None)
    if field=='intent': b['intent']=P('u');data['a'].update(intent=P('u'),criterion_id='TEST-ONLY-other')
    if field=='media': b.update(media=P('n'),registration=P('j'));data['a']['media']=P('n')
    encoded=records(fixture() | {'b':b}); new=row(ref('IntentBinding','TEST-ONLY-distinct-binding',1),**{k:v for k,v in json.loads(next(r for r in encoded if r['id']==R('b')['id'])['payload']).items() if k not in ('id','revision','schema_version')})
    context=row(ref('BindingContext','TEST-ONLY-distinct-context',1),binding=pin(new),origin=None,seal=None,view=None)
    data['a']['binding']=pin(new); extras=[new,context]
    if field=='media':
        extra=row(ref('TechnicalObservation','TEST-ONLY-distinct-observation',1),media=pin(next(r for r in records(data) if r['id']==R('n')['id'])),dimension='motion_plausibility',deviation='SEVERE')
        data['a']['observations']=[pin(extra)];extras.append(extra)
    rows=records(data)+extras;source=adapter(rows,{k:[pin(r)['ref'] for r in rows if r['kind']==k] for k in ENUMERATIONS})
    rejected(lw.prepare(source,R('t')),'t',('assessments',),'INTEGRITY_FAILURE','verdict assessment '+field+' correspondence')
@pytest.mark.parametrize('field',['intent','media','binding'])
def test_verdict_assessment_deletion(adapter,monkeypatch,field):
    original=lw._Preparation.guard
    monkeypatch.setattr(lw._Preparation,'guard',lambda self,reason,*args:None if reason=='verdict assessment '+field+' correspondence' else original(self,reason,*args))
    exact_error(lambda:test_verdict_assessment_context(adapter,field),AssertionError,'intended diagnostic')

@pytest.mark.parametrize('root',['l','r'])
@pytest.mark.parametrize('field',['subject','object'])
def test_relation_endpoint_contract(adapter,root,field):
    data=fixture();data[root][field]=R('u')
    rejected(run(adapter,data,root),root,(field,),'INTEGRITY_FAILURE','relation endpoint kind')
@pytest.mark.parametrize('root',['l','r'])
@pytest.mark.parametrize('field',['subject','object'])
def test_relation_endpoint_deletion(adapter,monkeypatch,root,field):
    original=lw._Preparation.guard
    monkeypatch.setattr(lw._Preparation,'guard',lambda self,reason,*a:None if reason=='relation endpoint kind' else original(self,reason,*a))
    exact_error(lambda:test_relation_endpoint_contract(adapter,root,field),AssertionError,'intended diagnostic')
@pytest.mark.parametrize('owner',['clip','run'])
def test_legacy_scope_contract(adapter,owner):
    data=fixture()
    if owner=='clip': del data['mr']
    else: data['d']['intent']=None
    assert run(adapter,data,'l').diagnostics==()
    if owner=='clip':data['d']['media']=R('m')
    else:data['mr']['media']=R('m')
    rejected(run(adapter,data,'l'),'el',('media',),'UNKNOWN','relation binding unavailable')
@pytest.mark.parametrize('owner',['clip','run'])
def test_legacy_scope_deletion(adapter,monkeypatch,owner):
    original=lw._Preparation.guard
    monkeypatch.setattr(lw._Preparation,'guard',lambda self,reason,*a:None if reason=='relation binding unavailable' else original(self,reason,*a))
    exact_error(lambda:test_legacy_scope_contract(adapter,owner),AssertionError,'intended diagnostic')
@pytest.mark.parametrize('predicate',['supports','contradicts'])
@pytest.mark.parametrize('value,state,reason',[(None,'UNKNOWN','null required field'),('', 'INTEGRITY_FAILURE','empty value'),(False,'INTEGRITY_FAILURE','wrong type')])
def test_relation_warrant_prerequisites(adapter,predicate,value,state,reason):
    data=fixture();data['r'].update(predicate=predicate,warrant=value)
    rejected(run(adapter,data,'r'),'r',('warrant',),state,reason)

@pytest.mark.parametrize('s,p,r,v,expected',[(0,1,2,3,(True,True,True)),(1,1,2,3,(False,True,True)),(0,1,1,3,(True,False,True)),(0,1,2,0,(True,True,False)),(2,1,0,1,(False,False,False)),(1,1,1,1,(False,False,False))])
def test_provenance_chronology_boundaries(adapter,s,p,r,v,expected):
    data=fixture()
    for alias,path,index in [('s',('created_at',),s),('s',('sealed_at',),s),('b',('seal','sealed_at'),s),('g',('created_at',),p),('g',('planned_at',),p),('b',('plan','planned_at'),p),('i',('created_at',),r),('b',('registered_at',),r),('w',('created_at',),v),('b',('first_view_at',),v)]:change(data,alias,path,TIMES[index])
    result=run(adapter,data); assert result.diagnostics==();assert result.chronology==(expected,), 'strict chronology operands'

@pytest.mark.parametrize('provenance',['SEALED','CONTEMPORANEOUS','RECONSTRUCTED','PROMPT_ONLY'])
def test_admitted_warrant_representatives(adapter,monkeypatch,provenance):
    from contextlib import closing
    from eval_lab.persistence import Repository
    from eval_lab.relation_v2 import RelationClaimV2
    from test_decisions import fixture as admitted, verdict
    if provenance=='SEALED':
        from eval_lab import generation as g
        from datetime import timedelta
        original=g.bind_intent
        def different_registration(repo,clip,intent,**kw):
            reg=repo.get(clip.ingestion).model_copy(update={'id':'TEST-ONLY-distinct-registration'});repo.put(reg)
            repo.put(g.FirstView(id='TEST-ONLY-distinct-view',media=g.pin(repo.get(clip.media)),registration=g.pin(reg),created_at=reg.created_at+timedelta(seconds=1)))
            return original(repo,clip,intent,**kw)
        monkeypatch.setattr(g,'bind_intent',different_registration)
    with closing(Repository()) as repo:
        form,observation,assessment,policy=admitted(repo,monkeypatch,provenance,'VIOLATED')
        terminal=verdict(repo,form);repo.put(terminal)
        relation=RelationClaimV2(id='TEST-ONLY-admitted-warrant',subject=observation.evidence[0].ref,object=terminal.intent.ref,intent=terminal.intent,
            predicate='fulfills',epistemic_status='asserted',evidence=(observation.evidence[0].ref,),asserted_by='TEST-ONLY author',purpose='TEST-ONLY purpose',scope='TEST-ONLY scope',
            valid_from=terminal.created_at,epistemic_purpose='SUPPORT',operational_purpose='INVESTIGATE',creative_anchor=('TEST-ONLY-geometry',))
        repo.put(relation); objects=[item for kind in le.ARTIFACT_TYPES for item in repo.all(kind)]
        rows=[dict(item.ref.model_dump(),payload=item.canonical(),sha256=item.digest) for item in objects]
        source=adapter(rows,{k:[pin(r)['ref'] for r in rows if r['kind']==k] for k in ENUMERATIONS})
        for item in (terminal,assessment,repo.get(terminal.binding.ref),relation):
            result=lw.prepare(source,item.ref.model_dump());assert result.diagnostics==();assert result.support()

@pytest.mark.parametrize('kind',ENUMERATIONS)
@pytest.mark.parametrize('raw,state,reason',[(le._MISSING,'UNKNOWN','missing required field'),(None,'UNKNOWN','null required field'),({},'INTEGRITY_FAILURE','wrong type')])
def test_warrant_collection_scope(adapter,monkeypatch,kind,raw,state,reason):
    source=reader(adapter,fixture());monkeypatch.setattr(source,'rows',lambda:le.field(raw,(),le.SEQUENCE,subject='universe'))
    p=lw._Preparation(source);exact_error(lambda:p.collection(kind),lt._Unavailable,'unavailable prerequisite')
    assert le.EvidenceResult(state,'universe',(),reason) in p.diagnostics
@pytest.mark.parametrize('entry',FIELDS)
def test_warrant_deleted_declaration(monkeypatch,entry):
    alias,path,token=entry;kind=ALIASES[alias];template='.'.join('*' if type(p) is int else p for p in path)
    monkeypatch.setitem(lw.SPECS,kind,' '.join(w for w in lw.SPECS[kind].split() if not w.startswith(template+'=')))
    exact_error(test_warrant_inventory_exact,AssertionError,'full declaration inventory')
@pytest.mark.parametrize('field',['reason','author','action'])
def test_override_consumption_deletion(adapter,monkeypatch,field):
    original=lw._Preparation.value
    monkeypatch.setattr(lw._Preparation,'value',lambda self,record,path,*a: 'TEST-ONLY bypass' if path==('override',field) else original(self,record,path,*a))
    exact_error(lambda:test_warrant_boundary_consumption(adapter,monkeypatch,'t'),AssertionError,'active obligation multiplicity')

CONSTRAINTS=[('v',('criteria',0,'priority'),'priority','MAY'),('b',('origin',),'origin','PLANNED'),('y',('origin',),'origin_kind','GENERATED'),
    ('b',('declaration',),'declaration','SEALED'),('s',('canonicalization',),'canonicalization','TEST-ONLY-other'),('s',('number_profile',),'profile','TEST-ONLY-other'),
    ('a',('flags',0),'flag','TEST-ONLY-other'),('o',('deviation',),'deviation','MAJOR'),('a',('status',),'status','PASS'),('t',('override','action'),'action','COMPLETE')]
@pytest.mark.parametrize('alias,path,token,bad',CONSTRAINTS)
def test_warrant_contract_constraints(adapter,alias,path,token,bad):
    data=fixture();change(data,alias,path,bad);p=lw._Preparation(reader(adapter,data));owner=p.read(R(alias),(ALIASES[alias],));error=None
    try:p.value(owner,path)
    except lt._Unavailable as caught:error=caught
    assert le.EvidenceResult('INTEGRITY_FAILURE',owner[2].subject,path,'unsupported value') in p.diagnostics, 'intended diagnostic'
    assert type(error) is lt._Unavailable and 'unavailable prerequisite' in str(error)
@pytest.mark.parametrize('alias,path,token,bad',CONSTRAINTS)
def test_warrant_constraint_deletion(adapter,monkeypatch,alias,path,token,bad):
    monkeypatch.setitem(lw.CONTRACTS,token,le.Contract((str,)))
    exact_error(lambda:test_warrant_contract_constraints(adapter,alias,path,token,bad),AssertionError,'intended diagnostic')
@pytest.mark.parametrize('owner,path,stamp,reason',[('b',('registered_at',),'2026-10-01T00:00:02+01:00','registration instant correspondence'),
    ('g',('created_at',),'2026-10-01T00:00:01+01:00','plan event instant correspondence'),('b',('plan','planned_at'),'2026-10-01T00:00:01+01:00','embedded plan instant correspondence'),
    ('s',('created_at',),'2026-10-01T00:00:00+01:00','seal event instant correspondence'),('b',('seal','sealed_at'),'2026-10-01T00:00:00+01:00','embedded seal instant correspondence'),
    ('b',('first_view_at',),'2026-10-01T00:00:03+01:00','embedded view instant correspondence')])
def test_different_instant_offsets(adapter,owner,path,stamp,reason):
    data=fixture();change(data,owner,path,stamp);rejected(run(adapter,data),owner,path,'INTEGRITY_FAILURE',reason)

MUTANTS=[("self.compatibility += ('legacy intent: no v2 criterion IDs',)","self.compatibility = ('legacy intent: no v2 criterion IDs',)",'legacy'),
    ("if self.value(record,('override',),True):",'if False:','override'),
    ("if self.value(record,('predicate',)) in ('supports','contradicts') or active:",'if active:','warrant'),
    ('if seal_active:','if False:','seal'),('if view_active:','if False:','view'),
    ("if active:\n            self.value(record,('plan',))","if False:\n            self.value(record,('plan',))",'plan'),
    ('sealed<planned','sealed<=planned','order'),('planned<registered','planned<=registered','order'),('sealed<viewed','sealed<=viewed','order'),
    ('record[2].field(path,contract)',"le.field(record[2].diagnostic_raw,path,contract,subject=record[2].subject)",'boundary')]
@pytest.mark.parametrize('old,new,case',MUTANTS)
def test_warrant_branch_deletion(adapter,monkeypatch,old,new,case):
    from pathlib import Path
    source=Path(lw.__file__).read_text();assert source.count(old)==1
    namespace=dict(lw.__dict__);exec(compile(source.replace(old,new),lw.__file__,'exec'),namespace)
    namespace['CONTRACTS']=lw.CONTRACTS  # Isolate the mutation, preserving contract class identity.
    monkeypatch.setattr(lw,'_Preparation',namespace['_Preparation'])
    if case=='legacy':action=lambda:test_warrant_partial_support(adapter,'l')
    elif case=='override':action=lambda:test_override_prerequisite_contract(adapter,'reason',None,'UNKNOWN','null required field')
    elif case=='warrant':action=lambda:test_relation_warrant_prerequisites(adapter,'supports',None,'UNKNOWN','null required field')
    elif case=='order':action=lambda:test_provenance_chronology_boundaries(adapter,1,1,1,1,(False,False,False))
    else:action=lambda:test_warrant_boundary_consumption(adapter,monkeypatch,'b')
    fragment='legacy compatibility operands' if case=='legacy' else 'intended diagnostic' if case in ('override','warrant') else 'strict chronology operands' if case=='order' else 'shared boundary consumption' if case=='boundary' else 'active obligation multiplicity'
    exact_error(action,AssertionError,fragment)

def test_warrant_dependency_propagation_deletion(adapter,monkeypatch):
    from pathlib import Path
    old="self.diagnostics.append(le.EvidenceResult(state, owner[2].subject, path, 'dependency unavailable'))"
    source=Path(lt.__file__).read_text();assert source.count(old)==1;namespace=dict(lt.__dict__)
    exec(compile(source.replace(old,'pass'),lt.__file__,'exec'),namespace);namespace['_Unavailable']=lt._Unavailable
    monkeypatch.setattr(lw._Preparation,'read',namespace['_Preparation'].read)
    exact_error(lambda:test_warrant_dependency_diagnostic(adapter,('b',('media',),'pin:MediaAsset'),'missing'),AssertionError,'dependency unavailable diagnostic')

def test_warrant_timestamp_guard_deletion(adapter,monkeypatch):
    monkeypatch.setattr(lw.Instant,'problem',le.Contract.problem)
    exact_error(lambda:test_required_chronology_contract(adapter,'b',('registered_at',),'2026-10-01T00:00:01'),AssertionError,'intended diagnostic')
@pytest.mark.parametrize('alias,field,token',[('a','status','status'),('o','deviation','deviation')])
def test_unknown_guard_deletion(adapter,monkeypatch,alias,field,token):
    from dataclasses import replace
    monkeypatch.setitem(lw.CONTRACTS,token,replace(lw.CONTRACTS[token],unavailable=()))
    exact_error(lambda:test_excuse_unknown_operands(adapter,alias,field,'UNKNOWN'),AssertionError,'intended diagnostic')

def test_warrant_repeated_contracts(adapter,monkeypatch):
    p=lw._Preparation(reader(adapter,fixture()));record=p.read(R('m'),('MediaAsset',));p.value(record,('checksum',))
    monkeypatch.setitem(lw.SPECS,'MediaAsset','checksum=text');p.value(record,('checksum',))
    assert [o[-1] for o in p.obligations]==[le.DIGEST,le.TEXT], 'distinct contract obligations'
    exact_error(lambda:p.value(record,('checksum',),True),KeyError,'undeclared presence')
def test_warrant_repeated_read_deletion(adapter,monkeypatch):
    cache={};original=lw._Preparation.value
    def cached(self,record,path,presence=False):
        key=(record[1],path,presence)
        if key not in cache:cache[key]=original(self,record,path,presence)
        return cache[key]
    monkeypatch.setattr(lw._Preparation,'value',cached)
    exact_error(lambda:test_warrant_boundary_consumption(adapter,monkeypatch,'b'),AssertionError,'active obligation multiplicity')
@pytest.mark.parametrize('bad',[False,True])
def test_retained_bytes_preserved(adapter,bad):
    data=fixture();data['s']['created_at']=TIMES[1] if bad else TIMES[0];rows=records(data);before=deepcopy(rows);source=reader(adapter,data)
    path=None if isinstance(source,lp.DirectRecords) else source.root/'pilot.sqlite';stored=path.read_bytes() if path else None
    result=lw.prepare(source,R('b'))
    if bad:rejected(result,'s',('created_at',),'INTEGRITY_FAILURE','seal event instant correspondence')
    else:assert result.diagnostics==()
    assert records(data)==before
    if path:assert path.read_bytes()==stored
