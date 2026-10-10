"""TEST-ONLY chronology and exact-pair role oracles; no real clip judgments."""
from datetime import timedelta
from types import SimpleNamespace
import pytest
from pydantic import ValidationError
from eval_lab import domain as d, generation as g, test_plans as tp, evidence_roles as er
from eval_lab.persistence import Repository
from eval_lab.pilot_domain import PilotClip
from test_competing_sets import seed, competing
from test_intent_v2 import anchors
from test_test_plans import T, form
from test_assessments import observation
from test_generation import PLAN


def at(seconds):
    return T + timedelta(seconds=seconds)


@pytest.fixture
def make(tmp_path, monkeypatch):
    repo = Repository("sqlite:///" + str(tmp_path / "pilot.sqlite"))
    hs = seed(repo)
    def build(h=10, e=30, registered=25, member=True, linked=True, frozen=True, measurement="HUMAN"):
        hyp = hs[0].model_copy(update=dict(id="TEST-ONLY-query-h", created_at=at(h))); repo.put(hyp)
        group = competing((hyp if member else hs[1],), id="TEST-ONLY-role-set", exhaustive=True); repo.put(group)
        draft = tp.TestPlan(**form(group, predictions={group.members[0].id: ["TEST-ONLY-X"]},
            measurement=dict(kind=measurement, protocol="TEST-ONLY run protocol"))); repo.put(draft)
        monkeypatch.setattr(tp, "now", lambda: at(20))
        plan = tp.freeze(repo, "TEST-ONLY-plan@1") if frozen else draft
        media, registration = anchors(repo, "TEST-ONLY-arm-clip", "d" * 64, at(registered))
        clip = PilotClip(id="TEST-ONLY-arm-clip", created_at=at(registered), media=media.ref,
            ingestion=registration.ref, selected_by="TEST-ONLY selector", label="TEST-ONLY source"); repo.put(clip)
        ev = d.Evidence(id="TEST-ONLY-frame", created_at=at(e), media=media.ref, source="synthetic_fixture",
            observation="TEST-ONLY frame record", method="TEST-ONLY sampled frame", coverage="sampled_frames",
            sampling_manifest=(.4,), author="TEST-ONLY viewer", independence_group="TEST-ONLY session"); repo.put(ev)
        link = er.EvidenceArm(id="TEST-ONLY-link", author="TEST-ONLY linker", evidence=g.pin(ev),
            plan=g.pin(plan), arm="TEST-ONLY-arm", clip=g.pin(clip))
        if linked: repo.put(link)
        return SimpleNamespace(repo=repo, h=hyp, e=ev, m=media, r=registration, c=clip, p=plan, link=link)
    yield build
    repo.close()


def role(x, **changes):
    return er.compute(x.repo, g.pin(changes.get("e", x.e)), g.pin(changes.get("h", x.h)))


@pytest.mark.parametrize("fields,expected,reason", [
    ({"linked": False}, "SUPPORTING", "NO_FROZEN_ARM"),
    ({}, "TEST_RESULT", "POST_FREEZE_CLIP"),
    ({"registered": 5}, "SUPPORTING", "EXISTING_CLIP"),
    ({"h": 25}, "SUPPORTING", "HYPOTHESIS_NOT_BEFORE_FREEZE"),
    ({"h": 20}, "SUPPORTING", "HYPOTHESIS_NOT_BEFORE_FREEZE"),
    ({"member": False}, "SUPPORTING", "HYPOTHESIS_NOT_FROZEN_MEMBER"),
    ({"e": 20}, "SUPPORTING", "EVIDENCE_NOT_AFTER_FREEZE"),
    ({"registered": 20}, "SUPPORTING", "EXISTING_CLIP"),
    ({"frozen": False}, "SUPPORTING", "NO_FROZEN_ARM"),
    ({"e": 5, "registered": 1}, "DISCOVERY", "EXISTED_AT_HYPOTHESIS"),
    ({"e": 10, "linked": False}, None, "CREATION_ORDER_UNKNOWN"),
])
def test_literal_acceptance_and_each_test_result_conjunct(make, fields, expected, reason):
    x = make(**fields); before = (x.h.canonical(), x.e.canonical(), x.p.canonical())
    result = role(x)
    assert result["role"] == expected and result["reason"] == reason
    assert result["status"] == ("UNKNOWN" if expected is None else "COMPUTED")
    assert result["rule_version"] == "evidence-roles-v1" and result["tool_version"] == "0.1.0"
    assert result["first_view"] == "Pair-level first-view events are not recorded."
    assert (x.repo.get(x.h.ref).canonical(), x.repo.get(x.e.ref).canonical(), x.repo.get(x.p.ref).canonical()) == before


