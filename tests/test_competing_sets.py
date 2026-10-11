"""TEST-ONLY hypothesis declarations and generated patterns; no real clip judgments."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from threading import Barrier

import pytest

from eval_lab import domain as d, pilot as authoring
from eval_lab.persistence import Repository
from eval_lab.pilot_cli import main, parser
from eval_lab.presentation import serialize_case, submit_pairwise
from test_domain_review import seed_review
from test_media import media_tools, codec_videos

STAMP = datetime(2026, 10, 8, tzinfo=timezone.utc)
TEXT = "TEST-ONLY private hypothesis set fixture"
RESIDUAL = {"kind": "RESIDUAL", "description": "none of the listed causes"}


def intent_form():
    return authoring.IntentInput(objective=TEXT, audience=TEXT, context=TEXT,
        criteria=(d.Criterion(dimension=d.Dimension.PROMPT, rationale=TEXT, acceptance=TEXT),))


def hypothesis_form(confidence=None):
    return authoring.HypothesisInput(observed_problem=TEXT, proposed_cause=TEXT,
        confidence=confidence, evidence_required=(TEXT,), discriminating_test=TEXT,
        predicted_observation=TEXT, falsifying_observation=TEXT)


def seed(repo):
    intent = d.IntentSpec(id="TEST-ONLY-intent", created_at=STAMP, owner=TEXT,
        authority="human_declared", approved_by=TEXT, **intent_form().model_dump(exclude={"revision_reason"}))
    repo.put(intent)
    hypotheses = tuple(d.Hypothesis(id=f"TEST-ONLY-h{i}", created_at=STAMP,
        intent=intent.ref, **hypothesis_form(confidence).model_dump())
        for i, confidence in enumerate((None, .8, .9)))
    for item in hypotheses:
        repo.put(item)
    return hypotheses


@pytest.fixture
def records():
    repo = Repository()
    try:
        yield repo, seed(repo)
    finally:
        repo.close()


def competing(hypotheses, **changes):
    fields = dict(id="TEST-ONLY-set", created_at=STAMP, intent=hypotheses[0].intent,
        members=tuple(h.ref for h in hypotheses), exclusive=False, exhaustive=False)
    return d.CompetingSet(**(fields | changes))


def relation(hypotheses, **changes):
    fields = dict(id="TEST-ONLY-relation", created_at=STAMP, subject=hypotheses[0].ref,
        object=hypotheses[1].ref, intent=hypotheses[0].intent, predicate="compatible_with",
        epistemic_status="asserted", evidence=(), asserted_by=TEXT, purpose=TEXT,
        scope=TEXT, valid_from=STAMP, confidence=.95)
    return d.RelationClaim(**(fields | changes))


@pytest.mark.parametrize("exclusive", [False, True])
@pytest.mark.parametrize("exhaustive", [False, True])
def test_flags_residual_and_claim_confidence_are_independent(records, exclusive, exhaustive):
    repo, hs = records
    before = {h.ref: (h.canonical(), h.digest) for h in hs}
    item = competing(hs, exclusive=exclusive, exhaustive=exhaustive)
    expected = [h.ref.model_dump() for h in hs] + ([RESIDUAL] if exhaustive else [])
    assert item.model_dump(mode="json")["members"] == expected
    assert "confidence" not in item.model_dump()
    assert item.digest == competing(hs, exclusive=exclusive, exhaustive=exhaustive).digest
    for _ in range(3):
        item = d.CompetingSet.model_validate_json(item.canonical())
        assert repo.put(item) == item.digest
        assert repo.get(item.ref).model_dump(mode="json")["members"] == expected
    assert {h.ref: (h.canonical(), h.digest) for h in repo.all("Hypothesis")} == before
    assert [h.confidence for h in repo.all("Hypothesis")] == [None, .8, .9]
    assert all(h.status == "proposed" and not h.supporting_evidence for h in repo.all("Hypothesis"))
    assert repo.all("RelationClaim") == repo.all("AgentAssessment") == ()


@pytest.mark.parametrize("members", [(), (RESIDUAL,), (RESIDUAL, RESIDUAL),
    ({"kind": "RESIDUAL", "description": "TEST-ONLY wrong label"},),
    (RESIDUAL | {"confidence": .2},)])
def test_invalid_members_and_residual_only_are_rejected(records, members):
    _, hs = records
    with pytest.raises(ValueError):
        competing(hs, members=members, exhaustive=True)


@pytest.mark.parametrize("extra", [[RESIDUAL, RESIDUAL],
    [RESIDUAL | {"status": "supported"}], [RESIDUAL | {"evidence": []}],
    [RESIDUAL | {"description": "TEST-ONLY malformed"}]])
def test_malformed_supplied_residual_with_named_member(records, extra):
    _, hs = records
    with pytest.raises(ValueError):
        competing(hs, members=(hs[0].ref, *extra), exhaustive=True)


def test_single_named_member_and_supplied_residual(records):
    repo, hs = records
    one = competing(hs[:1])
    repo.put(one)
    with pytest.raises(ValueError):
        competing(hs, members=(hs[0].ref, RESIDUAL))
    supplied = competing(hs, members=(RESIDUAL, hs[0].ref), exhaustive=True)
    assert supplied.model_dump(mode="json")["members"] == [RESIDUAL, hs[0].ref.model_dump()]
    for members in ((hs[0].ref, hs[0].ref), (hs[0].ref, hs[0].ref.model_copy(update={"revision": 2})), (hs[0].intent,)):
        with pytest.raises(ValueError):
            competing(hs, members=members)


@pytest.mark.parametrize("field", ["exclusive", "exhaustive"])
@pytest.mark.parametrize("value", [None, 0, 1, "false", "true"])
def test_flags_require_explicit_booleans(records, field, value):
    _, hs = records
    with pytest.raises(ValueError):
        competing(hs, **{field: value})
    payload = competing(hs).model_dump()
    del payload[field]
    with pytest.raises(ValueError):
        d.CompetingSet.model_validate(payload)


def test_set_reference_boundaries_and_copy_revalidation(records):
    repo, hs = records
    item = competing(hs)
    other = repo.get(hs[0].intent).model_copy(update={"id": "TEST-ONLY-other"})
    repo.put(other)
    foreign = hs[0].model_copy(update={"id": "TEST-ONLY-foreign", "intent": other.ref})
    repo.put(foreign)
    for changes in ({"intent": hs[0].ref}, {"members": ()}, {"members": (hs[0].intent,)},
        {"members": (hs[0].ref, foreign.ref)}, {"members": (hs[0].ref.model_copy(update={"revision": 8}),)}):
        with pytest.raises((ValueError, KeyError)):
            repo.put(item.model_copy(update=changes))
    assert repo.all("CompetingSet") == ()


@pytest.mark.parametrize("predicate", ["compatible_with", "refines"])
def test_relation_contract_and_no_inferred_edges(records, predicate):
    repo, hs = records
    edge = relation(hs, predicate=predicate)
    before = [h.canonical() for h in hs]
    repo.put(edge)
    assert repo.get(edge.ref) == edge
    assert len(repo.all("RelationClaim")) == 1
    assert [h.canonical() for h in repo.all("Hypothesis")] == before
    assert (edge.subject, edge.object, edge.confidence) == (hs[0].ref, hs[1].ref, .95)
    revised = hs[0].model_copy(update={"revision": 2})
    repo.put(revised)
    invalid_cases = (
        ({"subject": hs[0].intent}, "relation domain/range violation"),
        ({"object": hs[0].intent}, "relation domain/range violation"),
        ({"object": hs[0].ref}, "hypothesis cannot relate to itself"),
        ({"object": revised.ref}, "hypothesis cannot relate to itself"),
        ({"epistemic_status": "observed"}, "observed relation needs evidence"),
        ({"valid_from": STAMP.replace(tzinfo=None)}, "invalid validity interval"),
        ({"valid_until": STAMP}, "invalid validity interval"),
        *(({field: ""}, rf"{field}\s+String should have at least 1 character")
            for field in ("asserted_by", "purpose", "scope")),
    )
    for index, (changes, error) in enumerate(invalid_cases):
        candidate = edge.model_copy(update=changes | {"id": f"TEST-ONLY-invalid-{index}"})
        with pytest.raises(ValueError, match=error):
            repo.put(candidate)
    for field in ("intent", "asserted_by", "purpose", "scope", "valid_from"):
        payload = edge.model_dump()
        del payload[field]
        with pytest.raises(ValueError, match=rf"{field}\s+Field required"):
            d.RelationClaim.model_validate(payload)
    other = repo.get(hs[0].intent).model_copy(update={"revision": 2, "supersedes": hs[0].intent})
    repo.put(other)
    foreign = hs[2].model_copy(update={"revision": 2, "intent": other.ref})
    repo.put(foreign)
    for endpoint in ("subject", "object"):
        with pytest.raises(ValueError, match="relation crosses intent without explicit mapping"):
            repo.put(edge.model_copy(update={"id": f"TEST-ONLY-cross-{endpoint}", endpoint: foreign.ref}))
    assert repo.all("RelationClaim") == (edge,)


@pytest.mark.parametrize("predicate", ["compatible_with", "refines"])
def test_hypothesis_relation_with_persisted_evidence_is_still_a_claim(workspace, predicate):
    repo = workspace.repo
    hs = repo.all("Hypothesis")
    evidence = d.Evidence(id="TEST-ONLY-evidence", created_at=STAMP,
        media=workspace.clip("clip").media, observation=TEXT, source="synthetic_fixture",
        method=TEXT, coverage="full_clip", author=TEXT, independence_group=TEXT)
    repo.put(evidence)
    edge = relation(hs, predicate=predicate, evidence=(evidence.ref,))
    repo.put(edge)
    assert repo.get(evidence.ref) == evidence
    assert repo.get(edge.ref) == edge  # Same endpoints and evidence are valid for a claim.
    candidate = edge.model_copy(update={"id": "TEST-ONLY-observed", "epistemic_status": "observed"})
    with pytest.raises(ValueError, match="hypothesis relations are claims, not observations"):
        repo.put(candidate)
    assert repo.all("RelationClaim") == (edge,)


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("set_first", [False, True])
def test_exclusivity_both_insertion_orders_and_endpoint_orders(records, reverse, set_first):
    repo, hs = records
    item = competing(hs[:2], exclusive=True)
    edge = relation(tuple(reversed(hs[:2])) if reverse else hs)
    first, second = (item, edge) if set_first else (edge, item)
    repo.put(first)
    with pytest.raises(ValueError, match="exclusive"):
        repo.put(second)
    assert repo.all(second.ref.kind) == ()


def test_overlapping_sets_nonexclusive_unrelated_and_refinement(records):
    repo, hs = records
    repo.put(competing(hs[:2], exclusive=True))
    repo.put(competing(hs[1:], id="TEST-ONLY-overlap", exclusive=True))
    repo.put(competing((hs[0], hs[2]), id="TEST-ONLY-open"))
    repo.put(relation((hs[0], hs[2])))
    repo.put(relation(hs, id="TEST-ONLY-refinement", predicate="refines"))
    with pytest.raises(ValueError, match="exclusive"):
        repo.put(relation(hs[1:], id="TEST-ONLY-overlap-conflict"))
    assert len(repo.all("RelationClaim")) == 2


def test_revision_admission_uses_exact_pins_and_retains_history(records):
    repo, hs = records
    old = competing(hs[:2], exclusive=True)
    repo.put(old)
    revised = old.model_copy(update={"revision": 2, "supersedes": old.ref, "exclusive": False})
    repo.put(revised)
    assert repo.put(old) == old.digest
    with pytest.raises(ValueError, match="exclusive"):
        repo.put(relation(hs))
    h2 = hs[0].model_copy(update={"revision": 2, "confidence": None})
    repo.put(h2)
    edge = relation((h2, hs[1]))
    repo.put(edge)  # A newer member revision does not inherit membership.
    with pytest.raises(ValueError, match="exclusive"):
        repo.put(competing((h2, hs[1]), revision=3, supersedes=revised.ref, exclusive=True))
    new_edge = edge.model_copy(update={"revision": 2, "subject": hs[0].ref})
    with pytest.raises(ValueError, match="exclusive"):
        repo.put(new_edge)
    assert repo.get(old.ref).canonical() == old.canonical()
    assert repo.get(old.ref).digest == old.digest
    for changes in ({"exclusive": False}, {"revision": 3, "supersedes": old.ref},
        {"revision": 3, "supersedes": None}, {"revision": 4, "supersedes": revised.ref},
        {"revision": 3, "supersedes": hs[0].ref},
        {"revision": 3, "supersedes": revised.ref.model_copy(update={"id": "TEST-ONLY-wrong"})}):
        with pytest.raises(ValueError):
            repo.put(old.model_copy(update=changes))
    with pytest.raises((ValueError, KeyError)):
        repo.put(old.model_copy(update={"revision": 4, "supersedes": old.ref.model_copy(update={"revision": 3})}))
    with pytest.raises(ValueError):
        competing(hs, supersedes=old.ref)


def test_reopen_preserves_canonical_bytes_hashes_and_member_order(tmp_path):
    url = "sqlite:///" + str(tmp_path / "TEST-ONLY.sqlite")
    repo = Repository(url)
    hs = seed(repo)
    item = competing(tuple(reversed(hs)), exhaustive=True)
    repo.put(item)
    repo.close()
    repo = Repository(url)
    try:
        restored = repo.get(item.ref)
        assert restored.canonical() == item.canonical()
        assert restored.digest == item.digest
        assert restored.members == item.members
    finally:
        repo.close()


def test_concurrent_conflicting_admissions_cannot_both_commit(tmp_path, monkeypatch):
    url = "sqlite:///" + str(tmp_path / "TEST-ONLY-race.sqlite")
    owner = Repository(url)
    hs = seed(owner)
    peers = (Repository(url), Repository(url))
    candidates = (competing(hs[:2], exclusive=True), relation(hs))
    barrier = Barrier(2, timeout=5)
    validate = Repository._validate_links

    def synchronized_validation(self, item):
        validate(self, item)
        if isinstance(item, (d.CompetingSet, d.RelationClaim)):
            barrier.wait()

    monkeypatch.setattr(Repository, "_validate_links", synchronized_validation)

    def submit(index):
        try:
            peers[index].put(candidates[index])
            return "accepted"
        except ValueError as exc:
            assert "exclusive" in str(exc)
            return "rejected"

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(submit, range(2))) == ["accepted", "rejected"]
        assert len(owner.all("CompetingSet")) + len(owner.all("RelationClaim")) == 1
    finally:
        for repo in (*peers, owner):
            repo.close()


@pytest.fixture
def workspace(tmp_path, codec_videos):
    p = authoring.PilotWorkspace(tmp_path / "TEST-ONLY-workspace")
    p.init("TEST-ONLY", TEXT)
    p.register("TEST-ONLY", "clip", codec_videos["cfr"], TEXT, TEXT)
    p.intent("clip", TEXT, intent_form())
    for name, confidence in (("a", None), ("b", .8)):
        p.hypothesize("clip", TEXT, name, hypothesis_form(confidence))
    try:
        yield p
    finally:
        p.close()


def test_private_cli_draft_authoring_sessions_show_and_pinned_exports(workspace, tmp_path, capsys):
    p = workspace
    draft = tmp_path / "TEST-ONLY-draft.json"
    assert main(["draft", "competing-set", "--output", str(draft)]) == 0
    assert json.loads(draft.read_text()) == {"members": [], "exclusive": None, "exhaustive": None}
    with pytest.raises(ValueError):
        authoring.read_human_form("competing-set", draft)
    draft.write_text(json.dumps({"members": ["a", "b@1"], "exclusive": False, "exhaustive": True}))
    session = p.session_start("clip", TEXT)
    argv = ["--root", str(p.root), "--author", TEXT]
    capsys.readouterr()
    assert main(argv + ["competing-set", "clip", "--id", "causes", "--file", str(draft), "--session", session.id]) == 0
    result = json.loads(capsys.readouterr().out)
    first = p.repo.get(d.Ref(kind="CompetingSet", id=result["id"]))
    assert [m.id for m in first.members if isinstance(m, d.Ref)] == ["clip:hypothesis:a", "clip:hypothesis:b"]
    submission = next(s for s in p.repo.all("PilotSubmission") if s.artifact == first.ref)
    assert submission.session == session.ref and submission.author == TEXT
    assert main(argv + ["show", "clip"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["quality_verdict"] == "UNKNOWN"
    assert any(s["artifact"] == result for s in shown["submissions"])
    for predicate in ("compatible_with", "refines"):
        form = authoring.RelationInput(subject="a", subject_kind="Hypothesis", object="b", object_kind="Hypothesis",
            predicate=predicate, purpose=TEXT, scope=TEXT)
        assert p.relate("clip", TEXT, predicate, form).confidence is None
    old_snapshot = p.snapshot("TEST-ONLY", "before")
    old_export = p.export_snapshot(old_snapshot.id)
    h = p.latest("Hypothesis", "clip:hypothesis:a")
    p.repo.put(h.model_copy(update={"revision": 2}))
    form = authoring.CompetingSetInput(members=("a", "b@1"), exclusive=False, exhaustive=True)
    second = p.competing_set("clip", TEXT, "causes", form)
    assert second.supersedes == first.ref and second.members[0].revision == 2
    assert first.members[0].revision == 1
    p.snapshot("TEST-ONLY", "after")
    exported = p.export_snapshot("after")
    pinned = {d.Ref(**r["ref"]): r["sha256"] for r in exported["records"]}
    assert all(ref in pinned for ref in (first.ref, second.ref, h.ref, h.ref.model_copy(update={"revision": 2})))
    assert p.export_snapshot("before") == old_export
    assert main(argv + ["export-snapshot", "before"]) == 0
    assert json.loads(capsys.readouterr().out) == old_export
    assert p.status("TEST-ONLY")["clips"][0]["quality_verdict"] == "UNKNOWN"


def test_authoring_rejects_missing_intent_invalid_sessions_and_cross_intent_submission(workspace):
    p = workspace
    form = authoring.CompetingSetInput(members=("a", "b"), exclusive=True, exhaustive=False)
    session = p.session_start("clip", TEXT)
    p.session_event(session.id, "pause")
    with pytest.raises(ValueError, match="active session"):
        p.competing_set("clip", TEXT, "invalid", form, session.id)
    assert p.repo.all("CompetingSet") == ()
    item = p.competing_set("clip", TEXT, "valid", form)
    p.intent("clip", TEXT, intent_form().model_copy(update={"revision_reason": TEXT}))
    with pytest.raises(ValueError):
        p._submission(p.clip("clip"), item, TEXT)
    with pytest.raises(ValueError):
        p.competing_set("clip", TEXT, "cross", form)
    original = p.clip("clip")
    p.repo.put(original.model_copy(update={"revision": original.revision + 1, "intent": None}))
    with pytest.raises(ValueError, match="intent"):
        p.competing_set("clip", TEXT, "no-intent", form)


def test_cli_help_describes_set_and_relation_contract(capsys):
    with pytest.raises(SystemExit) as exit:
        parser().parse_args(["competing-set", "--help"])
    assert exit.value.code == 0
    help_text = capsys.readouterr().out
    assert "--session" in help_text and "revision" in help_text and "exclusive" in help_text
    with pytest.raises(SystemExit):
        parser().parse_args(["relate", "--help"])
    assert "compatible_with" in capsys.readouterr().out


def test_public_embed_exclude_sets_and_old_payloads_have_no_new_defaults(records):
    repo, hs = records
    lab = seed_review(repo)
    before = {mode: serialize_case(repo, lab.case.ref, lab.round.ref, lab.rater.ref, mode=mode) for mode in ("public", "embed")}
    repo.put(competing(hs, exhaustive=True))
    for mode in before:
        assert serialize_case(repo, lab.case.ref, lab.round.ref, lab.rater.ref, mode=mode) == before[mode]
    submit_pairwise(repo, lab.round.ref, lab.rater.ref, "tie", TEXT, created_at=STAMP)
    for mode in before:
        public = json.dumps(serialize_case(repo, lab.case.ref, lab.round.ref, lab.rater.ref, mode=mode))
        assert all(private not in public for private in (TEXT, "CompetingSet", "RESIDUAL", "TEST-ONLY-h0", "members"))
    assert set(hs[0].model_dump()) == {"id", "revision", "schema_version", "created_at", "intent", "observed_problem",
        "proposed_cause", "confidence", "confidence_kind", "supporting_evidence", "contradicting_evidence",
        "evidence_required", "discriminating_test", "predicted_observation", "falsifying_observation", "status"}
    assert set(relation(hs, predicate="alternative_to").model_dump()) == {"id", "revision", "schema_version", "created_at",
        "subject", "predicate", "object", "intent", "epistemic_status", "evidence", "asserted_by", "purpose",
        "scope", "valid_from", "valid_until", "confidence"}
