"""TEST-ONLY generated media, ordinary private snapshots, independent payload oracles."""
import json
import pytest
from eval_lab import domain as d
from eval_lab.generation import pin
from eval_lab.media import MediaStore
from eval_lab.pilot import PilotWorkspace, ObservationInput
from eval_lab.pilot_cli import parser
from test_media import media_tools, codec_videos
from test_relation_v2 import T, LEGACY, oracle, digest, edge, seed
from test_intent_v2 import intent, binding


def test_private_snapshot_literals_exact_dependencies_and_frozen_history(tmp_path, media_tools, codec_videos):
    root = tmp_path / "TEST-ONLY-workspace"
    p = PilotWorkspace(root); p._store = MediaStore(root / "media", media_tools)
    try:
        x = seed(p.repo)
        p.init("TEST-ONLY-dataset", "TEST-ONLY owner")
        clip = p.register("TEST-ONLY-dataset", "TEST-ONLY-generated", codec_videos["cfr"], "TEST-ONLY curator", "TEST-ONLY pattern")
        p.repo.put(clip.model_copy(update=dict(revision=2, intent=x.i.ref)))
        dataset = p.latest("PilotDataset", "TEST-ONLY-dataset")
        p.repo.put(dataset.model_copy(update=dict(revision=dataset.revision+1, clips=(clip.ref.model_copy(update={"revision": 2}),))))
        e = x.e.model_copy(update=dict(media=clip.media, id="TEST-ONLY-frame")); p.repo.put(e)
        # A real evidence submission is an existing root; no v2 relation envelope.
        root_e = p.observe("TEST-ONLY-generated", "TEST-ONLY observer", "TEST-ONLY-root", ObservationInput(
            observation="TEST-ONLY root observation", timestamp_start=0, timestamp_end=.2))
        x.e = e
        support = edge(x); p.repo.put(support)
        counter = edge(x, id="TEST-ONLY-counter", predicate="contradicts", epistemic_purpose="RULE_OUT",
            operational_purpose="REPAIR", warrant="TEST-ONLY counter warrant", qualifier="TEST-ONLY counter qualifier",
            rebuttal="TEST-ONLY counter rebuttal"); p.repo.put(counter)
        v2 = intent(id="TEST-ONLY-v2"); p.repo.put(v2)
        b = binding(v2, p.repo.get(clip.media), p.repo.get(clip.ingestion)); p.repo.put(b)
        anchored = edge(x, id="TEST-ONLY-anchored", predicate="fulfills", object=v2.ref, intent=pin(v2),
            creative_anchor=("criterion",), epistemic_purpose="QUALIFY", operational_purpose="SHIP",
            warrant="TEST-ONLY anchored warrant", qualifier="TEST-ONLY anchored qualifier", rebuttal="TEST-ONLY anchored rebuttal")
        p.repo.put(anchored)
        # Same exact intent, other media: cannot leak by shared intent alone.
        unrelated = edge(x, id="TEST-ONLY-unrelated", subject=d.Ref(kind="Evidence", id="TEST-ONLY-e"),
            evidence=(d.Ref(kind="Evidence", id="TEST-ONLY-e"),), object=x.i.ref, predicate="violates")
        p.repo.put(unrelated)
        # Incoming evidence path with no declared-intent endpoint.
        direct = edge(x, id="TEST-ONLY-direct", subject=root_e.ref, evidence=()); p.repo.put(direct)
        # Dependency h0 is added by relations above, but must not seed incoming discovery.
        downstream = edge(x, id="TEST-ONLY-downstream", predicate="refines", subject=x.hs[0].ref,
            object=x.hs[1].ref, evidence=()); p.repo.put(downstream)
        # Same ID at a different evidence revision and intent revision must not match.
        newer_i = x.i.model_copy(update=dict(revision=2, supersedes=x.i.ref)); p.repo.put(newer_i)
        foreign_clip = p.repo.get(d.Ref(kind="PilotClip", id="TEST-ONLY-clip"))
        p.repo.put(foreign_clip.model_copy(update=dict(revision=2, intent=newer_i.ref)))
        newer_e = root_e.model_copy(update=dict(revision=2, media=x.m.ref)); p.repo.put(newer_e)
        mismatch = edge(x, id="TEST-ONLY-revision-mismatch", subject=newer_e.ref, evidence=(),
            predicate="fulfills", object=newer_i.ref, intent=pin(newer_i)); p.repo.put(mismatch)
        first = p.snapshot("TEST-ONLY-dataset", "TEST-ONLY-before")
        exported = p.export_snapshot(first.id)
        assert exported["visibility"] == "PRIVATE_LOCAL_NOT_PUBLISHED"
        rows = {r["ref"]["id"]: r for r in exported["records"] if r["ref"]["kind"] == "RelationClaimV2"}
        assert set(rows) == {"TEST-ONLY-relation", "TEST-ONLY-counter", "TEST-ONLY-anchored", "TEST-ONLY-direct"}
        expected_e = dict(kind="Evidence", id="TEST-ONLY-frame", revision=1)
        # Full expected v2 intent payload is authored independently of its constructor/export.
        expected_v2 = dict(id="TEST-ONLY-v2", revision=1, schema_version=2, created_at="2026-01-01T00:00:00Z",
            owner="TEST-ONLY", objective="TEST-ONLY", revision_reason="CLARIFICATION", predecessor=None,
            use_context=dict(surface="TEST-ONLY", audience="TEST-ONLY", viewing_profile="FEED"), expected_deviations=[],
            criteria=[dict(id="criterion", dimension="motion_plausibility", priority="MUST", acceptance="TEST-ONLY", rejection="TEST-ONLY", tolerance="TEST-ONLY")])
        expectations = [oracle(subject=expected_e, evidence=[expected_e]),
            oracle(id="TEST-ONLY-counter", subject=expected_e, evidence=[expected_e], predicate="contradicts",
                epistemic_purpose="RULE_OUT", operational_purpose="REPAIR", warrant="TEST-ONLY counter warrant",
                qualifier="TEST-ONLY counter qualifier", rebuttal="TEST-ONLY counter rebuttal"),
            oracle(id="TEST-ONLY-anchored", subject=expected_e, evidence=[expected_e], predicate="fulfills",
                object=dict(kind="IntentSpecV2", id="TEST-ONLY-v2", revision=1),
                intent=dict(ref=dict(kind="IntentSpecV2", id="TEST-ONLY-v2", revision=1), sha256=digest(expected_v2)),
                creative_anchor=["criterion"], epistemic_purpose="QUALIFY", operational_purpose="SHIP",
                warrant="TEST-ONLY anchored warrant", qualifier="TEST-ONLY anchored qualifier", rebuttal="TEST-ONLY anchored rebuttal")]
        for expected in expectations:
            assert rows[expected["id"]] == dict(ref=dict(kind="RelationClaimV2", id=expected["id"], revision=1),
                sha256=digest(expected), artifact=expected)
        refs = {(r["ref"]["kind"], r["ref"]["id"], r["ref"]["revision"]) for r in exported["records"]}
        assert {("IntentSpec", "TEST-ONLY-intent", 1), ("IntentSpecV2", "TEST-ONLY-v2", 1),
            ("Hypothesis", "TEST-ONLY-h0", 1), ("Evidence", "TEST-ONLY-frame", 1)} <= refs
        assert ("IntentSpec", "TEST-ONLY-intent", 2) not in refs and ("Evidence", "TEST-ONLY-frame", 2) not in refs
        assert all(s.artifact.kind != "RelationClaimV2" for s in p.repo.all("PilotSubmission"))
        frozen = json.dumps(exported, sort_keys=True, separators=(",", ":"))
        p.repo.put(support.model_copy(update=dict(revision=2, predecessor=pin(support), warrant="TEST-ONLY successor warrant")))
        p.repo.put(intent(id=v2.id, revision=2, predecessor=pin(v2)))
        after = p.snapshot("TEST-ONLY-dataset", "TEST-ONLY-after")
        later = {(r.ref.kind, r.ref.id, r.ref.revision) for r in after.records}
        assert {("RelationClaimV2", "TEST-ONLY-relation", 1), ("RelationClaimV2", "TEST-ONLY-relation", 2)} <= later
        assert ("IntentSpecV2", "TEST-ONLY-v2", 2) not in later
        assert p.status("TEST-ONLY-dataset")["clips"][0]["quality_verdict"] == "UNKNOWN"
        assert json.dumps(p.export_snapshot(first.id), sort_keys=True, separators=(",", ":")) == frozen
    finally: p.close()
    reopened = PilotWorkspace(root)
    try: assert json.dumps(reopened.export_snapshot("TEST-ONLY-before"), sort_keys=True, separators=(",", ":")) == frozen
    finally: reopened.close()


@pytest.mark.parametrize("command", ["snapshot", "export-snapshot"])
def test_snapshot_cli_help_describes_private_relations(command, capsys):
    with pytest.raises(SystemExit, match="0"): parser().parse_args([command, "--help"])
    text = capsys.readouterr().out
    assert "private" in text.lower() and "relation" in text.lower() and "docs/relations-v2.md" in text
