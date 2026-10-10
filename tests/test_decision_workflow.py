"""TEST-ONLY private persistence, exact input closure and replay."""
import json
import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from eval_lab import decisions as d, pilot_cli
from eval_lab.domain import Hypothesis
from eval_lab.fixtures import seed
from eval_lab.presentation import serialize_case
from eval_lab.pilot import PilotWorkspace
from eval_lab.persistence import Repository
from test_decisions import env, fixture, policy, verdict, pin, T
from test_assessment_workflow import flip
from test_media import media_tools, codec_videos


@pytest.mark.parametrize("count,status,relevant,rule", [(2, "unresolved", True, "multiple-causes"),
    (1, "unresolved", True, "violation"), (0, "unresolved", True, "violation"),
    (2, "supported", True, "violation"), (2, "unresolved", False, "violation")])
def test_hypotheses_remain_unresolved(tmp_path, monkeypatch, count, status, relevant, rule):
    repo = Repository("sqlite:///"+str(tmp_path/"TEST-ONLY-hypotheses.sqlite"))
    form, obs, a, p = fixture(repo, monkeypatch, status="VIOLATED", product=True)
    old = repo.get(form["clip"].ref); legacy = seed(repo)["intent"]
    clip = old.model_copy(update={"revision": 2, "intent": legacy.ref}); repo.put(clip)
    hypotheses = [Hypothesis(id=f"TEST-ONLY-cause-{n}", created_at=T, intent=legacy.ref,
        observed_problem="TEST-ONLY morph", proposed_cause=f"TEST-ONLY cause {n}", confidence=(.2, .7)[n],
        supporting_evidence=tuple(x.ref for x in obs.evidence), evidence_required=("TEST-ONLY rerender",),
        discriminating_test="TEST-ONLY compare", predicted_observation="TEST-ONLY stability",
        falsifying_observation="TEST-ONLY drift", status=status) for n in range(count)]
    for h in hypotheses: repo.put(h)
    form |= {"clip": pin(clip), "hypotheses": tuple(dict(hypothesis=pin(h), criterion_ids=("TEST-ONLY-geometry",) if relevant else (),
        rationale=f"TEST-ONLY relevance {n}") for n, h in enumerate(hypotheses))}
    before = [(h.canonical(), h.digest) for h in hypotheses]
    result = verdict(repo, form); repo.put(result)
    assert (result.decision.action, result.decision.rule_id) == ("REGENERATE", rule)
    reopened = Repository(str(repo.engine.url))
    assert [(reopened.get(h.ref).canonical(), reopened.get(h.ref).digest) for h in hypotheses] == before
    assert [reopened.get(h.ref).confidence for h in hypotheses] == [0.2, 0.7][:count]
    assert d.preview(reopened, form)["decision"] == result.decision.model_dump(mode="json")
    if count == 2:
        revised = hypotheses[0].model_copy(update={"revision": 2, "status": "contradicted", "confidence": .9}); repo.put(revised)
        assert d.preview(reopened, form)["decision"] == result.decision.model_dump(mode="json")
        with pytest.raises(ValidationError, match="duplicate hypothesis identity"):
            verdict(repo, form | {"id": "TEST-ONLY-duplicate-revisions", "hypotheses": (form["hypotheses"][0], form["hypotheses"][0] | {"hypothesis": pin(revised)})})
        for alteration, message in [(dict(hypotheses=(form["hypotheses"][0],)*2), "duplicate hypothesis identity"),
            (dict(hypotheses=(form["hypotheses"][0] | {"criterion_ids": ("TEST-ONLY-absent",)},)), "unknown relevance criterion"),
            (dict(clip=pin(old)), "hypothesis legacy intent mismatch")]:
            with pytest.raises(ValueError, match=message): verdict(repo, form | {"id": "TEST-ONLY-invalid-relevance"} | alteration)
    reopened.close(); repo.close()


