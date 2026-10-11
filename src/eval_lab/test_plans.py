"""Private qualitative test declarations. No generation or measurement is executed."""
from hashlib import sha256
from pathlib import Path
import sqlite3
from typing import Annotated, Literal
from pydantic import Field, model_validator
from . import __version__
from .assessments import raw_payload
from .canonical_json import canonicalize, parse_json
from .domain import Artifact, ARTIFACT_TYPES, Ref
from .generation import now, pin
from .intent_v2 import CheckedValue, Pin, Text, Instant, kind, predecessor, pins_in
from .pilot_domain import Hash


class Arm(CheckedValue):
    id: Text
    description: Text
    generation_plan_ref: Pin | None

    @model_validator(mode="after")
    def contract(self):
        if self.generation_plan_ref: kind(self.generation_plan_ref, "GenerationPlan")
        return self


class SampleDesign(CheckedValue):
    n_per_arm: Annotated[int, Field(strict=True, gt=0)] | None = None
    stopping_rule: Text | None = None
    decision_rule: Text

    @model_validator(mode="after")
    def contract(self):
        if (self.n_per_arm is None) == (self.stopping_rule is None):
            raise ValueError("sample_design requires exactly one of n_per_arm or stopping_rule")
        return self


class Measurement(CheckedValue):
    kind: Literal["HUMAN", "INSTRUMENT"]
    protocol: Text


def freeze_digest(data):
    return sha256(canonicalize({k: v for k, v in data.items() if k != "frozen_digest"})).hexdigest()


class TestPlan(Artifact, CheckedValue):
    id: Text
    author: Text
    competing_set: Pin
    arms: tuple[Arm, ...] = Field(min_length=1)
    sample_design: SampleDesign | None = None
    measurement: Measurement
    outcome_categories: tuple[Text, ...] = Field(min_length=1)
    predictions: dict[Text, Annotated[tuple[Text, ...], Field(min_length=1)]]
    predecessor: Pin | None = None
    frozen_at: Instant | None = None
    frozen_digest: Hash | None = None
    tool_version: Text = __version__
    canonicalization: Literal["RFC8785"] = "RFC8785"
    number_profile: Literal["safe-integer-tokens-v1"] = "safe-integer-tokens-v1"

    @model_validator(mode="before")
    @classmethod
    def revalidate_copies(cls, value):
        if isinstance(value, cls):
            value = dict(value.__dict__) | (value.__pydantic_extra__ or {})
        if isinstance(value, dict):
            # Prediction keys are arbitrary hypothesis IDs, never reference metadata.
            return {k: v if k == "predictions" else raw_payload(v) for k, v in value.items()}
        return value

    @model_validator(mode="after")
    def contract(self):
        predecessor(self); kind(self.competing_set, "CompetingSet")
        if len({a.id for a in self.arms}) != len(self.arms): raise ValueError("unique arm IDs required")
        if len(set(self.outcome_categories)) != len(self.outcome_categories): raise ValueError("unique outcome categories required")
        for outcomes in self.predictions.values():
            if len(set(outcomes)) != len(outcomes): raise ValueError("unique predicted outcomes required")
            if set(outcomes) - set(self.outcome_categories): raise ValueError("undeclared outcome in predictions")
        if any(a.generation_plan_ref for a in self.arms) and self.sample_design is None:
            raise ValueError("sample_design required for generation arms")
        if (self.frozen_at is None) != (self.frozen_digest is None): raise ValueError("freeze fields must be paired")
        data = self.model_dump(mode="json")
        canonicalize(data)  # Enforce the declared number/Unicode profile on drafts too.
        if self.frozen_digest is not None and freeze_digest(data) != self.frozen_digest:
            raise ValueError("frozen digest mismatch")
        return self


ARTIFACT_TYPES["TestPlan"] = TestPlan
TRANSITION_FIELDS = {"created_at", "revision", "predecessor", "frozen_at", "frozen_digest", "tool_version"}


def validate_dependencies(item, get):
    """Walk exact retained dependencies, including predecessor history; never latest."""
    from .persistence import refs_in
    pending, seen = [item], set()
    while pending:
        current = pending.pop()
        if current.ref in seen: continue
        seen.add(current.ref)
        for p in pins_in(current):
            if get(p.ref).digest != p.sha256: raise ValueError("pinned artifact digest mismatch")
        if isinstance(current, TestPlan):
            named = {m.id for m in get(current.competing_set.ref).members if isinstance(m, Ref)}
            if set(current.predictions) != named: raise ValueError("predictions must cover exact named hypotheses")
        pending.extend(get(ref) for ref in refs_in(current))


def validate_admission(item, get, freezing=False):
    validate_dependencies(item, get)
    if item.frozen_at is not None:
        if not freezing: raise ValueError("frozen records require the explicit freeze command")
        if item.predecessor is None: raise ValueError("freeze requires a retained draft predecessor")
        old = get(item.predecessor.ref)
        if old.frozen_at is not None: raise ValueError("already frozen; append a draft revision")
        if old.model_dump(exclude=TRANSITION_FIELDS) != item.model_dump(exclude=TRANSITION_FIELDS):
            raise ValueError("freeze must preserve authored content")


