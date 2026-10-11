"""TEST-ONLY decision oracles. No real clips or installed production policy."""
from datetime import timedelta
import json
import pytest
from pydantic import ValidationError
from eval_lab import decisions as d, generation as g
from eval_lab.domain import Dimension, Hypothesis
from eval_lab.persistence import Repository
from test_assessments import declared, evidence, observation, assessment, pin
from test_generation import PLAN, seal, setup
from test_intent_v2 import T


def policy(scope, **changes):
    return d.DecisionPolicy(**(dict(id="TEST-ONLY-policy", created_at=T, author="TEST-ONLY policy author",
        version=1, scope=scope, rules=[
            dict(id="unknown", when=dict(unknown_must=True), action="HOLD"),
            dict(id="weak-intent", when=dict(provenance=["RECONSTRUCTED", "PROMPT_ONLY"],
                worst=["temporal_geometry", "MATERIAL"]), action="HOLD"),
            dict(id="multiple-causes", when=dict(priority_status=["MUST", "VIOLATED"], unresolved_at_least=2), action="REGENERATE"),
            dict(id="violation", when=dict(priority_status=["MUST", "VIOLATED"]), action="REGENERATE"),
            dict(id="accepted", when=dict(priority_status=["MUST", "SATISFIED"]), action="SHIP"),
            dict(id="default", action="INVESTIGATE")]) | changes))


def fixture(repo, monkeypatch, provenance="SEALED", status="SATISFIED", product=False):
    criteria = [dict(id="TEST-ONLY-geometry", dimension="temporal_geometry", priority="MUST",
        acceptance="TEST-ONLY stable object" if product else "TEST-ONLY dream morph",
        rejection="TEST-ONLY broken product" if product else "TEST-ONLY accidental morph",
        tolerance="TEST-ONLY no drift" if product else "TEST-ONLY unlimited morph")]
    i = declared(criteria=criteria, use_context=dict(surface="TEST-ONLY projection", audience="TEST-ONLY editors", viewing_profile="STUDIO"), expected_deviations=[] if product else [dict(
        criterion_id="TEST-ONLY-geometry", dimension="temporal_geometry", description="TEST-ONLY dream morph")])
    repo.put(i)
    if provenance in ("SEALED", "CONTEMPORANEOUS"): seal(repo, i, T)
    monkeypatch.setattr(g, "now", lambda: T+timedelta(seconds=1))
    plan = g.record_plan(repo, PLAN | {"intent_revision_ids": ["TEST-ONLY-intent@1"]}) if provenance == "SEALED" else None
    clip, _ = setup(repo, stamp=T+timedelta(seconds=2), planned=plan)
    m = repo.get(clip.media)
    if provenance == "CONTEMPORANEOUS":
        repo.put(g.FirstView(media=pin(m), registration=pin(repo.get(clip.ingestion)), created_at=T+timedelta(seconds=3)))
    b = g.bind_intent(repo, clip, pin(i), prompt_only=provenance == "PROMPT_ONLY")
    assert b.provenance == provenance
    ev = evidence(repo, m)
    obs = observation(m, ev, dimension="temporal_geometry", deviation="CATASTROPHIC"); repo.put(obs)
    a = assessment(m, i, b, obs, criterion_id="TEST-ONLY-geometry", status=status,
        flags=("CONTEMPORANEOUS_INTENT",) if provenance == "CONTEMPORANEOUS" and status == "SATISFIED" else ())
    repo.put(a); p = policy(i.use_context); repo.put(p)
    form = dict(id="TEST-ONLY-verdict", created_at=T, author="TEST-ONLY verdict author", media=pin(m),
        clip=pin(clip), intent=pin(i), binding=pin(b), policy=pin(p), assessments=(pin(a),),
        observations=(pin(obs),), hypotheses=(), intent_fulfillment="ACCEPT", salvage_guess="UNKNOWN")
    return form, obs, a, p


@pytest.fixture
def env(tmp_path, monkeypatch):
    repo = Repository("sqlite:///"+str(tmp_path/"TEST-ONLY-decisions.sqlite"))
    yield repo, fixture(repo, monkeypatch)
    repo.close()


