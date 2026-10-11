"""TEST-ONLY generated-media intent flip and private human import workflow."""
import json
import pytest
from pydantic import ValidationError
from eval_lab import assessments as a, generation as g, pilot_cli
from eval_lab.pilot import PilotWorkspace
from eval_lab.seals import seal_intent
from eval_lab.fixtures import seed
from eval_lab.presentation import serialize_case
from test_assessments import declared, evidence, observation, assessment, pin
from test_generation import PLAN
from test_media import media_tools, codec_videos


@pytest.fixture
def flip(tmp_path, codec_videos):
    root = tmp_path/"TEST-ONLY-workspace"; p = PilotWorkspace(root)
    intents = (declared("TEST-ONLY-slide"), declared("TEST-ONLY-physical", expected=False,
        objective="TEST-ONLY physical realism", criteria=[dict(id="TEST-ONLY-motion",
            dimension="motion_plausibility", priority="MUST", acceptance="TEST-ONLY planted feet",
            rejection="TEST-ONLY sliding feet", tolerance="TEST-ONLY no visible sliding")]))
    for i in intents:
        source = tmp_path/(i.id+".json"); source.write_text(i.model_dump_json()); seal_intent(root, source)
    plan = g.record_plan(p.repo, PLAN | {"intent_revision_ids": ["TEST-ONLY-slide@1", "TEST-ONLY-physical@1"]})
    p.init("TEST-ONLY-dataset", "TEST-ONLY owner")
    clip = p.register("TEST-ONLY-dataset", "TEST-ONLY-clip", codec_videos["cfr"], "TEST-ONLY operator",
        "TEST-ONLY generated pattern", plan=plan.id, intent="TEST-ONLY-slide@1")
    first = g.binding_history(p.repo, clip)[0]
    second = g.bind_intent(p.repo, clip, pin(intents[1]))
    assert (first.provenance, second.provenance) == ("SEALED", "SEALED")
    m = p.repo.get(clip.media); ev = evidence(p.repo, m); obs = observation(m, ev); p.repo.put(obs)
    left = assessment(m, intents[0], first, obs, id="TEST-ONLY-expected")
    right = assessment(m, intents[1], second, obs, id="TEST-ONLY-violation", status="VIOLATED",
        rationale="TEST-ONLY private slide violates physical realism")
    yield p, clip, obs, left, right
    p.close()


def test_intent_flip_private_export_freezes_exact_history(flip):
    p, clip, obs, left, right = flip
    for item in (left, right): p.repo.put(item)
    snap = p.snapshot("TEST-ONLY-dataset", "TEST-ONLY-before")
    before = p.export_snapshot(snap.id)
    records = {r["artifact"]["id"]: r["artifact"] for r in before["records"]}
    assert (records["TEST-ONLY-expected"]["status"], records["TEST-ONLY-violation"]["status"]) == ("SATISFIED", "VIOLATED")
    assert records["TEST-ONLY-expected"]["intent"]["ref"] == {"kind": "IntentSpecV2", "id": "TEST-ONLY-slide", "revision": 1}
    assert records["TEST-ONLY-violation"]["intent"]["ref"] == {"kind": "IntentSpecV2", "id": "TEST-ONLY-physical", "revision": 1}
    assert records["TEST-ONLY-expected"]["binding"]["ref"]["revision"] == 1
    assert records["TEST-ONLY-violation"]["binding"]["ref"]["revision"] == 2
    assert records["TEST-ONLY-expected"]["observations"] == records["TEST-ONLY-violation"]["observations"]
    cited = records["TEST-ONLY-expected"]["observations"]
    assert len(cited) == 1 and cited[0]["ref"] == {"kind": "TechnicalObservation", "id": "TEST-ONLY-observation", "revision": 1}
    assert cited[0]["sha256"] == next(r["sha256"] for r in before["records"] if r["ref"]["kind"] == "TechnicalObservation")
    assert records["TEST-ONLY-observation"]["span"] == [.2, .8]
    assert records["TEST-ONLY-observation"]["viewing_profile"] == "STUDIO"
    assert {"MediaAsset", "MediaIngestion", "Evidence", "GenerationPlan", "IntentBinding", "BindingContext", "SealRecord", "TechnicalObservation", "CriterionAssessment"} <= {r["ref"]["kind"] for r in before["records"]}
    later_obs = obs.model_copy(update={"revision": 2, "predecessor": pin(obs), "revision_reason": "TEST-ONLY more evidence", "deviation": "NONE"}); p.repo.put(later_obs)
    original = p.repo.get(left.intent.ref)
    p.repo.put(declared(original.id, expected=False, revision=2, predecessor=pin(original)))
    correction = left.model_copy(update={"revision": 2, "predecessor": pin(left), "revision_reason": "TEST-ONLY doubt", "status": "UNKNOWN"}); p.repo.put(correction)
    p.snapshot("TEST-ONLY-dataset", "TEST-ONLY-after")
    assert p.export_snapshot(snap.id) == before
    reopened = PilotWorkspace(p.root)
    assert reopened.export_snapshot(snap.id) == before
    assert reopened.repo.get(left.ref).status == "SATISFIED" and reopened.repo.get(right.ref).status == "VIOLATED"
    after = reopened.export_snapshot("TEST-ONLY-after")
    assert [(r["ref"]["revision"], r["artifact"]["status"]) for r in after["records"] if r["ref"]["id"] == "TEST-ONLY-expected"] == [(1, "SATISFIED"), (2, "UNKNOWN")]
    reopened.close()