def test_exact_member_revision_and_later_set_do_not_float(make):
    x = make(member=False)
    group = x.repo.get(x.p.competing_set.ref)
    x.repo.put(group.model_copy(update=dict(revision=2, supersedes=group.ref, members=(x.h.ref,))))
    assert role(x)["reason"] == "HYPOTHESIS_NOT_FROZEN_MEMBER"
    revised = x.h.model_copy(update=dict(revision=2, created_at=at(15))); x.repo.put(revised)
    assert role(x, h=revised)["reason"] == "HYPOTHESIS_NOT_FROZEN_MEMBER"


def test_pair_specific_discovery_and_prompt_citation_tie(make):
    x = make(e=10, linked=False)
    obs = observation(x.m, x.e, created_at=at(9)); x.repo.put(obs)
    context = er.HypothesisContext(id="TEST-ONLY-prompt", author="TEST-ONLY author",
        hypothesis=g.pin(x.h), observation=g.pin(obs)); x.repo.put(context)
    assert role(x)["role"] == "DISCOVERY" and role(x)["reason"] == "PROMPTING_OBSERVATION"
    early = x.h.model_copy(update=dict(id="TEST-ONLY-early", created_at=at(3))); x.repo.put(early)
    assert role(x, h=early)["role"] == "SUPPORTING"
    later = x.h.model_copy(update=dict(id="TEST-ONLY-later", created_at=at(40))); x.repo.put(later)
    assert role(x, h=later)["reason"] == "EXISTED_AT_HYPOTHESIS"


def run_for(x, **changes):
    return er.InstrumentRun(**(dict(id="TEST-ONLY-run", author="TEST-ONLY operator", evidence=g.pin(x.e),
        plan=g.pin(x.p), arm="TEST-ONLY-arm", executed_at=at(22), created_at=at(35),
        tool="TEST-ONLY meter", version="TEST-ONLY v3", tool_sha256="e" * 64,
        input_sha256="d" * 64, output_sha256=x.e.digest) | changes))


def test_retained_run_alternative_and_source_label_is_insufficient(make):
    x = make(registered=1, measurement="INSTRUMENT", linked=False)
    x.e = x.e.model_copy(update=dict(id="TEST-ONLY-instrument-e", source="instrument")); x.repo.put(x.e)
    x.link = x.link.model_copy(update=dict(evidence=g.pin(x.e))); x.repo.put(x.link)
    assert role(x)["reason"] == "EXISTING_CLIP"
    run = run_for(x); x.repo.put(run)
    correction = x.link.model_copy(update=dict(revision=2, predecessor=g.pin(x.link),
        revision_reason="TEST-ONLY attach declared run", run=g.pin(run))); x.repo.put(correction)
    result = role(x)
    assert result["role"] == "TEST_RESULT" and result["reason"] == "POST_FREEZE_RUN"
    assert result["selected_link"]["ref"] == {"kind": "EvidenceArm", "id": "TEST-ONLY-link", "revision": 2}


def test_original_registration_same_bytes_and_late_first_view(make):
    x = make()
    anchors(x.repo, "TEST-ONLY-earlier-bytes", "d" * 64, at(2))
    revised = x.c.model_copy(update=dict(revision=2, created_at=at(29))); x.repo.put(revised)
    x.repo.put(x.link.model_copy(update=dict(revision=2, predecessor=g.pin(x.link), clip=g.pin(revised),
        revision_reason="TEST-ONLY later clip revision")))
    x.repo.put(g.FirstView(media=g.pin(x.m), registration=g.pin(x.r), created_at=at(50)))
    assert role(x)["role"] == "SUPPORTING" and role(x)["reason"] == "EXISTING_CLIP"


@pytest.mark.parametrize("field,value,message", [
    ("role", "TEST_RESULT", "Extra inputs are not permitted"),
    ("reason", "TEST-ONLY fake", "Extra inputs are not permitted"),
    ("evidence", "hypothesis", "pin must reference Evidence"),
    ("plan", "hypothesis", "pin must reference TestPlan"),
    ("clip", "hypothesis", "pin must reference PilotClip"),
    ("run", "hypothesis", "pin must reference InstrumentRun"),
    ("origin", "hypothesis", "pin must reference ClipOrigin"),
])
def test_context_contract_copied_admission(make, field, value, message):
    x = make(linked=False)
    with pytest.raises(ValidationError, match=message):
        x.repo.put(x.link.model_copy(update={"id": "TEST-ONLY-invalid-copy", field: g.pin(x.h) if value == "hypothesis" else value}))
    x.repo.put(x.link)


