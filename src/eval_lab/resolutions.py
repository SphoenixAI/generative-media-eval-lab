"""Private prediction compatibility events; human outcomes, no causal inference."""
from hashlib import sha256
import hmac
from secrets import token_bytes
from types import SimpleNamespace
from typing import Annotated, Literal
from pydantic import Field, PrivateAttr, model_validator
from . import __version__, evidence_roles as er, test_plans as tp
from .assessments import raw_payload
from .canonical_json import canonicalize
from .domain import Artifact, ARTIFACT_TYPES, Ref
from .generation import now, pin
from .intent_v2 import CheckedValue, Pin, Text, Instant, kind, predecessor, content_identity
from .pilot_domain import Hash


class ResolutionUnavailable(ValueError):
    """Missing qualifying evidence remains UNKNOWN, never a default outcome."""


class SubmittedSample(CheckedValue):
    arm: Text
    evidence: Pin


class StoppingDeclaration(CheckedValue):
    author: Text
    plan: Pin
    rule: Text
    arms: tuple[Text, ...]
    samples: tuple[Pin, ...]
    met: Annotated[bool, Field(strict=True)]
    reason: Text


class ResolutionInput(CheckedValue):
    id: Text
    author: Text
    revision: Annotated[int, Field(strict=True, ge=1)] = 1
    predecessor: Pin | None = None
    revision_reason: Text | None = None
    plan: Pin
    outcome: Text
    evidence: tuple[SubmittedSample, ...] = Field(min_length=1)
    decision_reason: Text | None = None
    stopping: StoppingDeclaration | None = None
    mode: Literal['DETERMINATE', 'INDETERMINATE'] = 'DETERMINATE'
    indeterminate_reason: Text | None = None

    @model_validator(mode='before')
    @classmethod
    def revalidate_copies(cls, value):
        return raw_payload(value)

    @model_validator(mode='after')
    def contract(self):
        kind(self.plan, 'TestPlan')
        for sample in self.evidence: kind(sample.evidence, 'Evidence')
        if self.mode == 'INDETERMINATE' and self.indeterminate_reason is None:
            raise ValueError('indeterminate reason required')
        return self


class MemberState(CheckedValue):
    member: Pin | Literal['RESIDUAL']
    status: Literal['ELIMINATED', 'RETAINED', 'INDETERMINATE']


class RoleCheck(CheckedValue):
    hypothesis: Pin
    link: Pin
    role: Literal['TEST_RESULT']
    reason: Text


class CountedSample(SubmittedSample):
    unit: Text
    roles: tuple[RoleCheck, ...]


class ArmCount(CheckedValue):
    arm: Text
    count: Annotated[int, Field(strict=True, ge=0)]


class ResolutionEvent(Artifact, ResolutionInput):
    _timestamp_receipt: bytes = PrivateAttr(default=b'')
    created_at: Instant
    states: tuple[MemberState, ...]
    samples: tuple[CountedSample, ...]
    counts: tuple[ArmCount, ...]
    dependencies: tuple[Pin, ...]
    unpredicted: bool
    residual_present: bool
    input_sha256: Hash
    rule_version: Literal['resolution-v1']
    tool_version: Text

    @model_validator(mode='after')
    def history(self):
        predecessor(self)
        if self.revision > 1 and self.revision_reason is None: raise ValueError('revision reason required')
        return self


ARTIFACT_TYPES['ResolutionEvent'] = ResolutionEvent
DERIVED = {'states', 'samples', 'counts', 'dependencies', 'unpredicted', 'residual_present',
    'input_sha256', 'rule_version', 'tool_version'}
_PREPARATION_KEY = token_bytes(32)


def _timestamp_receipt(event):
    # Process-local admission provenance; not a persisted signature or trusted clock.
    return hmac.digest(_PREPARATION_KEY, canonicalize(event.model_dump(mode='json')), 'sha256')


def human_input(event):
    return ResolutionInput.model_validate({k: getattr(event, k) for k in ResolutionInput.model_fields})


def derive(repo, data):
    try:
        return _derive(repo, ResolutionInput.model_validate(data))
    except KeyError as exc:
        raise ResolutionUnavailable('UNKNOWN: missing artifact ' + str(exc)) from exc