def verdict(repo, form):
    return d.TerminalVerdict(**form, **d.preview(repo, form))


def test_identical_catastrophic_geometry_acceptance_matrix(monkeypatch):
    observations = []
    for provenance, status, product, action, rule, flags in [
        ("SEALED", "SATISFIED", False, "SHIP", "accepted", ()),
        ("CONTEMPORANEOUS", "SATISFIED", False, "SHIP", "accepted", ("CONTEMPORANEOUS_INTENT",)),
        ("RECONSTRUCTED", "VIOLATED", False, "HOLD", "weak-intent", ()),
        ("PROMPT_ONLY", "VIOLATED", False, "HOLD", "weak-intent", ()),
        ("SEALED", "VIOLATED", True, "REGENERATE", "violation", ()),
        ("SEALED", "UNKNOWN", False, "HOLD", "unknown", ())]:
        repo = Repository(); form, obs, a, p = fixture(repo, monkeypatch, provenance, status, product)
        before = (obs.canonical(), a.canonical()); result = verdict(repo, form); repo.put(result)
        assert (result.decision.action, result.decision.rule_id, result.flags) == (action, rule, flags)
        assert result.technical_integrity["temporal_geometry"].model_dump() == {"worst": "CATASTROPHIC", "unknown": False}
        assert result.technical_integrity["camera_language"].model_dump() == {"worst": "UNKNOWN", "unknown": True}
        assert set(result.technical_integrity) == {"prompt_adherence", "subject_consistency", "semantic_consistency", "temporal_consistency",
            "temporal_geometry", "motion_plausibility", "occlusion_consistency", "lighting_continuity", "camera_language",
            "composition", "artifacting", "aesthetic_quality", "editability"}
        assert result.decision.policy_id == "TEST-ONLY-policy" and result.decision.policy_version == 1
        assert (repo.get(obs.ref).canonical(), repo.get(a.ref).canonical()) == before
        observations.append((obs.canonical(), obs.digest)); repo.close()
    assert len(set(observations)) == 1
    assert json.loads(observations[0][0])["span"] == [0.2, 0.8]


@pytest.mark.parametrize("support", ["omitted", "empty", "unknown", "mixed"])
def test_unknown_must_and_ship_guard(env, support):
    repo, (form, obs, a, p) = env
    gap = obs.model_copy(update={"id": "TEST-ONLY-gap", "deviation": "UNKNOWN", "evidence": ()}); repo.put(gap)
    pins = {"omitted": (), "empty": (), "unknown": (pin(gap),), "mixed": (pin(obs), pin(gap))}[support]
    unknown = a.model_copy(update={"id": "TEST-ONLY-gap-assessment", "status": "UNKNOWN", "observations": pins}); repo.put(unknown)
    form = form | {"assessments": () if support == "omitted" else (pin(unknown),), "observations": (pin(obs), pin(gap))}
    result = verdict(repo, form); assert result.decision.action == "HOLD"
    assert result.technical_integrity["temporal_geometry"].model_dump() == {"worst": "CATASTROPHIC", "unknown": True}
    permissive = policy(p.scope, id="TEST-ONLY-permissive", rules=[dict(id="default", action="SHIP")]); repo.put(permissive)
    with pytest.raises(ValueError, match="SHIP requires known MUST evidence"):
        verdict(repo, form | {"id": "TEST-ONLY-bad-ship", "policy": pin(permissive)})
    with pytest.raises(ValueError, match="SHIP requires known MUST evidence"):
        repo.put(result.model_copy(update={"id": "TEST-ONLY-direct-bad-ship", "policy": pin(permissive)}))


@pytest.mark.parametrize("provenance", ["RECONSTRUCTED", "PROMPT_ONLY"])
def test_policy_cannot_bypass_material_provenance(monkeypatch, provenance):
    repo = Repository(); form, obs, a, p = fixture(repo, monkeypatch, provenance, "VIOLATED")
    permissive = policy(p.scope, id="TEST-ONLY-permissive", rules=[dict(id="default", action="SHIP")]); repo.put(permissive)
    with pytest.raises(ValueError, match="SHIP cannot excuse material deviation with weak intent"):
        verdict(repo, form | {"policy": pin(permissive)})
    repo.close()


