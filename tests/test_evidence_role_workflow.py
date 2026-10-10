"""TEST-ONLY private import, immutable replay and public-boundary checks."""
import json
import sqlite3
from types import SimpleNamespace
import pytest
from eval_lab import evidence_roles as er, pilot_cli, generation as g, domain as d
from eval_lab.persistence import Repository
from eval_lab.pilot import PilotWorkspace
from eval_lab.pilot_domain import PilotDataset
from eval_lab.presentation import serialize_case
from test_domain_review import seed_review
from test_evidence_roles import make, role, at
from test_intent_v2 import anchors


def test_cli_import_correction_schema_readonly_query(make, tmp_path, capsys):
    x = make(linked=False); args = ["--root", str(tmp_path), "--author", "TEST-ONLY linker"]
    source = tmp_path / "TEST-ONLY-link.json"
    source.write_text(x.link.model_dump_json(exclude={"created_at", "tool_version"}))
    assert pilot_cli.main(args + ["evidence-arm", "--file", str(source)]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["tool_version"] == "0.1.0" and data["arm"] == "TEST-ONLY-arm"
    retained = x.repo.get(x.link.ref)
    correction = retained.model_copy(update=dict(revision=2, predecessor=g.pin(retained), revision_reason="TEST-ONLY clarification"))
    source.write_text(correction.model_dump_json(exclude={"created_at", "tool_version"}))
    assert pilot_cli.main(args + ["evidence-arm", "--file", str(source)]) == 0
    assert json.loads(capsys.readouterr().out)["revision"] == 2
    source.write_text(json.dumps(dict(evidence=g.pin(x.e).model_dump(), hypothesis=g.pin(x.h).model_dump())))
    before = (tmp_path / "pilot.sqlite").read_bytes()
    assert pilot_cli.main(args + ["evidence-role", "--file", str(source)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["role"] == "TEST_RESULT" and result["reason"] == "POST_FREEZE_CLIP"
    assert result["selected_link"]["ref"] == {"kind": "EvidenceArm", "id": "TEST-ONLY-link", "revision": 2}
    assert (tmp_path / "pilot.sqlite").read_bytes() == before
    assert pilot_cli.main(args + ["schema"]) == 0
    assert {"EvidenceArm", "HypothesisContext", "InstrumentRun"} <= json.loads(capsys.readouterr().out)["record_schemas"].keys()
    reopened = Repository(str(x.repo.engine.url))
    try: assert er.compute(reopened, g.pin(x.e), g.pin(x.h)) == result
    finally: reopened.close()
    absent = tmp_path / "TEST-ONLY-absent"
    assert pilot_cli.main(["--root", str(absent), "evidence-role", "--file", str(source)]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "UNKNOWN" and not absent.exists()


@pytest.mark.parametrize("field", ["created_at", "tool_version"])
def test_import_application_fields_and_author_guard(make, field):
    x = make(linked=False); data = x.link.model_dump(mode="json", exclude={"created_at", "tool_version"})
    with pytest.raises(ValueError, match="application-owned"):
        er.record(x.repo, "evidence-arm", data | {field: "TEST-ONLY injected"}, "TEST-ONLY linker")
    with pytest.raises(ValueError, match="author declaration mismatch"):
        er.record(x.repo, "evidence-arm", data | {"id": "TEST-ONLY-author-mismatch"}, "TEST-ONLY stranger")


@pytest.mark.parametrize("damage,status,detail", [("missing", "UNKNOWN", "missing artifact"), ("corrupt", "INTEGRITY_FAILURE", "integrity")])
def test_query_dependency_failure_is_explicit_and_readonly(make, tmp_path, damage, status, detail):
    x = make()
    with sqlite3.connect(tmp_path / "pilot.sqlite") as db:
        if damage == "missing":
            db.execute("DROP TRIGGER no_delete_artifacts"); db.execute("DELETE FROM artifacts WHERE kind='CompetingSet'")
        else:
            db.execute("DROP TRIGGER no_update_artifacts"); db.execute("UPDATE artifacts SET sha256=? WHERE kind='TestPlan'", ("a" * 64,))
    before = (tmp_path / "pilot.sqlite").read_bytes()
    result = er.query(tmp_path, dict(evidence=g.pin(x.e), hypothesis=g.pin(x.h)))
    assert result["status"] == status and result["role"] is None and detail in result["detail"]
    assert (tmp_path / "pilot.sqlite").read_bytes() == before


def test_snapshot_cross_clip_roots_corrections_and_permuted_replay(make, tmp_path, monkeypatch):
    x = make(); p = PilotWorkspace(tmp_path)
    monkeypatch.setattr(p, "verify_clip", lambda clip: None)  # metadata-only replay; no byte-validation claim
    case_media, case_registration = anchors(p.repo, "TEST-ONLY-case-source", "a" * 64, at(1))
    original = x.c.model_copy(update=dict(id="TEST-ONLY-case-clip", media=case_media.ref,
        ingestion=case_registration.ref, intent=x.h.intent)); p.repo.put(original)
    p.repo.put(PilotDataset(id="TEST-ONLY-dataset", owner="TEST-ONLY curator", clips=(original.ref,)))
    p.snapshot("TEST-ONLY-dataset", "TEST-ONLY-before"); before = p.export_snapshot("TEST-ONLY-before")
    revised = x.link.model_copy(update=dict(revision=2, predecessor=g.pin(x.link), revision_reason="TEST-ONLY correction")); p.repo.put(revised)
    other_h = x.h.model_copy(update=dict(id="TEST-ONLY-unrelated-h", intent=x.repo.all("IntentSpec")[0].ref))
    # An unrelated context must have a distinct intent and distinct media, not merely a different ID.
    intent = x.repo.get(x.h.intent).model_copy(update=dict(id="TEST-ONLY-other-intent")); p.repo.put(intent)
    other_h = other_h.model_copy(update=dict(intent=intent.ref)); p.repo.put(other_h)
    from test_assessments import observation, evidence
    m, _ = anchors(p.repo, "TEST-ONLY-unrelated", "b" * 64, at(1))
    ev = evidence(p.repo, m, "TEST-ONLY-unrelated-e"); obs = observation(m, ev, id="TEST-ONLY-unrelated-o", created_at=at(1)); p.repo.put(obs)
    p.repo.put(er.HypothesisContext(id="TEST-ONLY-unrelated-context", author="TEST-ONLY private", hypothesis=g.pin(other_h), observation=g.pin(obs)))
    p.snapshot("TEST-ONLY-dataset", "TEST-ONLY-after"); exported = p.export_snapshot("TEST-ONLY-after")
    rows = exported["records"]; refs = {(r["ref"]["kind"], r["ref"]["id"], r["ref"]["revision"]) for r in rows}
    assert ("EvidenceArm", "TEST-ONLY-link", 1) in refs and ("EvidenceArm", "TEST-ONLY-link", 2) in refs
    assert ("PilotClip", "TEST-ONLY-arm-clip", 1) in refs
    assert ("HypothesisContext", "TEST-ONLY-unrelated-context", 1) not in refs
    records = {d.Ref(**r["ref"]): d.ARTIFACT_TYPES[r["ref"]["kind"]].model_validate(r["artifact"]) for r in rows}
    replay = SimpleNamespace(get=records.__getitem__, all=lambda kind: tuple(v for v in reversed(list(records.values())) if v.ref.kind == kind))
    live = role(x); replayed = er.compute(replay, g.pin(x.e), g.pin(x.h))
    for result in (live, replayed):
        assert result["role"] == "TEST_RESULT" and result["reason"] == "POST_FREEZE_CLIP"
    assert replayed == live  # Equality is the replay property, not the role oracle.
    assert p.export_snapshot("TEST-ONLY-before") == before
    lab = seed_review(p.repo)
    for mode in ("public", "embed"):
        payload = json.dumps(serialize_case(p.repo, lab.case.ref, lab.round.ref, lab.rater.ref, mode=mode))
        assert "TEST-ONLY-link" not in payload and "InstrumentRun" not in payload and "HypothesisContext" not in payload
    p.close()


@pytest.mark.parametrize("command", ["evidence-arm", "hypothesis-context", "instrument-run", "evidence-role"])
def test_context_cli_help(command, capsys):
    with pytest.raises(SystemExit, match="0"): pilot_cli.parser().parse_args([command, "--help"])
    help_text = capsys.readouterr().out
    assert "private" in help_text and "pin" in help_text and "docs/hypothesis-testing.md" in help_text


@pytest.mark.parametrize("field", ["role", "reason"])
def test_query_cannot_author_computed_fields(make, tmp_path, field):
    x = make()
    result = er.query(tmp_path, dict(evidence=g.pin(x.e), hypothesis=g.pin(x.h)) | {field: "TEST-ONLY injected"})
    assert result["status"] == "INTEGRITY_FAILURE" and result["role"] is None
    assert result["detail"] == "role query requires only evidence and hypothesis pins"


def test_show_includes_private_context_history(make, tmp_path, capsys):
    x = make()
    assert pilot_cli.main(["--root", str(tmp_path), "show", x.c.id]) == 0
    records = json.loads(capsys.readouterr().out)["evidence_role_contexts"]
    assert [(r["id"], r["revision"]) for r in records] == [("TEST-ONLY-link", 1)]


from test_competing_sets import workspace, TEXT
from test_media import media_tools, codec_videos
from eval_lab.pilot import ObservationInput


def test_scrubbed_generated_frame_is_supporting_and_review_does_not_reset_creation(workspace):
    p = workspace; h = p.repo.all("Hypothesis")[0]
    frames = p.frames("clip", (.3,))
    ev = p.observe("clip", TEXT, "TEST-ONLY-scrub", ObservationInput(observation="TEST-ONLY generated frame",
        timestamp_start=.2, timestamp_end=.5, derivative_id=frames.id, frame_indices=(frames.frames[0].frame_index,)))
    result = er.compute(p.repo, g.pin(ev), g.pin(h))
    assert result["role"] == "SUPPORTING" and result["reason"] == "NO_FROZEN_ARM"
    before = ev.canonical(); first_view = p.repo.all("FirstView")[0].canonical()
    p.frames("clip", (.4,))
    assert p.repo.get(ev.ref).canonical() == before and p.repo.all("FirstView")[0].canonical() == first_view
    assert er.compute(p.repo, g.pin(ev), g.pin(h))["role"] == "SUPPORTING"


def test_unlinked_run_histories_are_private_snapshot_roots(make):
    from test_evidence_roles import run_for
    x = make(measurement="INSTRUMENT", linked=False)
    first = run_for(x); x.repo.put(first)
    x.repo.put(first.model_copy(update=dict(revision=2, predecessor=g.pin(first), revision_reason="TEST-ONLY metadata correction")))
    refs = [r.model_dump() for r in er.roots(x.repo, (x.c,))]
    assert {"kind": "InstrumentRun", "id": "TEST-ONLY-run", "revision": 1} in refs
    assert {"kind": "InstrumentRun", "id": "TEST-ONLY-run", "revision": 2} in refs


def test_arm_only_snapshot_retains_exact_prompt_history_and_replays_discovery(make, tmp_path, monkeypatch):
    from test_assessments import observation, evidence
    x = make(e=10, registered=2)
    assert x.c.intent is None
    prior_media, _ = anchors(x.repo, "TEST-ONLY-prompt-source", "a" * 64, at(1))
    prior_e = evidence(x.repo, prior_media, "TEST-ONLY-prior-e")
    prior_o = observation(prior_media, prior_e, id="TEST-ONLY-prior-o", created_at=at(3)); x.repo.put(prior_o)
    prompt_o = observation(x.m, x.e, id="TEST-ONLY-prompt-o", created_at=at(10)); x.repo.put(prompt_o)
    context = er.HypothesisContext(id="TEST-ONLY-prompt", author="TEST-ONLY author",
        hypothesis=g.pin(x.h), observation=g.pin(prior_o)); x.repo.put(context)
    x.repo.put(context.model_copy(update=dict(revision=2, predecessor=g.pin(context),
        revision_reason="TEST-ONLY correct prompting observation", observation=g.pin(prompt_o))))
    # Same intent and same ID at another revision must not broaden incoming closure.
    for hyp, name in ((x.h.model_copy(update=dict(id="TEST-ONLY-unreached-h")), "TEST-ONLY-unreached-context"),
            (x.h.model_copy(update=dict(revision=2, created_at=at(11))), "TEST-ONLY-later-context")):
        x.repo.put(hyp)
        x.repo.put(er.HypothesisContext(id=name, author="TEST-ONLY unrelated author",
            hypothesis=g.pin(hyp), observation=g.pin(prior_o)))
    p = PilotWorkspace(tmp_path)
    monkeypatch.setattr(p, "verify_clip", lambda clip: None)  # Metadata-only replay, no media-byte claim.
    try:
        p.repo.put(PilotDataset(id="TEST-ONLY-arm-dataset", owner="TEST-ONLY curator", clips=(x.c.ref,)))
        p.snapshot("TEST-ONLY-arm-dataset", "TEST-ONLY-arm-snapshot")
        rows = p.export_snapshot("TEST-ONLY-arm-snapshot")["records"]
        assert [(r["ref"]["id"], r["ref"]["revision"]) for r in rows if r["ref"]["kind"] == "HypothesisContext"] == [
            ("TEST-ONLY-prompt", 1), ("TEST-ONLY-prompt", 2)]
        assert [(r["ref"]["id"], r["ref"]["revision"]) for r in rows if r["ref"]["kind"] == "Hypothesis"] == [
            ("TEST-ONLY-query-h", 1)]
        records = {d.Ref(**r["ref"]): d.ARTIFACT_TYPES[r["ref"]["kind"]].model_validate(r["artifact"]) for r in rows}
        replay = SimpleNamespace(get=records.__getitem__,
            all=lambda kind: tuple(v for v in reversed(list(records.values())) if v.ref.kind == kind))
        live = role(x); replayed = er.compute(replay, g.pin(x.e), g.pin(x.h))
        for result in (live, replayed):
            assert (result["status"], result["role"], result["reason"], result["selected_link"]) == (
                "COMPUTED", "DISCOVERY", "PROMPTING_OBSERVATION", None)
            assert result["detail"] == "The pinned prompting observation cites this evidence revision."
            assert {(v["ref"]["kind"], v["ref"]["id"], v["ref"]["revision"]) for v in result["dependencies"]} == {
                ("CompetingSet", "TEST-ONLY-role-set", 1), ("Evidence", "TEST-ONLY-frame", 1),
                ("Evidence", "TEST-ONLY-prior-e", 1), ("EvidenceArm", "TEST-ONLY-link", 1),
                ("Hypothesis", "TEST-ONLY-query-h", 1), ("HypothesisContext", "TEST-ONLY-prompt", 1),
                ("HypothesisContext", "TEST-ONLY-prompt", 2), ("IntentSpec", "TEST-ONLY-intent", 1),
                ("MediaAsset", "TEST-ONLY-arm-clip", 1), ("MediaAsset", "TEST-ONLY-prompt-source", 1),
                ("MediaIngestion", "TEST-ONLY-arm-clip", 1), ("PilotClip", "TEST-ONLY-arm-clip", 1),
                ("TechnicalObservation", "TEST-ONLY-prior-o", 1), ("TechnicalObservation", "TEST-ONLY-prompt-o", 1),
                ("TestPlan", "TEST-ONLY-plan", 1), ("TestPlan", "TEST-ONLY-plan", 2)}
        assert replayed == live  # Replay property includes exact dependency hashes, not the role oracle.
    finally:
        p.close()
