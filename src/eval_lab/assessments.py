"""Private human records: intent-free measurement and pinned acceptability."""
from typing import Annotated, Literal
from pydantic import BaseModel, Field, model_validator
from . import __version__
from .domain import Artifact, ARTIFACT_TYPES, Dimension
from .intent_v2 import CheckedValue, Pin, Text, kind, predecessor


def raw_payload(value):
    """Preserve injected copy fields, including nested ones, before serialization."""
    if isinstance(value, BaseModel):
        return raw_payload(dict(value.__dict__) | (value.__pydantic_extra__ or {}))
    if isinstance(value, dict):
        if "kind" in value and "id" in value and "revision" not in value:
            raise ValueError("pins require an explicit revision")
        return {k: raw_payload(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return tuple(raw_payload(v) for v in value)
    return value


class HumanRecord(Artifact, CheckedValue):
    id: Text
    media: Pin
    author: Text
    predecessor: Pin | None = None
    revision_reason: Text | None = None
    tool_version: Text = __version__

    @model_validator(mode="before")
    @classmethod
    def revalidate_copies(cls, value):
        return raw_payload(value)

    @model_validator(mode="after")
    def history_contract(self):
        predecessor(self)
        kind(self.media, "MediaAsset")
        if self.revision > 1 and self.revision_reason is None:
            raise ValueError("revision reason required")
        return self


Seconds = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class TechnicalObservation(HumanRecord):
    dimension: Dimension
    deviation: Literal["NONE", "MINOR", "MATERIAL", "SEVERE", "CATASTROPHIC", "UNKNOWN"]
    span: tuple[Seconds, Seconds]
    evidence: tuple[Pin, ...]
    viewing_profile: Literal["FEED", "STUDIO"]

    @model_validator(mode="after")
    def measurement_contract(self):
        for p in self.evidence: kind(p, "Evidence")
        if self.span[0] > self.span[1]: raise ValueError("span must be ordered")
        if not self.evidence and self.deviation != "UNKNOWN":
            raise ValueError("missing evidence requires UNKNOWN")
        return self


class CriterionAssessment(HumanRecord):
    criterion_id: Text
    intent: Pin
    binding: Pin
    status: Literal["SATISFIED", "VIOLATED", "NOT_APPLICABLE", "UNKNOWN"]
    observations: tuple[Pin, ...]
    rationale: Text
    flags: tuple[Literal["CONTEMPORANEOUS_INTENT"], ...] = ()

    @model_validator(mode="after")
    def assessment_contract(self):
        kind(self.intent, "IntentSpecV2"); kind(self.binding, "IntentBinding")
        for p in self.observations: kind(p, "TechnicalObservation")
        return self


TYPES = (TechnicalObservation, CriterionAssessment)
COMMANDS = dict(zip(("technical-observation", "criterion-assessment"), TYPES))
ARTIFACT_TYPES.update({cls.__name__: cls for cls in TYPES})


def validate_admission(item, get, contexts):
    """State checks on the serialized writer connection; never infer a status."""
    if item.predecessor:
        old = get(item.predecessor.ref)
        if old.media != item.media: raise ValueError("record media is immutable")
        if isinstance(item, CriterionAssessment) and (old.intent, old.binding, old.criterion_id) != (item.intent, item.binding, item.criterion_id):
            raise ValueError("assessment context is immutable")
    if isinstance(item, TechnicalObservation):
        media = get(item.media.ref)
        if media.duration is None or item.span[1] > media.duration:
            raise ValueError("span exceeds media duration")
        if any(get(p.ref).media != item.media.ref for p in item.evidence):
            raise ValueError("evidence belongs to another media")
        return
    binding, intent = get(item.binding.ref), get(item.intent.ref)
    if binding.media != item.media or binding.intent != item.intent:
        raise ValueError("binding intent or media mismatch")
    if not any(c.binding == item.binding for c in contexts):
        raise ValueError("binding requires retained context")
    criterion = next((c for c in intent.criteria if c.id == item.criterion_id), None)
    if criterion is None: raise ValueError("criterion absent from pinned intent")
    observations = [get(p.ref) for p in item.observations]
    if any(o.media != item.media or o.dimension != criterion.dimension for o in observations):
        raise ValueError("observation media or dimension mismatch")
    if (not observations or any(o.deviation == "UNKNOWN" for o in observations)) and item.status != "UNKNOWN":
        raise ValueError("missing or UNKNOWN observations require UNKNOWN")
    excuse = item.status == "SATISFIED" and any(o.deviation in ("MATERIAL", "SEVERE", "CATASTROPHIC") for o in observations)
    if excuse:
        if not any(d.criterion_id == criterion.id and d.dimension == criterion.dimension for d in intent.expected_deviations):
            raise ValueError("material excuse requires expected deviation")
        if binding.provenance not in ("SEALED", "CONTEMPORANEOUS"):
            raise ValueError("material excuse requires qualifying intent provenance")
    expected_flags = ("CONTEMPORANEOUS_INTENT",) if excuse and binding.provenance == "CONTEMPORANEOUS" else ()
    if item.flags != expected_flags: raise ValueError("contemporaneous flag mismatch")


def roots(repo, media, bindings):
    """Exact media and retained creative context only, including prior revisions."""
    return [x.ref for cls in TYPES for x in repo.all(cls.__name__) if x.media in media and
        (isinstance(x, TechnicalObservation) or x.binding in bindings)]


def clip_records(repo, clip):
    from .generation import binding_history, pin
    refs = roots(repo, {pin(repo.get(clip.media))}, {pin(b) for b in binding_history(repo, clip)})
    return {key: [repo.get(r).model_dump(mode="json") for r in refs if r.kind == cls.__name__]
        for key, cls in zip(("technical_observations", "criterion_assessments"), TYPES)}


def record(workspace, clip_id, author, command, data):
    if not isinstance(data, dict): raise ValueError("record form must be a JSON object")
    if "tool_version" in data: raise ValueError("tool_version is application recorded")
    item = COMMANDS[command].model_validate(data)
    clip = workspace.clip(clip_id)
    if item.author != author: raise ValueError("author declaration mismatch")
    if item.media.ref != clip.media: raise ValueError("record media differs from clip")
    workspace.verify_clip(clip)
    workspace.repo.put(item)
    return item