@pytest.mark.parametrize("rules,message", [
    ([], "exactly one final default"), ([dict(id="only", when=dict(unknown_must=True), action="HOLD")], "exactly one final default"),
    ([dict(id="early", action="HOLD"), dict(id="late", when=dict(unknown_must=True), action="SHIP")], "exactly one final default"),
    ([dict(id="same", when=dict(unknown_must=True), action="HOLD"), dict(id="same", action="HOLD")], "unique rule IDs")])
def test_policy_order_contract(env, rules, message):
    repo, (_, _, _, p) = env
    with pytest.raises(ValidationError, match=message): repo.put(p.model_copy(update={"id": "TEST-ONLY-invalid-policy", "rules": rules}))


@pytest.mark.parametrize("when,message", [(dict(prose="SHIP"), "Extra inputs"), (dict(unresolved_at_least=-1), "greater than or equal"),
    (dict(unresolved_at_least=True), "valid integer"), (dict(priority_status=["MUST", "PASS"]), "Input should be"),
    (dict(worst=["temporal_geometry", "UNKNOWN"]), "Input should be"), (dict(provenance=[]), "at least 1")])
def test_typed_condition_operands(env, when, message):
    _, (_, _, _, p) = env
    with pytest.raises(ValidationError, match=message):
        policy(p.scope, rules=[dict(id="bad", when=when, action="SHIP"), dict(id="default", action="HOLD")])


@pytest.mark.parametrize("action", ["SHIP", "HOLD", "REPAIR", "REGENERATE", "INVESTIGATE"])
def test_first_match_default_and_salvage(env, action):
    repo, (form, obs, a, p) = env
    candidate = policy(p.scope, id="TEST-ONLY-actions", rules=[
        dict(id="first", when=dict(salvage_guess="POST_FIXABLE"), action=action),
        dict(id="overlap", when=dict(salvage_guess="POST_FIXABLE"), action="INVESTIGATE"), dict(id="default", action="HOLD")]); repo.put(candidate)
    assert verdict(repo, form | {"policy": pin(candidate)}).decision.rule_id == "default"
    result = verdict(repo, form | {"policy": pin(candidate), "salvage_guess": "POST_FIXABLE"})
    assert (result.decision.rule_id, result.decision.action) == ("first", action)


@pytest.mark.parametrize("reason", [None, "", "  "])
@pytest.mark.parametrize("entry", ["constructor", "copy", "json"])
def test_override_reason_required(env, reason, entry):
    repo, (form, obs, a, p) = env
    result = verdict(repo, form); override = dict(action="REPAIR", author="TEST-ONLY override author")
    if reason is not None: override["reason"] = reason
    bad = result.model_copy(update={"id": "TEST-ONLY-invalid-override", "override": override})
    with pytest.raises(ValidationError, match="reason"):
        if entry == "copy": repo.put(bad)
        elif entry == "constructor": d.TerminalVerdict(**dict(bad.__dict__))
        else: d.TerminalVerdict.model_validate_json(json.dumps(d.raw_payload(bad), default=str))


@pytest.mark.parametrize("field,value,message", [("version", 2, "version must equal revision"), ("author", " ", "String should match"),
    ("predecessor", "self", "initial revision cannot"), ("rules", [dict(id="default", action="PASS")], "Input should be")])
def test_policy_identity(env, field, value, message):
    repo, (_, _, _, p) = env
    with pytest.raises(ValidationError, match=message):
        repo.put(p.model_copy(update={"id": "TEST-ONLY-invalid-identity", field: pin(p) if value == "self" else value}))


@pytest.mark.parametrize("field", ["intent_fulfillment", "salvage_guess", "author"])
def test_human_fields_required(env, field):
    repo, (form, _, _, _) = env
    raw = dict(form); del raw[field]
    with pytest.raises(ValidationError, match=field): d.preview(repo, raw)


