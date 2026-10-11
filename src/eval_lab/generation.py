"""Private declared generation lifecycle; chronology never establishes quality."""
from datetime import datetime, timezone
import json
from typing import Annotated, Literal
from uuid import uuid4
from pydantic import BeforeValidator, Field, JsonValue, model_validator
from . import __version__
from .domain import Artifact, ARTIFACT_TYPES, Ref
from .intent_v2 import (CheckedValue, Pin, Text, Instant, kind, predecessor,
    IntentBinding, SealEvidence, PlanEvidence, content_identity)


def now():
    return datetime.now(timezone.utc)


# CheckedValue unpacks arrays to tuples; normalize only these new JSON boundaries.
JSON = Annotated[JsonValue, BeforeValidator(lambda v: json.loads(json.dumps(v, allow_nan=False)))]


def pin(item):
    return Pin(ref=item.ref, sha256=item.digest)


class Event(Artifact, CheckedValue):
    id: Text = Field(default_factory=lambda: uuid4().hex)
    revision: int = Field(default=1, strict=True, ge=1, le=1)
    tool_version: Text = __version__


class GenerationPlan(Event):
    family_id: Text
    arm: Text
    varied_factor: Text
    controlled_factors: JSON
    prompt: Text
    model: Text
    model_version_string: Text
    settings: JSON
    seed: Annotated[int, Field(strict=True)] | None
    n_planned: int = Field(strict=True, gt=0)
    intent_revision_ids: tuple[Pin, ...]
    planned_at: Instant
    notes: str

    @model_validator(mode="after")
    def contract(self):
        for p in self.intent_revision_ids: kind(p, "IntentSpecV2", "IntentSpec")
        if len(set(p.ref for p in self.intent_revision_ids)) != len(self.intent_revision_ids):
            raise ValueError("intent pins must be unique")
        if self.planned_at != self.created_at: raise ValueError("plan event times must agree")
        return self


class ClipOrigin(Event):
    clip: Pin
    origin: Literal["PLANNED", "FOUND"]
    plan: Pin | None = None

    @model_validator(mode="after")
    def contract(self):
        kind(self.clip, "PilotClip")
        if self.plan: kind(self.plan, "GenerationPlan")
        if (self.origin == "PLANNED") != (self.plan is not None): raise ValueError("origin/plan mismatch")
        if self.clip.ref.revision != 1: raise ValueError("origin requires original clip")
        return self


class FirstView(Event):
    media: Pin
    registration: Pin

    @model_validator(mode="after")
    def contract(self):
        kind(self.media, "MediaAsset"); kind(self.registration, "MediaIngestion")
        return self


class Rejection(CheckedValue):
    ref: Ref
    reason: Text


class SelectionLog(Artifact, CheckedValue):
    dataset: Pin
    candidates_considered: tuple[Pin, ...] = Field(min_length=1)
    rejected: tuple[Rejection, ...]
    random_draw: JSON = None
    kept: tuple[Ref, ...]
    predecessor: Pin | None = None
    tool_version: Text = __version__

    @model_validator(mode="after")
    def contract(self):
        predecessor(self); kind(self.dataset, "PilotDataset")
        for p in self.candidates_considered: kind(p, "PilotClip")
        candidates = [p.ref for p in self.candidates_considered]
        if len(set(candidates)) != len(candidates): raise ValueError("candidates must be unique")
        partition = list(self.kept) + [r.ref for r in self.rejected]
        if len(set(partition)) != len(partition) or set(partition) != set(candidates):
            raise ValueError("kept/rejected must partition candidates")
        return self


class BindingContext(Event):
    binding: Pin
    origin: Pin | None = None
    seal: Pin | None = None
    view: Pin | None = None

    @model_validator(mode="after")
    def contract(self):
        for p, name in ((self.binding, "IntentBinding"), (self.origin, "ClipOrigin"),
                        (self.seal, "SealRecord"), (self.view, "FirstView")):
            if p: kind(p, name)
        return self


TYPES = (GenerationPlan, ClipOrigin, FirstView, SelectionLog, BindingContext)
ARTIFACT_TYPES.update({cls.__name__: cls for cls in TYPES})


class FirstViewExists(ValueError):
    pass


def identity(get, item):
    return content_identity(get, item.media.ref, item.registration.ref)


def chronology(get, registration, origin, seal, view):
    plan = get(origin.plan.ref) if origin and origin.plan else None
    return dict(seal=SealEvidence(intent=seal.intent, sealed_at=seal.sealed_at) if seal else None,
        plan=PlanEvidence(intents=plan.intent_revision_ids, registration=registration,
            planned_at=plan.planned_at) if plan and plan.intent_revision_ids else None,
        first_view_at=view.created_at if view else None)


