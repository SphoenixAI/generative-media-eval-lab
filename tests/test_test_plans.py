"""TEST-ONLY qualitative predictions and integrity; never real test outcomes."""
from copy import deepcopy
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from eval_lab import domain as d, generation as g, test_plans as tp
from eval_lab.persistence import Repository
from test_competing_sets import seed, competing
from test_generation import PLAN

T = datetime(2026, 10, 9, tzinfo=timezone.utc)
A, B, C = "TEST-ONLY-h0", "TEST-ONLY-h1", "TEST-ONLY-h2"
X, Y, Z = "TEST-ONLY-X", "TEST-ONLY-Y", "TEST-ONLY-Z"


def form(group, **changes):
    return dict(id="TEST-ONLY-plan", created_at=T, author="TEST-ONLY planner",
        competing_set=g.pin(group), arms=[dict(id="TEST-ONLY-arm", description="TEST-ONLY comparison", generation_plan_ref=None)],
        measurement=dict(kind="HUMAN", protocol="TEST-ONLY count declared categories"),
        outcome_categories=[X, Y, Z], predictions={A: [X], B: [Y]}) | changes


@pytest.fixture
def env(tmp_path):
    repo = Repository("sqlite:///" + str(tmp_path / "pilot.sqlite"))
    hs = seed(repo); group = competing(hs[:2], exhaustive=True); repo.put(group)
    yield repo, group
    repo.close()


@pytest.mark.parametrize("predictions,label,compatible", [
    ({A: [X], B: [X]}, "NON_DIAGNOSTIC", {X: [A, B], Y: [], Z: []}),
    ({A: [X], B: [Y]}, "DECISIVE", {X: [A], Y: [B], Z: []}),
    ({A: [X, Y], B: [Y]}, "PARTIALLY_DIAGNOSTIC", {X: [A], Y: [A, B], Z: []}),
    ({A: [Y, X], B: [Y]}, "PARTIALLY_DIAGNOSTIC", {X: [A], Y: [A, B], Z: []}),
    ({A: [Y, X], B: [X, Y]}, "NON_DIAGNOSTIC", {X: [A, B], Y: [A, B], Z: []}),
])
@pytest.mark.parametrize("residual", [False, True])
def test_literal_classes_order_and_residual(env, predictions, label, compatible, residual):
    repo, group = env
    group = competing(repo.all("Hypothesis")[:2], id="TEST-ONLY-class-set", exhaustive=residual); repo.put(group)
    plan = tp.TestPlan(**form(group, predictions=predictions)); repo.put(plan)
    before = [h.canonical() for h in repo.all("Hypothesis")]
    expected = dict(diagnosticity=label, compatible=compatible,
        unpredicted=[Y, Z] if predictions == {A: [X], B: [X]} else [Z],
        residual="not testable by this plan" if residual else None)
    assert tp.diagnosticity(plan, repo.get) == expected
    assert tp.diagnosticity(repo.get(plan.ref), repo.get) == expected
    assert repo.get(plan.ref).frozen_at is None and repo.get(plan.ref).frozen_digest is None
    assert [h.canonical() for h in repo.all("Hypothesis")] == before


@pytest.mark.parametrize("members,predictions,label", [
    (1, {A: [X]}, "NON_DIAGNOSTIC"), (3, {A: [X], B: [X], C: [Y]}, "PARTIALLY_DIAGNOSTIC")])
def test_single_and_identical_pair(env, members, predictions, label):
    repo, _ = env
    group = competing(repo.all("Hypothesis")[:members], id="TEST-ONLY-boundary", exhaustive=True); repo.put(group)
    plan = tp.TestPlan(**form(group, predictions=predictions)); repo.put(plan)
    assert tp.diagnosticity(plan, repo.get)["diagnosticity"] == label
    assert tp.classify({}, [X], False) == dict(diagnosticity="NON_DIAGNOSTIC", compatible={X: []}, unpredicted=[X], residual=None)


