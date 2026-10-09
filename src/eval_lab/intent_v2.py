"""Intent v2 and replayable local chronology; no generation or quality claims."""
from datetime import datetime, timezone
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, AfterValidator, model_validator
from .domain import Artifact, Value, Ref, Dimension, IntentSpec, ARTIFACT_TYPES
from .pilot_domain import Hash

Text = Annotated[str, Field(pattern=r"\S")]
Provenance = Literal["SEALED", "CONTEMPORANEOUS", "RECONSTRUCTED", "PROMPT_ONLY"]


def utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("event times require a timezone")
    return value.astimezone(timezone.utc)


Instant = Annotated[datetime, AfterValidator(utc)]


def unpack(value):
    """Revalidate nested copied models at constructors as well as repository admission."""
    if isinstance(value, BaseModel):
        return unpack(value.model_dump())
    if isinstance(value, dict):
        return {key: unpack(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return tuple(unpack(item) for item in value)
    return value


class CheckedValue(Value):
    model_config = ConfigDict(revalidate_instances="always")

    @model_validator(mode="before")
    @classmethod
    def revalidate_copies(cls, value):
        return unpack(value)


class Pin(CheckedValue):
    ref: Ref
    sha256: Hash


def kind(pin: Pin, *names: str):
    if pin.ref.kind not in names:
        raise ValueError("pin must reference " + " or ".join(names))


def predecessor(item):
    prior = item.predecessor
    if item.revision == 1:
        if prior is not None:
            raise ValueError("initial revision cannot have a predecessor")
    elif prior is None or prior.ref != Ref(kind=type(item).__name__, id=item.id, revision=item.revision-1):
        raise ValueError("predecessor must pin the immediate same-kind, same-ID revision")


class UseContext(CheckedValue):
    surface: Text
    audience: Text
    viewing_profile: Literal["FEED", "STUDIO"]


class CriterionV2(CheckedValue):
    id: Text
    dimension: Dimension
    priority: Literal["MUST", "SHOULD", "COULD", "WONT"]
    acceptance: Text
    rejection: Text
    tolerance: Text


class ExpectedDeviation(CheckedValue):
    dimension: Dimension
    description: Text
    criterion_id: Text


class IntentSpecV2(Artifact, CheckedValue):
    schema_version: Literal[2] = 2
    id: Text
    owner: Text
    objective: Text
    use_context: UseContext
    criteria: tuple[CriterionV2, ...] = Field(min_length=1)
    expected_deviations: tuple[ExpectedDeviation, ...] = ()
    revision_reason: Literal["SERENDIPITY", "CLARIFICATION", "CORRECTION", "SCOPE_CHANGE"]
    predecessor: Pin | None = None

    @model_validator(mode="after")
    def contract(self):
        predecessor(self)
        criteria = {c.id: c.dimension for c in self.criteria}
        if len(criteria) != len(self.criteria):
            raise ValueError("criterion IDs must be unique")
        if any(criteria.get(d.criterion_id) != d.dimension for d in self.expected_deviations):
            raise ValueError("expected deviation must reference a criterion of the same dimension")
        return self


class LegacyIntentView(CheckedValue):
    """Read-only compatibility view, never a rewritten v1 artifact."""
    source: IntentSpec

    @property
    def ref(self):
        return self.source.ref

    @property
    def digest(self):
        return self.source.digest

    @property
    def provenance(self) -> Provenance:
        return "RECONSTRUCTED"


class SealEvidence(CheckedValue):
    """Internal evidence seam, not an authenticated seal creation API."""
    intent: Pin
    sealed_at: Instant

    @model_validator(mode="after")
    def intent_kind(self):
        kind(self.intent, "IntentSpecV2", "IntentSpec")
        return self


class PlanEvidence(CheckedValue):
    intents: tuple[Pin, ...] = Field(min_length=1)
    registration: Pin
    planned_at: Instant

    @model_validator(mode="after")
    def pin_kinds(self):
        kind(self.registration, "MediaIngestion")
        for intent in self.intents:
            kind(intent, "IntentSpecV2", "IntentSpec")
        return self


class IntentBinding(Artifact, CheckedValue):
    schema_version: Literal[2] = 2
    id: Text
    intent: Pin
    media: Pin
    registration: Pin
    registered_at: Instant
    origin: Literal["FOUND", "GENERATED"]
    seal: SealEvidence | None = None
    plan: PlanEvidence | None = None
    first_view_at: Instant | None = None
    declaration: Literal["PROMPT_ONLY"] | None = None
    predecessor: Pin | None = None

    @model_validator(mode="after")
    def contract(self):
        predecessor(self)
        kind(self.intent, "IntentSpecV2", "IntentSpec")
        kind(self.media, "MediaAsset")
        kind(self.registration, "MediaIngestion")
        if self.registration.ref.revision != 1 or self.media.ref.revision != 1:
            raise ValueError("binding requires original registration/media anchors")
        if self.declaration and self.origin != "FOUND":
            raise ValueError("PROMPT_ONLY declaration requires FOUND content")
        return self

    @property
    def provenance(self) -> Provenance:
        return derive_provenance(self)


def derive_provenance(binding: IntentBinding) -> Provenance:
    """Pure, exact-revision classifier; absent facts never use the current clock."""
    if binding.intent.ref.kind == "IntentSpec":
        return "RECONSTRUCTED"
    if binding.declaration == "PROMPT_ONLY":
        return "PROMPT_ONLY"
    seal, plan = binding.seal, binding.plan
    if seal is None or seal.intent != binding.intent:
        return "RECONSTRUCTED"
    if (plan is not None and binding.intent in plan.intents
            and plan.registration == binding.registration
            and seal.sealed_at < plan.planned_at < binding.registered_at):
        return "SEALED"
    if binding.first_view_at is not None and seal.sealed_at < binding.first_view_at:
        return "CONTEMPORANEOUS"
    return "RECONSTRUCTED"


def content_identity(get, media: Ref, registration: Ref) -> str:
    """Conservative byte identity shared by admission and private snapshot roots."""
    if media.kind != "MediaAsset" or registration.kind != "MediaIngestion":
        raise ValueError("content identity requires media and registration")
    asset, ingestion = get(media), get(registration)
    if ingestion.media != media or ingestion.source_sha256 != asset.checksum:
        raise ValueError("registration/media identity mismatch")
    return ingestion.source_sha256


def pins_in(value):
    if isinstance(value, Pin):
        yield value
    elif isinstance(value, Value):
        for name in type(value).model_fields:
            yield from pins_in(getattr(value, name))
    elif isinstance(value, tuple):
        for item in value:
            yield from pins_in(item)


SUCCESSORS = {
    "SEALED": {"SEALED", "CONTEMPORANEOUS", "RECONSTRUCTED"},
    "CONTEMPORANEOUS": {"CONTEMPORANEOUS", "RECONSTRUCTED"},
    "RECONSTRUCTED": {"RECONSTRUCTED"},
    "PROMPT_ONLY": {"PROMPT_ONLY", "RECONSTRUCTED"},
}


def validate_admission(item, get, history):
    """Called under the repository writer transaction, using its connection."""
    for pinned in pins_in(item):
        if get(pinned.ref).digest != pinned.sha256:
            raise ValueError("pinned artifact digest mismatch")
    if not isinstance(item, IntentBinding):
        return
    identity = content_identity(get, item.media.ref, item.registration.ref)
    if get(item.registration.ref).created_at != item.registered_at:
        raise ValueError("registered_at must equal original registration time")
    for old in history:
        if content_identity(get, old.media.ref, old.registration.ref) == identity and old.id != item.id:
            raise ValueError("content identity already has a binding lineage")
    if item.predecessor is not None:
        old = get(item.predecessor.ref)
        if (old.media, old.registration, old.registered_at, old.origin) != (item.media, item.registration, item.registered_at, item.origin):
            raise ValueError("binding registration anchors and origin are immutable")
        if item.provenance not in SUCCESSORS[old.provenance]:
            raise ValueError("binding revision cannot raise provenance")


ARTIFACT_TYPES.update({cls.__name__: cls for cls in (IntentSpecV2, IntentBinding)})