@pytest.mark.parametrize("case,message,error", [("scope", "policy scope mismatch", ValueError),
    ("duplicate", "one assessment per criterion", ValueError), ("coverage", "assessment observations outside retained inputs", ValueError),
    ("digest", "pinned artifact digest mismatch", ValueError), ("revision", "explicit revision", ValidationError),
    ("kind", "pin must reference IntentSpecV2", ValidationError), ("extra", "Extra inputs", ValidationError),
    ("context", "assessment context mismatch", ValueError), ("trace", "derived verdict mismatch", ValueError),
    ("summary", "derived verdict mismatch", ValueError)])
def test_exact_context_and_trace_admission(env, case, message, error):
    repo, (form, obs, a, p) = env
    result = verdict(repo, form); candidate = result.model_copy(update={"id": "TEST-ONLY-invalid-input"})
    if case == "scope":
        foreign = policy(p.scope.model_copy(update={"audience": "TEST-ONLY other audience"}), id="TEST-ONLY-other-scope"); repo.put(foreign)
        candidate = candidate.model_copy(update={"policy": pin(foreign)})
    if case == "duplicate": candidate = candidate.model_copy(update={"assessments": (pin(a), pin(a))})
    if case == "coverage": candidate = candidate.model_copy(update={"observations": ()})
    if case == "digest": candidate = candidate.model_copy(update={"intent": pin(repo.get(form["intent"].ref)).model_copy(update={"sha256": "f"*64})})
    if case == "kind": candidate = candidate.model_copy(update={"intent": pin(obs)})
    if case == "extra": candidate = candidate.model_copy(update={"policy": pin(p).model_copy(update={"hidden": "TEST-ONLY"})})
    if case == "context":
        from test_assessments import declared
        i = declared("TEST-ONLY-other-intent"); repo.put(i)
        candidate = candidate.model_copy(update={"intent": pin(i)})
    if case == "trace": candidate = candidate.model_copy(update={"decision": result.decision.model_copy(update={"rule_id": "default"})})
    if case == "summary": candidate = candidate.model_copy(update={"technical_integrity": {}})
    with pytest.raises(error, match=message):
        if case == "revision":
            raw = candidate.model_dump(mode="json"); del raw["intent"]["ref"]["revision"]
            repo.put(d.TerminalVerdict.model_validate(raw))
        else: repo.put(candidate)


@pytest.mark.parametrize("target", ["policy", "verdict"])
def test_history_and_override_preserve_policy_result(env, target):
    repo, (form, obs, a, p) = env
    result = verdict(repo, form | {"override": dict(action="REPAIR", reason="TEST-ONLY schedule", author="TEST-ONLY producer")})
    assert result.decision.action == "SHIP" and result.override.action == "REPAIR"
    assert result.decision.inputs_sha256 == verdict(repo, form).decision.inputs_sha256
    item = p if target == "policy" else result; repo.put(item)
    changes = dict(revision=2, predecessor=pin(item), revision_reason="TEST-ONLY correction")
    if target == "policy": changes["version"] = 2
    for change, error, message in [({"author": "TEST-ONLY conflict"}, ValueError, "immutable revision conflict"),
        (changes | {"predecessor": None}, ValidationError, "immediate same-kind"),
        (changes | {"revision_reason": None}, ValidationError, "revision reason required"),
        (changes | {"predecessor": pin(item).model_copy(update={"sha256": "e"*64})}, ValueError, "digest mismatch")]:
        with pytest.raises(error, match=message): repo.put(item.model_copy(update=change))
    later = item.model_copy(update=changes); repo.put(later)
    assert repo.get(item.ref).canonical() == item.canonical()
    assert repo.get(later.ref).predecessor == pin(item)
    for sql in ("UPDATE artifacts SET payload='{}' WHERE kind=:kind", "DELETE FROM artifacts WHERE kind=:kind"):
        with pytest.raises(IntegrityError, match="append-only"):
            with repo.engine.begin() as c: c.exec_driver_sql(sql, {"kind": item.ref.kind})


