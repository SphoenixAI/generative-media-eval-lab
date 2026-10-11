"""Private E1/E2/E2w/E7 operands, never lint completion or readiness.

prepare(reader, exact_ref) accepts the same read-only readers as temporal
preparation. SPECS declares each consumed raw field and optional-slot presence;
ENUMERATIONS declares complete candidate collections (direct: TEST-ONLY only).
Only support() exposes usable values; any diagnostic denies all support. Raw
strings, payloads and pins remain unchanged. chronology contains strict instant
comparisons (seal<plan, plan<registration, seal<view), with None for inactive
operands. These are chronology operands, not provenance or acceptability labels.
"""
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from . import lint_evidence as le, lint_temporal_prerequisites as lt
from .canonical_json import canonicalize, parse_json
from .seals import source_intent

SPECS = {
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


class Instant(le.Contract):
    def problem(self, value):
        reason = super().problem(value)
        if reason: return reason
        try:
            if datetime.fromisoformat(value).utcoffset() is not None: return None
        except ValueError: pass
        return 'invalid timezone timestamp'


def choice(*values, unavailable=()): return le.Contract((str,), choices=values, unavailable=unavailable)
CONTRACTS = lt.CONTRACTS | dict(instant=Instant((str,)), priority=choice('MUST','SHOULD','COULD','WONT'),
    origin=choice('GENERATED','FOUND'), origin_kind=choice('PLANNED','FOUND'), declaration=choice('PROMPT_ONLY'),
    canonicalization=choice('RFC8785'), profile=choice('safe-integer-tokens-v1'), flag=choice('CONTEMPORANEOUS_INTENT'),
    deviation=choice('NONE','MINOR','MATERIAL','SEVERE','CATASTROPHIC','UNKNOWN',unavailable=('UNKNOWN',)),
    status=choice('SATISFIED','VIOLATED','NOT_APPLICABLE','UNKNOWN',unavailable=('UNKNOWN',)),
    action=choice('SHIP','HOLD','REPAIR','REGENERATE','INVESTIGATE'))


@dataclass
class Prepared(lt.Prepared):
    chronology: tuple = ()


class _Preparation(lt._Preparation):
    def __init__(self, source):
        super().__init__(source)
        self.chronology = []

    def spec(self, record, path):
        template = '.'.join('*' if type(p) is int else p for p in path)
        return template, dict(p.split('=') for p in SPECS[record[0]].split())[template]

    def value(self, record, path, presence=False):
        template, spec = self.spec(record,path)
        if presence and not spec.startswith('?'): raise KeyError('undeclared presence')
        token = spec.lstrip('?')
        contract = le.BOOLEAN if presence else le.MAPPING if token.startswith(('ref','pin:')) else CONTRACTS[token]
        self.obligations.append((record[0],template,'presence' if presence else 'value',record[2].subject,path,contract))
        raw = self.take(record[2].presence(path) if presence else record[2].field(path,contract))
        safe = tuple(sorted(raw)) if type(raw) is dict else tuple(range(len(raw))) if type(raw) in (list,tuple) else raw
        self.values[len(self.obligations)-1] = le.EvidenceResult('AVAILABLE',record[2].subject,path,value=safe)
        return raw

    def instant(self, record, path): return datetime.fromisoformat(self.value(record,path))

    def edges(self, record, path):
        return [self.edge(record,path+(i,)) for i in range(len(self.value(record,path)))]

    def criteria(self, record):
        if record[0]=='IntentSpec':
            self.compatibility += ('legacy intent: no v2 criterion IDs',)
            return {}
        criteria = {}
        for i in range(len(self.elements(record,('criteria',)))):
            path = ('criteria',i); cid = self.value(record,path+('id',))
            self.guard('unique criterion IDs',cid not in criteria,record,('criteria',))
            criteria[cid] = (self.value(record,path+('dimension',)),self.value(record,path+('priority',)))
        for i in range(len(self.elements(record,('expected_deviations',)))):
            path = ('expected_deviations',i); cid = self.value(record,path+('criterion_id',)); dimension = self.value(record,path+('dimension',))
            self.guard('expected criterion membership',cid in criteria,record,path+('criterion_id',))
            self.guard('expected dimension correspondence',cid in criteria and dimension==criteria[cid][0],record,path+('dimension',))
        return criteria

    def content(self, record):
        media = self.edge(record,('media',)); registration = self.edge(record,('registration',))
        self.guard('registration media correspondence',self.edge(registration,('media',))[1]==media[1],registration,('media',))
        checksum = self.value(media,('checksum',)); source = self.value(registration,('source_sha256',))
        self.guard('registration source correspondence',source==checksum,registration,('source_sha256',))
        return media, registration, source

    def seal(self, record, intent):
        self.guard('binding seal intent correspondence',self.edge(record,('intent',))[1]==intent[1],record,('intent',))
        self.value(record,('canonicalization',)); self.value(record,('number_profile',))
        source = self.value(record,('canonical_source',)); digest = self.value(record,('file_sha256',))
        try:
            data = parse_json(source); canonical = canonicalize(data); authored = source_intent(data)
        except (ValueError,TypeError):
            self.guard('canonical source correspondence',False,record,('canonical_source',)); return
        self.guard('canonical source correspondence',source==canonical.decode(),record,('canonical_source',))
        self.guard('canonical file correspondence',sha256(canonical).hexdigest()==digest,record,('file_sha256',))
        requested = self.value(record,('intent',))
        self.guard('canonical intent correspondence',authored.ref.model_dump()==requested['ref'] and authored.digest==requested['sha256'],record,('intent',))
        stamp = self.instant(record,('sealed_at',))
        self.guard('seal event instant correspondence',stamp==self.instant(record,('created_at',)),record,('created_at',))
        return stamp

    def binding(self, record, context=None):
        intent = self.edge(record,('intent',)); criteria = self.criteria(intent)
        media, registration, identity = self.content(record)
        for owner,label in ((media,'media'),(registration,'registration')):
            self.guard('original '+label+' anchor',owner[1][2]==1,record,(label,))
        registered = self.instant(record,('registered_at',))
        self.guard('registration instant correspondence',registered==self.instant(registration,('created_at',)),record,('registered_at',))
        origin = self.value(record,('origin',))
        if self.value(record,('declaration',),True):
            self.value(record,('declaration',))
            self.guard('prompt declaration origin correspondence',origin=='FOUND',record,('declaration',))
        contexts = [c for c in self.collection('BindingContext') if self.edge(c,('binding',))[1]==record[1]]
        self.guard('binding context unavailable',bool(contexts),record,(), 'UNKNOWN')
        self.guard('duplicate exact context',len(contexts)<=1,record,())
        if not contexts: return intent,media,criteria
        context = contexts[0] if context is None else context
        self.guard('exact context binding correspondence',self.edge(context,('binding',))[1]==record[1],context,('binding',))
        plan = None; planned = None; sealed = None; viewed = None
        if self.value(context,('origin',),True):
            o = self.edge(context,('origin',)); clip = self.edge(o,('clip',))
            self.guard('original clip anchor',clip[1][2]==1,o,('clip',))
            self.guard('origin media correspondence',self.edge(clip,('media',))[1]==media[1],clip,('media',))
            self.guard('origin registration correspondence',self.edge(clip,('ingestion',))[1]==registration[1],clip,('ingestion',))
            category = self.value(o,('origin',)); active = self.value(o,('plan',),True)
            self.guard('origin plan presence',(category=='PLANNED')==active,o,('plan',))
            self.guard('origin category correspondence',origin==('GENERATED' if category=='PLANNED' else 'FOUND'),record,('origin',))
            if active: plan = self.edge(o,('plan',))
        intents = []
        if plan is not None:
            intents = [p[1] for p in self.edges(plan,('intent_revision_ids',))]
            self.guard('unique plan intents',len(set(intents))==len(intents),plan,('intent_revision_ids',))
            planned = self.instant(plan,('planned_at',))
            self.guard('plan event instant correspondence',planned==self.instant(plan,('created_at',)),plan,('created_at',))
        active = self.value(record,('plan',),True)
        self.guard('plan support presence',active==bool(intents),record,('plan',))
        if active:
            self.value(record,('plan',))
            self.guard('retained plan intent correspondence',[p[1] for p in self.edges(record,('plan','intents'))]==intents,record,('plan','intents'))
            self.guard('retained plan registration correspondence',self.edge(record,('plan','registration'))[1]==registration[1],record,('plan','registration'))
            self.guard('embedded plan instant correspondence',self.instant(record,('plan','planned_at'))==planned,record,('plan','planned_at'))
        seal_active = self.value(context,('seal',),True); embedded = self.value(record,('seal',),True)
        self.guard('seal support presence',seal_active==embedded,record,('seal',))
        if seal_active:
            sealed = self.seal(self.edge(context,('seal',)),intent)
            self.value(record,('seal',))
            self.guard('embedded seal intent correspondence',self.edge(record,('seal','intent'))[1]==intent[1],record,('seal','intent'))
            self.guard('embedded seal instant correspondence',self.instant(record,('seal','sealed_at'))==sealed,record,('seal','sealed_at'))
        view_active = self.value(context,('view',),True); embedded = self.value(record,('first_view_at',),True)
        self.guard('view support presence',view_active==embedded,record,('first_view_at',))
        if view_active:
            view = self.edge(context,('view',)); vm,vi,content = self.content(view)
            self.guard('FirstView content correspondence',content==identity,view,('media',))
            viewed = self.instant(view,('created_at',))
            self.guard('embedded view instant correspondence',self.instant(record,('first_view_at',))==viewed,record,('first_view_at',))
        self.chronology.append((sealed<planned if sealed is not None and planned is not None else None,
                                planned<registered if planned is not None else None,
                                sealed<viewed if sealed is not None and viewed is not None else None))
        return intent,media,criteria

    def context(self, record): return self.binding(self.edge(record,('binding',)),record)

    def observation(self, record, media, dimension=None):
        self.guard('observation media correspondence',self.edge(record,('media',))[1]==media[1],record,('media',))
        measured = self.value(record,('dimension',)); self.value(record,('deviation',))
        if dimension is not None:
            self.guard('observation dimension correspondence',measured==dimension,record,('dimension',))

    def assessment(self, record):
        intent = self.edge(record,('intent',)); media = self.edge(record,('media',)); binding = self.edge(record,('binding',))
        bi,bm,criteria = self.binding(binding)
        self.guard('assessment intent correspondence',intent[1]==bi[1],record,('intent',))
        self.guard('assessment media correspondence',media[1]==bm[1],record,('media',))
        cid = self.value(record,('criterion_id',))
        self.guard('pinned criterion membership',cid in criteria,record,('criterion_id',))
        self.value(record,('status',)); self.elements(record,('flags',)); observations = self.edges(record,('observations',))
        self.guard('observation support unavailable',bool(observations),record,('observations',),'UNKNOWN')
        for observation in observations: self.observation(observation,media,criteria.get(cid,(None,))[0])
        return intent,media,binding,cid,[o[1] for o in observations]

    def legacy_scope(self, media, intent):
        matches = []
        for clip in self.collection('PilotClip'):
            linked = self.edge(clip,('media',)); active = self.value(clip,('intent',),True)
            if active: matches.append((linked[1],self.edge(clip,('intent',))[1]))
        for run in self.collection('ModelRun'):
            linked = self.edge(run,('media',)); prompt = self.edge(run,('prompt',))
            matches.append((linked[1],self.edge(prompt,('intent',))[1]))
        return (media[1],intent[1]) in matches

    def relation(self, record):
        super().relation(record)
        intent = self.edge(record,('intent',)); criteria = self.criteria(intent)
        endpoints = [self.edge(record,(name,)) for name in ('subject','object')]
        if record[0]=='RelationClaimV2':
            anchors = self.elements(record,('creative_anchor',))
            self.guard('unique anchor IDs',len(set(anchors))==len(anchors),record,('creative_anchor',))
            self.guard('anchor membership',set(anchors)<=set(criteria),record,('creative_anchor',))
            active = self.value(record,('warrant',),True)
            if self.value(record,('predicate',)) in ('supports','contradicts') or active: self.value(record,('warrant',))
        for endpoint in endpoints:
            if endpoint[0]=='Hypothesis':
                self.guard('relation hypothesis correspondence',self.edge(endpoint,('intent',))[1]==intent[1],endpoint,('intent',))
            if endpoint[0] in ('IntentSpec','IntentSpecV2'):
                self.guard('relation intent endpoint correspondence',endpoint[1]==intent[1],record,('object',))
        evidence = self.edges(record,('evidence',)) + [p for p in endpoints if p[0]=='Evidence']
        for item in evidence:
            media = self.edge(item,('media',))
            if intent[0]=='IntentSpec': linked = self.legacy_scope(media,intent)
            else:
                candidates = [(self.edge(b,('media',))[1],self.edge(b,('intent',))[1]) for b in self.collection('IntentBinding')]
                linked = (media[1],intent[1]) in candidates
            self.guard('relation binding unavailable',linked,item,('media',),'UNKNOWN')

    def verdict(self, record):
        media = self.edge(record,('media',)); intent = self.edge(record,('intent',)); binding = self.edge(record,('binding',))
        bi,bm,_ = self.binding(binding)
        self.guard('verdict binding intent correspondence',bi[1]==intent[1],record,('binding',))
        self.guard('verdict binding media correspondence',bm[1]==media[1],record,('binding',))
        clip = self.edge(record,('clip',))
        self.guard('clip media correspondence',self.edge(clip,('media',))[1]==media[1],record,('clip',))
        observations = self.edges(record,('observations',)); ids = [o[1] for o in observations]
        self.guard('unique selected observation',len(ids)==len(set(ids)),record,('observations',))
        for observation in observations: self.observation(observation,media)
        selected = []
        for assessment in self.edges(record,('assessments',)):
            ai,am,ab,cid,support = self.assessment(assessment)
            for label,actual,expected in (('intent',ai,intent),('media',am,media),('binding',ab,binding)):
                self.guard('verdict assessment '+label+' correspondence',actual[1]==expected[1],record,('assessments',))
            self.guard('assessment support subset correspondence',set(support)<=set(ids),assessment,('observations',))
            selected.append(cid)
        self.guard('unique selected criterion',len(selected)==len(set(selected)),record,('assessments',))
        for kind in ('RelationClaim','RelationClaimV2'):
            for relation in self.collection(kind):
                if self.edge(relation,('intent',))[1]==intent[1]: self.relation(relation)
        if self.value(record,('override',),True):
            self.value(record,('override',))
            for field in ('reason','author','action'): self.value(record,('override',field))


def prepare(source, reference):
    """Prepare only the selected group's prerequisites; never a rule result."""
    p = _Preparation(source); groups = ()
    handlers = {'IntentBinding':('binding',('E2','E2w')), 'BindingContext':('context',('E2','E2w')),
        'CriterionAssessment':('assessment',('E2','E2w')), 'TerminalVerdict':('verdict',('E1','E2','E2w','E7')),
        'RelationClaim':('relation',('E1',)), 'RelationClaimV2':('relation',('E1',))}
    try:
        record = p.read(reference,tuple(handlers)); handler,groups = handlers[record[0]]
        getattr(p,handler)(record)
    except lt._Unavailable: pass
    names = tuple(range(len(p.obligations)))
    return Prepared('partial prerequisites',tuple(p.diagnostics),names,tuple(sorted(p.values)),(),p.values,
        groups=groups,obligations=tuple(p.obligations),compatibility=p.compatibility if not p.diagnostics else (),
        chronology=tuple(p.chronology) if not p.diagnostics else ())
