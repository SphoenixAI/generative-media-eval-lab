"""Private, computed evidence/hypothesis roles; no authored outcomes or judgments."""
from pathlib import Path
import sqlite3
from pydantic import model_validator
from . import __version__, test_plans
from .assessments import raw_payload
from .domain import Artifact, ARTIFACT_TYPES, Ref
from .generation import now, pin
from .intent_v2 import CheckedValue, Pin, Text, Instant, kind, predecessor, content_identity
from .pilot_domain import Hash


class Context(Artifact, CheckedValue):
    id: Text
    author: Text
    predecessor: Pin | None = None
    revision_reason: Text | None = None
    tool_version: Text = __version__

    @model_validator(mode="before")
    @classmethod
    def revalidate_copies(cls, value):
        return raw_payload(value)

    @model_validator(mode="after")
    def contract(self):
        predecessor(self)
        if self.revision > 1 and self.revision_reason is None: raise ValueError("revision reason required")
        for field, name in (("evidence", "Evidence"), ("hypothesis", "Hypothesis"),
                ("observation", "TechnicalObservation"), ("plan", "TestPlan"), ("clip", "PilotClip"),
                ("run", "InstrumentRun"), ("origin", "ClipOrigin")):
            value = getattr(self, field, None)
            if value is not None: kind(value, name)
        return self


class HypothesisContext(Context):
    hypothesis: Pin
    observation: Pin


class InstrumentRun(Context):
    plan: Pin
    arm: Text
    evidence: Pin
    executed_at: Instant
    tool: Text
    version: Text
    tool_sha256: Hash
    input_sha256: Hash
    output_sha256: Hash


class EvidenceArm(Context):
    evidence: Pin
    plan: Pin
    arm: Text
    clip: Pin
    origin: Pin | None = None
    run: Pin | None = None


TYPES = (EvidenceArm, HypothesisContext, InstrumentRun)
COMMANDS = dict(zip(("evidence-arm", "hypothesis-context", "instrument-run"), TYPES))
ARTIFACT_TYPES.update({cls.__name__: cls for cls in TYPES})


def validate_admission(item, get):
    """Exact dependencies and consistency, also rechecked during private replay."""
    test_plans.validate_dependencies(item, get)
    subject = "hypothesis" if isinstance(item, HypothesisContext) else "evidence"
    if item.predecessor and getattr(get(item.predecessor.ref), subject) != getattr(item, subject):
        raise ValueError("context subject is immutable")
    if isinstance(item, HypothesisContext):
        if get(item.observation.ref).created_at > get(item.hypothesis.ref).created_at:
            raise ValueError("prompting observation must predate or equal hypothesis")
        return
    plan, evidence = get(item.plan.ref), get(item.evidence.ref)
    arm = next((a for a in plan.arms if a.id == item.arm), None)
    if arm is None: raise ValueError("arm absent from pinned plan")
    if isinstance(item, InstrumentRun):
        if plan.measurement.kind != "INSTRUMENT": raise ValueError("run requires INSTRUMENT measurement")
        if item.executed_at > evidence.created_at: raise ValueError("run cannot follow result evidence")
        if item.executed_at > item.created_at: raise ValueError("run cannot follow import time")
        if item.output_sha256 != evidence.digest: raise ValueError("run output digest mismatch")
        return
    clip = get(item.clip.ref)
    original = get(Ref(kind="PilotClip", id=clip.id, revision=1))
    if (clip.media, clip.ingestion) != (original.media, original.ingestion):
        raise ValueError("clip registration anchors changed")
    if evidence.media != clip.media: raise ValueError("evidence/clip media mismatch")
    if clip.ingestion.revision != 1: raise ValueError("original registration required")
    source = content_identity(get, clip.media, clip.ingestion)
    origin = get(item.origin.ref) if item.origin else None
    if origin and origin.clip != pin(original): raise ValueError("origin/clip mismatch")
    if arm.generation_plan_ref and (origin is None or origin.plan != arm.generation_plan_ref):
        raise ValueError("generation origin/arm mismatch")
    if item.run:
        run = get(item.run.ref)
        validate_admission(run, get)
        if (run.plan, run.arm, run.evidence) != (item.plan, item.arm, item.evidence):
            raise ValueError("run/link context mismatch")
        if run.input_sha256 != source: raise ValueError("run input content mismatch")


def record(repo, command, data, author):
    if not isinstance(data, dict) or {"created_at", "tool_version"} & data.keys():
        raise ValueError("created_at and tool_version are application-owned")
    item = COMMANDS[command].model_validate(data | dict(created_at=now(), tool_version=__version__))
    if item.author != author: raise ValueError("author declaration mismatch")
    repo.put(item)
    return item