def test_worst_case_permutation_digest_and_extra_observation(env):
    repo, (form, obs, a, p) = env
    lesser = obs.model_copy(update={"id": "TEST-ONLY-lesser", "deviation": "MINOR"}); repo.put(lesser)
    a2 = a.model_copy(update={"id": "TEST-ONLY-lesser-assessment", "observations": (pin(lesser),)}); repo.put(a2)
    both = form | {"assessments": (pin(a2),), "observations": (pin(lesser), pin(obs))}
    first = verdict(repo, both)
    assert first.technical_integrity["temporal_geometry"].worst == "CATASTROPHIC"
    assert d.preview(repo, both | {"observations": (pin(obs), pin(lesser))}) == d.preview(repo, both)
    assert first.decision.inputs_sha256 != verdict(repo, both | {"observations": (pin(lesser),)}).decision.inputs_sha256
    assert first.decision.inputs_sha256 != verdict(repo, both | {"intent_fulfillment": "REVISE"}).decision.inputs_sha256
    assert first.decision.inputs_sha256 != verdict(repo, both | {"salvage_guess": "EXPENSIVE_POST_FIX"}).decision.inputs_sha256
    pol2 = p.model_copy(update={"revision": 2, "version": 2, "predecessor": pin(p), "revision_reason": "TEST-ONLY policy revision"}); repo.put(pol2)
    assert first.decision.inputs_sha256 != verdict(repo, both | {"policy": pin(pol2)}).decision.inputs_sha256


