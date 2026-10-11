"""TEST-ONLY raw evidence contracts; no real media or authored judgments."""
from copy import deepcopy
from hashlib import sha256
import json
import sqlite3
import pytest
from eval_lab import lint_evidence as le


DIMENSION = le.Contract((str,), choices=("motion_plausibility", "composition"))
DURATION = le.Contract((int, float), minimum=0, exclusive=True)
COVERAGE = le.Contract((str,), choices=("full_clip", "sampled_frames", "interval"), unavailable=("unknown",))
CONTRACTS = [
    (le.TEXT, "TEST-ONLY text", "", "empty value"),
    (le.BOOLEAN, False, 0, "wrong type"),
    (le.MAPPING, {}, [], "wrong type"),
    (le.SEQUENCE, [], {}, "wrong type"),
    (le.REVISION, 1, True, "wrong type"),
    (le.DIGEST, "a" * 64, "g" * 64, "malformed digest"),
    (DIMENSION, "composition", "TEST-ONLY unknown dimension", "unsupported value"),
    (DURATION, .125, 0, "below minimum"),
    (COVERAGE, "full_clip", "TEST-ONLY unknown coverage", "unsupported value"),
    (le.Contract((int, float), minimum=0), 0, -.25, "below minimum"),
]


def failure(result, state, reason):
    assert type(result) is le.EvidenceResult
    assert result.state == state and reason in result.reason
    assert result.value is None
    assert result.subject and isinstance(result.path, tuple)


@pytest.mark.parametrize("contract,valid,bad,reason", CONTRACTS)
@pytest.mark.parametrize("case", ["missing", "null", "malformed", "valid"])
def test_shared_field_contract(contract, valid, bad, reason, case):
    raw = {} if case == "missing" else {"x": None if case == "null" else bad if case == "malformed" else valid}
    result = le.field(raw, ("x",), contract, subject="TEST-ONLY field")
    assert result.path == ("x",) and result.subject == "TEST-ONLY field"
    if case == "valid":
        assert result.state == "AVAILABLE" and result.value == valid and result.reason == ""
    else:
        failure(result, "INTEGRITY_FAILURE" if case == "malformed" else "UNKNOWN",
                reason if case == "malformed" else case)


@pytest.mark.parametrize("value,reason", [(True, "wrong type"), ("2.5", "wrong type"),
    (-.25, "below minimum"), (float("nan"), "nonfinite number"),
    (float("inf"), "nonfinite number"), (-float("inf"), "nonfinite number")])
def test_numeric_guard(value, reason):
    failure(le.field({"x": value}, ("x",), DURATION, subject="TEST-ONLY duration"), "INTEGRITY_FAILURE", reason)


@pytest.mark.parametrize("value", [0, -1, 1.5, "1", True])
def test_revision_guard(value):
    failure(le.field({"x": value}, ("x",), le.REVISION, subject="TEST-ONLY revision"),
            "INTEGRITY_FAILURE", "below minimum" if type(value) is int else "wrong type")


@pytest.mark.parametrize("value", ["a" * 63, "b" * 65, "A" * 64, "z" * 64, 22])
def test_digest_guard(value):
    failure(le.field({"x": value}, ("x",), le.DIGEST, subject="TEST-ONLY hash"),
            "INTEGRITY_FAILURE", "wrong type" if type(value) is int else "malformed digest")


@pytest.mark.parametrize("raw,state,reason", [({}, "UNKNOWN", "missing"),
    ({"outer": None}, "UNKNOWN", "null"), ({"outer": []}, "INTEGRITY_FAILURE", "container"),
    ({"outer": {}}, "UNKNOWN", "missing"), ({"outer": {"inner": None}}, "UNKNOWN", "null"),
    ({"outer": {"inner": 8}}, "INTEGRITY_FAILURE", "wrong type")])
def test_nested_container_guard(raw, state, reason):
    failure(le.field(raw, ("outer", "inner"), le.TEXT, subject="TEST-ONLY nested"), state, reason)


