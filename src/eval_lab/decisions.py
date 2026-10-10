"""Private human policies and verdicts over exact, immutable evaluation inputs."""
from hashlib import sha256
from typing import Annotated, Literal
import json
import sqlite3
from pydantic import Field, model_validator
from . import __version__
from .domain import Artifact, ARTIFACT_TYPES, Dimension, Ref
from .intent_v2 import CheckedValue, Pin, Text, Provenance, UseContext, kind, predecessor, pins_in
from .assessments import HumanRecord, raw_payload
from .pilot_domain import Hash
from .canonical_json import canonicalize

Action = Literal["SHIP", "HOLD", "REPAIR", "REGENERATE", "INVESTIGATE"]
Deviation = Literal["NONE", "MINOR", "MATERIAL", "SEVERE", "CATASTROPHIC"]
Salvage = Literal["POST_FIXABLE", "EXPENSIVE_POST_FIX", "REGENERATE", "UNKNOWN"]
Priority = Literal["MUST", "SHOULD", "COULD", "WONT"]
Status = Literal["SATISFIED", "VIOLATED", "NOT_APPLICABLE", "UNKNOWN"]
ORDER = ("NONE", "MINOR", "MATERIAL", "SEVERE", "CATASTROPHIC")


class Condition(CheckedValue):
    priority_status: tuple[Priority, Status] | None = None
    worst: tuple[Dimension, Deviation] | None = None
    provenance: Annotated[tuple[Provenance, ...], Field(min_length=1)] | None = None
    salvage_guess: Salvage | None = None
    unresolved_at_least: Annotated[int, Field(strict=True, ge=0)] | None = None
    unknown_must: Annotated[bool, Field(strict=True)] | None = None


class Rule(CheckedValue):
    id: Text
    when: Condition = Condition()
    action: Action


class DecisionPolicy(Artifact, CheckedValue):
    id: Text
    author: Text
    version: Annotated[int, Field(strict=True, ge=1)]
    scope: UseContext
    rules: tuple[Rule, ...]
    predecessor: Pin | None = None
    revision_reason: Text | None = None
    tool_version: Text = __version__

    @model_validator(mode="before")
    @classmethod
    def copies(cls, value):
        return raw_payload(value)

    @model_validator(mode="after")
    def policy_contract(self):
        predecessor(self)
        if self.revision > 1 and self.revision_reason is None: raise ValueError("revision reason required")
        if self.version != self.revision: raise ValueError("policy version must equal revision")
        if len({r.id for r in self.rules}) != len(self.rules): raise ValueError("unique rule IDs required")
        defaults = [n for n, r in enumerate(self.rules) if r.when == Condition()]
        if not self.rules or defaults != [len(self.rules)-1]: raise ValueError("exactly one final default required")
        return self


class Override(CheckedValue):
    action: Action
    reason: Text
    author: Text


class Relevance(CheckedValue):
    hypothesis: Pin
    criterion_ids: tuple[Text, ...]
    rationale: Text


class Integrity(CheckedValue):
    worst: Deviation | Literal["UNKNOWN"]
    unknown: Annotated[bool, Field(strict=True)]


class Trace(CheckedValue):
    policy_id: Text
    policy_version: Annotated[int, Field(strict=True, ge=1)]
    rule_id: Text
    action: Action
    inputs_sha256: Hash


class VerdictInput(HumanRecord):
    clip: Pin
    intent: Pin
    binding: Pin
    policy: Pin
    assessments: tuple[Pin, ...]
    observations: tuple[Pin, ...]
    hypotheses: tuple[Relevance, ...]
    intent_fulfillment: Literal["ACCEPT", "REVISE", "REJECT", "UNKNOWN"]
    salvage_guess: Salvage
    override: Override | None = None

    @model_validator(mode="after")
    def history_contract(self):
        # Preview forms describe TerminalVerdict history, not a separate lineage.
        kind(self.media, "MediaAsset")
        if self.revision == 1:
            if self.predecessor is not None: raise ValueError("initial revision cannot have a predecessor")
        elif self.predecessor is None or self.predecessor.ref != Ref(kind="TerminalVerdict", id=self.id, revision=self.revision-1):
            raise ValueError("predecessor must pin the immediate same-kind, same-ID revision")
        if self.revision > 1 and self.revision_reason is None: raise ValueError("revision reason required")
        return self

    @model_validator(mode="after")
    def input_contract(self):
        for p, name in ((self.clip, "PilotClip"), (self.intent, "IntentSpecV2"),
                        (self.binding, "IntentBinding"), (self.policy, "DecisionPolicy")):
            kind(p, name)
        for p in self.assessments: kind(p, "CriterionAssessment")
        for p in self.observations: kind(p, "TechnicalObservation")
        for r in self.hypotheses: kind(r.hypothesis, "Hypothesis")
        if len({r.hypothesis.ref.id for r in self.hypotheses}) != len(self.hypotheses):
            raise ValueError("duplicate hypothesis identity")
        if len(set(self.observations)) != len(self.observations): raise ValueError("duplicate observation pin")
        return self


