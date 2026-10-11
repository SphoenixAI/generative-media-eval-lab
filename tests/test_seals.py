"""TEST-ONLY local seal contracts; no real clips, intent authoring or network."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest
from eval_lab import __version__
from eval_lab.canonical_json import canonicalize, parse_json, file_digest
from eval_lab.domain import Ref
from eval_lab.intent_v2 import IntentSpecV2, Pin
from eval_lab.persistence import Repository
from eval_lab.seals import SealRecord, seal_intent, verify_seal
from test_media import media_tools, codec_videos


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "TEST-ONLY-intent.json"
    data = dict(id="TEST-ONLY-intent", schema_version=2, revision=1,
        created_at="2026-01-01T03:00:00+03:00", owner="TEST-ONLY", objective="TEST-ONLY",
        revision_reason="CLARIFICATION", use_context=dict(surface="TEST-ONLY",
        audience="TEST-ONLY", viewing_profile="FEED"), criteria=[dict(id="TEST-ONLY-c",
        dimension="motion_plausibility", priority="MUST", acceptance="TEST-ONLY",
        rejection="TEST-ONLY", tolerance="TEST-ONLY")])
    path.write_text(json.dumps(data, indent=2))
    return path


def cli(root, *args):
    result = subprocess.run([sys.executable, "-m", "eval_lab.pilot_cli", "--root", str(root),
        *map(str, args)], capture_output=True, text=True)
    return result.returncode, json.loads(result.stdout or result.stderr)


def contents(root):
    return {str(p.relative_to(root)): p.read_bytes() if p.is_file() else None for p in root.rglob("*")}


def test_cli_seal_verify_reformat_mutate_and_missing(source, tmp_path):
    root = tmp_path / "workspace"
    original = source.read_bytes()
    before = datetime.now(timezone.utc)
    code, result = cli(root, "seal-intent", source)
    assert code == 0
    seal = SealRecord.model_validate(result)
    assert source.read_bytes() == original
    assert seal.file_sha256 == file_digest(original)
    assert seal.canonical_source.encode() == canonicalize(parse_json(original))
    assert seal.canonicalization == "RFC8785" and seal.number_profile == "safe-integer-tokens-v1"
    assert before <= seal.sealed_at <= datetime.now(timezone.utc)
    assert seal.sealed_at.utcoffset().total_seconds() == 0
    assert seal.tool_version == __version__ and seal.git_witness is None
    assert seal.source_path == str(source.resolve())
    data = json.loads(original)
    source.write_text(json.dumps(dict(reversed(list(data.items())))))
    for target in (seal.id, source):
        snapshot = contents(tmp_path)
        code, result = cli(root, "verify-seal", target)
        assert code == 0 and result["status"] == "VERIFIED"
        assert result["quality_verdict"] == "UNKNOWN"
        assert contents(tmp_path) == snapshot
    data["objective"] = "TEST-ONLY changed"
    source.write_text(json.dumps(data))
    assert cli(root, "verify-seal", seal.id)[1]["status"] == "INTEGRITY_FAILURE"
    source.unlink()
    assert cli(root, "verify-seal", seal.id)[1]["status"] == "UNKNOWN"


def test_unknown_verification_creates_nothing(tmp_path, source):
    root = tmp_path / "absent"
    for target in ("unknown-id", source):
        assert cli(root, "verify-seal", target)[0] != 0
        assert verify_seal(root, str(target))["status"] == "UNKNOWN"
    assert not root.exists()
    seal_intent(root, source)
    for target in ("unknown-id", tmp_path / "unsealed.json"):
        assert cli(root, "verify-seal", target)[1]["status"] == "UNKNOWN"


def test_repeated_seals_check_all_events_and_preserve_history(tmp_path, source):
    root = tmp_path / "workspace"
    first = seal_intent(root, source)
    data = json.loads(source.read_text())
    intent = IntentSpecV2.model_validate(data)
    data.update(revision=2, predecessor=Pin(ref=intent.ref, sha256=intent.digest).model_dump(), objective="TEST-ONLY v2")
    source.write_text(json.dumps(data))
    second = seal_intent(root, source, git_commit="a"*40, git_remote="TEST-ONLY-declared-remote")
    third = seal_intent(root, source)
    assert len({first.id, second.id, third.id}) == 3
    assert second.git_witness.commit == "a"*40
    result = verify_seal(root, str(source))
    assert result["status"] == "INTEGRITY_FAILURE" and len(result["seals"]) == 3
    assert {r["seal_id"]: r["status"] for r in result["seals"]} == {
        first.id: "INTEGRITY_FAILURE", second.id: "VERIFIED", third.id: "VERIFIED"}
    repo = Repository("sqlite:///"+str(root/"pilot.sqlite"))
    assert repo.get(first.ref).canonical() == first.canonical()
    assert repo.put(first) == first.digest
    assert repo.get(intent.ref).digest == intent.digest
    assert first.file_sha256 != intent.digest
    repo.close()


@pytest.mark.parametrize("change", [
    {"revision": 2}, {"file_sha256": "0"*64}, {"canonical_source": '{}'},
    {"canonicalization": "TEST-ONLY"}, {"sealed_at": "2026-01-01T00:00:00"},
])
def test_copied_invalid_seal_cannot_enter_repository(tmp_path, source, change):
    seal = seal_intent(tmp_path, source)
    repo = Repository("sqlite:///"+str(tmp_path/"pilot.sqlite"))
    with pytest.raises(ValueError):
        repo.put(seal.model_copy(update=change))
    assert repo.get(seal.ref).canonical() == seal.canonical()
    repo.close()


def test_immutable_values_conflicts_sql_guards_and_exact_pin(tmp_path, source):
    seal = seal_intent(tmp_path, source)
    repo = Repository("sqlite:///"+str(tmp_path/"pilot.sqlite"))
    with pytest.raises(ValueError):
        seal.file_sha256 = "0"*64
    with pytest.raises(ValueError, match="immutable"):
        repo.put(seal.model_copy(update={"tool_version": "TEST-ONLY-other"}))
    for pin in (seal.intent.model_copy(update={"sha256": "0"*64}),
                seal.intent.model_copy(update={"ref": seal.intent.ref.model_copy(update={"revision": 2})})):
        with pytest.raises(ValueError):
            repo.put(seal.model_copy(update={"id": "TEST-ONLY-borrowed", "intent": pin}))
    with sqlite3.connect(tmp_path/"pilot.sqlite") as db:
        for sql in ("UPDATE artifacts SET sha256='changed'", "DELETE FROM artifacts"):
            with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                db.execute(sql)
        assert db.execute("SELECT target_id FROM artifact_references WHERE kind='SealRecord'").fetchall() == [(seal.intent.ref.id,)]
    assert repo.get(seal.ref).canonical() == seal.canonical()
    repo.close()


@pytest.mark.parametrize("missing", ["id", "schema_version", "revision", "created_at", "owner", "objective", "criteria", "revision_reason"])
def test_incomplete_input_rejected_before_import(tmp_path, source, missing):
    data = json.loads(source.read_text()); del data[missing]
    source.write_text(json.dumps(data))
    root = tmp_path / "absent"
    assert cli(root, "seal-intent", source)[0] != 0
    assert not root.exists()


@pytest.mark.parametrize("raw", ['{"schema_version":1}', '{', '{"a":1,"a":2}', '1.0', '"\\ud800"'])
def test_invalid_input_never_writes(tmp_path, source, raw):
    source.write_text(raw)
    assert cli(tmp_path/"absent", "seal-intent", source)[0] != 0
    assert not (tmp_path/"absent").exists()


def test_witness_pair_and_cli_help(tmp_path, source):
    assert cli(tmp_path/"absent", "seal-intent", source, "--git-commit", "a"*40)[0] != 0
    assert not (tmp_path/"absent").exists()
    code, result = cli(tmp_path, "seal-intent", source, "--git-commit", "a"*40, "--git-remote", "TEST-ONLY-remote")
    assert code == 0 and result["git_witness"]["remote_url"] == "TEST-ONLY-remote"
    for command, phrase in (("seal-intent", "integer"), ("verify-seal", "read-only")):
        help_text = subprocess.check_output([sys.executable, "-m", "eval_lab.pilot_cli", command, "--help"], text=True)
        assert phrase in help_text and "FILE" in help_text


def test_missing_or_wrong_predecessor_and_revision_conflict(tmp_path, source):
    data = json.loads(source.read_text())
    intent = IntentSpecV2.model_validate(data)
    data.update(revision=2, predecessor=Pin(ref=intent.ref, sha256=intent.digest).model_dump())
    source.write_text(json.dumps(data))
    with pytest.raises((ValueError, KeyError)):
        seal_intent(tmp_path, source)
    source.write_text(intent.model_dump_json()); seal_intent(tmp_path, source)
    data["predecessor"]["sha256"] = "0"*64
    source.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        seal_intent(tmp_path, source)
    data = intent.model_dump(mode="json") | {"objective": "TEST-ONLY conflict"}
    source.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="immutable"):
        seal_intent(tmp_path, source)


def test_admission_checks_stored_pin_and_partial_failure_is_explicit(tmp_path, source, monkeypatch):
    original = Repository.put
    def reject_seal(repo, item):
        if isinstance(item, SealRecord):
            raise ValueError("TEST-ONLY admission failure")
        return original(repo, item)
    with monkeypatch.context() as patch:
        patch.setattr(Repository, "put", reject_seal)
        with pytest.raises(ValueError, match="intent.*retained.*seal.*not"):
            seal_intent(tmp_path, source)
    repo = Repository("sqlite:///"+str(tmp_path/"pilot.sqlite"))
    assert len(repo.all("IntentSpecV2")) == 1 and repo.all("SealRecord") == ()
    repo.close()
    assert verify_seal(tmp_path, seal_intent(tmp_path, source).id)["status"] == "VERIFIED"


@pytest.mark.parametrize("target", ["seal", "intent", "identity", "source_and_hash", "missing_intent"])
def test_tampered_store_detected(tmp_path, source, target):
    seal = seal_intent(tmp_path, source)
    with sqlite3.connect(tmp_path/"pilot.sqlite") as db:
        db.execute("DROP TRIGGER no_update_artifacts")  # sacrificial TEST-ONLY store
        if target == "missing_intent":
            db.execute("DROP TRIGGER no_delete_artifacts")
            db.execute("DELETE FROM artifacts WHERE kind='IntentSpecV2'")
        else:
            kind = "IntentSpecV2" if target == "intent" else "SealRecord"
            raw = json.loads(db.execute("SELECT payload FROM artifacts WHERE kind=?", (kind,)).fetchone()[0])
            if target == "seal": raw["tool_version"] = "TEST-ONLY changed"
            if target == "intent": raw["objective"] = "TEST-ONLY changed"
            if target == "identity": raw["id"] = "TEST-ONLY wrong identity"
            if target == "source_and_hash":
                changed = json.loads(raw["canonical_source"]) | {"objective": "TEST-ONLY changed"}
                raw.update(canonical_source=canonicalize(changed).decode(), file_sha256=file_digest(json.dumps(changed)))
            payload = json.dumps(raw, sort_keys=True, separators=(",", ":"))
            digest = seal.digest if target == "seal" else sha256(payload.encode()).hexdigest()
            db.execute("UPDATE artifacts SET payload=?,sha256=? WHERE kind=?", (payload, digest, kind))
    before = contents(tmp_path)
    for lookup in (seal.id, str(source)):
        assert verify_seal(tmp_path, lookup)["status"] == "INTEGRITY_FAILURE"
    assert contents(tmp_path) == before


def test_pin_admission_rechecks_record_under_transaction(tmp_path, source):
    seal = seal_intent(tmp_path, source)
    repo = Repository("sqlite:///"+str(tmp_path/"pilot.sqlite"))
    # Keep a structurally valid seal but bypass the preliminary link walk.
    repo._validate_links = lambda item: None
    with sqlite3.connect(tmp_path/"pilot.sqlite") as db:
        db.execute("DROP TRIGGER no_update_artifacts")
        raw = json.loads(db.execute("SELECT payload FROM artifacts WHERE kind='IntentSpecV2'").fetchone()[0])
        raw["objective"] = "TEST-ONLY substituted"
        changed = IntentSpecV2.model_validate(raw)
        db.execute("UPDATE artifacts SET payload=?,sha256=? WHERE kind='IntentSpecV2'", (changed.canonical(), changed.digest))
    with pytest.raises(ValueError, match="pinned.*mismatch"):
        repo.put(seal.model_copy(update={"id": "TEST-ONLY new event"}))
    repo.close()


def test_source_is_read_once_and_defaults_do_not_change_file_digest(tmp_path, source, monkeypatch):
    original = source.read_bytes()
    reads = []
    read_bytes = Path.read_bytes
    def track(path):
        if path == source:
            reads.append(path)
        return read_bytes(path)
    monkeypatch.setattr(Path, "read_bytes", track)
    seal = seal_intent(tmp_path, source)
    assert reads == [source]
    assert "expected_deviations" not in json.loads(seal.canonical_source)
    assert seal.file_sha256 == file_digest(original)
    assert seal.intent.sha256 == IntentSpecV2.model_validate_json(original).digest


def test_witness_and_admitted_inputs_do_not_alias(tmp_path, source):
    seal = seal_intent(tmp_path, source, git_commit="a"*40, git_remote="TEST-ONLY-remote")
    raw = seal.model_dump(mode="json")
    copy = SealRecord.model_validate(raw)
    repo = Repository("sqlite:///"+str(tmp_path/"pilot.sqlite"))
    assert repo.put(copy) == seal.digest
    raw["git_witness"]["remote_url"] = "TEST-ONLY mutated"
    with pytest.raises(ValueError):
        copy.git_witness.remote_url = "TEST-ONLY mutated"
    with pytest.raises(ValueError):
        repo.put(seal.model_copy(update={"git_witness": seal.git_witness.model_copy(update={"commit": "bad"})}))
    assert repo.get(seal.ref).canonical() == seal.canonical()
    repo.close()


def test_invalid_current_source_and_corrupt_database_are_nonzero(tmp_path, source):
    seal = seal_intent(tmp_path, source)
    source.write_text('{"TEST-ONLY":1.0}')
    code, result = cli(tmp_path, "verify-seal", seal.id)
    assert code != 0 and result["status"] == "INTEGRITY_FAILURE"
    (tmp_path/"pilot.sqlite").write_bytes(b"TEST-ONLY corrupt database")
    code, result = cli(tmp_path, "verify-seal", seal.id)
    assert code != 0 and result["status"] == "INTEGRITY_FAILURE"


def test_unavailable_source_is_nonzero(tmp_path, source):
    seal = seal_intent(tmp_path, source)
    source.rename(tmp_path/"TEST-ONLY moved.json")
    before = contents(tmp_path)
    code, result = cli(tmp_path, "verify-seal", seal.id)
    assert code != 0 and result["status"] == "UNKNOWN"
    assert contents(tmp_path) == before


def test_seals_do_not_change_public_embed_or_existing_artifact_digests(tmp_path, source):
    from eval_lab.fixtures import seed
    from eval_lab.presentation import serialize_case
    repo = Repository("sqlite:///"+str(tmp_path/"pilot.sqlite"))
    data = seed(repo)  # Existing synthetic-only regression fixture.
    args = (repo, data["case"].ref, data["round"].ref, data["raters"][0].ref)
    before = {mode: serialize_case(*args, mode=mode) for mode in ("public", "embed")}
    digest = data["intent"].digest
    seal = seal_intent(tmp_path, source)
    for mode in before:
        after = serialize_case(*args, mode=mode)
        assert after == before[mode]
        assert seal.source_path not in json.dumps(after) and seal.canonical_source not in json.dumps(after)
    assert repo.get(data["intent"].ref).digest == digest
    repo.close()


@pytest.mark.parametrize("initial", ["valid", "missing", "invalid"])
@pytest.mark.parametrize("replacement", ["rewrite", "symlink"])
def test_verification_captures_one_source_despite_interleaved_change(tmp_path, source, monkeypatch, initial, replacement):
    first = seal_intent(tmp_path, source)
    data = json.loads(source.read_text())
    data.update(revision=2, predecessor=first.intent.model_dump(), objective="TEST-ONLY changed")
    source.write_text(json.dumps(data))
    second = seal_intent(tmp_path, source)
    ordered = sorted((first, second), key=lambda seal: seal.id)
    destination = tmp_path / "TEST-ONLY-second-source.json"
    destination.write_text(ordered[1].canonical_source)
    source.write_text(ordered[0].canonical_source if initial == "valid" else "{")
    if initial == "missing":
        source.unlink()
    reads = []
    read_bytes = Path.read_bytes
    def change_after_read(path):
        if path != source:
            return read_bytes(path)
        reads.append(path)
        try:
            return read_bytes(path)
        finally:
            if replacement == "symlink":
                source.unlink(missing_ok=True)
                source.symlink_to(destination)
            else:
                source.write_text(ordered[1].canonical_source)
    monkeypatch.setattr(Path, "read_bytes", change_after_read)
    result = verify_seal(tmp_path, str(source))
    assert result["status"] == ("UNKNOWN" if initial == "missing" else "INTEGRITY_FAILURE")
    assert [r["status"] for r in result["seals"]] == {
        "valid": ["VERIFIED", "INTEGRITY_FAILURE"],
        "missing": ["UNKNOWN", "UNKNOWN"],
        "invalid": ["INTEGRITY_FAILURE", "INTEGRITY_FAILURE"],
    }[initial]
    assert reads == [source]
    assert result["quality_verdict"] == "UNKNOWN"


def test_private_snapshot_retains_exact_seals_and_frozen_exports(tmp_path, source, media_tools, codec_videos):
    from eval_lab.intent_v2 import IntentBinding
    from eval_lab.media import MediaStore
    from eval_lab.pilot import PilotWorkspace
    root = tmp_path / "TEST-ONLY-workspace"
    p = PilotWorkspace(root)
    try:
        p._store = MediaStore(root / "media", media_tools)
        p.init("TEST-ONLY", "TEST-ONLY")
        clip = p.register("TEST-ONLY", "TEST-ONLY-clip", codec_videos["cfr"], "TEST-ONLY", "TEST-ONLY")
        first = seal_intent(root, source)
        data = json.loads(source.read_text())
        data.update(revision=2, predecessor=first.intent.model_dump(), objective="TEST-ONLY v2")
        source.write_text(json.dumps(data))
        second = seal_intent(root, source)
        m, r = p.repo.get(clip.media), p.repo.get(clip.ingestion)
        p.repo.put(IntentBinding(id="TEST-ONLY-binding", intent=second.intent,
            media=Pin(ref=m.ref, sha256=m.digest), registration=Pin(ref=r.ref, sha256=r.digest),
            registered_at=r.created_at, origin="FOUND"))
        data.update(revision=3, predecessor=second.intent.model_dump(), objective="TEST-ONLY unbound v3")
        source.write_text(json.dumps(data))
        unbound = seal_intent(root, source)
        data = json.loads(first.canonical_source) | {"id": "TEST-ONLY-unrelated"}
        source.write_text(json.dumps(data))
        unrelated = seal_intent(root, source)
        snap = p.snapshot("TEST-ONLY", "TEST-ONLY-before")
        frozen = json.dumps(p.export_snapshot(snap.id), sort_keys=True)
        pinned = {x.ref: x.sha256 for x in snap.records}
        assert {first.ref, second.ref} <= pinned.keys()
        assert {unbound.ref, unrelated.ref}.isdisjoint(pinned)
        exported = {Ref(**x["ref"]): x for x in json.loads(frozen)["records"]}
        for seal in (first, second):
            assert pinned[seal.ref] == seal.digest == exported[seal.ref]["sha256"]
            assert exported[seal.ref]["artifact"] == seal.model_dump(mode="json")
            assert pinned[seal.intent.ref] == seal.intent.sha256
        source.write_text(second.canonical_source)
        later_seal = seal_intent(root, source)
        later = p.snapshot("TEST-ONLY", "TEST-ONLY-after")
        later_pins = {x.ref: x.sha256 for x in later.records}
        assert later_pins[later_seal.ref] == later_seal.digest
        assert {unbound.ref, unrelated.ref}.isdisjoint(later_pins)
        assert p.repo.get(snap.ref).canonical() == snap.canonical()
        assert json.dumps(p.export_snapshot(snap.id), sort_keys=True) == frozen
        code, output = cli(root, "export-snapshot", snap.id)
        assert code == 0 and json.dumps(output, sort_keys=True) == frozen
    finally:
        p.close()