def classify(predictions, outcomes, residual):
    """Class precedence and ordered coverage only; no empirical diagnostic power."""
    sets = [set(values) for values in predictions.values()]
    compatible = {o: sorted(h for h, values in predictions.items() if o in values) for o in outcomes}
    label = "NON_DIAGNOSTIC" if len(sets) < 2 or all(s == sets[0] for s in sets) else (
        "DECISIVE" if all(len(hs) <= 1 for hs in compatible.values()) else "PARTIALLY_DIAGNOSTIC")
    return dict(diagnosticity=label, compatible=compatible, unpredicted=[o for o, hs in compatible.items() if not hs],
        residual="not testable by this plan" if residual else None)


def diagnosticity(item, get):
    item = TestPlan.model_validate(item)
    validate_dependencies(item, get)
    group = get(item.competing_set.ref)
    return classify(item.predictions, item.outcome_categories, any(not isinstance(m, Ref) for m in group.members))


def target_ref(text):
    name, marker, revision = text.rpartition("@")
    if not name or not marker or not revision.isdecimal(): raise ValueError("use an exact ID@REV")
    return Ref(kind="TestPlan", id=name, revision=int(revision))


def record(repo, data, author):
    if not isinstance(data, dict) or {"frozen_at", "frozen_digest", "tool_version"} & data.keys():
        raise ValueError("freeze metadata and tool_version are application-owned")
    item = TestPlan.model_validate(data | {"tool_version": __version__})
    if item.author != author: raise ValueError("author declaration mismatch")
    repo.put(item)
    return item


def freeze(repo, target):
    old = repo.get(target_ref(target))
    if old.frozen_at is not None: raise ValueError("already frozen; append a draft revision")
    if repo.latest(old.ref).ref != old.ref: raise ValueError("stale draft; freeze the current exact revision")
    diagnosticity(old, repo.get)
    stamp = now()
    data = old.model_dump(mode="json") | dict(revision=old.revision+1,
        created_at=stamp.isoformat().replace("+00:00", "Z"), frozen_at=stamp.isoformat().replace("+00:00", "Z"),
        predecessor=pin(old).model_dump(mode="json"), tool_version=__version__)
    data["frozen_digest"] = freeze_digest(data)
    item = TestPlan.model_validate(data)
    repo.put(item, _freeze_test_plan=True)
    return item


class MissingArtifact(KeyError):
    pass


def verify(root, target, source=None):
    """One read-only SQLite snapshot. Absence never becomes a verified plan."""
    from .seals import checked_record
    database = Path(root).resolve() / "pilot.sqlite"
    def result(status, detail): return dict(status=status, detail=detail, quality_verdict="UNKNOWN")
    if not database.is_file(): return result("UNKNOWN", "test plan database unavailable")
    db = None
    try:
        db = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True); db.row_factory = sqlite3.Row
        db.execute("BEGIN")
        def get(ref):
            row = db.execute("SELECT * FROM artifacts WHERE kind=? AND id=? AND revision=?", (ref.kind, ref.id, ref.revision)).fetchone()
            if row is None: raise MissingArtifact(f"missing artifact: {ref.kind}:{ref.id}@{ref.revision}")
            if row["kind"] == "TestPlan":
                data = parse_json(row["payload"])
                if not isinstance(data, dict):
                    raise ValueError("retained TestPlan payload must be a JSON object")
                if data.get("frozen_digest") is not None and freeze_digest(data) != data["frozen_digest"]:
                    raise ValueError("frozen digest mismatch in retained payload")
            return checked_record(row)
        item = get(target_ref(target))
        diagnosis = diagnosticity(item, get)
        if item.frozen_at is None: return result("NOT_FROZEN", "draft requires an explicit freeze command")
        if source is not None:
            data = parse_json(Path(source).read_bytes())
            TestPlan.model_validate(data)
            if canonicalize(data) != canonicalize(item.model_dump(mode="json")):
                raise ValueError("candidate differs from retained revision")
        return result("VERIFIED", "retained revision, freeze digest and dependencies verified") | diagnosis
    except (MissingArtifact, OSError) as exc: return result("UNKNOWN", str(exc))
    except sqlite3.OperationalError as exc:
        return result("UNKNOWN" if "locked" in str(exc) or "unable to open" in str(exc) else "INTEGRITY_FAILURE", str(exc))
    except (ValueError, KeyError, TypeError, sqlite3.DatabaseError) as exc: return result("INTEGRITY_FAILURE", str(exc))
    finally:
        if db is not None: db.close()


def roots(repo, clips):
    """Include complete plan histories tied to these clips' retained intent revisions."""
    ids = {c.id for c in clips}
    intents = {c.intent for c in repo.all("PilotClip") if c.id in ids and c.intent is not None}
    plans = repo.all("TestPlan")
    relevant = {p.id for p in plans if repo.get(p.competing_set.ref).intent in intents}
    return [p.ref for p in plans if p.id in relevant]


def clip_records(repo, clip):
    records = []
    for ref in roots(repo, (clip,)):
        item = repo.get(ref)
        records.append(dict(ref=ref.model_dump(), sha256=item.digest, artifact=item.model_dump(mode="json"), **diagnosticity(item, repo.get)))
    return {"test_plans": records}