def test_private_cli_snapshot_and_public_isolation(flip, tmp_path, capsys):
    p, clip, obs, left, right = flip
    p.repo.put(left); policy_item = policy(p.repo.get(left.intent.ref).use_context); p.repo.put(policy_item)
    form = dict(id="TEST-ONLY-private-verdict", created_at=T, author="TEST-ONLY verdict author", clip=pin(clip),
        media=left.media, intent=left.intent, binding=left.binding, policy=pin(policy_item), assessments=(pin(left),),
        observations=(pin(obs),), hypotheses=(), intent_fulfillment="ACCEPT", salvage_guess="POST_FIXABLE")
    item = verdict(p.repo, form)
    legacy = seed(p.repo); args = (p.repo, legacy["case"].ref, legacy["round"].ref, legacy["raters"][0].ref)
    before = {mode: serialize_case(*args, mode=mode) for mode in ("public", "embed")}
    for command, record in (("decision-policy", policy_item.model_copy(update={"id": "TEST-ONLY-cli-policy"})), ("terminal-verdict", item)):
        source = tmp_path/(command+".json"); source.write_text(record.model_dump_json(exclude={"tool_version"}))
        argv = ["--root", str(p.root), "--author", record.author, command]
        if command == "terminal-verdict": argv.append(clip.id)
        assert pilot_cli.main(argv+["--file", str(source)]) == 0; capsys.readouterr()
    source = tmp_path/"preview.json"; source.write_text(d.VerdictInput(**form).model_dump_json(exclude={"tool_version"}))
    db_before = (p.root/"pilot.sqlite").read_bytes()
    assert pilot_cli.main(["--root", str(p.root), "decision-preview", clip.id, "--file", str(source)]) == 0
    assert json.loads(capsys.readouterr().out)["decision"]["action"] == "SHIP"
    assert (p.root/"pilot.sqlite").read_bytes() == db_before
    # Discovery must also find direct repository admissions, including history.
    direct = item.model_copy(update={"id": "TEST-ONLY-direct"}); p.repo.put(direct)
    other_clip = clip.model_copy(update={"id": "TEST-ONLY-unrelated-clip"}); p.repo.put(other_clip)
    unrelated = verdict(p.repo, form | {"id": "TEST-ONLY-unrelated-verdict", "clip": pin(other_clip)}); p.repo.put(unrelated)
    assert unrelated.decision.inputs_sha256 != item.decision.inputs_sha256
    snap = p.snapshot("TEST-ONLY-dataset", "TEST-ONLY-decisions-before"); frozen = p.export_snapshot(snap.id)
    kinds = {r["ref"]["kind"] for r in frozen["records"]}
    assert {"TerminalVerdict", "DecisionPolicy", "CriterionAssessment", "TechnicalObservation", "IntentSpecV2", "IntentBinding"} <= kinds
    assert "TEST-ONLY-cli-policy" not in {r["ref"]["id"] for r in frozen["records"]}
    assert "TEST-ONLY-unrelated-verdict" not in {r["ref"]["id"] for r in frozen["records"]}
    p.repo.put(policy_item.model_copy(update={"revision": 2, "version": 2, "predecessor": pin(policy_item), "revision_reason": "TEST-ONLY new policy"}))
    p.repo.put(left.model_copy(update={"revision": 2, "predecessor": pin(left), "revision_reason": "TEST-ONLY doubt", "status": "UNKNOWN"}))
    p.repo.put(direct.model_copy(update={"revision": 2, "predecessor": pin(direct), "revision_reason": "TEST-ONLY override",
        "override": dict(action="HOLD", author="TEST-ONLY producer", reason="TEST-ONLY scheduling")}))
    reopened = PilotWorkspace(p.root)
    assert reopened.export_snapshot(snap.id) == frozen
    assert d.preview(reopened.repo, form)["decision"] == item.decision.model_dump(mode="json")
    after = reopened.export_snapshot(reopened.snapshot("TEST-ONLY-dataset", "TEST-ONLY-decisions-after").id)
    assert [r["ref"]["revision"] for r in after["records"] if r["ref"]["id"] == "TEST-ONLY-direct"] == [1, 2]
    reopened.close()
    assert pilot_cli.main(["--root", str(p.root), "show", clip.id]) == 0
    assert {x["id"] for x in json.loads(capsys.readouterr().out)["terminal_verdicts"]} == {"TEST-ONLY-private-verdict", "TEST-ONLY-direct"}
    assert pilot_cli.main(["schema"]) == 0
    assert {"DecisionPolicy", "TerminalVerdict"} <= json.loads(capsys.readouterr().out)["record_schemas"].keys()
    for command in ("decision-policy", "terminal-verdict", "decision-preview"):
        with pytest.raises(SystemExit, match="0"): pilot_cli.parser().parse_args([command, "--help"])
        assert "exact" in capsys.readouterr().out
    for mode in ("public", "embed"):
        assert serialize_case(*args, mode=mode) == before[mode]
        assert "TEST-ONLY-private-verdict" not in json.dumps(before[mode])


def test_revision_preview_and_context_immutability(env):
    repo, (form, obs, a, p) = env
    item = verdict(repo, form); repo.put(item)
    revised = form | dict(revision=2, predecessor=pin(item), revision_reason="TEST-ONLY correction")
    assert verdict(repo, revised).decision.inputs_sha256 == item.decision.inputs_sha256
    for changes, message in [({"predecessor": None}, "immediate same-kind"),
        ({"revision": 3}, "immediate same-kind"), ({"revision_reason": None}, "revision reason required")]:
        with pytest.raises(ValidationError, match=message): d.preview(repo, revised | changes)
    clip = repo.get(form["clip"].ref).model_copy(update={"revision": 2}); repo.put(clip)
    with pytest.raises(ValueError, match="verdict context is immutable"):
        repo.put(item.model_copy(update=revised | {"clip": pin(clip)}))


@pytest.mark.parametrize("case,message", [("author", "author declaration mismatch"), ("version", "tool_version is application recorded"),
    ("clip", "verdict clip differs"), ("form", "record form must be a JSON object")])