@pytest.mark.parametrize("predictions,message,error", [
    ({A: [], B: [Y]}, "at least 1 item", ValidationError),
    ({A: [X]}, "exact named hypotheses", ValueError),
    ({A: [X], B: [Y], C: [Z]}, "exact named hypotheses", ValueError),
    ({A: [X], B: [Y], "RESIDUAL": [Z]}, "exact named hypotheses", ValueError),
    ({A: ["TEST-ONLY-absent"], B: [Y]}, "undeclared outcome", ValidationError),
    ({A: [X, X], B: [Y]}, "unique predicted outcomes", ValidationError),
])
def test_prediction_guards(env, predictions, message, error):
    repo, group = env
    with pytest.raises(error, match=message): repo.put(tp.TestPlan(**form(group, predictions=predictions)))
    assert repo.all("TestPlan") == ()


@pytest.mark.parametrize("design,message", [
    ({}, "exactly one"), ({"n_per_arm": 2, "stopping_rule": "TEST-ONLY stop"}, "exactly one"),
    ({"n_per_arm": 0}, "greater than 0"), ({"n_per_arm": -2}, "greater than 0"),
    ({"n_per_arm": True}, "valid integer"), ({"stopping_rule": " "}, "String should match pattern"),
    ({"n_per_arm": 3, "decision_rule": " "}, "String should match pattern"),
])
def test_sample_design_guard(env, design, message):
    _, group = env
    with pytest.raises(ValidationError, match=message):
        tp.TestPlan(**form(group, sample_design={"decision_rule": "TEST-ONLY compare all arms"} | design))


def test_generation_requires_design_in_mixed_arms_and_decision_rule(env):
    repo, group = env; generation = g.record_plan(repo, PLAN | {"id": "TEST-ONLY-generation"})
    arms = form(group)["arms"] + [dict(id="TEST-ONLY-generated", description="TEST-ONLY changed camera", generation_plan_ref=g.pin(generation))]
    with pytest.raises(ValidationError, match="sample_design required"):
        tp.TestPlan(**form(group, arms=arms))
    with pytest.raises(ValidationError, match=r"decision_rule\s+Field required"):
        tp.TestPlan(**form(group, arms=arms, sample_design={"n_per_arm": 7}))
    for n, design in enumerate((dict(n_per_arm=7), dict(stopping_rule="TEST-ONLY stop after review"))):
        plan = tp.TestPlan(**form(group, id=f"TEST-ONLY-design-{n}", arms=arms,
            sample_design=design | {"decision_rule": "TEST-ONLY retain inconclusive"}))
        repo.put(plan)
        assert plan.arms[1].generation_plan_ref.ref.id == "TEST-ONLY-generation"
    assert repo.all("TestPlan")[0].sample_design.n_per_arm == 7
    assert repo.all("TestPlan")[1].sample_design.stopping_rule == "TEST-ONLY stop after review"


@pytest.mark.parametrize("change,message", [
    ({"arms": []}, "at least 1 item"), ({"outcome_categories": []}, "at least 1 item"),
    ({"outcome_categories": [X, Y, Y]}, "unique outcome categories"),
    ({"arms": [dict(id="TEST-ONLY-a", description="TEST-ONLY left", generation_plan_ref=None),
               dict(id="TEST-ONLY-a", description="TEST-ONLY right", generation_plan_ref=None)]}, "unique arm IDs"),
    ({"measurement": dict(kind="AUTO", protocol="TEST-ONLY unsupported")}, "Input should be 'HUMAN' or 'INSTRUMENT'"),
    ({"measurement": dict(kind="HUMAN", protocol=" ")}, "String should match pattern"),
    ({"author": " "}, "String should match pattern"),
    ({"frozen_at": T}, "freeze fields must be paired"),
    ({"frozen_digest": "a" * 64}, "freeze fields must be paired"),
    ({"revision": 2}, "immediate same-kind"),
])
def test_structure_guards(env, change, message):
    _, group = env
    with pytest.raises(ValidationError, match=message): tp.TestPlan(**form(group, **change))