def test_explicit_unavailability_and_no_mutation_or_truthiness():
    failure(le.field({"x": "unknown"}, ("x",), COVERAGE, subject="TEST-ONLY coverage"), "UNKNOWN", "unavailable")
    failure(le.field({"x": "unknown"}, ("x",), DIMENSION, subject="TEST-ONLY dimension"), "INTEGRITY_FAILURE", "unsupported value")
    raw = {"x": [{"id": "TEST-ONLY item"}]}
    result = le.field(raw, ("x",), le.SEQUENCE, subject="TEST-ONLY list")
    result.value[0]["id"] = "TEST-ONLY changed"
    assert raw == {"x": [{"id": "TEST-ONLY item"}]}
    assert le.field(raw, ("x", 0, "id"), le.TEXT, subject="TEST-ONLY item").value == "TEST-ONLY item"
    failure(le.field(raw, ("x", 1), le.MAPPING, subject="TEST-ONLY absent index"), "UNKNOWN", "missing")
    for value in (result, le.field({}, ("x",), le.TEXT, subject="TEST-ONLY missing")):
        with pytest.raises(TypeError, match="inspect state explicitly"): bool(value)


def ref(**changes):
    return {"kind": "MediaAsset", "id": "TEST-ONLY raw", "revision": 3} | changes


def payload(**changes):
    return {"id": "TEST-ONLY raw", "revision": 3, "schema_version": 1,
            "dimension": "composition", "metadata": {"duration_seconds": 2.75},
            "coverage": "full_clip", "predictions": {"kind": ["TEST-ONLY X"], "id": ["TEST-ONLY Y"]}} | changes


def checksum(data):
    # Independent fixture encoding, not a call to the implementation under test.
    return sha256(json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


@pytest.fixture
def store(tmp_path):
    path = tmp_path / "pilot.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE schema_migrations(version INTEGER)")
        db.execute("INSERT INTO schema_migrations VALUES (1)")
        db.execute("CREATE TABLE artifacts(kind TEXT, id TEXT, revision INTEGER, sha256 TEXT, payload TEXT)")
    return tmp_path


def put(root, data=None, **row):
    data = payload() if data is None else data
    values = dict(kind="MediaAsset", id="TEST-ONLY raw", revision=3, sha256=checksum(data), payload=json.dumps(data)) | row
    with sqlite3.connect(root / "pilot.sqlite") as db:
        db.execute("INSERT INTO artifacts VALUES (:kind,:id,:revision,:sha256,:payload)", values)


@pytest.mark.parametrize("path,contract,bad,reason", [
    (("dimension",), DIMENSION, "TEST-ONLY bogus", "unsupported value"),
    (("dimension",), DIMENSION, False, "wrong type"),
    (("metadata", "duration_seconds"), DURATION, "2.75", "wrong type"),
    (("metadata", "duration_seconds"), DURATION, 0, "below minimum"),
    (("metadata", "duration_seconds"), DURATION, -2, "below minimum"),
    (("metadata", "duration_seconds"), DURATION, True, "wrong type"),
    (("coverage",), COVERAGE, "TEST-ONLY bogus", "unsupported value"),
    (("coverage",), COVERAGE, "unknown", "unavailable"),
])
@pytest.mark.parametrize("case", ["missing", "null", "malformed"])
def test_direct_and_retained_prerequisite_contract(store, path, contract, bad, reason, case):
    data = payload(); parent = data if len(path) == 1 else data[path[0]]
    if case == "missing": del parent[path[-1]]
    else: parent[path[-1]] = None if case == "null" else bad
    expected_state = "INTEGRITY_FAILURE" if case == "malformed" and reason != "unavailable" else "UNKNOWN"
    expected_reason = reason if case == "malformed" else case
    failure(le.field(data, path, contract, subject="TEST-ONLY direct"), expected_state, expected_reason)
    put(store, data)
    with le.RawReader(store) as reader:
        record = reader.read(ref())
        assert record.diagnostics == ()
        failure(record.field(path, contract), expected_state, expected_reason)