def test_import_guards(flip, case, message):
    p, clip, obs, left, right = flip
    p.repo.put(left); pol = policy(p.repo.get(left.intent.ref).use_context); p.repo.put(pol)
    form = dict(id="TEST-ONLY-import-guards", created_at=T, author="TEST-ONLY importer", media=left.media, clip=pin(clip),
        intent=left.intent, binding=left.binding, policy=pin(pol), assessments=(pin(left),), observations=(pin(obs),),
        hypotheses=(), intent_fulfillment="ACCEPT", salvage_guess="UNKNOWN")
    raw = verdict(p.repo, form).model_dump(mode="json", exclude={"tool_version"})
    if case == "version": raw["tool_version"] = "TEST-ONLY spoof"
    if case == "form": raw = []
    with pytest.raises(ValueError, match=message):
        d.record(p, "TEST-ONLY wrong author" if case == "author" else form["author"], "terminal-verdict", raw,
            "TEST-ONLY-wrong-clip" if case == "clip" else clip.id)
    assert p.repo.all("TerminalVerdict") == ()


def test_missing_context_and_foreign_media_are_integrity_errors(env):
    from test_intent_v2 import anchors
    from test_assessments import evidence, observation
    repo, (form, obs, a, p) = env
    other, _ = anchors(repo, "TEST-ONLY-foreign", "b"*64)
    foreign = observation(other, evidence(repo, other, "TEST-ONLY-foreign-evidence"), id="TEST-ONLY-foreign-observation"); repo.put(foreign)
    with pytest.raises(ValueError, match="observation media mismatch"):
        verdict(repo, form | {"observations": (pin(obs), pin(foreign))})
    with pytest.raises(ValueError, match="clip media mismatch"):
        verdict(repo, form | {"media": pin(other)})
    with pytest.raises(ValidationError, match="duplicate observation pin"):
        verdict(repo, form | {"observations": (pin(obs), pin(obs))})
    b = repo.get(form["binding"].ref); later = b.model_copy(update={"revision": 2, "predecessor": pin(b)}); repo.put(later)
    with pytest.raises(ValueError, match="binding requires retained context"):
        verdict(repo, form | {"binding": pin(later), "assessments": ()})


def test_policy_copied_nested_extra_not_discarded(env):
    repo, (_, _, _, p) = env
    bad = p.model_copy(update={"id": "TEST-ONLY-policy-extra", "scope": p.scope.model_copy(update={"secret_input": "TEST-ONLY"})})
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        d.DecisionPolicy.model_validate(bad)


@pytest.mark.parametrize("entry", ["preview", "admission"])
def test_selected_assessment_requires_exact_context(env, entry):
    from eval_lab import generation as g
    repo, (form, obs, a, _) = env
    original = verdict(repo, form)
    foreign_intent = repo.get(form["intent"].ref).model_copy(update={"id": "TEST-ONLY-foreign-intent"})
    repo.put(foreign_intent)
    foreign_binding = g.bind_intent(repo, repo.get(form["clip"].ref), pin(foreign_intent))
    foreign = a.model_copy(update={"id": "TEST-ONLY-foreign-assessment", "intent": pin(foreign_intent),
        "binding": pin(foreign_binding), "status": "VIOLATED"})
    repo.put(foreign)
    assert foreign.criterion_id == "TEST-ONLY-geometry" and foreign.observations == (pin(obs),)
    changes = dict(id="TEST-ONLY-foreign-selection-"+entry, assessments=(pin(foreign),))
    # The verdict's own clip/media/intent/binding remain valid. Anchor the message
    # so neither the earlier binding check nor a later trace check can satisfy it.
    with pytest.raises(ValueError, match="^assessment context mismatch$"):
        if entry == "preview": verdict(repo, form | changes)
        else: repo.put(original.model_copy(update=changes))
    assert repo.all("TerminalVerdict") == ()