@pytest.mark.parametrize("case,message,error", [
    ("set-kind", "pin must reference CompetingSet", ValidationError),
    ("generation-kind", "pin must reference GenerationPlan", ValidationError),
    ("set-hash", "pinned artifact digest mismatch", ValueError),
    ("generation-hash", "pinned artifact digest mismatch", ValueError),
    ("missing", "TEST-ONLY-missing", KeyError),
    ("explicit", "explicit revision", ValidationError),
    ("nested-extra", "Extra inputs", ValidationError),
])
def test_pins_and_nested_copy_admission(env, case, message, error):
    repo, group = env; plan = tp.TestPlan(**form(group))
    gp = g.record_plan(repo, PLAN | {"id": "TEST-ONLY-gp"})
    if case == "set-kind": plan = plan.model_copy(update={"competing_set": g.pin(gp)})
    if case == "set-hash": plan = plan.model_copy(update={"competing_set": g.pin(group).model_copy(update={"sha256": "a" * 64})})
    if case == "missing": plan = plan.model_copy(update={"competing_set": g.pin(group).model_copy(update={"ref": d.Ref(kind="CompetingSet", id="TEST-ONLY-missing")})})
    if case.startswith("generation"):
        link = g.pin(group) if case == "generation-kind" else g.pin(gp).model_copy(update={"sha256": "b" * 64})
        plan = plan.model_copy(update={"arms": (plan.arms[0].model_copy(update={"generation_plan_ref": link}),),
            "sample_design": tp.SampleDesign(n_per_arm=4, decision_rule="TEST-ONLY compare")})
    if case == "nested-extra": plan = plan.model_copy(update={"measurement": plan.measurement.model_copy(update={"hidden": "TEST-ONLY injected"})})
    with pytest.raises(error, match=message):
        if case == "explicit":
            data = plan.model_dump(mode="json"); del data["competing_set"]["ref"]["revision"]
            tp.TestPlan.model_validate(data)
        else: repo.put(plan)
    assert repo.all("TestPlan") == ()


def test_freeze_successor_correction_and_exact_set_revision(env, monkeypatch):
    repo, group = env; monkeypatch.setattr(tp, "now", lambda: T)
    draft = tp.TestPlan(**form(group)); repo.put(draft)
    newer = group.model_copy(update={"revision": 2, "supersedes": group.ref, "members": (repo.all("Hypothesis")[-1].ref,)})
    repo.put(newer)
    frozen = tp.freeze(repo, "TEST-ONLY-plan@1")
    assert frozen.revision == 2 and frozen.predecessor == g.pin(draft)
    assert frozen.competing_set.ref.revision == 1 and frozen.predictions == {A: (X,), B: (Y,)}
    assert frozen.frozen_at == T and len(frozen.frozen_digest) == 64
    assert frozen.frozen_digest != frozen.digest and repo.get(draft.ref).frozen_digest is None
    with pytest.raises(ValueError, match="already frozen"): tp.freeze(repo, "TEST-ONLY-plan@2")
    with pytest.raises(ValueError, match="stale draft"): tp.freeze(repo, "TEST-ONLY-plan@1")
    correction = tp.TestPlan(**form(group, revision=3, predecessor=g.pin(frozen), predictions={A: [X, Y], B: [Y]})); repo.put(correction)
    assert tp.freeze(repo, "TEST-ONLY-plan@3").revision == 4
    reopened = Repository(str(repo.engine.url))
    assert reopened.get(frozen.ref).canonical() == frozen.canonical()
    assert [x.revision for x in reopened.all("TestPlan")] == [1, 2, 3, 4]
    reopened.close()


def test_freeze_admission_authorization_content_and_predecessor(env, monkeypatch):
    repo, group = env; monkeypatch.setattr(tp, "now", lambda: T)
    draft = tp.TestPlan(**form(group)); repo.put(draft)
    data = draft.model_dump(mode="json") | dict(revision=2, predecessor=g.pin(draft).model_dump(mode="json"), frozen_at=T.isoformat())
    # Use the declared wire timestamp format when constructing valid frozen candidates.
    data["frozen_at"] = "2026-10-09T00:00:00Z"
    data["frozen_digest"] = tp.freeze_digest(data)
    candidate = tp.TestPlan.model_validate(data)
    with pytest.raises(ValueError, match="explicit freeze command"): repo.put(candidate)
    changed = deepcopy(data); changed["measurement"]["protocol"] = "TEST-ONLY altered during freeze"
    changed["frozen_digest"] = tp.freeze_digest(changed)
    with pytest.raises(ValueError, match="freeze must preserve authored content"):
        repo.put(tp.TestPlan.model_validate(changed), _freeze_test_plan=True)
    bad = candidate.model_copy(update={"predecessor": g.pin(draft).model_copy(update={"sha256": "d" * 64})})
    bad = bad.model_copy(update={"frozen_digest": tp.freeze_digest(bad.model_dump(mode="json"))})
    with pytest.raises(ValueError, match="pinned artifact digest mismatch"): repo.put(bad, _freeze_test_plan=True)
    assert repo.all("TestPlan") == (draft,)