@pytest.mark.parametrize("component", ["kind", "id", "revision"])
@pytest.mark.parametrize("case", ["missing", "null", "malformed"])
def test_explicit_reference_components(store, component, case):
    request = ref(); put(store)
    if case == "missing": del request[component]
    else: request[component] = None if case == "null" else []
    with le.RawReader(store) as reader:
        record = reader.read(request)
        failure(record.diagnostics[0], "INTEGRITY_FAILURE" if case == "malformed" else "UNKNOWN",
                "wrong type" if case == "malformed" else case)
        assert record.diagnostics[0].path == (component,)
        assert record.diagnostic_raw is None


@pytest.mark.parametrize("query,state,reason", [(None, "UNKNOWN", "null"),
    ([], "INTEGRITY_FAILURE", "wrong type"), (ref(kind="TEST-ONLY alien"), "INTEGRITY_FAILURE", "unsupported value"),
    (ref(revision=0), "INTEGRITY_FAILURE", "below minimum"), (ref(revision=True), "INTEGRITY_FAILURE", "wrong type"),
    (ref(revision=2), "UNKNOWN", "missing exact target"), (ref(extra="TEST-ONLY"), "INTEGRITY_FAILURE", "reference keys")])
def test_reference_envelope_and_no_latest_fallback(store, query, state, reason):
    put(store)
    with le.RawReader(store) as reader: failure(reader.read(query).diagnostics[0], state, reason)


@pytest.mark.parametrize("field_name", ["ref", "sha256"])
@pytest.mark.parametrize("case", ["missing", "null", "malformed"])
def test_pin_required_components(store, field_name, case):
    put(store); request = {"ref": ref(), "sha256": checksum(payload())}
    if case == "missing": del request[field_name]
    else: request[field_name] = None if case == "null" else 42
    with le.RawReader(store) as reader:
        failure(reader.read(request, pinned=True).diagnostics[0], "INTEGRITY_FAILURE" if case == "malformed" else "UNKNOWN",
                "wrong type" if case == "malformed" else case)


def test_exact_revision_pin_and_arbitrary_mapping(store):
    put(store, payload(revision=1, dimension="motion_plausibility"), revision=1)
    put(store)
    with le.RawReader(store) as reader:
        first = reader.read(ref(revision=1)); current = reader.read({"ref": ref(), "sha256": checksum(payload())}, pinned=True)
        assert first.field(("dimension",), DIMENSION).value == "motion_plausibility"
        assert current.field(("dimension",), DIMENSION).value == "composition"
        assert current.field(("metadata", "duration_seconds"), DURATION).value == 2.75
        assert current.field(("predictions",), le.MAPPING).value == {"kind": ["TEST-ONLY X"], "id": ["TEST-ONLY Y"]}
        failure(reader.read({"ref": ref(), "sha256": "d" * 64}, pinned=True).diagnostics[0], "INTEGRITY_FAILURE", "pin digest mismatch")


@pytest.mark.parametrize("field_name,case,state,reason", [
    ("id", "missing", "UNKNOWN", "missing"), ("id", None, "UNKNOWN", "null"),
    ("id", [], "INTEGRITY_FAILURE", "wrong type"), ("id", "TEST-ONLY other", "INTEGRITY_FAILURE", "payload identity mismatch"),
    ("revision", "missing", "UNKNOWN", "missing"), ("revision", None, "UNKNOWN", "null"),
    ("revision", True, "INTEGRITY_FAILURE", "wrong type"), ("revision", 4, "INTEGRITY_FAILURE", "payload identity mismatch"),
    ("schema_version", "missing", "UNKNOWN", "missing"), ("schema_version", None, "UNKNOWN", "null"),
    ("schema_version", 2, "INTEGRITY_FAILURE", "unsupported value"), ("schema_version", True, "INTEGRITY_FAILURE", "wrong type"),
])
def test_retained_identity_and_version_contract(store, field_name, case, state, reason):
    data = payload()
    if case == "missing": del data[field_name]
    else: data[field_name] = case
    put(store, data)
    with le.RawReader(store) as reader:
        record = reader.read(ref()); failure(record.diagnostics[0], state, reason)
        failure(record.field(("dimension",), DIMENSION), state, "record")


