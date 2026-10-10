"""TEST-ONLY local CLI and private history; no executed measurements."""
import json
import sqlite3
import pytest
from pydantic import ValidationError
from eval_lab import test_plans as tp, pilot_cli, generation as g
from eval_lab.domain import Ref
from eval_lab.persistence import Repository
from eval_lab.presentation import serialize_case
from test_domain_review import seed_review
from test_competing_sets import workspace, competing
from test_media import media_tools, codec_videos
from test_test_plans import env, form, T, A, B, X, Y, Z


def test_cli_import_freeze_readonly_verify_and_schema(env, tmp_path, capsys):
    repo, group = env
    source = tmp_path / "TEST-ONLY-input.json"
    source.write_text(tp.TestPlan(**form(group)).model_dump_json(exclude={"tool_version", "frozen_at", "frozen_digest"}))
    args = ["--root", str(tmp_path), "--author", "TEST-ONLY planner"]
    assert pilot_cli.main(args + ["test-plan", "--file", str(source)]) == 0
    draft = json.loads(capsys.readouterr().out)
    assert draft["frozen_at"] is None and draft["frozen_digest"] is None and draft["tool_version"] == "0.1.0"
    assert pilot_cli.main(args + ["verify-test-plan", "TEST-ONLY-plan@1"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "NOT_FROZEN"
    assert pilot_cli.main(args + ["freeze-test-plan", "TEST-ONLY-plan@1"]) == 0
    frozen = json.loads(capsys.readouterr().out); source.write_text(json.dumps(frozen, indent=3, sort_keys=True))
    before = (tmp_path / "pilot.sqlite").read_bytes()
    assert pilot_cli.main(args + ["verify-test-plan", "TEST-ONLY-plan@2", "--file", str(source)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "VERIFIED" and result["quality_verdict"] == "UNKNOWN"
    assert result["diagnosticity"] == "DECISIVE" and result["residual"] == "not testable by this plan"
    assert (tmp_path / "pilot.sqlite").read_bytes() == before
    assert pilot_cli.main(args + ["schema"]) == 0
    assert "TestPlan" in json.loads(capsys.readouterr().out)["record_schemas"]


@pytest.mark.parametrize("field", ["frozen_at", "frozen_digest", "tool_version"])
def test_import_rejects_application_owned_fields(env, field):
    repo, group = env
    with pytest.raises(ValueError, match="application-owned"):
        tp.record(repo, form(group) | {field: None}, "TEST-ONLY planner")
    assert repo.all("TestPlan") == ()


def test_import_author_and_exact_target_guards(env):
    repo, group = env
    with pytest.raises(ValueError, match="author declaration mismatch"):
        tp.record(repo, form(group), "TEST-ONLY other person")
    with pytest.raises(ValueError, match="exact ID@REV"):
        tp.freeze(repo, "TEST-ONLY-plan")
    assert repo.all("TestPlan") == ()


@pytest.mark.parametrize("case,status,detail", [
    ("workspace", "UNKNOWN", "unavailable"), ("record", "UNKNOWN", "missing artifact"),
    ("dependency", "UNKNOWN", "missing artifact"), ("source", "UNKNOWN", "No such file"),
    ("corrupt", "INTEGRITY_FAILURE", "integrity"), ("dependency-corrupt", "INTEGRITY_FAILURE", "integrity"),
    ("forged", "INTEGRITY_FAILURE", "differs from retained revision"),
    ("digest", "INTEGRITY_FAILURE", "frozen digest mismatch"),
])
def test_verification_failures_remain_nonzero_and_readonly(env, tmp_path, capsys, case, status, detail):
    repo, group = env; draft = tp.TestPlan(**form(group)); repo.put(draft)
    frozen = tp.freeze(repo, "TEST-ONLY-plan@1")
    root = tmp_path / "TEST-ONLY-absent" if case == "workspace" else tmp_path
    target = "TEST-ONLY-missing@1" if case == "record" else "TEST-ONLY-plan@2"
    args = ["--root", str(root), "verify-test-plan", target]
    source = tmp_path / "TEST-ONLY-candidate.json"
    if case in ("source", "forged", "digest"):
        args += ["--file", str(source)]
        if case != "source":
            data = frozen.model_dump(mode="json"); data["measurement"]["protocol"] = "TEST-ONLY forged protocol"
            if case == "forged": data["frozen_digest"] = tp.freeze_digest(data)
            source.write_text(json.dumps(data))
    if case in ("dependency", "corrupt", "dependency-corrupt"):
        with sqlite3.connect(tmp_path / "pilot.sqlite") as db:
            if case == "dependency":
                db.execute("DROP TRIGGER no_delete_artifacts")
                db.execute("DELETE FROM artifacts WHERE kind='CompetingSet'")
            else:
                db.execute("DROP TRIGGER no_update_artifacts")
                db.execute("UPDATE artifacts SET sha256=? WHERE kind=?", ("e" * 64, "Hypothesis" if case == "dependency-corrupt" else "TestPlan"))
    before = (tmp_path / "pilot.sqlite").read_bytes()
    assert pilot_cli.main(args) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == status and detail in result["detail"] and result["quality_verdict"] == "UNKNOWN"
    assert "diagnosticity" not in result
    assert (tmp_path / "pilot.sqlite").read_bytes() == before
    assert not (tmp_path / "TEST-ONLY-absent").exists()


def test_private_histories_snapshot_scope_and_public_omission(workspace, capsys):
    p = workspace; hs = p.repo.all("Hypothesis")
    group = competing(hs, id="TEST-ONLY-relevant"); p.repo.put(group)
    data = form(group, predictions={hs[0].id: [X], hs[1].id: [Y]})
    p.snapshot("TEST-ONLY", "TEST-ONLY-before")
    old = json.dumps(p.export_snapshot("TEST-ONLY-before"), sort_keys=True)
    lab = seed_review(p.repo)
    args = (p.repo, lab.case.ref, lab.round.ref, lab.rater.ref)
    public = {mode: serialize_case(*args, mode=mode) for mode in ("public", "embed")}
    first = tp.record(p.repo, data, "TEST-ONLY planner"); frozen = tp.freeze(p.repo, "TEST-ONLY-plan@1")
    gp = g.record_plan(p.repo, dict(family_id="TEST-ONLY-family", arm="TEST-ONLY-g-arm", varied_factor="TEST-ONLY-motion",
        controlled_factors={}, prompt="TEST-ONLY move", model="TEST-ONLY model", model_version_string="TEST-ONLY v2",
        settings={}, seed=17, n_planned=5, intent_revision_ids=[], notes="TEST-ONLY notes"))
    later = tp.record(p.repo, data | dict(revision=3, predecessor=g.pin(frozen), arms=[dict(id="TEST-ONLY-new-arm",
        description="TEST-ONLY generated comparison", generation_plan_ref=g.pin(gp))],
        sample_design=dict(n_per_arm=5, decision_rule="TEST-ONLY inconclusive allowed")), "TEST-ONLY planner")
    other_intent = p.repo.get(group.intent).model_copy(update={"id": "TEST-ONLY-other-intent"}); p.repo.put(other_intent)
    foreign_h = hs[0].model_copy(update={"id": "TEST-ONLY-foreign-h", "intent": other_intent.ref}); p.repo.put(foreign_h)
    foreign = competing((foreign_h,), id="TEST-ONLY-foreign-set"); p.repo.put(foreign)
    tp.record(p.repo, form(foreign, id="TEST-ONLY-unrelated", predictions={foreign_h.id: [Z]}), "TEST-ONLY planner")
    assert pilot_cli.main(["--root", str(p.root), "show", "clip"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert [r["artifact"]["revision"] for r in shown["test_plans"]] == [1, 2, 3]
    assert shown["test_plans"][1]["diagnosticity"] == "DECISIVE"
    p.snapshot("TEST-ONLY", "TEST-ONLY-after")
    pins = {Ref(**r["ref"]) for r in p.export_snapshot("TEST-ONLY-after")["records"]}
    assert all(x.ref in pins for x in (first, frozen, later, group, gp, *hs))
    assert Ref(kind="TestPlan", id="TEST-ONLY-unrelated") not in pins
    assert json.dumps(p.export_snapshot("TEST-ONLY-before"), sort_keys=True) == old
    for mode in public: assert serialize_case(*args, mode=mode) == public[mode]
    assert p.repo.all("TechnicalObservation") == p.repo.all("CriterionAssessment") == p.repo.all("TerminalVerdict") == ()


@pytest.mark.parametrize("command,words", [("test-plan", ["sample_design", "author", "private"]),
    ("freeze-test-plan", ["successor", "ID@REV"]), ("verify-test-plan", ["UNKNOWN", "read-only", "NOT_FROZEN"])])
def test_cli_help(command, words, capsys):
    with pytest.raises(SystemExit, match="0"): pilot_cli.parser().parse_args([command, "--help"])
    help_text = capsys.readouterr().out
    assert all(word in help_text for word in words)


def test_digest_set_revision_and_complete_candidate(env, tmp_path):
    repo, group = env; repo.put(tp.TestPlan(**form(group)))
    frozen = tp.freeze(repo, "TEST-ONLY-plan@1"); data = frozen.model_dump(mode="json")
    data["competing_set"]["ref"]["revision"] = 2
    with pytest.raises(ValidationError, match="frozen digest mismatch"): tp.TestPlan.model_validate(data)
    data = frozen.model_dump(mode="json"); del data["schema_version"]
    source = tmp_path / "TEST-ONLY-incomplete.json"; source.write_text(json.dumps(data))
    result = tp.verify(tmp_path, "TEST-ONLY-plan@2", source)
    assert result["status"] == "INTEGRITY_FAILURE" and "differs from retained revision" in result["detail"]


def test_cli_rejection_does_not_admit_or_freeze(env, tmp_path, capsys):
    repo, group = env; data = tp.TestPlan(**form(group)).model_dump(mode="json", exclude={"tool_version", "frozen_at", "frozen_digest"})
    data["predictions"][A] = []
    source = tmp_path / "TEST-ONLY-empty.json"; source.write_text(json.dumps(data))
    assert pilot_cli.main(["--root", str(tmp_path), "--author", "TEST-ONLY planner", "test-plan", "--file", str(source)]) == 2
    error = json.loads(capsys.readouterr().err)
    assert "at least 1 item" in error["error"] and error["quality_verdict"] == "UNKNOWN"
    assert repo.all("TestPlan") == ()


@pytest.mark.parametrize("field", ["tool_version", "schema_version", "canonicalization", "number_profile", "sample_design"])
def test_retained_default_deletion_is_integrity_failure(env, tmp_path, field):
    repo, group = env; repo.put(tp.TestPlan(**form(group)))
    frozen = tp.freeze(repo, "TEST-ONLY-plan@1"); data = frozen.model_dump(mode="json"); del data[field]
    with sqlite3.connect(tmp_path / "pilot.sqlite") as db:
        db.execute("DROP TRIGGER no_update_artifacts")
        db.execute("UPDATE artifacts SET payload=? WHERE kind='TestPlan' AND revision=2", (json.dumps(data),))
    result = tp.verify(tmp_path, "TEST-ONLY-plan@2")
    assert result["status"] == "INTEGRITY_FAILURE" and "frozen digest mismatch" in result["detail"]
    assert "diagnosticity" not in result


@pytest.mark.parametrize("payload", ["[]", "null", "42", '"TEST-ONLY corrupt"', "true"])
@pytest.mark.parametrize("revision", [1, 2])
def test_nonobject_retained_payload_is_readonly_integrity_failure(env, tmp_path, capsys, payload, revision):
    repo, group = env; repo.put(tp.TestPlan(**form(group, id="TEST-ONLY-shape")))
    tp.freeze(repo, "TEST-ONLY-shape@1")
    database = tmp_path / "pilot.sqlite"
    with sqlite3.connect(database) as db:
        db.execute("DROP TRIGGER no_update_artifacts")
        db.execute("UPDATE artifacts SET payload=? WHERE kind='TestPlan' AND id='TEST-ONLY-shape' AND revision=?", (payload, revision))
    before = database.read_bytes()
    expected = dict(status="INTEGRITY_FAILURE", detail="retained TestPlan payload must be a JSON object", quality_verdict="UNKNOWN")
    assert tp.verify(tmp_path, "TEST-ONLY-shape@2") == expected
    assert database.read_bytes() == before
    assert pilot_cli.main(["--root", str(tmp_path), "verify-test-plan", "TEST-ONLY-shape@2"]) == 2
    output = capsys.readouterr()
    assert json.loads(output.out) == expected and output.err == ""
    assert database.read_bytes() == before


@pytest.mark.parametrize("with_revision_hypothesis", [False, True])
def test_prediction_keys_are_hypothesis_ids_through_freeze(env, tmp_path, capsys, with_revision_hypothesis):
    repo, _ = env
    names = ["kind", "id", "revision"] if with_revision_hypothesis else ["kind", "id"]
    hypotheses = [h.model_copy(update={"id": name}) for h, name in zip(repo.all("Hypothesis"), names)]
    for h in hypotheses: repo.put(h)
    group = competing(hypotheses, id="TEST-ONLY-key-set"); repo.put(group)
    predictions = {"kind": [X], "id": [Y]}
    if with_revision_hypothesis: predictions["revision"] = [Z]
    plan = tp.TestPlan(**form(group, id="TEST-ONLY-key-plan", predictions=predictions)); repo.put(plan)
    source = tmp_path / "TEST-ONLY-keys.json"
    data = plan.model_dump(mode="json", exclude={"tool_version", "frozen_at", "frozen_digest"})
    data["id"] = "TEST-ONLY-key-import"; source.write_text(json.dumps(data))
    args = ["--root", str(tmp_path), "--author", "TEST-ONLY planner"]
    assert pilot_cli.main(args + ["test-plan", "--file", str(source)]) == 0
    assert json.loads(capsys.readouterr().out)["predictions"] == predictions
    tp.freeze(repo, "TEST-ONLY-key-plan@1")
    assert pilot_cli.main(args + ["freeze-test-plan", "TEST-ONLY-key-import@1"]) == 0
    assert json.loads(capsys.readouterr().out)["predictions"] == predictions
    reopened = Repository(str(repo.engine.url))
    try:
        for name in ("TEST-ONLY-key-plan", "TEST-ONLY-key-import"):
            assert reopened.get(Ref(kind="TestPlan", id=name, revision=2)).model_dump(mode="json")["predictions"] == predictions
            result = tp.verify(tmp_path, name + "@2")
            assert result["status"] == "VERIFIED" and result["diagnosticity"] == "DECISIVE"
            assert result["compatible"][X] == ["kind"] and result["compatible"][Y] == ["id"]
            assert result["compatible"][Z] == (["revision"] if with_revision_hypothesis else [])
    finally: reopened.close()
