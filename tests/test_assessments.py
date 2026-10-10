"""TEST-ONLY contracts; literals are human-authored fixture oracles, not judgments."""
import json
from datetime import timedelta
import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from eval_lab import assessments as a, generation as g
from eval_lab.domain import Evidence, Ref
from eval_lab.persistence import Repository
from test_intent_v2 import T, intent, anchors, pin
from test_generation import PLAN, seal, setup


def declared(name="TEST-ONLY-intent", expected=True, **updates):
    return intent(**(dict(id=name, objective="TEST-ONLY sliding choreography", criteria=[dict(
        id="TEST-ONLY-motion", dimension="motion_plausibility", priority="MUST",
        acceptance="TEST-ONLY deliberate sliding", rejection="TEST-ONLY accidental slipping",
        tolerance="TEST-ONLY one continuous slide")], expected_deviations=[dict(
        criterion_id="TEST-ONLY-motion", dimension="motion_plausibility",
        description="TEST-ONLY material slide")] if expected else []) | updates))


def evidence(repo, media, name="TEST-ONLY-evidence"):
    item = Evidence(id=name, created_at=T, media=media.ref, observation="TEST-ONLY feet slide",
        timestamp_start=.2, timestamp_end=.8, source="synthetic_fixture", coverage="interval",
        method="TEST-ONLY declared fixture", author="TEST-ONLY witness", independence_group="TEST-ONLY group")
    repo.put(item)
    return item


def observation(media, ev, **updates):
    return a.TechnicalObservation(**(dict(id="TEST-ONLY-observation", created_at=T,
        media=pin(media), author="TEST-ONLY observer", dimension="motion_plausibility",
        deviation="MATERIAL", span=(.2, .8), evidence=(pin(ev),), viewing_profile="STUDIO") | updates))


def assessment(m, i, b, obs, **updates):
    return a.CriterionAssessment(**(dict(id="TEST-ONLY-assessment", created_at=T,
        media=pin(m), author="TEST-ONLY assessor", intent=pin(i), binding=pin(b),
        criterion_id="TEST-ONLY-motion", observations=(pin(obs),), status="SATISFIED",
        rationale="TEST-ONLY private deliberate slide matches declared criterion") | updates))


@pytest.fixture
def env(tmp_path, monkeypatch):
    repo = Repository("sqlite:///"+str(tmp_path/"TEST-ONLY.sqlite"))
    i = declared(); repo.put(i); seal(repo, i, T)
    monkeypatch.setattr(g, "now", lambda: T+timedelta(seconds=1))
    plan = g.record_plan(repo, PLAN | {"intent_revision_ids": ["TEST-ONLY-intent@1"]})
    clip, _ = setup(repo, stamp=T+timedelta(seconds=2), planned=plan)
    b = g.bind_intent(repo, clip, pin(i)); assert b.provenance == "SEALED"
    m = repo.get(clip.media); ev = evidence(repo, m); obs = observation(m, ev); repo.put(obs)
    yield repo, m, ev, i, b, obs
    repo.close()


@pytest.mark.parametrize("field", ["intent", "criterion_id", "binding", "status", "decision"])
@pytest.mark.parametrize("entry", ["constructor", "json", "copy"])
def test_intent_free_boundary(env, field, entry):
    repo, m, ev, i, b, obs = env
    bad = obs.model_copy(update={"id": "TEST-ONLY-injected", field: pin(i)})
    raw = dict(bad.__dict__)
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        if entry == "copy": repo.put(bad)
        elif entry == "constructor": a.TechnicalObservation(**raw)
        else: a.TechnicalObservation.model_validate_json(json.dumps(raw, default=lambda x: x.model_dump(mode="json") if hasattr(x, "model_dump") else x.isoformat()))
    assert [x.id for x in repo.all("TechnicalObservation")] == ["TEST-ONLY-observation"]


@pytest.mark.parametrize("target", ["pin", "ref"])
@pytest.mark.parametrize("entry", ["constructor", "repository"])
def test_nested_injected_fields_survive_admission_validation(env, target, entry):
    repo, m, ev, i, b, obs = env
    p = pin(ev)
    p = p.model_copy(update={"intent": pin(i)}) if target == "pin" else p.model_copy(update={"ref": p.ref.model_copy(update={"intent": i.ref})})
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        bad = obs.model_copy(update={"id": "TEST-ONLY-nested", "evidence": (p,)})
        if entry == "constructor": a.TechnicalObservation(**dict(bad.__dict__))
        else: repo.put(bad)


