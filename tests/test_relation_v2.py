"""TEST-ONLY authored relations; independent literals, never real clip judgments."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
import json
from threading import Barrier
from types import SimpleNamespace
import pytest
from pydantic import ValidationError
from sqlalchemy import select
from eval_lab import domain as d
from eval_lab.persistence import Repository, artifacts
from eval_lab.pilot_domain import PilotClip
from eval_lab.generation import pin
from eval_lab.intent_v2 import Pin
from test_intent_v2 import anchors, intent, binding

T = datetime(2026, 10, 8, tzinfo=timezone.utc)
LEGACY = dict(id="TEST-ONLY-intent", revision=1, schema_version=1, created_at="2026-10-08T00:00:00Z",
    owner="TEST-ONLY owner", objective="TEST-ONLY objective", audience="TEST-ONLY audience",
    context="TEST-ONLY context", constraints=[], prohibited_outcomes=[], authority="human_declared",
    approved_by="TEST-ONLY approver", supersedes=None, criteria=[dict(dimension="motion_plausibility",
    applicability="required", rationale="TEST-ONLY rationale", acceptance="TEST-ONLY acceptance")])


def canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def digest(payload):
    return sha256(canonical(payload).encode()).hexdigest()


def oracle(**changes):
    return dict(id="TEST-ONLY-relation", revision=1, schema_version=2, created_at="2026-10-08T00:00:00Z",
        subject=dict(kind="Evidence", id="TEST-ONLY-e", revision=1), predicate="supports",
        object=dict(kind="Hypothesis", id="TEST-ONLY-h0", revision=1),
        intent=dict(ref=dict(kind="IntentSpec", id="TEST-ONLY-intent", revision=1), sha256=digest(LEGACY)),
        epistemic_status="asserted", evidence=[dict(kind="Evidence", id="TEST-ONLY-e", revision=1)],
        asserted_by="TEST-ONLY author", purpose="TEST-ONLY free purpose", scope="TEST-ONLY scope",
        valid_from="2026-10-08T00:00:00Z", valid_until="2026-10-09T00:00:00Z", confidence=.37,
        creative_anchor=[], epistemic_purpose="EXPLAIN", operational_purpose="INVESTIGATE",
        warrant="  TEST-ONLY warrant  ", qualifier="TEST-ONLY qualifier", rebuttal="TEST-ONLY rebuttal",
        predecessor=None) | changes


def edge(x, **changes):
    from eval_lab.relation_v2 import RelationClaimV2
    return RelationClaimV2(**(dict(id="TEST-ONLY-relation", created_at=T, subject=x.e.ref,
        predicate="supports", object=x.hs[0].ref, intent=pin(x.i), epistemic_status="asserted",
        evidence=(x.e.ref,), asserted_by="TEST-ONLY author", purpose="TEST-ONLY free purpose",
        scope="TEST-ONLY scope", valid_from=T, valid_until=datetime(2026,10,9,tzinfo=timezone.utc),
        confidence=.37, epistemic_purpose="EXPLAIN", operational_purpose="INVESTIGATE",
        warrant="  TEST-ONLY warrant  ", qualifier="TEST-ONLY qualifier", rebuttal="TEST-ONLY rebuttal") | changes))


def seed(repo):
    i = d.IntentSpec(**LEGACY); repo.put(i)
    m, r = anchors(repo, "TEST-ONLY-media")
    repo.put(PilotClip(id="TEST-ONLY-clip", media=m.ref, ingestion=r.ref, intent=i.ref,
        selected_by="TEST-ONLY curator", label="TEST-ONLY generated metadata"))
    hs = tuple(d.Hypothesis(id=f"TEST-ONLY-h{n}", created_at=T, intent=i.ref,
        observed_problem="TEST-ONLY problem", proposed_cause=f"TEST-ONLY cause {n}",
        evidence_required=("TEST-ONLY missing evidence",), discriminating_test="TEST-ONLY test",
        predicted_observation="TEST-ONLY predicted", falsifying_observation="TEST-ONLY falsifying",
        confidence=None, status="unresolved") for n in range(3))
    e = d.Evidence(id="TEST-ONLY-e", created_at=T, media=m.ref, observation="TEST-ONLY observation",
        source="synthetic_fixture", method="TEST-ONLY method", coverage="full_clip",
        author="TEST-ONLY observer", independence_group="TEST-ONLY independent")
    for item in (*hs, e): repo.put(item)
    return SimpleNamespace(repo=repo, i=i, m=m, r=r, hs=hs, e=e)


@pytest.fixture
def x(tmp_path):
    repo = Repository("sqlite:///" + str(tmp_path / "TEST-ONLY.sqlite"))
    try: yield seed(repo)
    finally: repo.close()


@pytest.mark.parametrize("predicate,ep,op,warrant,qualifier,rebuttal", [
    ("supports", "EXPLAIN", "INVESTIGATE", "  TEST-ONLY warrant  ", "TEST-ONLY qualifier", "TEST-ONLY rebuttal"),
    ("contradicts", "RULE_OUT", "REPAIR", "TEST-ONLY counter warrant", "TEST-ONLY counter qualifier", "TEST-ONLY counter rebuttal")])
def test_literal_storage_load_replay_and_history(x, predicate, ep, op, warrant, qualifier, rebuttal):
    from eval_lab.relation_v2 import load_relation
    expected = oracle(predicate=predicate, epistemic_purpose=ep, operational_purpose=op,
        warrant=warrant, qualifier=qualifier, rebuttal=rebuttal)
    item = edge(x, predicate=predicate, epistemic_purpose=ep, operational_purpose=op,
        warrant=warrant, qualifier=qualifier, rebuttal=rebuttal)
    assert item.model_dump(mode="json") == expected
    assert x.repo.put(item) == digest(expected) == x.repo.put(item)
    with x.repo.engine.connect() as conn:
        row = conn.execute(select(artifacts).where(x.repo.key(item.ref))).mappings().one()
    assert row["payload"] == canonical(expected) and row["sha256"] == digest(expected)
    x.repo.put(item.model_copy(update=dict(revision=2, predecessor=pin(item), qualifier="TEST-ONLY revised qualifier")))
    reopened = Repository(str(x.repo.engine.url))
    try:
        assert load_relation(reopened, item.ref).canonical() == canonical(expected)
        assert load_relation(reopened, item.ref).digest == digest(expected)
    finally: reopened.close()
    assert [(h.status, h.confidence, h.supporting_evidence) for h in x.repo.all("Hypothesis")] == [
        ("unresolved", None, ()), ("unresolved", None, ()), ("unresolved", None, ())]
    assert x.repo.all("AgentAssessment") == x.repo.all("DecisionRecord") == ()


@pytest.mark.parametrize("field,values", [("epistemic_purpose", ["SUPPORT", "RULE_OUT", "DISCRIMINATE", "LOCALIZE", "EXPLAIN", "QUALIFY", "SCOPE", "OPERATIONALIZE"]),
    ("operational_purpose", ["SHIP", "REPAIR", "REGENERATE", "REVISE_RUBRIC", "ADD_GOLD", "RETRAIN_SIGNAL", "INVESTIGATE"])])
def test_all_purposes_are_independent_labels(x, field, values):
    for n, value in enumerate(values):
        item = edge(x, id=f"TEST-ONLY-purpose-{n}", **{field: value})
        x.repo.put(item)
        assert getattr(x.repo.get(item.ref), field) == value


@pytest.mark.parametrize("field", ["epistemic_purpose", "operational_purpose"])
@pytest.mark.parametrize("bad", [None, "", " ", "support", "UNKNOWN", "UNSPECIFIED", "MISSING"])
def test_explicit_purpose_contract(x, field, bad):
    from eval_lab.relation_v2 import RelationClaimV2
    data = oracle(id="TEST-ONLY-bad-purpose")
    if bad == "MISSING": del data[field]
    else: data[field] = bad
    with pytest.raises(ValidationError, match=field): RelationClaimV2(**data)
    assert x.repo.all("RelationClaimV2") == ()


@pytest.mark.parametrize("predicate", ["supports", "contradicts"])
@pytest.mark.parametrize("bad", [None, "", " \t", "MISSING"])
def test_required_warrant_cannot_be_replaced_by_purpose(x, predicate, bad):
    from eval_lab.relation_v2 import RelationClaimV2
    data = oracle(id="TEST-ONLY-bad-warrant", predicate=predicate)
    if bad == "MISSING": del data["warrant"]
    else: data["warrant"] = bad
    with pytest.raises(ValidationError, match="warrant"): RelationClaimV2(**data)
    assert x.repo.all("RelationClaimV2") == ()


@pytest.mark.parametrize("field", ["qualifier", "rebuttal"])
@pytest.mark.parametrize("bad", ["", " \n"])
def test_optional_text_is_nonblank(x, field, bad):
    with pytest.raises(ValidationError, match=field): edge(x, **{field: bad})


@pytest.mark.parametrize("predicate", ["supports", "contradicts", "motivated_by", "fulfills", "violates", "alternative_to", "compatible_with", "refines"])
def test_all_predicates_and_optional_absence(x, predicate):
    subject = x.e.ref if predicate in ("supports", "contradicts", "fulfills", "violates") else x.hs[0].ref
    obj = x.i.ref if predicate in ("motivated_by", "fulfills", "violates") else x.hs[1].ref
    item = edge(x, predicate=predicate, subject=subject, object=obj, qualifier=None, rebuttal=None,
        warrant="TEST-ONLY required" if predicate in ("supports", "contradicts") else None)
    x.repo.put(item)
    assert x.repo.get(item.ref).qualifier is None and x.repo.get(item.ref).rebuttal is None


@pytest.mark.parametrize("changes,message", [
    ({"subject": d.Ref(kind="Hypothesis", id="TEST-ONLY-h0")}, "domain/range"),
    ({"evidence": (d.Ref(kind="Hypothesis", id="TEST-ONLY-h1"),)}, "evidence must reference Evidence"),
    ({"intent": Pin(ref=d.Ref(kind="Evidence", id="TEST-ONLY-e"), sha256="a"*64)}, "pin must reference"),
    ({"epistemic_status": "observed", "evidence": ()}, "observed relation needs evidence"),
    ({"epistemic_status": "observed"}, "claims, not observations"),
    ({"valid_from": T.replace(tzinfo=None)}, "invalid validity interval"),
    ({"valid_until": T}, "invalid validity interval"),
    ({"valid_until": T.replace(tzinfo=None)}, "invalid validity interval"),
    ({"created_at": T.replace(tzinfo=None)}, "created_at must have timezone"),
    ({"creative_anchor": ("a", "a")}, "unique"), ({"creative_anchor": (" ",)}, "creative_anchor"),
    ({"predicate": "compatible_with", "subject": d.Ref(kind="Hypothesis", id="TEST-ONLY-h0"),
      "object": d.Ref(kind="Hypothesis", id="TEST-ONLY-h0")}, "cannot relate to itself")])
def test_copied_and_deserialized_contracts(x, changes, message):
    from eval_lab.relation_v2 import RelationClaimV2
    candidate = edge(x).model_copy(update=changes | {"id": "TEST-ONLY-invalid"})
    with pytest.raises(ValidationError, match=message): x.repo.put(candidate)
    with pytest.raises(ValidationError, match=message): RelationClaimV2.model_validate_json(candidate.model_dump_json())
    assert x.repo.all("RelationClaimV2") == ()


def test_nested_pin_and_reference_copies_revalidated(x):
    for n, changes in enumerate((dict(subject=x.e.ref.model_copy(update={"revision": 0})),
            dict(intent=pin(x.i).model_copy(update={"sha256": "bad"})))):
        with pytest.raises(ValidationError, match="revision|sha256"):
            x.repo.put(edge(x).model_copy(update=changes | dict(id=f"TEST-ONLY-nested-{n}")))
    assert x.repo.all("RelationClaimV2") == ()


def test_admission_pins_anchors_and_exact_binding(x):
    i = intent(id="TEST-ONLY-v2"); x.repo.put(i)
    later = intent(id=i.id, revision=2, predecessor=pin(i), criteria=[dict(
        id="TEST-ONLY-new", dimension="motion_plausibility", priority="MUST", acceptance="TEST-ONLY a",
        rejection="TEST-ONLY r", tolerance="TEST-ONLY t")]); x.repo.put(later)
    base = edge(x, predicate="fulfills", object=i.ref, intent=pin(i), creative_anchor=("criterion",), evidence=())
    with pytest.raises(ValueError, match="retained IntentBinding"): x.repo.put(base)
    # Another intent revision on the same media is insufficient.
    old_binding = binding(later, x.m, x.r); x.repo.put(old_binding)
    with pytest.raises(ValueError, match="retained IntentBinding"):
        x.repo.put(base.model_copy(update={"id": "TEST-ONLY-wrong-binding"}))
    x.repo.put(binding(i, x.m, x.r, revision=2, predecessor=pin(old_binding)))
    for n, (changes, error) in enumerate((
        ({"creative_anchor": ("TEST-ONLY-new",)}, "pinned intent"),
        ({"intent": pin(i).model_copy(update={"sha256": "b"*64})}, "digest mismatch"),
        ({"object": later.ref}, "relation intent mismatch"),
        ({"creative_anchor": ("criterion",), "intent": pin(x.i), "object": x.i.ref}, "legacy intent"))):
        with pytest.raises(ValueError, match=error): x.repo.put(base.model_copy(update=changes | dict(id=f"TEST-ONLY-admission-{n}")))
    assert x.repo.all("RelationClaimV2") == ()
    x.repo.put(base)
    assert x.repo.get(base.ref).creative_anchor == ("criterion",)
    # Matching intent but another media's binding does not authorize this evidence.
    other, _ = anchors(x.repo, "TEST-ONLY-other-media", "c"*64)
    e = x.e.model_copy(update=dict(id="TEST-ONLY-other-e", media=other.ref)); x.repo.put(e)
    with pytest.raises(ValueError, match="retained IntentBinding"):
        x.repo.put(base.model_copy(update=dict(id="TEST-ONLY-other-media-relation", subject=e.ref)))
    assert len(x.repo.all("RelationClaimV2")) == 1


def test_legacy_evidence_and_hypothesis_scope(x):
    other = x.i.model_copy(update=dict(id="TEST-ONLY-other-intent")); x.repo.put(other)
    h = x.hs[0].model_copy(update=dict(id="TEST-ONLY-other-h", intent=other.ref)); x.repo.put(h)
    cases = [(dict(object=h.ref), "crosses intent"), (dict(intent=pin(other), object=h.ref, evidence=()), "outside declared intent")]
    v2 = intent(id="TEST-ONLY-v2-scope"); x.repo.put(v2)
    x.repo.put(binding(v2, x.m, x.r))
    cases.append((dict(intent=pin(v2)), "crosses intent"))
    for n, (changes, message) in enumerate(cases):
        with pytest.raises(ValueError, match=message): x.repo.put(edge(x, id=f"TEST-ONLY-scope-{n}", **changes))
    assert x.repo.all("RelationClaimV2") == ()


@pytest.mark.parametrize("case", ["initial", "missing", "skipped", "kind", "identity", "digest"])
def test_predecessor_contract_without_masking_conflicts(x, case):
    base = edge(x); x.repo.put(base)
    if case == "initial":
        candidate = base.model_copy(update=dict(id="TEST-ONLY-fresh-initial", predecessor=pin(base)))
        error, message = ValidationError, "initial revision"
    else:
        prior = pin(base)
        if case == "missing": prior = None
        if case == "skipped": prior = prior.model_copy(update={"ref": base.ref.model_copy(update={"revision": 2})})
        if case == "kind": prior = pin(x.i)
        if case == "identity": prior = prior.model_copy(update={"ref": base.ref.model_copy(update={"id": "TEST-ONLY-another"})})
        if case == "digest": prior = prior.model_copy(update={"sha256": "d"*64})
        candidate = base.model_copy(update=dict(revision=2, predecessor=prior))
        error, message = (ValueError, "digest mismatch") if case == "digest" else (ValidationError, "predecessor must pin")
    with pytest.raises(error, match=message): x.repo.put(candidate)
    assert x.repo.all("RelationClaimV2") == (base,)


def test_revision_conflict_and_missing_reference(x):
    base = edge(x); x.repo.put(base)
    with pytest.raises(ValueError, match="immutable revision conflict"):
        x.repo.put(base.model_copy(update=dict(warrant="TEST-ONLY overwrite")))
    with pytest.raises(KeyError, match="TEST-ONLY-absent"):
        x.repo.put(edge(x, id="TEST-ONLY-dangling", subject=d.Ref(kind="Evidence", id="TEST-ONLY-absent")))
    assert x.repo.all("RelationClaimV2") == (base,)


def group(x):
    return d.CompetingSet(id="TEST-ONLY-set", intent=x.i.ref, members=tuple(h.ref for h in x.hs[:2]), exclusive=True, exhaustive=False)


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("set_first", [False, True])
def test_exclusivity_orders_and_historical_sets(x, reverse, set_first):
    hs = x.hs[:2][::-1] if reverse else x.hs[:2]
    relation = edge(x, predicate="compatible_with", subject=hs[0].ref, object=hs[1].ref)
    s = group(x)
    first, second = (s, relation) if set_first else (relation, s)
    x.repo.put(first)
    if set_first: x.repo.put(s.model_copy(update=dict(revision=2, supersedes=s.ref, exclusive=False)))
    with pytest.raises(ValueError, match="exclusive competing set"): x.repo.put(second.model_copy())
    assert x.repo.all(second.ref.kind) == ()


def test_exclusive_set_and_relation_competing_writers(x, monkeypatch):
    from eval_lab.relation_v2 import RelationClaimV2
    peers = [Repository(str(x.repo.engine.url)) for _ in range(2)]
    candidates = (group(x), edge(x, predicate="compatible_with", subject=x.hs[0].ref, object=x.hs[1].ref))
    barrier = Barrier(2, timeout=10); validate = Repository._validate_links
    def synchronized(repo, item):
        validate(repo, item)
        if isinstance(item, (d.CompetingSet, RelationClaimV2)): barrier.wait()
    monkeypatch.setattr(Repository, "_validate_links", synchronized)
    def write(n):
        try: peers[n].put(candidates[n]); return "accepted"
        except ValueError as exc:
            assert "exclusive competing set" in str(exc)
            return "rejected"
    try:
        with ThreadPoolExecutor(max_workers=2) as pool: assert sorted(pool.map(write, range(2))) == ["accepted", "rejected"]
        assert len(x.repo.all("CompetingSet")) + len(x.repo.all("RelationClaimV2")) == 1
    finally:
        for repo in peers: repo.close()


def test_legacy_read_view_is_frozen_unregistered_and_readonly(x):
    from eval_lab.relation_v2 import load_relation
    data = oracle(); data["schema_version"] = 1; data["intent"] = data["intent"]["ref"]
    for name in ("creative_anchor", "epistemic_purpose", "operational_purpose", "warrant", "qualifier", "rebuttal", "predecessor"): del data[name]
    old = d.RelationClaim(**data); x.repo.put(old)
    with x.repo.engine.connect() as conn: before = conn.execute(select(artifacts)).all()
    view = load_relation(x.repo, old.ref)
    assert view.ref == d.Ref(kind="RelationClaim", id="TEST-ONLY-relation")
    assert view.canonical() == canonical(data) and view.digest == digest(data)
    assert (view.epistemic_purpose, view.operational_purpose, view.creative_anchor, view.warrant, view.qualifier, view.rebuttal) == ("UNSPECIFIED", "UNSPECIFIED", (), None, None, None)
    assert view.purpose == "TEST-ONLY free purpose" and view.scope == "TEST-ONLY scope"
    with pytest.raises(ValidationError, match="frozen"): view.source = old
    with pytest.raises(TypeError, match="unregistered artifact"): x.repo.put(view)
    with pytest.raises(ValueError, match="relation reference"): load_relation(x.repo, x.i.ref)
    with x.repo.engine.connect() as conn: assert conn.execute(select(artifacts)).all() == before


def test_public_embed_unchanged_blind_and_revealed(x):
    from test_domain_review import seed_review
    from eval_lab.presentation import serialize_case, submit_pairwise
    lab = seed_review(x.repo)
    for stage in ("blind", "revealed"):
        if stage == "revealed": submit_pairwise(x.repo, lab.round.ref, lab.rater.ref, "tie", "TEST-ONLY choice", created_at=T)
        before = [serialize_case(x.repo, lab.case.ref, lab.round.ref, lab.rater.ref, mode=m) for m in ("public", "embed")]
        x.repo.put(edge(x, id=f"TEST-ONLY-{stage}", warrant="TEST-ONLY PRIVATE SENTINEL"))
        after = [serialize_case(x.repo, lab.case.ref, lab.round.ref, lab.rater.ref, mode=m) for m in ("public", "embed")]
        assert after == before and all(p["stage"] == stage for p in after)
        assert "TEST-ONLY PRIVATE SENTINEL" not in json.dumps(after)


def test_ordered_anchors_only_from_pinned_intent_and_observed_predicates(x):
    from eval_lab.intent_v2 import CriterionV2
    first = CriterionV2(id="TEST-ONLY-a", dimension="motion_plausibility", priority="MUST",
        acceptance="TEST-ONLY accepts a", rejection="TEST-ONLY rejects a", tolerance="TEST-ONLY tolerance a")
    second = first.model_copy(update=dict(id="TEST-ONLY-b", acceptance="TEST-ONLY accepts b"))
    foreign = intent(id="TEST-ONLY-foreign-v2", criteria=(first,)); x.repo.put(foreign)
    local = intent(id="TEST-ONLY-local-v2", criteria=(second,)); x.repo.put(local)
    x.repo.put(binding(local, x.m, x.r))
    candidate = edge(x, id="TEST-ONLY-foreign-anchor", predicate="violates", intent=pin(local), object=local.ref,
        creative_anchor=("TEST-ONLY-a",), epistemic_status="observed", warrant=None, qualifier=None, rebuttal=None)
    with pytest.raises(ValueError, match="exact pinned intent"): x.repo.put(candidate)
    expanded = intent(id=local.id, revision=2, predecessor=pin(local), criteria=(first, second)); x.repo.put(expanded)
    b = x.repo.all("IntentBinding")[0]
    x.repo.put(binding(expanded, x.m, x.r, revision=2, predecessor=pin(b)))
    for n, predicate in enumerate(("fulfills", "violates")):
        item = edge(x, id=f"TEST-ONLY-observed-{n}", predicate=predicate, intent=pin(expanded), object=expanded.ref,
            creative_anchor=("TEST-ONLY-b", "TEST-ONLY-a"), epistemic_status="observed", warrant=None,
            qualifier=None, rebuttal=None)
        x.repo.put(item)
        assert x.repo.get(item.ref).creative_anchor == ("TEST-ONLY-b", "TEST-ONLY-a")
        assert x.repo.get(item.ref).warrant is None


def test_exact_hypothesis_revision_and_v1_v2_exclusivity(x):
    s = group(x); x.repo.put(s)
    revised = x.hs[0].model_copy(update=dict(revision=2)); x.repo.put(revised)
    allowed = edge(x, predicate="compatible_with", subject=revised.ref, object=x.hs[1].ref)
    x.repo.put(allowed)
    with pytest.raises(ValueError, match="exclusive competing set"):
        x.repo.put(allowed.model_copy(update=dict(revision=2, predecessor=pin(allowed), subject=x.hs[0].ref)))
    # A new exclusive set must still inspect both generations of retained claims.
    legacy = d.RelationClaim(**dict(id="TEST-ONLY-v1-compat", subject=x.hs[1].ref, object=x.hs[2].ref,
        intent=x.i.ref, predicate="compatible_with", epistemic_status="proposed", evidence=(),
        asserted_by="TEST-ONLY legacy author", purpose="TEST-ONLY legacy purpose", scope="TEST-ONLY legacy scope", valid_from=T))
    x.repo.put(legacy)
    with pytest.raises(ValueError, match="exclusive competing set"):
        x.repo.put(group(x).model_copy(update=dict(id="TEST-ONLY-v1-set", members=(x.hs[1].ref, x.hs[2].ref))))
    assert len(x.repo.all("CompetingSet")) == 1