@pytest.mark.parametrize("case,message,error", [
    ("arm", "arm absent from pinned plan", ValueError),
    ("digest", "pinned artifact digest mismatch", ValueError),
    ("media", "evidence/clip media mismatch", ValueError),
    ("nested", "Extra inputs are not permitted", ValidationError),
    ("revision", "pins require an explicit revision", ValidationError),
    ("initial", "initial revision cannot have a predecessor", ValidationError),
])
def test_link_admission_guards_are_isolated(make, case, message, error):
    x = make(linked=False); updates = {"id": "TEST-ONLY-invalid-" + case}
    if case == "arm": updates["arm"] = "TEST-ONLY-absent-arm"
    if case == "digest": updates["plan"] = g.pin(x.p).model_copy(update={"sha256": "f" * 64})
    if case == "media":
        m, r = anchors(x.repo, "TEST-ONLY-other-media", "a" * 64, at(24))
        c = x.c.model_copy(update=dict(id="TEST-ONLY-other-clip", media=m.ref, ingestion=r.ref)); x.repo.put(c)
        updates["clip"] = g.pin(c)
    if case == "nested": updates["evidence"] = g.pin(x.e).model_copy(update={"role": "DISCOVERY"})
    if case == "revision":
        updates["evidence"] = g.pin(x.e).model_dump(); del updates["evidence"]["ref"]["revision"]
    if case == "initial":
        x.repo.put(x.link); updates["predecessor"] = g.pin(x.link)
    with pytest.raises(error, match=message): x.repo.put(x.link.model_copy(update=updates))


@pytest.mark.parametrize("case,message", [("reason", "revision reason required"), ("predecessor", "immediate same-kind")])
def test_correction_contract_without_conflicting_revision(make, case, message):
    x = make(); updates = dict(revision=2, predecessor=g.pin(x.link), revision_reason="TEST-ONLY fix")
    updates[case if case == "predecessor" else "revision_reason"] = None
    with pytest.raises(ValidationError, match=message): x.repo.put(x.link.model_copy(update=updates))


def test_prompt_time_and_subject_immutability(make):
    x = make(linked=False); obs = observation(x.m, x.e, created_at=at(11)); x.repo.put(obs)
    context = er.HypothesisContext(id="TEST-ONLY-late-prompt", author="TEST-ONLY author", hypothesis=g.pin(x.h), observation=g.pin(obs))
    with pytest.raises(ValueError, match="prompting observation must predate or equal hypothesis"):
        x.repo.put(context)
    old = observation(x.m, x.e, id="TEST-ONLY-old-prompt", created_at=at(9)); x.repo.put(old)
    context = context.model_copy(update=dict(id="TEST-ONLY-good-prompt", observation=g.pin(old))); x.repo.put(context)
    h = x.h.model_copy(update=dict(id="TEST-ONLY-other-h")); x.repo.put(h)
    with pytest.raises(ValueError, match="context subject is immutable"):
        x.repo.put(context.model_copy(update=dict(revision=2, predecessor=g.pin(context), hypothesis=g.pin(h), revision_reason="TEST-ONLY correction")))


@pytest.mark.parametrize("changes,message", [
    ({"executed_at": at(31)}, "run cannot follow result evidence"),
    ({"created_at": at(21)}, "run cannot follow import time"),
    ({"output_sha256": "b" * 64}, "run output digest mismatch"),
    ({"arm": "TEST-ONLY-missing"}, "arm absent from pinned plan"),
])
def test_run_admission_guards(make, changes, message):
    x = make(measurement="INSTRUMENT", linked=False)
    with pytest.raises(ValueError, match=message): x.repo.put(run_for(x, **changes))


def test_run_requires_instrument_declaration(make):
    x = make(linked=False)
    with pytest.raises(ValueError, match="run requires INSTRUMENT measurement"): x.repo.put(run_for(x))