@pytest.mark.parametrize("field,value,message", [
    ("media", "intent", "pin must reference MediaAsset"),
    ("evidence", "intent", "pin must reference Evidence"),
    ("span", (.8, .2), "span must be ordered"), ("span", (-.1, .8), "greater than or equal"),
    ("span", (.2, float("inf")), "finite number"), ("span", (.2, 1.2), "span exceeds media duration"),
    ("deviation", "SATISFIED", "Input should be"), ("viewing_profile", "PRIVATE", "Input should be")])
def test_observation_contracts(env, field, value, message):
    repo, m, ev, i, b, obs = env
    if value == "intent": value = (pin(i),) if field == "evidence" else pin(i)
    error = ValueError if field == "span" and value == (.2, 1.2) else ValidationError
    with pytest.raises(error, match=message):
        repo.put(obs.model_copy(update={"id": "TEST-ONLY-contract", field: value}))


@pytest.mark.parametrize("deviation", ["NONE", "MINOR", "MATERIAL", "SEVERE", "CATASTROPHIC"])
def test_missing_evidence_requires_unknown(env, deviation):
    repo, m, ev, i, b, obs = env
    with pytest.raises(ValidationError, match="missing evidence requires UNKNOWN"):
        repo.put(obs.model_copy(update={"id": "TEST-ONLY-empty", "evidence": (), "deviation": deviation}))
    unknown = observation(m, ev, id="TEST-ONLY-gap", evidence=(), deviation="UNKNOWN")
    repo.put(unknown); assert repo.get(unknown.ref).deviation == "UNKNOWN"


@pytest.mark.parametrize("support", ["empty", "unknown", "mixed"])
@pytest.mark.parametrize("status", ["SATISFIED", "VIOLATED", "NOT_APPLICABLE"])
def test_unknown_cannot_be_promoted(env, support, status):
    repo, m, ev, i, b, obs = env
    unknown = observation(m, ev, id="TEST-ONLY-gap", evidence=(), deviation="UNKNOWN"); repo.put(unknown)
    pins = {"empty": (), "unknown": (pin(unknown),), "mixed": (pin(obs), pin(unknown))}[support]
    with pytest.raises(ValueError, match="missing or UNKNOWN observations require UNKNOWN"):
        repo.put(assessment(m, i, b, obs, id="TEST-ONLY-bad-gap", observations=pins, status=status))
    valid = assessment(m, i, b, obs, observations=pins, status="UNKNOWN", rationale="TEST-ONLY missing coverage")
    repo.put(valid); assert repo.get(valid.ref).status == "UNKNOWN"


@pytest.mark.parametrize("status", ["UNKNOWN", "NOT_APPLICABLE", "VIOLATED", "SATISFIED"])
def test_known_support_allows_explicit_human_status(env, status):
    repo, m, ev, i, b, obs = env
    item = assessment(m, i, b, obs, status=status); repo.put(item)
    assert repo.get(item.ref).status == status


@pytest.mark.parametrize("case,message", [("evidence", "evidence belongs to another media"),
    ("observation", "observation media or dimension mismatch"), ("dimension", "observation media or dimension mismatch"),
    ("binding", "binding intent or media mismatch"), ("criterion", "criterion absent from pinned intent")])
def test_cross_context_rejected(env, case, message):
    repo, m, ev, i, b, obs = env
    other, _ = anchors(repo, "TEST-ONLY-other", "d"*64); foreign = evidence(repo, other, "TEST-ONLY-other-evidence")
    other_i = declared("TEST-ONLY-other-intent"); repo.put(other_i)
    candidate = assessment(m, i, b, obs)
    if case == "evidence": candidate = obs.model_copy(update={"id": "TEST-ONLY-cross", "evidence": (pin(foreign),)})
    if case in ("observation", "dimension"):
        alt = observation(other, foreign, id="TEST-ONLY-alt") if case == "observation" else observation(m, ev, id="TEST-ONLY-alt", dimension="camera_language")
        repo.put(alt); candidate = candidate.model_copy(update={"observations": (pin(alt),)})
    if case == "binding": candidate = candidate.model_copy(update={"intent": pin(other_i)})
    if case == "criterion": candidate = candidate.model_copy(update={"criterion_id": "TEST-ONLY-absent"})
    with pytest.raises(ValueError, match=message): repo.put(candidate)
    assert repo.all("CriterionAssessment") == ()


