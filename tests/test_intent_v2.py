"""TEST-ONLY provenance contracts; generated patterns, no real-media judgments."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from itertools import product
import json
from threading import Barrier

import pytest
from pydantic import ValidationError
from eval_lab.domain import Criterion, Dimension, IntentSpec, MediaAsset, Ref
from eval_lab.persistence import Repository, refs_in
from eval_lab.pilot_domain import MediaIngestion, VideoMetadata, FrameTime, ToolIdentity
from eval_lab.intent_v2 import (IntentSpecV2, IntentBinding, Pin, SealEvidence,
    PlanEvidence, LegacyIntentView, content_identity)
from eval_lab.pilot import PilotWorkspace
from eval_lab.media import MediaStore
from eval_lab.pilot_cli import parser
from test_media import media_tools, codec_videos

T = datetime(2026, 1, 1, tzinfo=timezone.utc)
TEXT = "TEST-ONLY"
CLASSES = ("SEALED", "CONTEMPORANEOUS", "RECONSTRUCTED", "PROMPT_ONLY")


def pin(item):
    return Pin(ref=item.ref, sha256=item.digest)


def intent(**updates):
    data = dict(id="TEST-ONLY-intent", created_at=T, owner=TEXT, objective=TEXT,
        revision_reason="CLARIFICATION", use_context=dict(surface=TEXT, audience=TEXT,
        viewing_profile="FEED"), criteria=[dict(id="criterion", dimension="motion_plausibility",
        priority="MUST", acceptance=TEXT, rejection=TEXT, tolerance=TEXT)])
    return IntentSpecV2(**(data | updates))


def anchors(repo, name="TEST-ONLY", checksum="a" * 64, stamp=T):
    media = MediaAsset(id=name, created_at=T, type="video", storage_reference=TEXT,
        checksum=checksum, duration=1, fps=1, width=16, height=16, provenance="uploaded")
    reg = MediaIngestion(id=name, created_at=stamp, media=media.ref, original_name=TEXT,
        source_sha256=checksum, source_size_bytes=1, original_relative_path=TEXT,
        probe_relative_path=TEXT, probe_sha256="b" * 64,
        probe_tool=ToolIdentity(name="ffprobe", version=TEXT, executable_sha256="c" * 64),
        metadata=VideoMetadata(stream_index=0, codec=TEXT, container=TEXT, width=16,
        height=16, duration_seconds=1, duration_basis="last_frame_duration", average_fps=1,
        time_base="1/1", source_start_seconds=0, variable_frame_rate=False,
        pixel_format=TEXT, audio_present=False, frames=(FrameTime(index=0, pts=0, seconds=0, source_seconds=0),)))
    repo.put(media)
    repo.put(reg)
    return media, reg


def binding(i, m, r, cls="RECONSTRUCTED", **updates):
    data = dict(id="TEST-ONLY-binding", created_at=T, intent=pin(i), media=pin(m),
        registration=pin(r), registered_at=r.created_at, origin="FOUND")
    if cls in ("SEALED", "CONTEMPORANEOUS"):
        stamp = r.created_at - timedelta(seconds=2)
        data["seal"] = SealEvidence(intent=pin(i), sealed_at=stamp)
        if cls == "SEALED":
            data["plan"] = PlanEvidence(intents=(pin(i),), registration=pin(r), planned_at=stamp + timedelta(seconds=1))
        else:
            data["first_view_at"] = stamp + timedelta(seconds=1)
    if cls == "PROMPT_ONLY":
        data["declaration"] = "PROMPT_ONLY"
    return IntentBinding(**(data | updates))


@pytest.fixture
def env():
    repo = Repository()
    i = intent()
    repo.put(i)
    m, r = anchors(repo)
    yield repo, i, m, r
    repo.close()


# Explicit oracle: (seal, plan, registration, sealed); all 13 weak orderings.
ORDERS = [(0,1,2,True), (0,2,1,False), (1,0,2,False), (2,0,1,False),
    (1,2,0,False), (2,1,0,False), (0,0,1,False), (1,1,0,False),
    (0,1,0,False), (1,0,1,False), (1,0,0,False), (0,1,1,False), (0,0,0,False)]


@pytest.mark.parametrize("s,p,r,sealed", ORDERS)
@pytest.mark.parametrize("view_delta", [-1, 0, 1, None])
@pytest.mark.parametrize("origin", ["FOUND", "GENERATED"])
def test_every_chronology_order(env, s, p, r, sealed, view_delta, origin):
    repo, i, m, reg = env
    reg = reg.model_copy(update={"created_at":T + timedelta(seconds=r)})
    seal = SealEvidence(intent=pin(i), sealed_at=T + timedelta(seconds=s))
    plan = PlanEvidence(intents=(pin(i),), registration=pin(reg), planned_at=T + timedelta(seconds=p))
    view = None if view_delta is None else seal.sealed_at + timedelta(seconds=view_delta)
    b = binding(i, m, reg, seal=seal, plan=plan, first_view_at=view, origin=origin)
    expected = "SEALED" if sealed else ("CONTEMPORANEOUS" if view_delta == 1 else "RECONSTRUCTED")
    assert b.provenance == expected
    assert IntentBinding.model_validate_json(b.canonical()).provenance == expected
    assert b.canonical() == IntentBinding.model_validate_json(b.canonical()).canonical()


@pytest.mark.parametrize("field,expected", [("seal","RECONSTRUCTED"), ("plan","CONTEMPORANEOUS"), ("first_view_at","SEALED")])
def test_missing_evidence_and_sealed_precedence(env, field, expected):
    _, i, m, r = env
    b = binding(i, m, r, "SEALED", first_view_at=T)
    assert IntentBinding.model_validate(b.model_dump() | {field:None}).provenance == expected
    assert binding(i, m, r, first_view_at=T).provenance == "RECONSTRUCTED"


@pytest.mark.parametrize("case", ["old_seal", "wrong_plan_revision", "wrong_registration"])
def test_exact_revision_and_bound_plan(env, case):
    repo, i, m, r = env
    newer = intent(revision=2, predecessor=pin(i))
    repo.put(newer)
    other_m, other_r = anchors(repo, "TEST-ONLY-other", "d" * 64)
    b = binding(newer, m, r, "SEALED")
    if case == "old_seal":
        b = b.model_copy(update={"seal":SealEvidence(intent=pin(i), sealed_at=T-timedelta(seconds=2))})
    else:
        plan = b.plan.model_copy(update={"intents":(pin(i),)} if case == "wrong_plan_revision" else {"registration":pin(other_r)})
        b = b.model_copy(update={"plan":plan})
    repo.put(b)
    assert repo.get(b.ref).provenance == "RECONSTRUCTED"
    if case != "old_seal":
        assert b.model_copy(update={"first_view_at":T}).provenance == "CONTEMPORANEOUS"


@pytest.mark.parametrize("origin", ["FOUND", "GENERATED"])
@pytest.mark.parametrize("has_plan", [False, True])
def test_earlier_revision_seal_cannot_establish_contemporaneous(tmp_path, origin, has_plan):
    url = "sqlite:///" + str(tmp_path / "TEST-ONLY-borrowed-seal.sqlite")
    repo = Repository(url)
    try:
        first = intent()
        newer = intent(revision=2, predecessor=pin(first))
        repo.put(first)
        repo.put(newer)
        m, r = anchors(repo)
        expected = "SEALED" if has_plan else "CONTEMPORANEOUS"
        matching = binding(newer, m, r, expected, origin=origin, first_view_at=T)
        assert matching.provenance == expected
        borrowed = IntentBinding.model_validate(matching.model_dump() | {
            "seal": SealEvidence(intent=pin(first), sealed_at=matching.seal.sealed_at)})
        assert borrowed.seal.sealed_at < borrowed.first_view_at
        assert borrowed.provenance == "RECONSTRUCTED"
        restored = IntentBinding.model_validate_json(borrowed.canonical())
        assert restored.provenance == "RECONSTRUCTED"
        assert restored.canonical() == borrowed.canonical()
        repo.put(restored)
        assert repo.get(borrowed.ref).provenance == "RECONSTRUCTED"
    finally:
        repo.close()
    reopened = Repository(url)
    try:
        stored = reopened.get(borrowed.ref)
        assert stored.provenance == "RECONSTRUCTED"
        assert stored.canonical() == borrowed.canonical()
    finally:
        reopened.close()


@pytest.mark.parametrize("reason", ["SERENDIPITY", "CLARIFICATION", "CORRECTION", "SCOPE_CHANGE"])
def test_reason_values_on_initial_and_successor(env, reason):
    repo, i, _, _ = env
    first = intent(id="TEST-ONLY-reasons", revision_reason=reason)
    repo.put(first)
    repo.put(intent(id=first.id, revision=2, predecessor=pin(first), revision_reason=reason))


@pytest.mark.parametrize("reason", [None, "", " ", "OTHER", "MISSING"])
@pytest.mark.parametrize("revision", [1, 2])
def test_reason_is_required_on_every_path(env, reason, revision):
    repo, i, _, _ = env
    valid = intent(id="TEST-ONLY-reason-first") if revision == 1 else intent(revision=2, predecessor=pin(i))
    data = valid.model_dump()
    if reason == "MISSING":
        data.pop("revision_reason")
    else:
        data["revision_reason"] = reason
    with pytest.raises(ValidationError, match="revision_reason"): IntentSpecV2(**data)
    with pytest.raises(ValidationError, match="revision_reason"): IntentSpecV2.model_validate(data)
    invalid = valid.model_copy(update={} if reason == "MISSING" else {"revision_reason":reason})
    if reason == "MISSING": object.__delattr__(invalid, "revision_reason")
    with pytest.raises(ValidationError, match="revision_reason"): repo.put(invalid)
    with pytest.raises(KeyError): repo.get(valid.ref)
    assert repo.put(valid) == valid.digest
    assert repo.get(valid.ref).canonical() == valid.canonical()


@pytest.mark.parametrize("case", ["missing", "skip", "stale", "cross_id", "wrong_kind", "digest", "initial"])
def test_predecessor_must_pin_immediate_revision(env, case):
    repo, i, _, _ = env
    second = intent(revision=2, predecessor=pin(i))
    repo.put(second)
    prior, revision = pin(second), 3
    if case == "missing": prior = None
    if case == "skip": revision = 4
    if case == "stale": prior = pin(i)
    if case == "cross_id": prior = prior.model_copy(update={"ref":Ref(kind="IntentSpecV2", id="other", revision=2)})
    if case == "wrong_kind": prior = prior.model_copy(update={"ref":Ref(kind="MediaAsset", id=i.id, revision=2)})
    if case == "digest": prior = prior.model_copy(update={"sha256":"f" * 64})
    if case == "initial": revision = 1
    with pytest.raises(ValueError): repo.put(intent(revision=revision, predecessor=prior))
    assert [x.digest for x in repo.all("IntentSpecV2")] == [i.digest, second.digest]


def test_context_criteria_and_deviations(env):
    repo, i, _, _ = env
    for profile, priority in product(("FEED", "STUDIO"), ("MUST", "SHOULD", "COULD", "WONT")):
        data = i.model_dump()
        data["use_context"]["viewing_profile"] = profile
        data["criteria"][0]["priority"] = priority
        data["criteria"] += (data["criteria"][0] | {"id":"second"},)
        data["expected_deviations"] = [dict(dimension="motion_plausibility", description=TEXT, criterion_id="second")]
        assert IntentSpecV2(**data).criteria[1].id == "second"
    deviation = dict(dimension="motion_plausibility", description=TEXT, criterion_id="criterion")
    invalid = [("criteria", (), i.criteria, "at least 1 item"),
        ("criteria", (i.criteria[0], i.criteria[0]),
            (i.criteria[0], i.criteria[0].model_copy(update={"id":"second"})), "criterion IDs must be unique"),
        ("expected_deviations", [deviation | {"criterion_id":"missing"}], [deviation], "same dimension"),
        ("expected_deviations", [deviation | {"dimension":"camera_language"}], [deviation], "same dimension")]
    for index, (field, value, corrected, error) in enumerate(invalid):
        valid = intent(id=f"TEST-ONLY-contract-{index}", **{field:corrected})
        with pytest.raises(ValidationError, match=error): repo.put(valid.model_copy(update={field:value}))
        with pytest.raises(KeyError): repo.get(valid.ref)
        assert repo.put(valid) == valid.digest
        assert repo.get(valid.ref).canonical() == valid.canonical()
    for field in ("surface", "audience", "viewing_profile"):
        with pytest.raises(ValueError): intent(use_context=i.use_context.model_copy(update={field:" "}))
    for field in ("id", "dimension", "priority", "acceptance", "rejection", "tolerance"):
        with pytest.raises(ValueError): intent(criteria=(i.criteria[0].model_copy(update={field:" "}),))
    for dimension in ("SENSITIVE", "INVARIANT"):
        with pytest.raises(ValueError): intent(criteria=(i.criteria[0].model_copy(update={"dimension":dimension}),))
    for field in ("owner", "objective", "id"):
        with pytest.raises(ValueError): intent(**{field:" "})


@pytest.mark.parametrize("origin,declared,valid", [(o,c,o=="FOUND" and c=="PROMPT_ONLY") for o,c in product(("FOUND","GENERATED"),CLASSES)])
def test_only_found_prompt_only_is_declarable(env, origin, declared, valid):
    repo, i, m, r = env
    if valid:
        b = binding(i, m, r, origin=origin, declaration=declared)
        repo.put(b)
        assert b.provenance == "PROMPT_ONLY"
    else:
        with pytest.raises(ValueError): binding(i, m, r, origin=origin, declaration=declared)
    with pytest.raises(ValueError): binding(i, m, r, provenance=declared)


@pytest.mark.parametrize("field", ["registered_at", "first_view_at", "sealed_at", "planned_at"])
@pytest.mark.parametrize("bad", ["nonsense", "2026-01-01T00:00:00"])
def test_malformed_or_naive_event_times_rejected(env, field, bad):
    repo, i, m, r = env
    b = binding(i, m, r, "SEALED")
    data = b.model_dump()
    if field == "sealed_at": data["seal"][field] = bad
    elif field == "planned_at": data["plan"][field] = bad
    else: data[field] = bad
    with pytest.raises(ValueError): IntentBinding(**data)
    with pytest.raises(ValueError): repo.put(b.model_copy(update=data))


@pytest.mark.parametrize("case", ["media", "registration", "seal", "plan", "registered_at", "missing", "registration_revision", "mismatched_media", "seal_kind", "plan_kind"])
def test_pins_and_original_registration_reject_tampering(env, case):
    repo, i, m, r = env
    b = binding(i, m, r, "SEALED")
    if case in ("media", "registration"):
        b = b.model_copy(update={case:getattr(b, case).model_copy(update={"sha256":"f" * 64})})
    if case == "seal": b = b.model_copy(update={"seal":b.seal.model_copy(update={"intent":pin(i).model_copy(update={"sha256":"f" * 64})})})
    if case == "plan": b = b.model_copy(update={"plan":b.plan.model_copy(update={"intents":(pin(i).model_copy(update={"sha256":"f" * 64}),)})})
    if case == "registered_at": b = b.model_copy(update={"registered_at":T+timedelta(seconds=1)})
    if case == "missing": b = b.model_copy(update={"registration":None})
    if case == "registration_revision":
        r = r.model_copy(update={"revision":2})
        repo.put(r)
        b = b.model_copy(update={"registration":pin(r)})
    if case == "mismatched_media":
        other, _ = anchors(repo, "TEST-ONLY-other", "d" * 64)
        b = b.model_copy(update={"media":pin(other)})
    if case == "seal_kind": b = b.model_copy(update={"seal":b.seal.model_copy(update={"intent":pin(m)})})
    if case == "plan_kind": b = b.model_copy(update={"plan":b.plan.model_copy(update={"intents":(pin(m),)})})
    with pytest.raises(ValueError): repo.put(b)
    assert repo.all("IntentBinding") == ()


@pytest.mark.parametrize("old,new", tuple(product(CLASSES, repeat=2)))
def test_all_sixteen_provenance_transitions(env, old, new):
    repo, i, m, r = env
    first = binding(i, m, r, old)
    repo.put(first)
    next_record = binding(i, m, r, new, revision=2, predecessor=pin(first))
    allowed = {"SEALED":{"SEALED","CONTEMPORANEOUS","RECONSTRUCTED"},
        "CONTEMPORANEOUS":{"CONTEMPORANEOUS","RECONSTRUCTED"},
        "RECONSTRUCTED":{"RECONSTRUCTED"}, "PROMPT_ONLY":{"PROMPT_ONLY","RECONSTRUCTED"}}
    if new in allowed[old]:
        repo.put(next_record)
        assert repo.get(next_record.ref).provenance == new
    else:
        with pytest.raises(ValueError, match="provenance"): repo.put(next_record)
    assert repo.get(first.ref).canonical() == first.canonical()
    assert repo.put(first) == first.digest


def aliases(repo, m, r, mode="both"):
    if mode in ("both", "media"):
        m = m.model_copy(update={"id":m.id+"-alias"})
        repo.put(m)
    r = r.model_copy(update={"id":r.id+"-alias", "media":m.ref, "created_at":T+timedelta(days=1)})
    repo.put(r)
    return m, r


@pytest.mark.parametrize("mode", ["rename", "ingestion", "media", "both", "intent", "anchors", "predecessor"])
def test_edits_and_aliases_cannot_reset_ceiling(env, mode):
    repo, i, m, r = env
    first = binding(i, m, r)
    repo.put(first)
    updates = dict(id=first.id, revision=2, predecessor=pin(first))
    if mode in ("ingestion", "media", "both", "anchors"):
        m, r = aliases(repo, m, r, mode if mode != "anchors" else "both")
    if mode in ("rename", "ingestion", "media", "both"):
        updates = dict(id="TEST-ONLY-renamed")
    if mode == "intent":
        i = intent(revision=2, predecessor=pin(i))
        repo.put(i)
    if mode == "predecessor": updates["predecessor"] = pin(first).model_copy(update={"sha256":"f" * 64})
    with pytest.raises(ValueError, match="lineage|anchors|provenance|digest"):
        repo.put(binding(i, m, r, "SEALED", **updates))
    other_m, other_r = anchors(repo, "TEST-ONLY-independent", "d" * 64)
    repo.put(binding(i, other_m, other_r, "SEALED", id="TEST-ONLY-independent"))
    assert repo.get(first.ref).canonical() == first.canonical()


def test_competing_writers_share_checksum_lineage(tmp_path):
    url = "sqlite:///" + str(tmp_path / "TEST-ONLY.sqlite")
    a, b = Repository(url), Repository(url)
    i = intent()
    a.put(i)
    m, r = anchors(a)
    alias_m, alias_r = aliases(a, m, r)
    candidates = [binding(i, m, r), binding(i, alias_m, alias_r, "SEALED", id="TEST-ONLY-race")]
    barrier = Barrier(2)
    def write(repo, candidate):
        original = repo._validate_links
        def synchronized(item):
            original(item)
            barrier.wait(timeout=10)
        repo._validate_links = synchronized
        try: return repo.put(candidate)
        except ValueError as error: return str(error)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(write, (a,b), candidates))
    stored = a.all("IntentBinding")
    assert len(stored) == 1 and stored[0].digest in results
    assert sum("lineage" in value for value in results) == 1
    a.close()
    b.close()
    reopened = Repository(url)
    assert reopened.get(stored[0].ref).canonical() == stored[0].canonical()
    reopened.close()


def test_legacy_view_and_adaptation_cannot_upgrade(env):
    repo, i, m, r = env
    legacy = IntentSpec(id=TEXT, created_at=T, owner=TEXT, objective=TEXT, audience=TEXT,
        context=TEXT, authority="human_declared", approved_by=TEXT,
        criteria=(Criterion(dimension=Dimension.MOTION, rationale=TEXT, acceptance=TEXT),))
    repo.put(legacy)
    payload, digest = legacy.canonical(), legacy.digest
    view = LegacyIntentView(source=repo.get(legacy.ref))
    assert (view.ref, view.digest, view.provenance) == (legacy.ref, digest, "RECONSTRUCTED")
    assert view.source.canonical() == payload and sha256(payload.encode()).hexdigest() == digest
    assert not {"revision_reason", "use_context", "seal", "plan"} & view.model_dump().keys()
    with pytest.raises(ValueError): view.provenance = "SEALED"
    first = binding(legacy, m, r, "SEALED")
    repo.put(first)
    assert first.provenance == "RECONSTRUCTED"
    with pytest.raises(ValueError, match="provenance"):
        repo.put(binding(i, m, r, "SEALED", revision=2, predecessor=pin(first)))
    assert repo.get(legacy.ref).canonical() == payload


def test_equivalent_offsets_and_replay_are_deterministic(env):
    repo, i, m, r = env
    b = binding(i, m, r, "SEALED")
    data = b.model_dump()
    zone = timezone(timedelta(hours=5))
    data["registered_at"] = b.registered_at.astimezone(zone)
    data["seal"]["sealed_at"] = b.seal.sealed_at.astimezone(zone)
    data["plan"]["planned_at"] = b.plan.planned_at.astimezone(zone)
    equivalent = IntentBinding(**data)
    assert equivalent.canonical() == b.canonical() and equivalent.digest == b.digest
    assert repo.put(b) == repo.put(equivalent)


@pytest.mark.parametrize("alias_first", [False, True])
def test_actual_workspace_snapshot_closure_and_frozen_export(tmp_path, media_tools, codec_videos, alias_first):
    root = tmp_path / "TEST-ONLY-workspace"
    p = PilotWorkspace(root)
    p._store = MediaStore(root / "media", media_tools)
    p.init("TEST-ONLY-dataset", TEXT)
    clip = p.register("TEST-ONLY-dataset", "TEST-ONLY-clip", codec_videos["cfr"], TEXT, TEXT)
    i = intent()
    p.repo.put(i)
    m, r = p.repo.get(clip.media), p.repo.get(clip.ingestion)
    if alias_first: m, r = aliases(p.repo, m, r)
    first = binding(i, m, r, "SEALED")
    p.repo.put(first)
    other_m, other_r = anchors(p.repo, "TEST-ONLY-unrelated", "d" * 64)
    unrelated = binding(i, other_m, other_r, id="TEST-ONLY-unrelated")
    p.repo.put(unrelated)
    snap = p.snapshot("TEST-ONLY-dataset", "TEST-ONLY-snapshot")
    frozen = json.dumps(p.export_snapshot(snap.id), sort_keys=True)
    refs = {x.ref for x in snap.records}
    assert {first.ref, i.ref, m.ref, r.ref, clip.media, clip.ingestion} <= refs
    assert unrelated.ref not in refs and other_m.ref not in refs and other_r.ref not in refs
    for record in snap.records:
        obj = p.repo.get(record.ref)
        assert obj.digest == record.sha256 and set(refs_in(obj)) <= refs
    if alias_first:
        with pytest.raises(ValueError, match="lineage"):
            p.repo.put(binding(i, p.repo.get(clip.media), p.repo.get(clip.ingestion), id="TEST-ONLY-second-lineage"))
    newer = intent(revision=2, predecessor=pin(i))
    p.repo.put(newer)
    second = binding(newer, m, r, revision=2, predecessor=pin(first))
    p.repo.put(second)
    later = p.snapshot("TEST-ONLY-dataset", "TEST-ONLY-later")
    assert {first.ref, second.ref, i.ref, newer.ref} <= {x.ref for x in later.records}
    assert p.status("TEST-ONLY-dataset")["clips"][0]["quality_verdict"] == "UNKNOWN"
    assert json.dumps(p.export_snapshot(snap.id), sort_keys=True) == frozen
    assert content_identity(p.repo.get, clip.media, clip.ingestion) == content_identity(p.repo.get, m.ref, r.ref)
    p.close()
    reopened = PilotWorkspace(root)
    assert json.dumps(reopened.export_snapshot(snap.id), sort_keys=True) == frozen
    reopened.close()


def test_snapshot_help_describes_private_binding_history(capsys):
    with pytest.raises(SystemExit): parser().parse_args(["snapshot", "--help"])
    assert "binding" in capsys.readouterr().out.lower()


@pytest.mark.parametrize("field,updates", [("use_context", {"surface":" "}),
    ("use_context", {"viewing_profile":"INVALID"}), ("criteria", {"tolerance":" "}),
    ("criteria", {"priority":"INVALID"}), ("expected_deviations", {"description":" "}),
    ("expected_deviations", {"criterion_id":"missing"})])
def test_nested_copies_rejected_at_all_entry_points(env, field, updates):
    repo, i, _, _ = env
    valid = intent(id="TEST-ONLY-nested", expected_deviations=[dict(dimension="motion_plausibility", description=TEXT, criterion_id="criterion")])
    value = getattr(valid, field)
    updated = value[0].model_copy(update=updates) if isinstance(value, tuple) else value.model_copy(update=updates)
    replacement = (updated,) if isinstance(value, tuple) else updated
    error = "same dimension" if "criterion_id" in updates else next(iter(updates))
    with pytest.raises(ValidationError, match=error): IntentSpecV2(**(valid.model_dump() | {field:replacement}))
    invalid = valid.model_copy(update={field:replacement})
    with pytest.raises(ValidationError, match=error): IntentSpecV2.model_validate_json(invalid.canonical())
    with pytest.raises(ValidationError, match=error): repo.put(invalid)
    with pytest.raises(KeyError): repo.get(valid.ref)
    assert repo.put(valid) == valid.digest
    assert repo.get(valid.ref).canonical() == valid.canonical()
    assert repo.get(i.ref).digest == i.digest


@pytest.mark.parametrize("field", ["registered_at", "registration", "media"])
def test_required_registration_anchors_cannot_be_absent(env, field):
    repo, i, m, r = env
    data = binding(i, m, r).model_dump()
    data.pop(field)
    with pytest.raises(ValueError): IntentBinding(**data)
    with pytest.raises(ValueError): IntentBinding(**(data | {field:None}))


@pytest.mark.parametrize("case", ["missing", "stale", "cross_id", "wrong_kind"])
def test_binding_predecessor_paths(env, case):
    repo, i, m, r = env
    first = binding(i, m, r)
    repo.put(first)
    second = binding(i, m, r, revision=2, predecessor=pin(first))
    repo.put(second)
    prior = pin(second)
    if case == "missing": prior = None
    if case == "stale": prior = pin(first)
    if case == "cross_id": prior = Pin(ref=Ref(kind="IntentBinding", id="other", revision=2), sha256=second.digest)
    if case == "wrong_kind": prior = pin(i)
    with pytest.raises(ValueError): binding(i, m, r, revision=3, predecessor=prior)
    with pytest.raises(ValueError): repo.put(second.model_copy(update={"revision":3, "predecessor":prior}))
    assert tuple(x.digest for x in repo.all("IntentBinding")) == (first.digest, second.digest)


def test_documented_example_is_executable():
    from pathlib import Path
    doc = (Path(__file__).parents[1] / "docs/intent-provenance.md").read_text()
    example = doc.split("```python\n", 1)[1].split("```", 1)[0]
    namespace = {}
    exec(compile(example, "TEST-ONLY-documentation-example", "exec"), namespace)
    assert namespace["second"].predecessor == pin(namespace["first"])


@pytest.mark.parametrize("target", ["intent", "context", "seal", "binding"])
def test_model_validate_rechecks_existing_copied_instances(env, target):
    _, i, m, r = env
    b = binding(i, m, r, "SEALED")
    invalid = {"intent":i.model_copy(update={"revision_reason":None}),
        "context":i.use_context.model_copy(update={"surface":" "}),
        "seal":b.seal.model_copy(update={"sealed_at":T.replace(tzinfo=None)}),
        "binding":b.model_copy(update={"origin":"INVALID"})}[target]
    with pytest.raises(ValueError): type(invalid).model_validate(invalid)