class TerminalVerdict(VerdictInput):
    technical_integrity: dict[Dimension, Integrity]
    decision: Trace
    flags: tuple[Literal["CONTEMPORANEOUS_INTENT"], ...]


TYPES = (DecisionPolicy, TerminalVerdict)
ARTIFACT_TYPES.update({cls.__name__: cls for cls in TYPES})


def matches(condition, inputs):
    """Typed conjunction, with priority and status paired on one criterion."""
    if condition.priority_status and list(condition.priority_status) not in inputs["criteria"]: return False
    if condition.worst:
        dimension, minimum = condition.worst
        worst = inputs["integrity"][dimension]["worst"]
        if worst == "UNKNOWN" or ORDER.index(worst) < ORDER.index(minimum): return False
    if condition.provenance and inputs["provenance"] not in condition.provenance: return False
    if condition.salvage_guess is not None and inputs["salvage_guess"] != condition.salvage_guess: return False
    if condition.unresolved_at_least is not None and inputs["unresolved"] < condition.unresolved_at_least: return False
    if condition.unknown_must is not None and inputs["unknown_must"] != condition.unknown_must: return False
    return True


def derive(item, get, contexts):
    """Read pinned declarations; never revise evidence or select a policy implicitly."""
    for p in pins_in(item):
        if get(p.ref).digest != p.sha256: raise ValueError("pinned artifact digest mismatch")
    clip, intent, binding, policy = (get(p.ref) for p in (item.clip, item.intent, item.binding, item.policy))
    if clip.media != item.media.ref: raise ValueError("clip media mismatch")
    if binding.intent != item.intent or binding.media != item.media: raise ValueError("assessment context mismatch: binding")
    if not any(c.binding == item.binding for c in contexts): raise ValueError("binding requires retained context")
    if policy.scope != intent.use_context: raise ValueError("policy scope mismatch")
    if item.predecessor:
        old = get(item.predecessor.ref)
        if (old.clip, old.media, old.intent, old.binding) != (item.clip, item.media, item.intent, item.binding):
            raise ValueError("verdict context is immutable")
    observations = [get(p.ref) for p in item.observations]
    if any(o.media != item.media for o in observations): raise ValueError("observation media mismatch")
    criteria = {c.id: c for c in intent.criteria}
    selected = {}
    for p in item.assessments:
        a = get(p.ref)
        if (a.intent, a.binding, a.media) != (item.intent, item.binding, item.media): raise ValueError("assessment context mismatch")
        if a.criterion_id not in criteria: raise ValueError("criterion absent from pinned intent")
        if a.criterion_id in selected: raise ValueError("one assessment per criterion required")
        if not set(a.observations) <= set(item.observations): raise ValueError("assessment observations outside retained inputs")
        selected[a.criterion_id] = a
    integrity = {}
    for dimension in Dimension:
        values = [o.deviation for o in observations if o.dimension == dimension]
        known = [v for v in values if v != "UNKNOWN"]
        integrity[dimension.value] = dict(worst=max(known, key=ORDER.index) if known else "UNKNOWN",
            unknown=not values or "UNKNOWN" in values)
    unknown_must = False
    statuses = []
    for cid, c in sorted(criteria.items()):
        a = selected.get(cid)
        unknown = a is None or a.status == "UNKNOWN" or not a.observations or any(get(p.ref).deviation == "UNKNOWN" for p in a.observations)
        unknown_must |= c.priority == "MUST" and unknown
        statuses.append([c.priority, a.status if a else "UNKNOWN"])
    unresolved = 0
    for r in item.hypotheses:
        h = get(r.hypothesis.ref)
        if len(set(r.criterion_ids)) != len(r.criterion_ids) or set(r.criterion_ids) - criteria.keys(): raise ValueError("unknown relevance criterion or duplicate")
        if h.intent != clip.intent: raise ValueError("hypothesis legacy intent mismatch")
        if any(get(e).media != item.media.ref for e in h.supporting_evidence + h.contradicting_evidence): raise ValueError("hypothesis evidence media mismatch")
        unresolved += bool(r.criterion_ids) and h.status == "unresolved"
    inputs = dict(criteria=statuses, integrity=integrity, provenance=binding.provenance,
        salvage_guess=item.salvage_guess, unresolved=unresolved, unknown_must=unknown_must)
    rule = next(r for r in policy.rules if matches(r.when, inputs))
    material = any(o.deviation in ORDER[2:] for o in observations)
    if rule.action == "SHIP" and unknown_must: raise ValueError("SHIP requires known MUST evidence")
    if rule.action == "SHIP" and material and binding.provenance in ("RECONSTRUCTED", "PROMPT_ONLY"):
        raise ValueError("SHIP cannot excuse material deviation with weak intent")
    flags = ("CONTEMPORANEOUS_INTENT",) if any(a.flags for a in selected.values()) or (
        rule.action == "SHIP" and material and binding.provenance == "CONTEMPORANEOUS") else ()
    # Only set-like selections are sorted. Source digests bind original bytes,
    # including float-valued evidence, without putting floats in this envelope.
    sources = {name: getattr(item, name).model_dump(mode="json") for name in ("clip", "media", "intent", "binding", "policy")}
    for name in ("assessments", "observations"):
        sources[name] = sorted((p.model_dump(mode="json") for p in getattr(item, name)), key=canonicalize)
    relevance = [r.model_dump(mode="json") | {"criterion_ids": sorted(r.criterion_ids)} for r in item.hypotheses]
    envelope = dict(schema_version=1, sources=sources, policy_id=policy.id, policy_version=policy.version,
        inputs=inputs, author=item.author, intent_fulfillment=item.intent_fulfillment,
        relevance=sorted(relevance, key=canonicalize))
    return dict(technical_integrity=integrity, flags=flags, decision=dict(policy_id=policy.id,
        policy_version=policy.version, rule_id=rule.id, action=rule.action, inputs_sha256=input_digest(envelope)))