@pytest.mark.parametrize("field", ["media", "intent", "binding", "observations"])
def test_exact_assessment_pin_kinds(env, field):
    repo, m, ev, i, b, obs = env
    expected = {"media": "MediaAsset", "intent": "IntentSpecV2", "binding": "IntentBinding", "observations": "TechnicalObservation"}[field]
    with pytest.raises(ValidationError, match="pin must reference " + expected):
        repo.put(assessment(m, i, b, obs).model_copy(update={field: (pin(ev),) if field == "observations" else pin(ev)}))


@pytest.mark.parametrize("case,message,error", [("digest", "pinned artifact digest mismatch", ValueError),
    ("missing", "TEST-ONLY-missing", KeyError), ("revision", "explicit revision", ValidationError),
    ("rationale", "String should match pattern", ValidationError)])
def test_exact_pins_and_rationale(env, case, message, error):
    repo, m, ev, i, b, obs = env
    raw = assessment(m, i, b, obs).model_dump(mode="json")
    if case == "digest": raw["intent"]["sha256"] = "0"*64
    if case == "missing": raw["observations"][0]["ref"]["id"] = "TEST-ONLY-missing"
    if case == "revision": del raw["intent"]["ref"]["revision"]
    if case == "rationale": raw["rationale"] = "  "
    with pytest.raises(error, match=message): repo.put(a.CriterionAssessment.model_validate(raw))


@pytest.mark.parametrize("provenance", ["SEALED", "CONTEMPORANEOUS", "RECONSTRUCTED", "PROMPT_ONLY"])
@pytest.mark.parametrize("deviation", ["MATERIAL", "SEVERE", "CATASTROPHIC"])
def test_material_excuse_requires_qualifying_provenance(tmp_path, monkeypatch, provenance, deviation):
    repo = Repository(); i = declared(); repo.put(i)
    if provenance in ("SEALED", "CONTEMPORANEOUS"): seal(repo, i, T)
    monkeypatch.setattr(g, "now", lambda: T+timedelta(seconds=1))
    plan = g.record_plan(repo, PLAN | {"intent_revision_ids": ["TEST-ONLY-intent@1"]}) if provenance == "SEALED" else None
    clip, _ = setup(repo, stamp=T+timedelta(seconds=2), planned=plan)
    m = repo.get(clip.media)
    if provenance == "CONTEMPORANEOUS": repo.put(g.FirstView(media=pin(m), registration=pin(repo.get(clip.ingestion)), created_at=T+timedelta(seconds=3)))
    b = g.bind_intent(repo, clip, pin(i), prompt_only=provenance == "PROMPT_ONLY"); assert b.provenance == provenance
    ev = evidence(repo, m); obs = observation(m, ev, deviation=deviation); repo.put(obs)
    item = assessment(m, i, b, obs, flags=("CONTEMPORANEOUS_INTENT",) if provenance == "CONTEMPORANEOUS" else ())
    if provenance in ("RECONSTRUCTED", "PROMPT_ONLY"):
        with pytest.raises(ValueError, match="material excuse requires qualifying intent provenance"): repo.put(item)
        assert repo.all("CriterionAssessment") == ()
    else:
        repo.put(item); assert repo.get(item.ref).status == "SATISFIED"
        if provenance == "CONTEMPORANEOUS":
            assert repo.get(item.ref).flags == ("CONTEMPORANEOUS_INTENT",)
            with pytest.raises(ValueError, match="contemporaneous flag mismatch"):
                repo.put(item.model_copy(update={"id": "TEST-ONLY-no-flag", "flags": ()}))
    repo.close()


def test_material_excuse_requires_declared_dimension(env):
    repo, m, ev, i, b, obs = env
    later = declared("TEST-ONLY-no-deviation", expected=False); repo.put(later)
    clip = repo.all("PilotClip")[0]; bound = g.bind_intent(repo, clip, pin(later))
    with pytest.raises(ValueError, match="material excuse requires expected deviation"):
        repo.put(assessment(m, later, bound, obs))