def validate_admission(item, get, history):
    """State-dependent checks run on the repository's serialized writer connection."""
    if isinstance(item, ClipOrigin) and any(x.clip.ref.id == item.clip.ref.id for x in history):
        raise ValueError("clip already has an origin")
    if isinstance(item, FirstView):
        source = identity(get, item)
        if any(identity(get, x) == source for x in history): raise FirstViewExists("first access already recorded")
    if isinstance(item, SelectionLog):
        if not {p.ref for p in item.candidates_considered} <= set(get(item.dataset.ref).clips):
            raise ValueError("candidate outside pinned dataset")
        if item.predecessor and get(item.predecessor.ref).dataset.ref.id != item.dataset.ref.id:
            raise ValueError("selection dataset is immutable")
    if isinstance(item, BindingContext):
        b = get(item.binding.ref)
        origin, seal, view = (get(p.ref) if p else None for p in (item.origin, item.seal, item.view))
        if origin:
            clip = get(origin.clip.ref)
            if (clip.media, clip.ingestion) != (b.media.ref, b.registration.ref):
                raise ValueError("context origin anchors mismatch")
            if b.origin != ("GENERATED" if origin.origin == "PLANNED" else "FOUND"):
                raise ValueError("context binding origin mismatch")
        if view and identity(get, view) != identity(get, b): raise ValueError("context view identity mismatch")
        if seal and seal.intent != b.intent: raise ValueError("context seal intent mismatch")
        expected = chronology(get, b.registration, origin, seal, view)
        if any(getattr(b, name) != value for name, value in expected.items()):
            raise ValueError("binding differs from stored chronology")
        if any(x.binding == item.binding for x in history): raise ValueError("binding already has context")


def exact(repo, text, default="IntentSpecV2"):
    if not isinstance(text, str): raise ValueError("use an exact ID@REV string")
    name, marker, revision = text.rpartition("@")
    if not marker or not revision.isdecimal(): raise ValueError("use an exact ID@REV")
    prefix, colon, rest = name.partition(":")
    target = prefix if colon and prefix in ("IntentSpec", "IntentSpecV2") else default
    try: return pin(repo.get(Ref(kind=target, id=rest if colon and target == prefix else name, revision=int(revision))))
    except KeyError as exc: raise ValueError("missing exact reference: " + text) from exc


def supplied(data, allowed):
    if not isinstance(data, dict) or set(data) - set(allowed):
        raise ValueError("unsupported fields; event time, provenance and pins are application derived")


def require_arrays(data, *fields):
    for field in fields:
        if not isinstance(data.get(field), list):
            raise ValueError(f"{field} must be a JSON array")


def record_plan(repo, data):
    supplied(data, set(GenerationPlan.model_fields) - {"revision", "schema_version", "created_at", "planned_at", "tool_version"})
    require_arrays(data, "intent_revision_ids")
    stamp = now()
    item = GenerationPlan(**(data | {"intent_revision_ids": tuple(exact(repo, x) for x in data["intent_revision_ids"])}),
        created_at=stamp, planned_at=stamp)
    repo.put(item)
    return item


def registration_choice(repo, plan_id, intent_id):
    plan = repo.get(Ref(kind="GenerationPlan", id=plan_id)) if plan_id is not None else None
    choice = exact(repo, intent_id) if intent_id is not None else None
    if plan:
        if choice and choice not in plan.intent_revision_ids: raise ValueError("intent is not listed in plan")
        if not choice and len(plan.intent_revision_ids) > 1: raise ValueError("multiple intents require --intent ID@REV")
        if not choice and plan.intent_revision_ids: choice = plan.intent_revision_ids[0]
    return plan, choice


def record_origin(repo, clip, plan):
    item = ClipOrigin(clip=pin(clip), origin="PLANNED" if plan else "FOUND", plan=pin(plan) if plan else None, created_at=now())
    repo.put(item)
    return item


def first_access(workspace, clip):
    workspace.verify_clip(clip)  # No event if bytes are unavailable or corrupt.
    repo = workspace.repo
    item = FirstView(media=pin(repo.get(clip.media)), registration=pin(repo.get(clip.ingestion)), created_at=now())
    def existing():
        return next((x for x in repo.all("FirstView") if identity(repo.get, x) == identity(repo.get, item)), None)
    old = existing()
    if old: return old
    try: repo.put(item)
    except FirstViewExists: return existing()
    return item


def binding_history(repo, clip):
    source = content_identity(repo.get, clip.media, clip.ingestion)
    return sorted((b for b in repo.all("IntentBinding") if identity(repo.get, b) == source), key=lambda b: b.revision)