def ordered(items):
    return sorted(items, key=lambda x: (x.ref.kind, x.id, x.revision))


def heads(items):
    current = {}
    for item in ordered(items): current[item.id] = item
    return list(current.values())


REASONS = {
    "POST_FREEZE_CLIP": "Frozen member tested using evidence and registered content created after freeze.",
    "POST_FREEZE_RUN": "Frozen member tested using post-freeze evidence from a retained declared instrument run.",
    "EXISTED_AT_HYPOTHESIS": "Evidence existed before this hypothesis revision was created.",
    "PROMPTING_OBSERVATION": "The pinned prompting observation cites this evidence revision.",
    "EXISTING_CLIP": "The arm content was already registered at freeze; later viewing does not make a new test.",
    "HYPOTHESIS_NOT_BEFORE_FREEZE": "This hypothesis revision did not predate freeze.",
    "HYPOTHESIS_NOT_FROZEN_MEMBER": "This exact hypothesis revision is absent from the frozen set's named members.",
    "EVIDENCE_NOT_AFTER_FREEZE": "This evidence revision was not created strictly after freeze.",
    "NO_FROZEN_ARM": "No linked frozen test arm establishes a test result for this pair.",
    "CREATION_ORDER_UNKNOWN": "Equal creation timestamps do not establish evidence/hypothesis order.",
}


def compute(repo, evidence, hypothesis):
    """Read-only classification in one retained context; corrections use lineage heads."""
    dependencies = {}
    def get(ref):
        value = repo.get(ref); dependencies[ref] = value
        return value
    def checked(p, name):
        p = Pin.model_validate(raw_payload(p)); kind(p, name)
        item = get(p.ref)
        if item.digest != p.sha256: raise ValueError("pinned artifact digest mismatch")
        return item
    def result(status, role=None, reason=None, detail=None, selected=None):
        return dict(status=status, role=role, reason=reason, detail=detail or REASONS.get(reason),
            evidence=raw_payload(evidence), hypothesis=raw_payload(hypothesis),
            selected_link=pin(selected).model_dump(mode="json") if selected else None,
            dependencies=[pin(x).model_dump(mode="json") for x in ordered(dependencies.values())],
            rule_version="evidence-roles-v1", tool_version=__version__,
            first_view="Pair-level first-view events are not recorded.")
    try:
        ev, hyp = checked(evidence, "Evidence"), checked(hypothesis, "Hypothesis")
        # Normalize pins once; all output is JSON-compatible and exact.
        evidence, hypothesis = pin(ev).model_dump(mode="json"), pin(hyp).model_dump(mode="json")
        links = [x for x in heads(repo.all("EvidenceArm")) if x.evidence.ref == ev.ref]
        contexts = [x for x in heads(repo.all("HypothesisContext")) if x.hypothesis.ref == hyp.ref]
        reasons, missing, selected, success = [], [], None, None
        for link in links:
            failed = None
            try:
                get(link.ref)
                plan = checked(link.plan, "TestPlan")
                if plan.frozen_at is None: failed = "NO_FROZEN_ARM"
                elif hyp.created_at >= plan.frozen_at: failed = "HYPOTHESIS_NOT_BEFORE_FREEZE"
                elif hyp.ref not in checked(plan.competing_set, "CompetingSet").members: failed = "HYPOTHESIS_NOT_FROZEN_MEMBER"
                elif ev.created_at <= plan.frozen_at: failed = "EVIDENCE_NOT_AFTER_FREEZE"
                validate_admission(link, get)
                if failed:
                    reasons.append(failed); continue
                test_plans.validate_admission(plan, get, freezing=True)
                clip = get(link.clip.ref)
                source = content_identity(get, clip.media, clip.ingestion)
                registrations = [r for r in repo.all("MediaIngestion") if r.source_sha256 == source]
                for registration in registrations:
                    get(registration.ref); content_identity(get, registration.media, registration.ref)
                earliest = min(r.created_at for r in registrations)
                reason = "POST_FREEZE_CLIP" if earliest > plan.frozen_at else (
                    "POST_FREEZE_RUN" if link.run and get(link.run.ref).executed_at > plan.frozen_at else "EXISTING_CLIP")
                if reason != "EXISTING_CLIP" and selected is None: selected, success = link, reason
                reasons.append(reason)
            except KeyError as exc:
                if failed: reasons.append(failed)
                else: missing.append(str(exc))
        prompted = False
        for context in contexts:
            try:
                get(context.ref); validate_admission(context, get)
                prompted |= pin(ev) in get(context.observation.ref).evidence
            except KeyError as exc: missing.append(str(exc))
        if selected: return result("COMPUTED", "TEST_RESULT", success, selected=selected)
        if ev.created_at < hyp.created_at: return result("COMPUTED", "DISCOVERY", "EXISTED_AT_HYPOTHESIS")
        if prompted: return result("COMPUTED", "DISCOVERY", "PROMPTING_OBSERVATION")
        if missing: return result("UNKNOWN", detail="Missing role context: " + "; ".join(sorted(missing)))
        if ev.created_at == hyp.created_at: return result("UNKNOWN", reason="CREATION_ORDER_UNKNOWN")
        return result("COMPUTED", "SUPPORTING", reasons[0] if reasons else "NO_FROZEN_ARM")
    except KeyError as exc: return result("UNKNOWN", detail="missing artifact: " + str(exc))
    except (ValueError, TypeError) as exc: return result("INTEGRITY_FAILURE", detail=str(exc))