def test_missing_retained_binding_context(env):
    repo, m, ev, i, b, obs = env
    successor = b.model_copy(update={"revision": 2, "predecessor": pin(b)})
    repo.put(successor)
    with pytest.raises(ValueError, match="binding requires retained context"):
        repo.put(assessment(m, i, successor, obs))


@pytest.mark.parametrize("kind", ["observation", "assessment"])
def test_revision_contract_and_append_only(env, kind):
    repo, m, ev, i, b, obs = env
    item = obs if kind == "observation" else assessment(m, i, b, obs)
    repo.put(item)
    for change, error, message in [
        ({"id": "TEST-ONLY-initial", "predecessor": pin(item)}, ValidationError, "initial revision cannot"),
        ({"revision": 2}, ValidationError, "immediate same-kind"),
        ({"revision": 3, "predecessor": pin(item), "revision_reason": "TEST-ONLY correction"}, ValidationError, "immediate same-kind"),
        ({"revision": 2, "predecessor": pin(item)}, ValidationError, "revision reason required"),
        ({"revision": 2, "predecessor": pin(item).model_copy(update={"sha256": "f"*64}), "revision_reason": "TEST-ONLY correction"}, ValueError, "digest mismatch"),
        ({"author": "TEST-ONLY another"}, ValueError, "immutable revision conflict")]:
        with pytest.raises(error, match=message): repo.put(item.model_copy(update=change))
    successor = item.model_copy(update={"revision": 2, "predecessor": pin(item), "revision_reason": "TEST-ONLY correction"})
    other, _ = anchors(repo, "TEST-ONLY-lineage", "e"*64)
    with pytest.raises(ValueError, match="record media is immutable"): repo.put(successor.model_copy(update={"media": pin(other)}))
    if kind == "assessment":
        with pytest.raises(ValueError, match="assessment context is immutable"):
            repo.put(successor.model_copy(update={"criterion_id": "TEST-ONLY-changed"}))
    repo.put(successor); assert repo.get(item.ref) == item
    assert repo.get(successor.ref).predecessor == pin(item)
    for sql in ("UPDATE artifacts SET payload='{}' WHERE kind=:kind", "DELETE FROM artifacts WHERE kind=:kind"):
        with pytest.raises(IntegrityError, match="append-only"):
            with repo.engine.begin() as c: c.exec_driver_sql(sql, {"kind": item.ref.kind})


def test_fixed_input_serialization_reopen_and_integrity(env):
    repo, m, ev, i, b, obs = env
    item = assessment(m, i, b, obs); repo.put(item)
    reopened = Repository(str(repo.engine.url))
    for record in (obs, item):
        assert reopened.get(record.ref).canonical() == record.canonical()
        assert type(record).model_validate_json(record.canonical()).digest == record.digest
    reopened.close()
    # Disposable TEST-ONLY database: simulate external corruption, not an authored correction.
    with repo.engine.begin() as c:
        c.exec_driver_sql("DROP TRIGGER no_update_artifacts")
        c.exec_driver_sql("UPDATE artifacts SET sha256=:hash WHERE kind='TechnicalObservation'", {"hash": "0"*64})
    with pytest.raises(ValueError, match="snapshot integrity failure"): repo.get(obs.ref)
    with pytest.raises(ValueError, match="snapshot integrity failure"):
        repo.put(item.model_copy(update={"id": "TEST-ONLY-corrupt-support"}))


def test_fixed_serialization_literal_oracle():
    item = a.TechnicalObservation(id="TEST-ONLY-fixed", created_at=T, author="TEST-ONLY reader",
        media={"ref": {"kind": "MediaAsset", "id": "TEST-ONLY-source", "revision": 7}, "sha256": "a"*64},
        dimension="motion_plausibility", deviation="UNKNOWN", evidence=(), span=(.1, .9), viewing_profile="FEED")
    assert item.canonical() == '{"author":"TEST-ONLY reader","created_at":"2026-01-01T00:00:00Z","deviation":"UNKNOWN","dimension":"motion_plausibility","evidence":[],"id":"TEST-ONLY-fixed","media":{"ref":{"id":"TEST-ONLY-source","kind":"MediaAsset","revision":7},"sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},"predecessor":null,"revision":1,"revision_reason":null,"schema_version":1,"span":[0.1,0.9],"tool_version":"0.1.0","viewing_profile":"FEED"}'
    assert item.digest == "583434ec9790fba0b5d7502ec1a516e1b3ae057b8b4868c0269a39a31ebabbea"