@pytest.mark.parametrize("digest,state,reason", [(None, "UNKNOWN", "null"),
    (17, "INTEGRITY_FAILURE", "malformed digest"), ("z" * 64, "INTEGRITY_FAILURE", "malformed digest"),
    ("b" * 64, "INTEGRITY_FAILURE", "stored digest mismatch")])
def test_stored_digest_guard(store, digest, state, reason):
    put(store, sha256=digest)
    with le.RawReader(store) as reader:
        record = reader.read(ref()); failure(record.diagnostics[0], state, reason)
        failure(record.field(("dimension",), DIMENSION), state, "record")


def test_field_and_integrity_diagnostics_separate_and_raw_is_unchecked(store):
    put(store, payload(dimension=None), sha256="c" * 64)
    with le.RawReader(store) as reader:
        record = reader.read(ref())
        failure(record.diagnostics[0], "INTEGRITY_FAILURE", "stored digest mismatch")
        failure(record.field(("dimension",), DIMENSION), "UNKNOWN", "null")
        failure(record.field(("metadata", "duration_seconds"), DURATION), "INTEGRITY_FAILURE", "record")
        raw = record.diagnostic_raw; raw["dimension"] = "motion_plausibility"
        assert record.diagnostic_raw["dimension"] is None


@pytest.mark.parametrize("source,state,reason", [(None, "UNKNOWN", "null"), (9, "INTEGRITY_FAILURE", "wrong type"),
    ("null", "UNKNOWN", "null"), ("[]", "INTEGRITY_FAILURE", "wrong type"), ("{", "INTEGRITY_FAILURE", "JSON"),
    ('{"id":1,"id":2}', "INTEGRITY_FAILURE", "duplicate JSON key"),
    ('{"x":NaN}', "INTEGRITY_FAILURE", "nonfinite number"), ('{"x":Infinity}', "INTEGRITY_FAILURE", "nonfinite number"),
    ('{"x":-Infinity}', "INTEGRITY_FAILURE", "nonfinite number"), ('{"x":1e999}', "INTEGRITY_FAILURE", "nonfinite number")])
def test_strict_json_guard(store, source, state, reason):
    put(store, payload=source)
    with le.RawReader(store) as reader: failure(reader.read(ref()).diagnostics[0], state, reason)


def test_duplicate_rows_and_row_identity_guard(store):
    put(store); put(store)
    with le.RawReader(store) as reader: failure(reader.read(ref()).diagnostics[0], "INTEGRITY_FAILURE", "duplicate exact target")


def test_row_identity_not_sql_collation(store):
    with sqlite3.connect(store / "pilot.sqlite") as db:
        db.execute("DROP TABLE artifacts")
        db.execute("CREATE TABLE artifacts(kind TEXT, id TEXT COLLATE NOCASE, revision INTEGER, sha256 TEXT, payload TEXT)")
    put(store, id="test-only raw")
    with le.RawReader(store) as reader: failure(reader.read(ref()).diagnostics[0], "INTEGRITY_FAILURE", "row identity mismatch")


@pytest.mark.parametrize("damage,reason", [("bytes", "store structure"), ("table", "store structure"),
    ("column", "store structure"), ("version", "store version"), ("null-version", "store version"),
    ("no-version", "store version"), ("text-version", "store version")])