def query(root, data):
    """Open an existing SQLite snapshot without schema creation or writes."""
    from .seals import checked_record
    from .canonical_json import parse_json
    from types import SimpleNamespace
    database = Path(root).resolve() / "pilot.sqlite"
    db = None
    def failure(status, detail):
        return dict(status=status, role=None, reason=None, detail=detail)
    try:
        if not isinstance(data, dict) or set(data) != {"evidence", "hypothesis"}:
            raise ValueError("role query requires only evidence and hypothesis pins")
        if not database.is_file(): return failure("UNKNOWN", "role database unavailable")
        db = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True); db.row_factory = sqlite3.Row
        db.execute("BEGIN")
        def get(ref):
            row = db.execute("SELECT * FROM artifacts WHERE kind=? AND id=? AND revision=?", (ref.kind, ref.id, ref.revision)).fetchone()
            if row is None: raise KeyError(f"missing artifact: {ref.kind}:{ref.id}@{ref.revision}")
            if ref.kind == "TestPlan":
                payload = parse_json(row["payload"])
                if not isinstance(payload, dict): raise ValueError("retained TestPlan payload must be a JSON object")
                if payload.get("frozen_digest") is not None and test_plans.freeze_digest(payload) != payload["frozen_digest"]:
                    raise ValueError("frozen digest mismatch")
            return checked_record(row)
        def all_records(name):
            return tuple(get(Ref(kind=name, id=r[0], revision=r[1])) for r in db.execute("SELECT id, revision FROM artifacts WHERE kind=?", (name,)))
        return compute(SimpleNamespace(get=get, all=all_records), **data)
    except OSError as exc: return failure("UNKNOWN", str(exc))
    except sqlite3.OperationalError as exc:
        return failure("UNKNOWN" if "locked" in str(exc) or "unable to open" in str(exc) else "INTEGRITY_FAILURE", str(exc))
    except (ValueError, TypeError, sqlite3.DatabaseError) as exc: return failure("INTEGRITY_FAILURE", str(exc))
    finally:
        if db is not None: db.close()


def roots(repo, clips):
    """Incoming links cross from original case intent to arm clips; retain histories."""
    from .persistence import refs_in
    clips = tuple(clips)
    media = {c.media for c in clips}
    intents = {c.intent for c in repo.all("PilotClip") if c.id in {v.id for v in clips} and c.intent}
    candidates = [*repo.all("EvidenceArm"), *repo.all("InstrumentRun")]
    relevant = [x for x in candidates if repo.get(x.evidence.ref).media in media
        or repo.get(repo.get(x.plan.ref).competing_set.ref).intent in intents]
    ids = {(x.ref.kind, x.id) for x in relevant}
    retained = [x for x in candidates if (x.ref.kind, x.id) in ids]
    links = [x for x in retained if isinstance(x, EvidenceArm)]
    # Arm-only datasets reach exact hypotheses through plans and predecessor histories.
    pending, reached = [x.ref for x in retained], set()
    while pending:
        ref = pending.pop()
        if ref in reached: continue
        reached.add(ref)
        pending.extend(refs_in(repo.get(ref)))
    prompts = [x for x in repo.all("HypothesisContext") if x.hypothesis.ref in reached
        or repo.get(x.hypothesis.ref).intent in intents]
    result = [x.ref for x in retained + prompts]
    sources = set()
    for link in links:
        clip = repo.get(link.clip.ref)
        result.append(Ref(kind="PilotClip", id=clip.id, revision=1))
        sources.add(content_identity(repo.get, clip.media, clip.ingestion))
    result.extend(r.ref for r in repo.all("MediaIngestion") if r.source_sha256 in sources)
    return result


def clip_records(repo, clip):
    return {"evidence_role_contexts": [repo.get(ref).model_dump(mode="json") for ref in roots(repo, (clip,))
        if ref.kind in {cls.__name__ for cls in TYPES}]}