def bind_intent(repo, clip, intent, prompt_only=False):
    kind(intent, "IntentSpecV2", "IntentSpec")
    if prompt_only and intent.ref.kind != "IntentSpecV2": raise ValueError("PROMPT_ONLY requires v2 intent")
    history = binding_history(repo, clip); prior = history[-1] if history else None
    media = prior.media if prior else pin(repo.get(clip.media))
    registration = prior.registration if prior else pin(repo.get(clip.ingestion))
    origins = [o for o in repo.all("ClipOrigin") if o.clip.ref.id == clip.id]
    context = next((x for x in repo.all("BindingContext") if prior and x.binding == pin(prior)), None)
    origin = repo.get(context.origin.ref) if context and context.origin else None
    if prior is None: origin = origins[0] if origins else None
    source = content_identity(repo.get, media.ref, registration.ref)
    seals = sorted((s for s in repo.all("SealRecord") if s.intent == intent), key=lambda s: (s.sealed_at, s.ref.kind, s.id, s.revision))
    seal = seals[0] if seals else None
    view = next((v for v in repo.all("FirstView") if identity(repo.get, v) == source), None)
    item = IntentBinding(id=prior.id if prior else uuid4().hex, revision=prior.revision+1 if prior else 1,
        created_at=now(), predecessor=pin(prior) if prior else None, intent=intent, media=media,
        registration=registration, registered_at=repo.get(registration.ref).created_at,
        origin=prior.origin if prior else ("GENERATED" if origin and origin.origin == "PLANNED" else "FOUND"),
        declaration="PROMPT_ONLY" if prompt_only else None, **chronology(repo.get, registration, origin, seal, view))
    repo.put(item)
    try:
        repo.put(BindingContext(binding=pin(item), origin=pin(origin) if origin else None,
            seal=pin(seal) if seal else None, view=pin(view) if view else None, created_at=now()))
    except Exception as exc:
        raise ValueError(f"binding {item.id}@{item.revision} retained; context not stored: {exc}") from exc
    return item


def record_selection(repo, dataset, data):
    supplied(data, {"id", "candidates_considered", "rejected", "random_draw", "kept"})
    require_arrays(data, "candidates_considered", "rejected", "kept")
    for rejection in data["rejected"]:
        if not isinstance(rejection, dict) or set(rejection) != {"ref", "reason"}:
            raise ValueError("rejected entries must be objects with exactly ref and reason")
    try: prior = repo.latest(Ref(kind="SelectionLog", id=data["id"]))
    except KeyError: prior = None
    item = SelectionLog(id=data["id"], created_at=now(), dataset=pin(dataset),
        revision=prior.revision+1 if prior else 1, predecessor=pin(prior) if prior else None,
        candidates_considered=tuple(exact(repo, x, "PilotClip") for x in data["candidates_considered"]),
        rejected=tuple(Rejection(**(r | {"ref": exact(repo, r["ref"], "PilotClip").ref})) for r in data["rejected"]),
        kept=tuple(exact(repo, x, "PilotClip").ref for x in data["kept"]), random_draw=data.get("random_draw"))
    repo.put(item)
    return item


def lifecycle_roots(repo, identities, datasets=()):
    roots = []
    for name in ("ClipOrigin", "FirstView", "BindingContext", "SelectionLog", "DerivativeManifest"):
        for item in repo.all(name):
            if isinstance(item, SelectionLog):
                clips = [repo.get(p.ref) for p in item.candidates_considered]
                include = item.dataset.ref.id in datasets or any(content_identity(repo.get, c.media, c.ingestion) in identities for c in clips)
            elif name == "DerivativeManifest":
                include = content_identity(repo.get, item.media, item.ingestion) in identities
            elif isinstance(item, ClipOrigin):
                c = repo.get(item.clip.ref); include = content_identity(repo.get, c.media, c.ingestion) in identities
            else:
                anchor = repo.get(item.binding.ref) if isinstance(item, BindingContext) else item
                include = identity(repo.get, anchor) in identities
            if include: roots.append(item.ref)
    return roots


def audit(repo, clip):
    from .persistence import refs_in
    history = binding_history(repo, clip)
    roots = lifecycle_roots(repo, {content_identity(repo.get, clip.media, clip.ingestion)}) + [b.ref for b in history]
    seen = {}
    while roots:
        ref = roots.pop()
        if ref not in seen:
            item = repo.get(ref); seen[ref] = item
            roots.extend(refs_in(item))
    for seal in repo.all("SealRecord"):
        if seal.intent.ref in seen and seen[seal.intent.ref].digest == seal.intent.sha256: seen[seal.ref] = seal
    origin = next((o.origin for o in repo.all("ClipOrigin") if o.clip.ref.id == clip.id), "UNKNOWN")
    return dict(origin=origin, provenance=history[-1].provenance if history else "UNKNOWN", quality_verdict="UNKNOWN",
        lifecycle_records=[dict(ref=r.model_dump(), sha256=seen[r].digest, artifact=seen[r].model_dump(mode="json"))
            for r in sorted(seen, key=lambda r: (r.kind, r.id, r.revision))])