def test_store_structure_guard(store, damage, reason):
    if damage == "bytes": (store / "pilot.sqlite").write_bytes(b"TEST-ONLY corrupt database")
    else:
        with sqlite3.connect(store / "pilot.sqlite") as db:
            if damage == "table": db.execute("DROP TABLE artifacts")
            elif damage == "column": db.execute("ALTER TABLE artifacts DROP COLUMN sha256")
            elif damage == "no-version": db.execute("DELETE FROM schema_migrations")
            else: db.execute("UPDATE schema_migrations SET version=?", ({"version": 2, "null-version": None, "text-version": "TEST-ONLY"}[damage],))
    before = (store / "pilot.sqlite").read_bytes()
    with le.RawReader(store) as reader: failure(reader.read(ref()).diagnostics[0], "INTEGRITY_FAILURE", reason)
    assert (store / "pilot.sqlite").read_bytes() == before


def test_missing_store_readonly_cleanup_and_snapshot(store, tmp_path):
    missing = tmp_path / "TEST-ONLY absent ? #"
    with le.RawReader(missing) as reader: failure(reader.read(ref()).diagnostics[0], "UNKNOWN", "store unavailable")
    assert not missing.exists()
    with sqlite3.connect(store / "pilot.sqlite") as db: db.execute("PRAGMA journal_mode=WAL")
    put(store)
    with le.RawReader(store) as reader:
        connection = reader._db
        assert reader.read(ref()).field(("dimension",), DIMENSION).value == "composition"
        with pytest.raises(sqlite3.OperationalError, match="readonly database"):
            connection.execute("DELETE FROM artifacts")
        put(store, payload(revision=4, dimension="motion_plausibility"), revision=4)
        failure(reader.read(ref(revision=4)).diagnostics[0], "UNKNOWN", "missing exact target")
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"): connection.execute("SELECT 1")
    with le.RawReader(store) as later:
        assert later.read(ref(revision=4)).field(("dimension",), DIMENSION).value == "motion_plausibility"


def test_success_nonmutation_uri_escaping_and_exception_cleanup(store, tmp_path):
    put(store); unusual = tmp_path.parent / (tmp_path.name + " TEST-ONLY ? # workspace"); store.rename(unusual)
    before = (unusual / "pilot.sqlite").read_bytes()
    with pytest.raises(RuntimeError, match="TEST-ONLY consumer"):
        with le.RawReader(unusual) as reader:
            connection = reader._db
            assert reader.read(ref()).diagnostics == ()
            raise RuntimeError("TEST-ONLY consumer")
    assert (unusual / "pilot.sqlite").read_bytes() == before
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"): connection.execute("SELECT 1")
    failure(reader.read(ref()).diagnostics[0], "UNKNOWN", "session unavailable")


def test_admitted_fractional_records_and_predictions(tmp_path):
    from eval_lab.persistence import Repository
    from eval_lab import test_plans as tp
    from test_intent_v2 import anchors
    from test_assessments import evidence, observation
    from test_competing_sets import seed, competing
    from test_test_plans import form
    repo = Repository("sqlite:///" + str(tmp_path / "pilot.sqlite"))
    try:
        media, ingestion = anchors(repo)
        obs = observation(media, evidence(repo, media), dimension="composition"); repo.put(obs)
        fractional_media = media.model_copy(update={"id": "TEST-ONLY fractional media", "duration": 1.375}); repo.put(fractional_media)
        timeline = ingestion.model_copy(update={"id": "TEST-ONLY fractional timeline",
            "media": fractional_media.ref,
            "metadata": ingestion.metadata.model_copy(update={"duration_seconds": 1.375})}); repo.put(timeline)
        hypotheses = seed(repo)
        named = [hypotheses[0].model_copy(update={"id": "kind"}), hypotheses[1].model_copy(update={"id": "id"})]
        for item in named: repo.put(item)
        group = competing(named); repo.put(group)
        plan = tp.TestPlan(**form(group, predictions={"kind": ["TEST-ONLY-X"], "id": ["TEST-ONLY-Y"]})); repo.put(plan)
        frozen = tp.freeze(repo, "TEST-ONLY-plan@1")
    finally: repo.close()
    before = (tmp_path / "pilot.sqlite").read_bytes()
    with le.RawReader(tmp_path) as reader:
        record = reader.read(obs.ref.model_dump())
        assert record.diagnostics == () and record.field(("span",), le.SEQUENCE).value == [.2, .8]
        assert record.field(("dimension",), DIMENSION).value == "composition"
        assert reader.read(timeline.ref.model_dump()).field(("metadata", "duration_seconds"), DURATION).value == 1.375
        record = reader.read({"ref": frozen.ref.model_dump(), "sha256": frozen.digest}, pinned=True)
        assert record.diagnostics == ()
        assert record.field(("predictions",), le.MAPPING).value == {"kind": ["TEST-ONLY-X"], "id": ["TEST-ONLY-Y"]}
    assert (tmp_path / "pilot.sqlite").read_bytes() == before