@pytest.mark.parametrize("case,message", [("input", "run input content mismatch"), ("plan", "run/link context mismatch"), ("evidence", "run/link context mismatch")])
def test_run_link_checks_distinct_fields(make, case, message):
    x = make(measurement="INSTRUMENT", linked=False); changes = {}
    if case == "input": changes["input_sha256"] = "c" * 64
    if case == "plan":
        other = tp.TestPlan(**form(x.repo.get(x.p.competing_set.ref), id="TEST-ONLY-other-plan", predictions={x.h.id: ["TEST-ONLY-X"]}, measurement=dict(kind="INSTRUMENT", protocol="TEST-ONLY distinct protocol")))
        x.repo.put(other); changes["plan"] = g.pin(other)
    if case == "evidence":
        other = x.e.model_copy(update=dict(id="TEST-ONLY-other-result")); x.repo.put(other)
        changes.update(evidence=g.pin(other), output_sha256=other.digest)
    run = run_for(x, **changes); x.repo.put(run)
    with pytest.raises(ValueError, match=message): x.repo.put(x.link.model_copy(update={"run": g.pin(run)}))


def test_generation_origin_plan_consistency(make):
    x = make(linked=False); gp = g.record_plan(x.repo, PLAN | {"id": "TEST-ONLY-generation"})
    other = g.record_plan(x.repo, PLAN | {"id": "TEST-ONLY-other-generation", "arm": "TEST-ONLY-other-arm"})
    plan = tp.TestPlan(**form(x.repo.get(x.p.competing_set.ref), id="TEST-ONLY-generated-plan",
        predictions={x.h.id: ["TEST-ONLY-X"]}, arms=[dict(id="TEST-ONLY-arm", description="TEST-ONLY generated", generation_plan_ref=g.pin(gp))],
        sample_design=dict(n_per_arm=2, decision_rule="TEST-ONLY compare"))); x.repo.put(plan)
    origin = g.record_origin(x.repo, x.c, other)
    link = x.link.model_copy(update=dict(plan=g.pin(plan), origin=g.pin(origin)))
    with pytest.raises(ValueError, match="generation origin/arm mismatch"): x.repo.put(link)


def test_readonly_missing_and_corrupt_pins(make):
    x = make()
    missing = g.pin(x.e).model_copy(update={"ref": d.Ref(kind="Evidence", id="TEST-ONLY-missing")})
    assert er.compute(x.repo, missing, g.pin(x.h))["status"] == "UNKNOWN"
    bad = g.pin(x.h).model_copy(update={"sha256": "0" * 64})
    result = er.compute(x.repo, g.pin(x.e), bad)
    assert result["status"] == "INTEGRITY_FAILURE" and result["role"] is None
    assert "pinned artifact digest mismatch" in result["detail"]


@pytest.mark.parametrize("executed,expected,reason", [(19, "SUPPORTING", "EXISTING_CLIP"), (20, "SUPPORTING", "EXISTING_CLIP"), (21, "TEST_RESULT", "POST_FREEZE_RUN")])
def test_run_freeze_boundary_is_strict(make, executed, expected, reason):
    x = make(registered=1, measurement="INSTRUMENT", linked=False)
    run = run_for(x, executed_at=at(executed)); x.repo.put(run)
    x.repo.put(x.link.model_copy(update=dict(run=g.pin(run))))
    result = role(x)
    assert result["role"] == expected and result["reason"] == reason


def test_all_links_checked_in_stable_order_and_test_result_precedes_discovery(make):
    x = make(linked=False)
    draft = x.repo.get(d.Ref(kind="TestPlan", id="TEST-ONLY-plan", revision=1))
    x.repo.put(x.link.model_copy(update=dict(id="TEST-ONLY-a-draft", plan=g.pin(draft))))
    x.repo.put(x.link.model_copy(update=dict(id="TEST-ONLY-z-frozen")))
    obs = observation(x.m, x.e, created_at=at(8)); x.repo.put(obs)
    x.repo.put(er.HypothesisContext(id="TEST-ONLY-prompt-precedence", author="TEST-ONLY observer", hypothesis=g.pin(x.h), observation=g.pin(obs)))
    permuted = SimpleNamespace(get=x.repo.get, all=lambda name: tuple(reversed(x.repo.all(name))))
    results = [role(x), er.compute(permuted, g.pin(x.e), g.pin(x.h))]
    for result in results:
        assert result["role"] == "TEST_RESULT" and result["reason"] == "POST_FREEZE_CLIP"
        assert result["selected_link"]["ref"] == {"kind": "EvidenceArm", "id": "TEST-ONLY-z-frozen", "revision": 1}
    assert results[0] == results[1]  # Enumeration invariance, with literal oracles above.