@pytest.mark.parametrize("field,value", [
    ("author", "TEST-ONLY changed author"), ("tool_version", "TEST-ONLY 9.8"),
    ("created_at", "2026-10-08T01:02:03Z"), ("frozen_at", "2026-10-09T01:02:03Z"),
    ("measurement", {"kind": "INSTRUMENT", "protocol": "TEST-ONLY declared only"}),
    ("outcome_categories", [Z, Y, X]), ("predictions", {A: [Y], B: [X]}),
    ("arms", [dict(id="TEST-ONLY-other-arm", description="TEST-ONLY other description", generation_plan_ref=None)]),
    ("sample_design", dict(n_per_arm=11, decision_rule="TEST-ONLY new rule")),
])
def test_frozen_digest_covers_fields(env, field, value):
    repo, group = env; draft = tp.TestPlan(**form(group)); repo.put(draft)
    frozen = tp.freeze(repo, "TEST-ONLY-plan@1")
    with pytest.raises(ValidationError, match="frozen digest mismatch"):
        tp.TestPlan.model_validate(frozen.model_dump(mode="json") | {field: value})


VECTOR = (
    b'{"arms":[{"description":"TEST-ONLY vector arm","generation_plan_ref":null,"id":"TEST-ONLY-arm"}],'
    b'"author":"TEST-ONLY vector author","canonicalization":"RFC8785",'
    b'"competing_set":{"ref":{"id":"TEST-ONLY-vector-set","kind":"CompetingSet","revision":3},'
    b'"sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},'
    b'"created_at":"2026-10-09T01:02:03Z","frozen_at":"2026-10-09T04:05:06Z","id":"TEST-ONLY-vector",'
    b'"measurement":{"kind":"INSTRUMENT","protocol":"TEST-ONLY declaration only"},'
    b'"number_profile":"safe-integer-tokens-v1","outcome_categories":["TEST-ONLY-X","TEST-ONLY-Y","TEST-ONLY-Z"],'
    b'"predecessor":{"ref":{"id":"TEST-ONLY-vector","kind":"TestPlan","revision":1},'
    b'"sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},'
    b'"predictions":{"TEST-ONLY-h0":["TEST-ONLY-X"],"TEST-ONLY-h1":["TEST-ONLY-Y"]},'
    b'"revision":2,"sample_design":{"decision_rule":"TEST-ONLY vector decision","n_per_arm":9,"stopping_rule":null},'
    b'"schema_version":1,"tool_version":"TEST-ONLY vector tool"}'
)


def test_literal_canonical_vector_and_digest():
    import json
    from eval_lab.canonical_json import canonicalize
    data = json.loads(VECTOR)
    assert canonicalize(data) == VECTOR
    plan = tp.TestPlan.model_validate(data | {"frozen_digest": "e2517c985ba3e137c80316c8d87b6b3edfb321767e31b3c232c81a44adf8a474"})
    assert canonicalize(plan.model_dump(mode="json", exclude={"frozen_digest"})) == VECTOR
    assert tp.freeze_digest(data) == "e2517c985ba3e137c80316c8d87b6b3edfb321767e31b3c232c81a44adf8a474"
    assert tp.freeze_digest(json.loads(json.dumps(dict(reversed(list(data.items()))), indent=4))) == "e2517c985ba3e137c80316c8d87b6b3edfb321767e31b3c232c81a44adf8a474"


@pytest.mark.parametrize("pin_field", ["predecessor", "competing_set"])
def test_frozen_digest_covers_pins(env, pin_field):
    repo, group = env; repo.put(tp.TestPlan(**form(group)))
    frozen = tp.freeze(repo, "TEST-ONLY-plan@1"); data = frozen.model_dump(mode="json")
    data[pin_field]["sha256"] = "f" * 64
    with pytest.raises(ValidationError, match="frozen digest mismatch"): tp.TestPlan.model_validate(data)