@pytest.mark.parametrize("damage,state,reason", [("tamper", "INTEGRITY_FAILURE", "frozen digest mismatch"),
    ("missing", "UNKNOWN", "missing"), ("null", "UNKNOWN", "null"), ("malformed", "INTEGRITY_FAILURE", "malformed digest"),
    ("missing-time", "UNKNOWN", "missing"), ("null-time", "UNKNOWN", "null"),
    ("wrong-time", "INTEGRITY_FAILURE", "wrong type"), ("bad-time", "INTEGRITY_FAILURE", "freeze time"),
    ("naive-time", "INTEGRITY_FAILURE", "freeze time")])
def test_frozen_digest_independent_of_outer_hash(store, damage, state, reason):
    from eval_lab.test_plans import freeze_digest
    data = payload(frozen_at="2026-10-10T01:02:03Z", metadata={"duration_seconds": 2})
    data["frozen_digest"] = freeze_digest(data)
    if damage == "tamper": data["predictions"]["kind"] = ["TEST-ONLY tampered"]
    elif damage == "missing": del data["frozen_digest"]
    elif damage == "missing-time": del data["frozen_at"]
    elif damage in ("null-time", "wrong-time"): data["frozen_at"] = None if damage == "null-time" else 7
    elif damage in ("bad-time", "naive-time"): data["frozen_at"] = "TEST-ONLY bad time" if damage == "bad-time" else "2026-10-10T01:02:03"
    else: data["frozen_digest"] = None if damage == "null" else "TEST-ONLY bad digest"
    put(store, data, kind="TestPlan")  # Recomputed outer hash isolates freeze verification.
    with le.RawReader(store) as reader: failure(reader.read(ref(kind="TestPlan")).diagnostics[0], state, reason)


def test_repeated_diagnostics_are_stable(store):
    put(store, payload(dimension=None), sha256="e" * 64)
    with le.RawReader(store) as reader:
        one, two = reader.read(ref()), reader.read(ref())
        assert [(r.state, r.path, r.reason) for r in one.diagnostics] == [
            ("INTEGRITY_FAILURE", ("sha256",), "stored digest mismatch")]
        assert one.diagnostics == two.diagnostics
        assert one.field(("dimension",), DIMENSION) == two.field(("dimension",), DIMENSION)


def test_mapping_key_guard_and_nested_sequence_containers():
    failure(le.field({1: "TEST-ONLY key"}, (), le.MAPPING, subject="TEST-ONLY keys"),
            "INTEGRITY_FAILURE", "mapping keys")
    failure(le.field({"items": {}}, ("items", 0), le.TEXT, subject="TEST-ONLY list"),
            "INTEGRITY_FAILURE", "container")
    failure(le.field({"items": []}, ("items", -1), le.TEXT, subject="TEST-ONLY index"), "UNKNOWN", "missing")
    failure(le.field({"x": "  "}, ("x",), le.TEXT, subject="TEST-ONLY blank"), "INTEGRITY_FAILURE", "empty value")