@pytest.mark.parametrize("support", ["empty", "unknown", "mixed"])
def test_private_discovery_exact_media_unknown_and_unavailable(flip, codec_videos, support):
    p, clip, obs, left, right = flip
    gap = obs.model_copy(update={"id": "TEST-ONLY-gap", "deviation": "UNKNOWN", "evidence": ()}); p.repo.put(gap)
    pins = {"empty": (), "unknown": (pin(gap),), "mixed": (pin(obs), pin(gap))}[support]
    unknown = left.model_copy(update={"status": "UNKNOWN", "observations": pins, "rationale": "TEST-ONLY coverage gap"}); p.repo.put(unknown)
    retained = left.model_copy(update={"id": "TEST-ONLY-retained"}); p.repo.put(retained)
    p.init("TEST-ONLY-other", "TEST-ONLY owner")
    other = p.register("TEST-ONLY-other", "TEST-ONLY-other-clip", codec_videos["different"], "TEST-ONLY other", "TEST-ONLY different pattern")
    m = p.repo.get(other.media); ev = evidence(p.repo, m, "TEST-ONLY-foreign-evidence")
    p.repo.put(observation(m, ev, id="TEST-ONLY-excluded"))
    revised_media = p.repo.get(clip.media).model_copy(update={"revision": 2}); p.repo.put(revised_media)
    ev2 = evidence(p.repo, revised_media, "TEST-ONLY-revised-evidence")
    p.repo.put(observation(revised_media, ev2, id="TEST-ONLY-revision-excluded"))
    p.snapshot("TEST-ONLY-dataset", "TEST-ONLY-unknown")
    exported = p.export_snapshot("TEST-ONLY-unknown")
    assert {r["artifact"]["status"] for r in exported["records"] if r["ref"]["kind"] == "CriterionAssessment"} == {"UNKNOWN", "SATISFIED"}
    assert not {"TEST-ONLY-excluded", "TEST-ONLY-revision-excluded"} & {r["ref"]["id"] for r in exported["records"]}
    p.verify_clip(clip).unlink()
    assert p.status("TEST-ONLY-dataset")["clips"][0]["media_availability"] == "UNKNOWN"
    assert p.repo.get(unknown.ref).status == "UNKNOWN" and p.export_snapshot("TEST-ONLY-unknown") == exported
    assert p.repo.get(retained.ref).status == "SATISFIED"