def test_derived_envelope_literal_oracle(monkeypatch):
    from eval_lab import generation as g
    from eval_lab.domain import IntentSpec
    from eval_lab.pilot_domain import PilotClip
    from test_assessments import declared, evidence, observation, assessment
    from test_intent_v2 import anchors, binding
    repo = Repository()
    m, registration = anchors(repo, "TEST-ONLY-envelope-media")
    i = declared("TEST-ONLY-envelope-intent"); repo.put(i)
    b = binding(i, m, registration); repo.put(b)
    repo.put(g.BindingContext(id="TEST-ONLY-envelope-context", created_at=T, binding=pin(b)))
    legacy = IntentSpec(id="TEST-ONLY-legacy", created_at=T, owner="TEST-ONLY owner", objective="TEST-ONLY objective",
        audience="TEST-ONLY audience", context="TEST-ONLY context", authority="human_declared", approved_by="TEST-ONLY approver", criteria=[dict(
        dimension="motion_plausibility", rationale="TEST-ONLY relevance", acceptance="TEST-ONLY stability")]); repo.put(legacy)
    clip = PilotClip(id="TEST-ONLY-envelope-clip", created_at=T, media=m.ref, ingestion=registration.ref,
        intent=legacy.ref, selected_by="TEST-ONLY selector", label="TEST-ONLY label"); repo.put(clip)
    ev = evidence(repo, m); obs = observation(m, ev); repo.put(obs)
    a = assessment(m, i, b, obs, status="VIOLATED"); repo.put(a)
    p = policy(i.use_context, rules=[dict(id="TEST-ONLY-default", action="HOLD")]); repo.put(p)
    h = Hypothesis(id="TEST-ONLY-envelope-cause", created_at=T, intent=legacy.ref, observed_problem="TEST-ONLY slide",
        proposed_cause="TEST-ONLY contact", confidence=.37, supporting_evidence=(ev.ref,), evidence_required=("TEST-ONLY rerender",),
        discriminating_test="TEST-ONLY compare", predicted_observation="TEST-ONLY stable", falsifying_observation="TEST-ONLY drift",
        status="unresolved"); repo.put(h)
    relevance = dict(hypothesis=pin(h), criterion_ids=("TEST-ONLY-motion",), rationale="TEST-ONLY causal link")
    form = dict(id="TEST-ONLY-envelope-verdict", created_at=T, author="TEST-ONLY digest author", clip=pin(clip), media=pin(m),
        intent=pin(i), binding=pin(b), policy=pin(p), assessments=(pin(a),), observations=(pin(obs),), hypotheses=(relevance,),
        intent_fulfillment="REJECT", salvage_guess="EXPENSIVE_POST_FIX")
    captured, digest = [], d.input_digest
    def capture(envelope):
        captured.append(d.canonicalize(envelope))
        return digest(envelope)
    monkeypatch.setattr(d, "input_digest", capture)
    result = verdict(repo, form); repo.put(result)
    # Authored envelope and independently hashed source JSON; never sampled from derive.
    expected = (b'{"author":"TEST-ONLY digest author","inputs":{"criteria":[["MUST","VIOLATED"]],"integrity":{'
        b'"aesthetic_quality":{"unknown":true,"worst":"UNKNOWN"},"artifacting":{"unknown":true,"worst":"UNKNOWN"},'
        b'"camera_language":{"unknown":true,"worst":"UNKNOWN"},"composition":{"unknown":true,"worst":"UNKNOWN"},'
        b'"editability":{"unknown":true,"worst":"UNKNOWN"},"lighting_continuity":{"unknown":true,"worst":"UNKNOWN"},'
        b'"motion_plausibility":{"unknown":false,"worst":"MATERIAL"},"occlusion_consistency":{"unknown":true,"worst":"UNKNOWN"},'
        b'"prompt_adherence":{"unknown":true,"worst":"UNKNOWN"},"semantic_consistency":{"unknown":true,"worst":"UNKNOWN"},'
        b'"subject_consistency":{"unknown":true,"worst":"UNKNOWN"},"temporal_consistency":{"unknown":true,"worst":"UNKNOWN"},'
        b'"temporal_geometry":{"unknown":true,"worst":"UNKNOWN"}},"provenance":"RECONSTRUCTED","salvage_guess":"EXPENSIVE_POST_FIX","unknown_must":false,"unresolved":1},'
        b'"intent_fulfillment":"REJECT","policy_id":"TEST-ONLY-policy","policy_version":1,"relevance":[{"criterion_ids":["TEST-ONLY-motion"],'
        b'"hypothesis":{"ref":{"id":"TEST-ONLY-envelope-cause","kind":"Hypothesis","revision":1},"sha256":"3f6ca8959138ad474c6352a2d8a10dd915f43702406b1865c51369b3373b0fd5"},"rationale":"TEST-ONLY causal link"}],"schema_version":1,"sources":{'
        b'"assessments":[{"ref":{"id":"TEST-ONLY-assessment","kind":"CriterionAssessment","revision":1},"sha256":"bbac7ba86c0cbcb97d7a9a9c42466264e72942b6bc4fd5567e7c5c3585799835"}],'
        b'"binding":{"ref":{"id":"TEST-ONLY-binding","kind":"IntentBinding","revision":1},"sha256":"ba34fcd1d5bd81342dd6cc383543684e442a079cf87f63edf44c38b4d77a1b1b"},'
        b'"clip":{"ref":{"id":"TEST-ONLY-envelope-clip","kind":"PilotClip","revision":1},"sha256":"da56f3a1d0ed6ff855f8fd0467e1e618ccb0b28da53b828799371d45d60ced7e"},'
        b'"intent":{"ref":{"id":"TEST-ONLY-envelope-intent","kind":"IntentSpecV2","revision":1},"sha256":"1da1ab4e23116b531daa0b8b2891c277dcece5d65abc8e2fb0ee3d5f2c1c24bd"},'
        b'"media":{"ref":{"id":"TEST-ONLY-envelope-media","kind":"MediaAsset","revision":1},"sha256":"6e78fc4513732c61cbf29048434238ee9212738b68512eb8baaf7cf3a813af83"},'
        b'"observations":[{"ref":{"id":"TEST-ONLY-observation","kind":"TechnicalObservation","revision":1},"sha256":"e5a65ce69725b871bcb1804800b5f1bd2fedbc552a0ed1c6169168a4c0742c3d"}],'
        b'"policy":{"ref":{"id":"TEST-ONLY-policy","kind":"DecisionPolicy","revision":1},"sha256":"2b0106f593f424703005ac720e49ff095ed3c4809811b7881d9c383cea9c2e7e"}}}')
    assert captured == [expected, expected]
    assert result.decision.inputs_sha256 == "3915f975c0b2a490f0738cb435cb988f7ed7aa3ca2c0ebf93cf34915e9b2afac"
    revised_h = h.model_copy(update={"revision": 2, "proposed_cause": "TEST-ONLY alternate contact"}); repo.put(revised_h)
    revised_a = a.model_copy(update={"revision": 2, "predecessor": pin(a), "revision_reason": "TEST-ONLY clarification",
        "rationale": "TEST-ONLY retained violation"}); repo.put(revised_a)
    for changes in ({"author": "TEST-ONLY second author"}, {"intent_fulfillment": "REVISE"},
        {"hypotheses": (relevance | {"rationale": "TEST-ONLY revised causal link"},)},
        {"hypotheses": (relevance | {"hypothesis": pin(revised_h)},)}, {"assessments": (pin(revised_a),)}):
        changed = verdict(repo, form | changes)
        assert (changed.decision.action, changed.decision.rule_id) == ("HOLD", "TEST-ONLY-default")
        assert changed.decision.inputs_sha256 != result.decision.inputs_sha256
    assert (result.decision.action, result.decision.rule_id) == ("HOLD", "TEST-ONLY-default")
    repo.close()