def input_digest(envelope):
    return sha256(canonicalize(envelope)).hexdigest()


def validate_admission(item, get, contexts):
    if isinstance(item, TerminalVerdict):
        expected = derive(item, get, contexts)
        actual = item.model_dump(mode="json", include={"technical_integrity", "flags", "decision"})
        if canonicalize(actual) != canonicalize(json.loads(json.dumps(expected))): raise ValueError("derived verdict mismatch")


def preview(repo, data):
    item = VerdictInput.model_validate(data)
    return derive(item, repo.get, repo.all("BindingContext"))


def preview_file(root, clip_id, data):
    """Read-only SQLite path: never initialize a workspace or write a verdict."""
    item = VerdictInput.model_validate(data)
    if item.clip.ref.id != clip_id: raise ValueError("verdict clip differs from requested clip")
    with sqlite3.connect((root / "pilot.sqlite").resolve().as_uri()+"?mode=ro", uri=True) as db:
        def get(ref):
            row = db.execute("SELECT payload,sha256 FROM artifacts WHERE kind=? AND id=? AND revision=?", (ref.kind, ref.id, ref.revision)).fetchone()
            if row is None: raise KeyError(ref)
            value = ARTIFACT_TYPES[ref.kind].model_validate_json(row[0])
            if value.digest != row[1]: raise ValueError("snapshot integrity failure")
            return value
        contexts = [get(Ref(kind="BindingContext", id=id, revision=rev)) for id, rev in db.execute("SELECT id,revision FROM artifacts WHERE kind='BindingContext'")]
        return derive(item, get, contexts)


def record(workspace, author, command, data, clip_id=None):
    if not isinstance(data, dict): raise ValueError("record form must be a JSON object")
    if "tool_version" in data: raise ValueError("tool_version is application recorded")
    cls = DecisionPolicy if command == "decision-policy" else TerminalVerdict
    item = cls.model_validate(data)
    if item.author != author: raise ValueError("author declaration mismatch")
    if isinstance(item, TerminalVerdict):
        clip = workspace.repo.get(item.clip.ref)
        if clip.id != clip_id: raise ValueError("verdict clip differs from requested clip")
        workspace.verify_clip(clip)
    workspace.repo.put(item)
    return item


def roots(repo, clips):
    media = {(c.id, c.media) for c in clips}
    return [x.ref for x in repo.all("TerminalVerdict") if (x.clip.ref.id, x.media.ref) in media]


def clip_records(repo, clip):
    return {"terminal_verdicts": [repo.get(r).model_dump(mode="json") for r in roots(repo, (clip,))]}
