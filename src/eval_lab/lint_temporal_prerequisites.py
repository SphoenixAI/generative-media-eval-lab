"""Private E3/E4/W1/W4/W5 prerequisites, never complete lint or readiness.

prepare(reader, exact_ref) uses DirectRecords or an open read-only RawReader.
SPECS declares consumed raw paths ('*' is a checked collection element); '?' adds
an explicit presence obligation, not a nullable required value. References and
pins inherit the shared reader's identity/version/digest obligations. Direct
inventories attest only their supplied TEST-ONLY universe. support() denies all
values on any diagnostic. Containers expose keys/indices, never raw descendants.
Coordinates and bounds stay separate for later predicates. No human truth,
intent acceptability, sample adequacy or operational decision is inferred here.
"""
from dataclasses import dataclass
from . import lint_evidence as le, lint_prerequisites as lp
from .domain import Dimension

SPECS = {
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
ENDPOINTS = {'supports': ('Evidence','Hypothesis'), 'contradicts': ('Evidence','Hypothesis'),
    'motivated_by': ('Hypothesis','IntentSpec'), 'fulfills': ('Evidence','IntentSpec'), 'violates': ('Evidence','IntentSpec'),
    'alternative_to': ('Hypothesis','Hypothesis'), 'compatible_with': ('Hypothesis','Hypothesis'), 'refines': ('Hypothesis','Hypothesis')}
CONTRACTS = dict(mapping=le.MAPPING, sequence=le.SEQUENCE, text=le.TEXT, digest=le.DIGEST,
    nonempty=le.Contract((list,tuple),nonempty=True), seconds=le.Contract((int,float),minimum=0),
    positive=le.Contract((int,float),minimum=0,exclusive=True), index=le.Contract((int,),minimum=0),
    integer=le.Contract((int,)), count=le.REVISION, dimension=le.Contract((str,),choices=tuple(d.value for d in Dimension)),
    media_type=le.Contract((str,),choices=('image','video')), predicate=le.Contract((str,),choices=tuple(ENDPOINTS)),
    coverage=le.Contract((str,),choices=('interval','full_clip','sampled_frames','unknown'),unavailable=('unknown',)),
    epistemic=le.Contract((str,),choices=('SUPPORT','RULE_OUT','DISCRIMINATE','LOCALIZE','EXPLAIN','QUALIFY','SCOPE','OPERATIONALIZE')),
    operational=le.Contract((str,),choices=('SHIP','REPAIR','REGENERATE','REVISE_RUBRIC','ADD_GOLD','RETRAIN_SIGNAL','INVESTIGATE')))


class _Unavailable(Exception): pass


@dataclass
class Prepared(lp._Group):
    groups: tuple = ()
    obligations: tuple = ()
    compatibility: tuple = ()

    def support(self):
        if self.diagnostics: raise ValueError('unavailable prerequisite')
        return tuple(self.get(name) for name in self.declared)


class _Preparation:
    def __init__(self, source):
        self.source = source
        self.diagnostics = []; self.obligations = []; self.values = {}; self.compatibility = ()

    def take(self, result):
        if result.state != 'AVAILABLE':
            self.diagnostics.append(result)
            raise _Unavailable('unavailable prerequisite')
        return result.value

    def guard(self, reason, condition, record, path, state='INTEGRITY_FAILURE'):
        if not condition: self.take(le.EvidenceResult(state, record[2].subject, path, reason))

    def read(self, request, kinds, pinned=False, dependency=None):
        raw = self.source.read(request, pinned=pinned)
        if raw.diagnostics:
            self.diagnostics.extend(raw.diagnostics)
            if dependency is not None:
                owner, path = dependency
                state = 'INTEGRITY_FAILURE' if any(d.state=='INTEGRITY_FAILURE' for d in raw.diagnostics) else 'UNKNOWN'
                self.diagnostics.append(le.EvidenceResult(state, owner[2].subject, path, 'dependency unavailable'))
            raise _Unavailable('unavailable prerequisite')
        target = request['ref'] if pinned else request  # Reader has checked every component.
        kind = self.take(le.field(target, ('kind',), le.Contract((str,),choices=kinds), subject='reference'))
        return kind, (kind,target['id'],target['revision']), raw

    def spec(self, record, path):
        template = '.'.join('*' if type(p) is int else p for p in path)
        return template, dict(p.split('=') for p in SPECS[record[0]].split())[template]

    def value(self, record, path, presence=False):
        template, spec = self.spec(record,path)
        if presence and not spec.startswith('?'): raise KeyError('undeclared presence')
        token = spec.lstrip('?')
        contract = le.BOOLEAN if presence else le.MAPPING if token.startswith(('ref','pin:')) else CONTRACTS[token]
        declaration = (record[0],template,'presence' if presence else 'value',record[2].subject,path,contract)
        self.obligations.append(declaration)
        result = record[2].presence(path) if presence else record[2].field(path,contract)
        raw = self.take(result)
        safe = tuple(sorted(raw)) if type(raw) is dict else tuple(range(len(raw))) if type(raw) in (list,tuple) else raw
        self.values[len(self.obligations)-1] = le.EvidenceResult('AVAILABLE',record[2].subject,path,value=safe)
        return raw

    def edge(self, record, path):
        token = self.spec(record,path)[1].lstrip('?')
        kinds = tuple(le.ARTIFACT_TYPES) if token=='refkind' else ('IntentSpec','IntentSpecV2') if token=='pin:intent' else (token.split(':')[1],)
        return self.read(self.value(record,path),kinds,token.startswith('pin:'),(record,path))

    def elements(self, record, path):
        return [self.value(record,path+(i,)) for i in range(len(self.value(record,path)))]

    def collection(self, kind):
        slot = len(self.obligations)
        self.obligations.append(('@collection',kind,'value','universe',(),le.SEQUENCE))
        refs = self.take(lp._identities(self.source.rows()))
        refs = [r for r in refs if r['kind']==kind]
        if isinstance(self.source,lp.DirectRecords):
            inventory = self.take(le.field(self.source.inventory,(),le.MAPPING,subject='inventory'))
            members = self.take(le.field(inventory,(kind,),le.SEQUENCE,subject='inventory'))
            checked = [self.read(r,(kind,))[1] for r in members]
            expected = [(r['kind'],r['id'],r['revision']) for r in refs]
            if sorted(checked)!=sorted(expected):
                self.take(le.EvidenceResult('INTEGRITY_FAILURE','inventory',(kind,),'inventory membership mismatch'))
        result = [self.read(r,(kind,)) for r in refs]
        self.values[slot] = le.EvidenceResult('AVAILABLE','universe',(),value=tuple(r[1] for r in result))
        return result

    def timeline(self, media, ingestion):
        linked = self.edge(ingestion,('media',))
        self.guard('ingestion media correspondence',linked[1]==media[1],ingestion,('media',))
        source = self.value(ingestion,('source_sha256',)); checksum = self.value(media,('checksum',))
        self.guard('source correspondence',source==checksum,ingestion,('source_sha256',))
        self.value(ingestion,('metadata',))
        duration = self.value(ingestion,('metadata','duration_seconds')); declared = self.value(media,('duration',))
        self.guard('duration correspondence',duration==declared,ingestion,('metadata','duration_seconds'))
        frames = self.elements(ingestion,('metadata','frames')); decoded = []
        for i in range(len(frames)):
            p = ('metadata','frames',i)
            index = self.value(ingestion,p+('index',)); seconds = self.value(ingestion,p+('seconds',)); pts = self.value(ingestion,p+('pts',))
            self.guard('contiguous decoded indices',index==i,ingestion,p+('index',))
            self.guard('timeline starts at zero',i!=0 or seconds==0,ingestion,p+('seconds',))
            self.guard('increasing decoded times',i==0 or seconds>decoded[-1][0],ingestion,p+('seconds',))
            decoded.append((seconds,pts))
        self.guard('last frame below duration',decoded[-1][0]<duration,ingestion,('metadata','frames',len(frames)-1,'seconds'))
        return decoded

    def media(self, record, pinned=False):
        media = self.edge(record,('media',))
        if self.value(media,('type',))=='video':
            matches = [i for i in self.collection('MediaIngestion') if self.edge(i,('media',))[1]==media[1]]
            self.guard('decoded ingestion unavailable',bool(matches),record,('media',),'UNKNOWN')
            for ingestion in matches: self.timeline(media,ingestion)
        return media

    def evidence(self, record, expected=None, attachments=True):
        if expected is not None:
            media = self.edge(record,('media',))
            self.guard('support media correspondence',media[1]==expected[1],record,('media',))
        self.media(record)
        coverage = self.value(record,('coverage',))
        start = self.value(record,('timestamp_start',),True); end = self.value(record,('timestamp_end',),True)
        if start != end:
            try: self.value(record,('timestamp_end' if start else 'timestamp_start',))
            except _Unavailable: pass  # Preserve the missing operand and the pairing diagnostic.
        self.guard('paired timestamps',start==end,record,('timestamp_start',),'UNKNOWN')
        if start or coverage=='interval':
            a = self.value(record,('timestamp_start',)); b = self.value(record,('timestamp_end',))
            self.guard('ordered timestamps',a<=b,record,('timestamp_end',))
        samples = self.elements(record,('sampling_manifest',))
        self.guard('sampled coverage requires samples',coverage!='sampled_frames' or bool(samples),record,('sampling_manifest',))
        if attachments:
            for submission in self.collection('PilotSubmission'):
                # Membership accepts other human artifact kinds; active attachments require Evidence.
                request = self.value(submission,('artifact',))
                artifact = self.read(request,tuple(le.ARTIFACT_TYPES),dependency=(submission,('artifact',)))
                if artifact[1]==record[1]: self.attachment(submission)

    def attachment(self, record):
        indices = self.elements(record,('frame_indices',))
        self.guard('unique selected indices',len(indices)==len(set(indices)),record,('frame_indices',))
        present = self.value(record,('derivative',),True)
        if not indices and not present: return
        derivative = self.edge(record,('derivative',)); evidence = self.edge(record,('artifact',)); clip = self.edge(record,('clip',))
        media = self.edge(clip,('media',)); ingestion = self.edge(clip,('ingestion',))
        self.value(media,('type',)); decoded = self.timeline(media,ingestion)
        linked = self.edge(evidence,('media',))
        self.guard('attachment media correspondence',linked[1]==media[1],evidence,('media',))
        self.evidence(evidence,attachments=False)
        self.guard('derivative media correspondence',self.edge(derivative,('media',))[1]==media[1],derivative,('media',))
        self.guard('derivative ingestion correspondence',self.edge(derivative,('ingestion',))[1]==ingestion[1],derivative,('ingestion',))
        self.guard('derivative source correspondence',self.value(derivative,('source_sha256',))==self.value(ingestion,('source_sha256',)),derivative,('source_sha256',))
        frames = self.elements(derivative,('frames',)); selected = []; available = []
        for i in range(len(frames)):
            p = ('frames',i); index = self.value(derivative,p+('frame_index',)); actual = self.value(derivative,p+('actual_seconds',))
            requested = self.value(derivative,p+('requested_seconds',)); pts = self.value(derivative,p+('pts',))
            self.guard('decoded index in timeline',index<len(decoded),derivative,p+('frame_index',))
            if index>=len(decoded): continue  # Bounds remain safe even when a diagnostic guard is instrumented.
            self.guard('decoded PTS correspondence',pts==decoded[index][1],derivative,p+('pts',))
            self.guard('decoded time correspondence',actual==decoded[index][0],derivative,p+('actual_seconds',))
            self.guard('request precedes actual',requested<=actual,derivative,p+('requested_seconds',))
            available.append(index)
            if index in indices: selected.append(actual)
        self.guard('selected index in manifest',set(indices)<=set(available),record,('frame_indices',))
        start = self.value(evidence,('timestamp_start',)); end = self.value(evidence,('timestamp_end',))
        self.guard('selected frame within interval',all(start<=t<=end for t in selected),record,('frame_indices',))

    def observation(self, record):
        self.value(record,('dimension',)); media = self.media(record)
        span = self.elements(record,('span',))
        self.guard('two element span',len(span)==2,record,('span',))
        self.guard('ordered span',span[0]<=span[1],record,('span',))
        for i in range(len(self.value(record,('evidence',)))):
            self.evidence(self.edge(record,('evidence',i)),media)
        return media

    def hypothesis(self, record):
        contexts = [c for c in self.collection('HypothesisContext') if self.edge(c,('hypothesis',))[1]==record[1]]
        self.guard('hypothesis context unavailable',bool(contexts),record,('supporting_evidence',),'UNKNOWN')
        support = range(len(self.value(record,('supporting_evidence',))))
        for context in contexts:
            media = self.observation(self.edge(context,('observation',)))
            for i in support: self.evidence(self.edge(record,('supporting_evidence',i)),media)

    def relation(self, record):
        predicate = self.value(record,('predicate',)); expected = ENDPOINTS[predicate]
        if record[0]=='RelationClaimV2':
            intent = self.edge(record,('intent',))
            if predicate in ('fulfills','violates'): expected = ('Evidence',intent[0])
            self.value(record,('epistemic_purpose',)); self.value(record,('operational_purpose',))
        else: self.compatibility = ('UNSPECIFIED','UNSPECIFIED')
        for field,kind in zip(('subject','object'),expected):
            self.guard('relation endpoint kind',self.edge(record,(field,))[0]==kind,record,(field,))

    def sample(self, record):
        arms = self.elements(record,('arms',)); ids = []; generation = False
        for i in range(len(arms)):
            ids.append(self.value(record,('arms',i,'id')))
            if self.value(record,('arms',i,'generation_plan_ref'),True):
                generation = True; self.edge(record,('arms',i,'generation_plan_ref'))
        self.guard('unique arm IDs',len(ids)==len(set(ids)),record,('arms',))
        present = self.value(record,('sample_design',),True)
        if not generation and not present: return
        self.value(record,('sample_design',)); self.value(record,('sample_design','decision_rule'))
        count = self.value(record,('sample_design','n_per_arm'),True); stopping = self.value(record,('sample_design','stopping_rule'),True)
        self.guard('exclusive sample count or stopping rule',count!=stopping,record,('sample_design',))
        self.value(record,('sample_design','n_per_arm' if count else 'stopping_rule'))


def prepare(source, reference):
    """Prepare exactly the root's group; no all-rule context, defaults or writes."""
    p = _Preparation(source); groups = ()
    handlers = {'Evidence':('evidence',('E3',)), 'PilotSubmission':('attachment',('E3',)),
        'TechnicalObservation':('observation',('E3','W1')), 'Hypothesis':('hypothesis',('E3','W1')),
        'RelationClaim':('relation',('E4','W5')), 'RelationClaimV2':('relation',('E4','W5')), 'TestPlan':('sample',('W4',))}
    try:
        record = p.read(reference,tuple(handlers))
        handler,groups = handlers[record[0]]
        getattr(p,handler)(record)
    except _Unavailable: pass
    names = tuple(range(len(p.obligations)))
    return Prepared('partial prerequisites',tuple(p.diagnostics),names,tuple(sorted(p.values)),(),p.values,
                    groups=groups,obligations=tuple(p.obligations),compatibility=p.compatibility if not p.diagnostics else ())