def test_human_cli_import_show_schema_help_and_no_partial_write(flip, tmp_path, capsys):
    p, clip, obs, left, right = flip
    for cmd, item in (("technical-observation", obs.model_copy(update={"id": "TEST-ONLY-cli-observation"})), ("criterion-assessment", left)):
        source = tmp_path/(cmd+".json")
        raw = item.model_dump(mode="json", exclude={"tool_version"}); source.write_text(json.dumps(raw))
        argv = ["--root", str(p.root), "--author", item.author, cmd, clip.id, "--file", str(source)]
        assert pilot_cli.main(argv) == 0
        out = json.loads(capsys.readouterr().out); assert out["tool_version"] == "0.1.0" and out["author"] == item.author
        count = len(p.repo.all(item.ref.kind))
        source.write_text(json.dumps(raw | {"id": "TEST-ONLY-cli-invalid", "intent_extra": "TEST-ONLY forbidden"}))
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            a.record(p, clip.id, item.author, cmd, json.loads(source.read_text()))
        assert pilot_cli.main(argv) == 2
        assert "Extra inputs are not permitted" in json.loads(capsys.readouterr().err)["error"]
        assert len(p.repo.all(item.ref.kind)) == count
    assert pilot_cli.main(["--root", str(p.root), "show", clip.id]) == 0
    out = json.loads(capsys.readouterr().out)
    assert {x["id"] for x in out["technical_observations"]} == {"TEST-ONLY-observation", "TEST-ONLY-cli-observation"}
    assert out["criterion_assessments"][0]["status"] == "SATISFIED"
    assert pilot_cli.main(["schema"]) == 0
    assert {"TechnicalObservation", "CriterionAssessment"} <= json.loads(capsys.readouterr().out)["record_schemas"].keys()
    for cmd in ("technical-observation", "criterion-assessment"):
        with pytest.raises(SystemExit, match="0"): pilot_cli.parser().parse_args([cmd, "--help"])
        assert "exact" in capsys.readouterr().out


def test_import_media_author_and_version_guards(flip):
    p, clip, obs, left, right = flip
    raw = left.model_dump(mode="json", exclude={"tool_version"})
    for changes, author, message in [({}, "TEST-ONLY imposter", "author declaration mismatch"),
        ({"media": {"ref": {"kind": "MediaAsset", "id": "TEST-ONLY-foreign", "revision": 1}, "sha256": "f"*64}}, left.author, "record media differs from clip"),
        ({"tool_version": "TEST-ONLY fake version"}, left.author, "tool_version is application recorded")]:
        with pytest.raises(ValueError, match=message):
            a.record(p, clip.id, author, "criterion-assessment", raw | {"id": "TEST-ONLY-import-invalid"} | changes)
    assert p.repo.all("CriterionAssessment") == ()


@pytest.mark.parametrize("raw", [None, 8, True, "TEST-ONLY", []])
def test_import_requires_json_object(flip, raw):
    p, clip, obs, left, right = flip
    with pytest.raises(ValueError, match="record form must be a JSON object"):
        a.record(p, clip.id, left.author, "criterion-assessment", raw)
    assert p.repo.all("CriterionAssessment") == ()


def test_public_embed_and_v1_digests_unchanged(flip):
    p, clip, obs, left, right = flip
    d = seed(p.repo); args = (p.repo, d["case"].ref, d["round"].ref, d["raters"][0].ref)
    before = {mode: serialize_case(*args, mode=mode) for mode in ("public", "embed")}
    digest = d["intent"].digest
    p.repo.put(left); p.repo.put(right)
    for mode in ("public", "embed"):
        out = serialize_case(*args, mode=mode)
        assert set(out) == {"schema_version", "mode", "slug", "title", "prompt", "stage", "fixture_notice", "outputs", "choices"}
        assert out == before[mode]
        assert "TEST-ONLY private" not in json.dumps(out)
        assert "CriterionAssessment" not in json.dumps(out) and "TechnicalObservation" not in json.dumps(out)
    assert p.repo.get(d["intent"].ref).digest == digest