@pytest.mark.parametrize("code,state,reason", [(sqlite3.SQLITE_BUSY, "UNKNOWN", "store unavailable"),
    (sqlite3.SQLITE_LOCKED, "UNKNOWN", "store unavailable"), (sqlite3.SQLITE_CANTOPEN, "UNKNOWN", "store unavailable"),
    (sqlite3.SQLITE_BUSY_RECOVERY, "UNKNOWN", "store unavailable"),
    (sqlite3.SQLITE_LOCKED_SHAREDCACHE, "UNKNOWN", "store unavailable"),
    (sqlite3.SQLITE_CORRUPT, "INTEGRITY_FAILURE", "store structure")])
def test_store_open_failure_classification_and_sanitization(tmp_path, monkeypatch, code, state, reason):
    (tmp_path / "pilot.sqlite").write_bytes(b"TEST-ONLY inaccessible store")
    def unavailable(*args, **kwargs):
        error = sqlite3.OperationalError("TEST-ONLY PRIVATE /secret/path")
        error.sqlite_errorcode = code
        raise error
    monkeypatch.setattr(le.sqlite3, "connect", unavailable)
    with le.RawReader(tmp_path) as reader:
        result = reader.read(ref()).diagnostics[0]
        failure(result, state, reason)
        assert "PRIVATE" not in result.reason and "/secret/path" not in result.reason


def test_failed_enter_closes_connection(store, monkeypatch):
    with sqlite3.connect(store / "pilot.sqlite") as db: db.execute("DROP TABLE artifacts")
    original = sqlite3.connect; captured = []
    def connect(*args, **kwargs):
        db = original(*args, **kwargs); captured.append(db); return db
    monkeypatch.setattr(le.sqlite3, "connect", connect)
    with le.RawReader(store) as reader:
        failure(reader.read(ref()).diagnostics[0], "INTEGRITY_FAILURE", "store structure")
        with pytest.raises(sqlite3.ProgrammingError, match="closed database"): captured[0].execute("SELECT 1")


@pytest.mark.parametrize("case", ["missing-time", "missing-digest", "missing-both", "null-pair"])
def test_draft_freeze_metadata_presence_contract(store, case):
    data = payload(frozen_at=None, frozen_digest=None)
    if case in ("missing-time", "missing-both"): del data["frozen_at"]
    if case in ("missing-digest", "missing-both"): del data["frozen_digest"]
    put(store, data, kind="TestPlan")
    with le.RawReader(store) as reader:
        record = reader.read(ref(kind="TestPlan"))
        if case == "null-pair": assert record.diagnostics == ()
        else:
            path = ("frozen_digest",) if case == "missing-digest" else ("frozen_at",)
            failure(next(d for d in record.diagnostics if d.path == path), "UNKNOWN", "missing")


@pytest.mark.parametrize("location", ["key", "value"])
def test_corrupt_unicode_retained_guard(store, location):
    data = payload()
    data["\ud800" if location == "key" else "note"] = "TEST-ONLY value" if location == "key" else "\ud800"
    put(store, data)
    with le.RawReader(store) as reader:
        failure(reader.read(ref()).diagnostics[0], "INTEGRITY_FAILURE", "malformed text")


def test_reader_reentry_does_not_leak_session(store):
    with le.RawReader(store) as reader:
        connection = reader._db
        with pytest.raises(RuntimeError, match="reader session already open"): reader.__enter__()
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"): connection.execute("SELECT 1")


def test_direct_corrupt_text_guard():
    failure(le.field({"x": "\udfff"}, ("x",), le.TEXT, subject="TEST-ONLY corrupt text"),
            "INTEGRITY_FAILURE", "malformed text")


@pytest.mark.parametrize("location", ["pin", "ref"])
def test_pin_envelope_keys_are_checked_independently(store, location):
    put(store)
    query = {"ref": ref(), "sha256": checksum(payload())}
    (query if location == "pin" else query["ref"])["extra"] = "TEST-ONLY extra field"
    with le.RawReader(store) as reader:
        failure(reader.read(query, pinned=True).diagnostics[0], "INTEGRITY_FAILURE", "reference keys")