def _derive(repo, data):
    dependencies = {}
    def get(ref):
        value = repo.get(ref); dependencies[ref] = value
        return value
    plan = get(data.plan.ref)
    if plan.digest != data.plan.sha256: raise ValueError('pinned artifact digest mismatch')
    if plan.frozen_at is None: raise ValueError('frozen plan required')
    tp.validate_admission(plan, get, freezing=True)
    if data.outcome not in plan.outcome_categories: raise ValueError('outcome absent from frozen plan')
    if data.predecessor:
        if get(data.predecessor.ref).digest != data.predecessor.sha256: raise ValueError('pinned artifact digest mismatch')
    group = get(plan.competing_set.ref)
    named = [get(m) for m in group.members if isinstance(m, Ref)]
    arms = [a.id for a in plan.arms]
    samples, used = [], set()
    for submitted in data.evidence:
        if submitted.arm not in arms: raise ValueError('unknown arm')
        # Apply corrections before scoping; an old link moved elsewhere cannot qualify.
        def all_records(name):
            values = repo.all(name)
            if name == 'EvidenceArm':
                heads = [get(v.ref) for v in er.heads(values) if v.evidence.ref == submitted.evidence.ref]
                return [v for v in heads if v.plan == data.plan and v.arm == submitted.arm and v.evidence == submitted.evidence]
            if name == 'HypothesisContext':
                return [v for v in er.heads(values) if v.hypothesis.ref in {h.ref for h in named}]
            return values
        scoped = SimpleNamespace(get=get, all=all_records)
        roles = []
        for hyp in named:
            result = er.compute(scoped, submitted.evidence, pin(hyp))
            if result['status'] == 'UNKNOWN': raise ResolutionUnavailable('UNKNOWN: TEST_RESULT required: ' + str(result['detail']))
            if result['status'] == 'INTEGRITY_FAILURE': raise ValueError('INTEGRITY_FAILURE: ' + str(result['detail']))
            if result['role'] != 'TEST_RESULT': raise ValueError('TEST_RESULT required: ' + str(result['role']))
            roles.append(RoleCheck(hypothesis=pin(hyp), link=result['selected_link'], role=result['role'], reason=result['reason']))
        link = get(roles[0].link.ref); clip = get(link.clip.ref)
        unit = ('run:' + get(link.run.ref).id if roles[0].reason == 'POST_FREEZE_RUN'
            else 'source:' + content_identity(get, clip.media, clip.ingestion))
        if unit in used: raise ValueError('duplicate sample unit')
        used.add(unit)
        samples.append(CountedSample(**submitted.model_dump(), unit=unit, roles=tuple(roles)))
    if len({s.evidence.ref.id for s in samples}) != len(samples):
        raise ValueError('duplicate sample unit: repeated Evidence identity')
    design = plan.sample_design
    if design and data.decision_reason is None: raise ValueError('decision reason required for sample design')
    counts = [ArmCount(arm=arm, count=sum(s.arm == arm for s in samples)) for arm in arms]
    minimum = design.n_per_arm if design and design.n_per_arm else 1
    if any(c.count < minimum for c in counts): raise ResolutionUnavailable('UNKNOWN: insufficient samples per arm')
    if design and design.stopping_rule:
        stop = data.stopping
        if stop is None: raise ValueError('stopping declaration required')
        if len({p.ref for p in stop.samples}) != len(stop.samples):
            raise ValueError('duplicate stopping sample reference')
        if (not stop.met or stop.author != data.author or stop.plan != data.plan or stop.rule != design.stopping_rule
                or sorted(stop.arms) != sorted(arms) or sorted((p.ref.kind, p.ref.id, p.ref.revision, p.sha256) for p in stop.samples)
                != sorted((s.evidence.ref.kind, s.evidence.ref.id, s.evidence.ref.revision, s.evidence.sha256) for s in data.evidence)):
            raise ValueError('stopping declaration mismatch')
    elif data.stopping is not None: raise ValueError('frozen design has no stopping rule')
    states = []
    for member in group.members:
        if isinstance(member, Ref):
            status = 'INDETERMINATE' if data.mode == 'INDETERMINATE' else (
                'RETAINED' if data.outcome in plan.predictions[member.id] else 'ELIMINATED')
            states.append(MemberState(member=pin(get(member)), status=status))
        else: states.append(MemberState(member='RESIDUAL', status='RETAINED'))
    # Pin transitive closure as well as every context actually consulted by the role query.
    from .persistence import refs_in
    pending = list(dependencies.values())
    while pending:
        for ref in refs_in(pending.pop()):
            if ref not in dependencies: pending.append(get(ref))
    return dict(states=tuple(states), samples=tuple(samples), counts=tuple(counts),
        dependencies=tuple(pin(v) for v in er.ordered(dependencies.values())),
        unpredicted=not any(data.outcome in plan.predictions[h.id] for h in named),
        residual_present=any(not isinstance(m, Ref) for m in group.members),
        input_sha256=sha256(canonicalize(data.model_dump(mode='json'))).hexdigest(),
        rule_version='resolution-v1', tool_version=__version__)


def prepare(repo, data, author):
    data = ResolutionInput.model_validate(data)
    if data.author != author: raise ValueError('author declaration mismatch')
    event = ResolutionEvent(**data.model_dump(), created_at=now(), **derive(repo, data))
    event._timestamp_receipt = _timestamp_receipt(event)
    return event


def record(repo, data, author):
    event = prepare(repo, data, author)
    repo.put(event)
    return event


def validate_admission(event, repo):
    expected = ResolutionEvent(**human_input(event).model_dump(), created_at=event.created_at,
        **derive(repo, human_input(event)))
    if event.model_dump(include=DERIVED) != expected.model_dump(include=DERIVED):
        raise ValueError('computed resolution mismatch; prepare again against current context')
    if not hmac.compare_digest(event._timestamp_receipt, _timestamp_receipt(event)):
        raise ValueError('created_at is application recorded; prepare the resolution before admission')


def replay(repo, event):
    """Recompute from the captured dependency universe, never later lineage heads."""
    event = ResolutionEvent.model_validate(event)
    records = {}
    for p in event.dependencies:
        value = repo.get(p.ref)
        if value.digest != p.sha256: raise ValueError('pinned artifact digest mismatch')
        records[p.ref] = value
    captured = SimpleNamespace(get=records.__getitem__, all=lambda name: [v for v in records.values() if v.ref.kind == name])
    expected = ResolutionEvent(**human_input(event).model_dump(), created_at=event.created_at,
        **derive(captured, human_input(event)))
    if expected.model_dump(include=DERIVED) != event.model_dump(include=DERIVED): raise ValueError('computed resolution mismatch')
    return expected.model_dump(mode='json', include=DERIVED)


def roots(repo, clips):
    clips = tuple(clips)
    media = {c.media for c in clips}
    plans = set(tp.roots(repo, clips))
    events = repo.all('ResolutionEvent')
    ids = {e.id for e in events if e.plan.ref in plans or any(repo.get(s.evidence.ref).media in media for s in e.evidence)}
    return [e.ref for e in events if e.id in ids]


def clip_records(repo, clip):
    return {'resolutions': [repo.get(ref).model_dump(mode='json') for ref in roots(repo, (clip,))]}