def test_nested_prediction_mutation_rejected_at_admission(env):
    repo, group = env; draft = tp.TestPlan(**form(group))
    draft.predictions[A] = ()
    with pytest.raises(ValidationError, match="at least 1 item"): repo.put(draft)


def test_freeze_transition_requires_draft_and_keeps_immutable_revisions(env, monkeypatch):
    repo, group = env; monkeypatch.setattr(tp, "now", lambda: T)
    draft = tp.TestPlan(**form(group)); repo.put(draft)
    frozen = tp.freeze(repo, "TEST-ONLY-plan@1")
    data = frozen.model_dump(mode="json") | dict(id="TEST-ONLY-initial-frozen", revision=1, predecessor=None)
    data["frozen_digest"] = tp.freeze_digest(data)
    with pytest.raises(ValueError, match="retained draft predecessor"):
        repo.put(tp.TestPlan.model_validate(data), _freeze_test_plan=True)
    data = frozen.model_dump(mode="json") | dict(revision=3, predecessor=g.pin(frozen).model_dump(mode="json"))
    data["frozen_digest"] = tp.freeze_digest(data)
    with pytest.raises(ValueError, match="already frozen"):
        repo.put(tp.TestPlan.model_validate(data), _freeze_test_plan=True)
    data = frozen.model_dump(mode="json"); data["measurement"]["protocol"] = "TEST-ONLY changed retained content"
    data["frozen_digest"] = tp.freeze_digest(data)
    with pytest.raises(ValueError, match="immutable revision conflict"): repo.put(tp.TestPlan.model_validate(data))
    assert [x.revision for x in repo.all("TestPlan")] == [1, 2]


@pytest.mark.parametrize("field,value,message", [
    ("id", " ", "String should match pattern"), ("description", " ", "String should match pattern"),
    ("generation_plan_ref", "omit", "Field required")])
def test_arm_fields_are_required(env, field, value, message):
    _, group = env; data = form(group)
    if value == "omit": del data["arms"][0][field]
    else: data["arms"][0][field] = value
    with pytest.raises(ValidationError, match=message): tp.TestPlan(**data)


def test_instrument_declaration_and_sample_size_profile(env):
    repo, group = env
    item = tp.TestPlan(**form(group, measurement=dict(kind="INSTRUMENT", protocol="TEST-ONLY inert instrument declaration")))
    repo.put(item)
    assert tp.freeze(repo, "TEST-ONLY-plan@1").measurement.protocol == "TEST-ONLY inert instrument declaration"
    assert repo.all("Evidence") == repo.all("AgentAssessment") == ()
    with pytest.raises(ValidationError, match="Unsupported number"):
        tp.TestPlan(**form(group, id="TEST-ONLY-too-large", sample_design=dict(n_per_arm=9007199254740992, decision_rule="TEST-ONLY compare")))


@pytest.mark.parametrize("field", ["competing_set", "predecessor", "generation_plan_ref"])
@pytest.mark.parametrize("entry", ["constructor", "import", "admission"])
def test_actual_plan_pins_require_explicit_revisions(env, field, entry):
    repo, group = env
    gp = g.record_plan(repo, PLAN | {"id": "TEST-ONLY-explicit-generation"})
    draft = tp.TestPlan(**form(group, id="TEST-ONLY-explicit-plan",
        arms=[dict(id="TEST-ONLY-explicit-arm", description="TEST-ONLY pin isolation", generation_plan_ref=g.pin(gp))],
        sample_design=dict(n_per_arm=6, decision_rule="TEST-ONLY inspect exact pins")))
    repo.put(draft)
    candidate = tp.TestPlan(**(draft.model_dump() | dict(revision=2, predecessor=g.pin(draft))))
    data = candidate.model_dump(mode="json", exclude={"tool_version", "frozen_at", "frozen_digest"})
    link = data["arms"][0][field] if field == "generation_plan_ref" else data[field]
    del link["ref"]["revision"]
    with pytest.raises(ValidationError, match="pins require an explicit revision"):
        if entry == "constructor": tp.TestPlan.model_validate(data)
        elif entry == "import": tp.record(repo, data, "TEST-ONLY planner")
        else: repo.put(candidate.model_copy(update=data))
    assert [p.revision for p in repo.all("TestPlan")] == [1]
    repo.put(candidate)
    assert [p.revision for p in repo.all("TestPlan")] == [1, 2]