def test_pair_priority_status_on_same_criterion(env):
    repo, (form, obs, a, p) = env
    # Pure projection has deliberately different priorities/statuses.
    condition = d.Condition(priority_status=("MUST", "VIOLATED"))
    assert not d.matches(condition, dict(criteria=[["MUST", "SATISFIED"], ["COULD", "VIOLATED"]]))
    assert d.matches(condition, dict(criteria=[["MUST", "VIOLATED"], ["COULD", "SATISFIED"]]))


def test_phase2_regression_matrix():
    from eval_lab.fixtures import seed
    from eval_lab.scoring import evaluate
    from eval_lab.domain import DimensionScore
    from test_core import scored
    repo = Repository(); legacy = seed(repo); rubric, intent = legacy["rubric"], legacy["intent"]
    fail = evaluate((scored(Dimension.GEOMETRY, 0),), rubric, intent)
    assert (fail.status, fail.recommendation, len(fail.missing_dimensions)) == ("FAILED", "REGENERATE", 12)
    assert evaluate((), rubric, intent).status == "UNKNOWN"
    full = tuple(scored(x, 4) for x in Dimension)
    assert evaluate(full, rubric, intent).status == "PASS"
    assert evaluate(tuple(scored(x, 2) for x in Dimension), rubric, intent).status == "REVIEW"
    assert evaluate(full, rubric, intent.model_copy(update={"authority": "agent_proposed", "approved_by": None})).status == "UNKNOWN"
    surreal = intent.model_copy(update={"criteria": tuple(c.model_copy(update={"applicability": "not_applicable"}) if c.dimension == Dimension.GEOMETRY else c for c in intent.criteria)})
    scores = tuple(DimensionScore(dimension=x, status="not_applicable", rationale="TEST-ONLY surreal") if x == Dimension.GEOMETRY else scored(x, 4) for x in Dimension)
    assert evaluate(scores, rubric, surreal).status == "PASS"
    with pytest.raises(ValueError, match="only declared intent can exclude"): evaluate(scores, rubric, intent)
    repo.close()


def test_literal_input_envelope_codec():
    value = dict(schema_version=1, sources=dict(intent=dict(ref=dict(kind="IntentSpecV2", id="TEST-ONLY-digest", revision=7), sha256="a"*64)),
        policy_id="TEST-ONLY-policy", policy_version=3, inputs=dict(criteria=[["MUST", "VIOLATED"], ["COULD", "SATISFIED"]],
        integrity=dict(temporal_geometry=dict(worst="CATASTROPHIC", unknown=False)), provenance="SEALED",
        salvage_guess="EXPENSIVE_POST_FIX", unresolved=2, unknown_must=False), author="TEST-ONLY analyst", intent_fulfillment="REJECT", relevance=[])
    assert d.canonicalize(value) == b'{"author":"TEST-ONLY analyst","inputs":{"criteria":[["MUST","VIOLATED"],["COULD","SATISFIED"]],"integrity":{"temporal_geometry":{"unknown":false,"worst":"CATASTROPHIC"}},"provenance":"SEALED","salvage_guess":"EXPENSIVE_POST_FIX","unknown_must":false,"unresolved":2},"intent_fulfillment":"REJECT","policy_id":"TEST-ONLY-policy","policy_version":3,"relevance":[],"schema_version":1,"sources":{"intent":{"ref":{"id":"TEST-ONLY-digest","kind":"IntentSpecV2","revision":7},"sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}}}'
    assert d.input_digest(value) == "2e22465839cfa7f648ea8499c9a343621df1ccf93292cac73f7b89d10736fa03"


@pytest.mark.parametrize("worst,expected", [("NONE", False), ("MINOR", False), ("MATERIAL", True), ("SEVERE", True), ("CATASTROPHIC", True), ("UNKNOWN", False)])
def test_literal_worst_threshold_order(worst, expected):
    condition = d.Condition(worst=("temporal_geometry", "MATERIAL"))
    assert d.matches(condition, dict(integrity=dict(temporal_geometry=dict(worst=worst)))) is expected