@pytest.mark.parametrize("h,e,expected,reason", [(25, 30, "SUPPORTING", "HYPOTHESIS_NOT_BEFORE_FREEZE"), (10, 5, "DISCOVERY", "EXISTED_AT_HYPOTHESIS")])
def test_known_failed_predicate_does_not_require_source_chronology(make, h, e, expected, reason):
    x = make(h=h, e=e)
    def missing(ref):
        if ref == x.r.ref: raise KeyError("TEST-ONLY missing registration")
        return x.repo.get(ref)
    result = er.compute(SimpleNamespace(get=missing, all=x.repo.all), g.pin(x.e), g.pin(x.h))
    assert result["role"] == expected and result["reason"] == reason


@pytest.mark.parametrize("case,message", [("missing", "generation origin/arm mismatch"), ("clip", "origin/clip mismatch")])
def test_origin_missing_or_from_another_clip_is_rejected(make, case, message):
    x = make(linked=False); gp = g.record_plan(x.repo, PLAN | {"id": "TEST-ONLY-planned-source"})
    plan = tp.TestPlan(**form(x.repo.get(x.p.competing_set.ref), id="TEST-ONLY-origin-plan",
        predictions={x.h.id: ["TEST-ONLY-X"]}, arms=[dict(id="TEST-ONLY-arm", description="TEST-ONLY origin check", generation_plan_ref=g.pin(gp))],
        sample_design=dict(n_per_arm=3, decision_rule="TEST-ONLY source check"))); x.repo.put(plan)
    other = x.c.model_copy(update=dict(id="TEST-ONLY-different-clip")); x.repo.put(other)
    origin = g.record_origin(x.repo, other, gp)
    link = x.link.model_copy(update=dict(plan=g.pin(plan), origin=None if case == "missing" else g.pin(origin)))
    with pytest.raises(ValueError, match=message): x.repo.put(link)
    correct = g.record_origin(x.repo, x.c, gp)
    x.repo.put(link.model_copy(update=dict(origin=g.pin(correct))))


@pytest.mark.parametrize("field,kind_name", [("hypothesis", "Hypothesis"), ("observation", "TechnicalObservation")])
def test_prompt_pin_kinds(make, field, kind_name):
    x = make(linked=False); obs = observation(x.m, x.e, created_at=at(5)); x.repo.put(obs)
    data = dict(id="TEST-ONLY-pin-kind", author="TEST-ONLY reader", hypothesis=g.pin(x.h), observation=g.pin(obs))
    with pytest.raises(ValidationError, match="pin must reference " + kind_name):
        x.repo.put(er.HypothesisContext.model_construct(**(data | {field: g.pin(x.e)})))


def test_new_revision_of_frozen_member_does_not_inherit_membership(make):
    x = make()
    later = x.h.model_copy(update=dict(revision=2, created_at=at(15))); x.repo.put(later)
    result = role(x, h=later)
    assert result["role"] == "SUPPORTING" and result["reason"] == "HYPOTHESIS_NOT_FROZEN_MEMBER"
    assert role(x)["role"] == "TEST_RESULT"


@pytest.mark.parametrize("case,message", [("anchors", "clip registration anchors changed"), ("registration", "original registration required")])
def test_original_clip_and_registration_guards(make, case, message):
    x = make(linked=False)
    if case == "anchors":
        media, registration = anchors(x.repo, "TEST-ONLY-swapped", "a" * 64, at(26))
        ev = x.e.model_copy(update=dict(id="TEST-ONLY-swapped-e", media=media.ref)); x.repo.put(ev)
        clip = x.c.model_copy(update=dict(revision=2, media=media.ref, ingestion=registration.ref))
    else:
        registration = x.r.model_copy(update=dict(revision=2, created_at=at(27))); x.repo.put(registration)
        ev = x.e; clip = x.c.model_copy(update=dict(id="TEST-ONLY-revised-registration", ingestion=registration.ref))
        x.repo.put(clip)
    link = x.link.model_copy(update=dict(id="TEST-ONLY-anchor-guard", evidence=g.pin(ev), clip=g.pin(clip)))
    def get(ref):
        return clip if ref == clip.ref else x.repo.get(ref)
    with pytest.raises(ValueError, match=message): er.validate_admission(link, get)
