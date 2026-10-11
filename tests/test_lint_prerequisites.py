"""TEST-ONLY shared preparation: literal oracles, raw direct and retained paths."""
from copy import deepcopy
from collections import Counter
from hashlib import sha256
import json
import sqlite3
import pytest
from eval_lab import lint_evidence as le, lint_prerequisites as lp

def ref(kind="Evidence", identity="TEST-ONLY root", revision=3):
    return dict(kind=kind, id=identity, revision=revision)

def row(reference=None, **fields):
    r = ref() if reference is None else reference
    raw = dict(id=r["id"], revision=r["revision"], schema_version=2 if r["kind"] in
               ("IntentSpecV2", "IntentBinding", "RelationClaimV2") else 1, **fields)
    payload = json.dumps(raw, sort_keys=True, separators=(",", ":"))
    return dict(r, payload=payload, sha256=sha256(payload.encode()).hexdigest())

def pin(record):
    return {"ref": {k: record[k] for k in ("kind", "id", "revision")}, "sha256": record["sha256"]}

def declaration(name="leaf", **changes):
    return dict(name=name, group="TEST-ONLY shared", source="root", kind="Evidence", path=("note",),
                contract=le.TEXT, mode="field", target="Evidence", scope="none", depends=(), **{}) | changes

DEFAULT = object()

def run(source, declarations=DEFAULT, roots=DEFAULT, scopes=DEFAULT):
    return lp.prepare(source, [declaration()] if declarations is DEFAULT else declarations,
                      {"root": ref()} if roots is DEFAULT else roots, {} if scopes is DEFAULT else scopes,
                      group="TEST-ONLY shared")

def exact_error(action, expected, fragment):
    error = None
    try: action()
    except Exception as exc: error = exc
    assert type(error) is expected and fragment in str(error)

def first(record):
    assert record.diagnostics, "expected explicit diagnostic"
    return record.diagnostics[0]

def issue(result, subject, path, state, reason):
    assert type(result) is le.EvidenceResult
    assert (result.subject, result.path, result.state, result.reason, result.value) == (subject, path, state, reason, None)

def diagnostic(group, subject, path, state, reason):
    matches = [d for d in group.diagnostics if (d.subject, d.path, d.reason) == (subject, path, reason)]
    assert matches, group.diagnostics
    issue(matches[0], subject, path, state, reason)
    with pytest.raises(ValueError, match="unavailable prerequisite"): group.get("leaf")

@pytest.fixture(params=["direct", "retained"])
def adapter(request, tmp_path):
    opened = []
    def make(rows, inventory=None):
        if request.param == "direct": return lp.DirectRecords(rows, inventory)
        root = tmp_path / str(len(opened)); root.mkdir()
        with sqlite3.connect(root / "pilot.sqlite") as db:
            db.execute("CREATE TABLE schema_migrations(version INTEGER)"); db.execute("INSERT INTO schema_migrations VALUES(1)")
            db.execute("CREATE TABLE artifacts(kind TEXT,id TEXT,revision INTEGER,sha256 TEXT,payload TEXT)")
            for r in rows: db.execute("INSERT INTO artifacts VALUES(:kind,:id,:revision,:sha256,:payload)", r)
        reader = le.RawReader(root).__enter__(); opened.append(reader)
        return reader
    yield make
    for reader in opened: reader.__exit__()

META = [("name", "leaf", 7), ("group", "TEST-ONLY shared", 8), ("source", "root", 9),
        ("kind", "Evidence", 10), ("path", ("note",), 11), ("contract", le.TEXT, 12),
        ("mode", "field", 13), ("target", "Evidence", 14), ("scope", "none", 15), ("depends", (), 16)]
VARIANTS = [("missing", "UNKNOWN", "missing required field"), ("null", "UNKNOWN", "null required field"),
            ("malformed", "INTEGRITY_FAILURE", "wrong type"), ("valid", "AVAILABLE", "")]

@pytest.mark.parametrize("key,valid,bad", META)
@pytest.mark.parametrize("case,state,reason", VARIANTS)
def test_shared_declaration_contract(key, valid, bad, case, state, reason):
    d = declaration()
    if case == "missing": del d[key]
    else: d[key] = None if case == "null" else bad if case == "malformed" else valid
    g = run(lp.DirectRecords([row(note="TEST-ONLY checked")], {}), [d])
    if case == "valid": assert g.get("leaf")[0].value == "TEST-ONLY checked"
    else: issue(first(g), "declarations", (0, key), state, reason)

@pytest.mark.parametrize("changes,path,reason", [
    ({"path": (False,)}, (0, "path", 0), "wrong type"), ({"path": (-1,)}, (0, "path", 0), "below minimum"),
    ({"depends": (9,)}, (0, "depends", 0), "wrong type"),
    ({"depends": ("missing",)}, (0, "depends"), "unresolved dependency"),
    ({"source": "other"}, (0, "source"), "source must be a declared dependency or root"),
    ({"depends": ("leaf",)}, (), "declaration cycle"),
])
def test_shared_declaration_graph(changes, path, reason):
    g = run(lp.DirectRecords([row(note="TEST-ONLY checked")], {}), [declaration(**changes)])
    issue(first(g), "declarations", path, "INTEGRITY_FAILURE", reason)

def test_shared_duplicate_declarations_and_valid_dependencies():
    source = lp.DirectRecords([row(note="TEST-ONLY checked")], {})
    issue(first(run(source, [declaration(), declaration()])), "declarations", (1, "name"),
          "INTEGRITY_FAILURE", "duplicate declaration")
    g = run(source, [declaration("second", depends=("leaf",)), declaration()])
    assert g.consumed == ("leaf", "second") and g.get("second")[0].value == "TEST-ONLY checked"

@pytest.mark.parametrize("path,contract,valid,bad", [
    (("note",), le.TEXT, "TEST-ONLY checked", 4), (("bag",), le.MAPPING, {"secret": object}, []),
    (("items",), le.SEQUENCE, [], {}), (("active",), le.BOOLEAN, False, 0),
    (("count",), le.Contract((int,), minimum=0), 0, "0"),
    (("items", 0, "count"), le.Contract((int,), minimum=0), 0, "0")])
@pytest.mark.parametrize("case,state,reason", VARIANTS)
def test_shared_traversal_contract(adapter, path, contract, valid, bad, case, state, reason):
    valid = {"secret": "TEST-ONLY unchecked"} if path == ("bag",) else valid
    data = {path[-1]: None if case == "null" else bad if case == "malformed" else valid}
    if case == "missing": data = {}
    if len(path) == 3: data = {"items": [data]}
    g = run(adapter([row(**data)]), [declaration(path=path, contract=contract)])
    if case == "valid":
        expected = ("secret",) if path == ("bag",) else () if path == ("items",) else valid
        assert g.get("leaf")[0].value == expected
    else: diagnostic(g, "Evidence:TEST-ONLY root@3", path, state, reason)

def test_checked_output_has_no_unchecked_descendants(adapter):
    data = row(note="TEST-ONLY checked", bag={"kind": "TEST-ONLY not a Ref", "id": None, "revision": -8})
    g = run(adapter([data]), [declaration(path=("bag",), contract=le.MAPPING)])
    assert g.get("leaf")[0].value == ("id", "kind", "revision")
    assert not hasattr(g, "diagnostic_raw")

def test_shared_access_is_declared_and_consumed(monkeypatch):
    calls = []; original = le.RawRecord.field
    def observed(self, path, contract):
        calls.append((self.subject, path)); return original(self, path, contract)
    monkeypatch.setattr(le.RawRecord, "field", observed)
    g = run(lp.DirectRecords([row(note="TEST-ONLY checked", count=0)], {}),
            [declaration(), declaration("count", path=("count",), contract=le.Contract((int,), minimum=0))])
    assert calls == [("Evidence:TEST-ONLY root@3", ("count",)), ("Evidence:TEST-ONLY root@3", ("note",))]
    assert g.consumed == ("count", "leaf")
    exact_error(lambda: g.get("absent"), KeyError, "undeclared prerequisite")
    g._values.pop("leaf")
    exact_error(lambda: g.get("leaf"), RuntimeError, "unconsumed prerequisite")

@pytest.mark.parametrize("mode", ["ref", "pin"])
@pytest.mark.parametrize("component", ["kind", "id", "revision", "ref", "sha256"])
@pytest.mark.parametrize("case,state,reason", VARIANTS)
def test_shared_exact_dependency_contract(adapter, mode, component, case, state, reason):
    if mode == "ref" and component in ("ref", "sha256"): return  # Not a Ref component.
    target = row(ref("MediaAsset", "TEST-ONLY media", 5), note="TEST-ONLY target")
    value = pin(target) if mode == "pin" else pin(target)["ref"]
    holder = value["ref"] if mode == "pin" and component not in ("ref", "sha256") else value
    if case == "missing": del holder[component]
    elif case != "valid": holder[component] = None if case == "null" else False
    g = run(adapter([row(link=value), target]), [declaration(path=("link",), contract=le.MAPPING, mode=mode, target="MediaAsset")])
    if case == "valid": assert g.get("leaf")[0].value == ("MediaAsset", "TEST-ONLY media", 5)
    else: diagnostic(g, "reference", (component,), state, reason)

@pytest.mark.parametrize("damage,subject,path,state,reason", [
    ("wrong-kind", "reference", ("kind",), "INTEGRITY_FAILURE", "unsupported value"),
    ("missing-exact", "MediaAsset:TEST-ONLY media@6", (), "UNKNOWN", "missing exact target"),
    ("bad-pin", "MediaAsset:TEST-ONLY media@5", ("sha256",), "INTEGRITY_FAILURE", "pin digest mismatch")])
def test_shared_edge_obligations(adapter, damage, subject, path, state, reason):
    target = row(ref("MediaAsset", "TEST-ONLY media", 5)); value = pin(target)
    if damage == "wrong-kind": value["ref"]["kind"] = "Evidence"
    if damage == "missing-exact": value["ref"]["revision"] = 6
    if damage == "bad-pin": value["sha256"] = "f" * 64
    g = run(adapter([row(link=value), target]), [declaration(path=("link",), contract=le.MAPPING, mode="pin", target="MediaAsset")])
    diagnostic(g, subject, path, state, reason)

@pytest.mark.parametrize("mode", ["ref", "pin"])
def test_shared_data_mapping_is_not_a_reference_and_revisits(adapter, mode):
    root = row(link=ref(), note="TEST-ONLY cycle", bag={"kind": "TEST-ONLY", "id": 0, "revision": -1})
    # A self Ref is finite under the declaration DAG; independently pinned revisits use two roots.
    g = run(adapter([root]), [declaration(path=("link",), contract=le.MAPPING, mode="ref"),
            declaration("again", source="leaf", depends=("leaf",), path=("link",), contract=le.MAPPING, mode="ref"),
            declaration("data", path=("bag",), contract=le.MAPPING)])
    assert g.get("again")[0].value == ("Evidence", "TEST-ONLY root", 3)
    assert g.get("data")[0].value == ("id", "kind", "revision")
    assert g.visited == (("Evidence", "TEST-ONLY root", 3),)
    target = row(ref("MediaAsset", "TEST-ONLY media", 5)); good = pin(target); bad = deepcopy(good); bad["sha256"] = "e" * 64
    g = run(adapter([row(a=good, b=bad), target]), [declaration(path=("a",), mode="pin", contract=le.MAPPING, target="MediaAsset"),
        declaration("bad", path=("b",), mode="pin", contract=le.MAPPING, target="MediaAsset")])
    diagnostic(g, "MediaAsset:TEST-ONLY media@5", ("sha256",), "INTEGRITY_FAILURE", "pin digest mismatch")

@pytest.mark.parametrize("kind,version,state,reason", [("IntentSpecV2", 2, "AVAILABLE", ""),
    ("IntentBinding", 2, "AVAILABLE", ""), ("RelationClaimV2", 2, "AVAILABLE", ""),
    ("IntentSpecV2", 1, "INTEGRITY_FAILURE", "unsupported value"), ("IntentBinding", 3, "INTEGRITY_FAILURE", "unsupported value"),
    ("RelationClaimV2", 1, "INTEGRITY_FAILURE", "unsupported value"), ("MediaAsset", 2, "INTEGRITY_FAILURE", "unsupported value")])
def test_shared_v2_versions(adapter, kind, version, state, reason):
    r = row(ref(kind, "TEST-ONLY version", 7), note="TEST-ONLY checked")
    raw = json.loads(r["payload"]); raw["schema_version"] = version
    r["payload"] = json.dumps(raw, sort_keys=True, separators=(",", ":")); r["sha256"] = sha256(r["payload"].encode()).hexdigest()
    record = adapter([r]).read(pin(r)["ref"])
    if state == "AVAILABLE": assert record.field(("note",), le.TEXT).value == "TEST-ONLY checked"
    else: issue(first(record), kind + ":TEST-ONLY version@7", ("schema_version",), state, reason)

@pytest.mark.parametrize("key,bad", [("id", 9), ("revision", "3"), ("schema_version", False)])
@pytest.mark.parametrize("case,state,reason", VARIANTS)
def test_shared_record_identity_contract(adapter, key, bad, case, state, reason):
    r = row(note="TEST-ONLY checked"); data = json.loads(r["payload"])
    if case == "missing": del data[key]
    elif case != "valid": data[key] = None if case == "null" else bad
    r["payload"] = json.dumps(data, sort_keys=True, separators=(",", ":")); r["sha256"] = sha256(r["payload"].encode()).hexdigest()
    g = run(adapter([r]))
    if case == "valid": assert g.get("leaf")[0].value == "TEST-ONLY checked"
    else: diagnostic(g, "Evidence:TEST-ONLY root@3", (key,), state, reason)

@pytest.mark.parametrize("key,bad,reason", [("id", "TEST-ONLY wrong", "payload identity mismatch"),
    ("revision", 8, "payload identity mismatch"), ("sha256", "d" * 64, "stored digest mismatch")])
def test_shared_identity_mismatch_and_record_failure(adapter, key, bad, reason):
    r = row()
    if key == "sha256": r[key] = bad
    else:
        data = json.loads(r["payload"]); data[key] = bad
        r["payload"] = json.dumps(data, sort_keys=True, separators=(",", ":")); r["sha256"] = sha256(r["payload"].encode()).hexdigest()
    g = run(adapter([r]))
    diagnostic(g, "Evidence:TEST-ONLY root@3", (key,), "INTEGRITY_FAILURE", reason)
    diagnostic(g, "Evidence:TEST-ONLY root@3", ("note",), "UNKNOWN", "missing required field")

def collection():
    return declaration(source="universe", kind="Evidence", path=("media",), contract=le.MAPPING,
                       mode="collection", target="MediaAsset", scope="media")

@pytest.mark.parametrize("damage,state,reason", [("missing", "UNKNOWN", "missing required field"),
    ("null", "UNKNOWN", "null required field"), ("malformed", "INTEGRITY_FAILURE", "wrong type"),
    ("omitted", "INTEGRITY_FAILURE", "inventory membership mismatch"),
    ("duplicate", "INTEGRITY_FAILURE", "duplicate inventory member"),
    ("missing-member", "UNKNOWN", "missing exact target"), ("valid", "AVAILABLE", "")])
def test_shared_collection_completeness(damage, state, reason):
    media = row(ref("MediaAsset", "TEST-ONLY scope", 9)); member = row(media=pin(media)["ref"])
    inventory = {} if damage == "missing" else {"leaf": None if damage == "null" else 4 if damage == "malformed" else
        [] if damage == "omitted" else [ref(), ref()] if damage == "duplicate" else [ref(identity="TEST-ONLY absent")] if damage == "missing-member" else [ref()]}
    inventory["complete"] = True  # Never substitutes for checked membership.
    g = run(lp.DirectRecords([media, member], inventory), [collection()], scopes={"media": pin(media)})
    if damage == "valid": assert g.get("leaf")[0].value == (("Evidence", "TEST-ONLY root", 3),)
    elif damage == "missing-member": diagnostic(g, "Evidence:TEST-ONLY absent@3", (), state, reason)
    else: diagnostic(g, "inventory", ("leaf",), state, reason)

@pytest.mark.parametrize("scope,kind", [("media", "MediaAsset"), ("intent", "IntentSpecV2")])
@pytest.mark.parametrize("damage,state,reason", [("missing", "UNKNOWN", "missing required field"),
    ("null", "UNKNOWN", "null required field"), ("malformed", "INTEGRITY_FAILURE", "wrong type"),
    ("identity", "INTEGRITY_FAILURE", "scope correspondence mismatch"),
    ("revision", "INTEGRITY_FAILURE", "scope correspondence mismatch"), ("valid", "AVAILABLE", "")])
def test_shared_scope_correspondence(adapter, scope, kind, damage, state, reason):
    expected = row(ref(kind, "TEST-ONLY scope", 9)); actual = row(ref(kind,
        "TEST-ONLY other" if damage == "identity" else "TEST-ONLY scope", 10 if damage == "revision" else 9))
    scopes = {} if damage == "missing" else {scope: None if damage == "null" else 4 if damage == "malformed" else pin(expected)}
    rows = [row(link=pin(actual)), expected] + ([actual] if damage in ("identity", "revision") else [])
    g = run(adapter(rows), [declaration(path=("link",), contract=le.MAPPING, mode="pin", target=kind, scope=scope)], scopes=scopes)
    if damage == "valid": assert g.get("leaf")[0].value == (kind, "TEST-ONLY scope", 9)
    elif damage in ("identity", "revision"): diagnostic(g, "Evidence:TEST-ONLY root@3", ("link",), state, reason)
    else: diagnostic(g, "scopes", (scope,), state, reason)

def test_shared_group_cannot_be_all_rule_context():
    for rows, declarations in [([row(note="TEST-ONLY checked")], [declaration()]), ([], [declaration()]), ([], [])]:
        g = run(lp.DirectRecords(rows, {}), declarations)
        assert g.group == "TEST-ONLY shared"
        assert not any(hasattr(g, name) for name in ("ready", "complete", "context", "verdict", "status"))

def test_shared_preparation_preserves_inputs_and_diagnostics_repeat(adapter):
    rows = [row(ref("MediaAsset", "TEST-ONLY scope", 9)), row(media=ref("MediaAsset", "TEST-ONLY scope", 9))]
    original = deepcopy(rows); inventory = {"leaf": [ref()]}
    results = []
    for ordered in (rows, rows[::-1], rows):
        reader = adapter(ordered, inventory); before = (reader.root / "pilot.sqlite").read_bytes() if isinstance(reader, le.RawReader) and not isinstance(reader, lp.DirectRecords) else None
        g = run(reader, [collection()], scopes={"media": pin(rows[0])})
        assert g.diagnostics == () and g.get("leaf")[0].value == (("Evidence", "TEST-ONLY root", 3),)
        results.append((g.diagnostics, g.get("leaf")))
        if before is not None: assert (reader.root / "pilot.sqlite").read_bytes() == before
    assert results[0] == results[1] == results[2] and rows == original and inventory == {"leaf": [ref()]}

def test_shared_inventory_exact():
    assert tuple(lp.METADATA) == ("name", "group", "source", "kind", "path", "contract", "mode", "target", "scope", "depends")
    assert lp.INVENTORY == ("declarations", "name", "group", "source", "kind", "path", "contract", "mode", "target", "scope", "depends",
        "path.component", "depends.component", "roots", "source.kind", "universe", "envelope", "kind", "id", "revision", "payload",
        "payload.id", "payload.revision", "schema_version", "sha256", "reference", "reference.kind", "reference.id", "reference.revision",
        "pin.ref", "pin.sha256", "scopes", "scope.pin", "scope.kind", "membership", "inventory", "inventory.member")

@pytest.mark.parametrize("location,bad,path,reason", [
    ("universe", None, (), "null required field"), ("universe", {}, (), "wrong type"),
    ("row", None, (0,), "null required field"), ("row", [], (0,), "wrong type"),
    ("duplicate", None, (1,), "duplicate exact identity")])
def test_shared_universe_guards(location, bad, path, reason):
    rows = bad if location == "universe" else [bad] if location == "row" else [row(), row()]
    g = run(lp.DirectRecords(rows, {}))
    diagnostic(g, "universe", path, "UNKNOWN" if reason == "null required field" else "INTEGRITY_FAILURE", reason)

@pytest.mark.parametrize("key,bad", [("kind", 7), ("id", 8), ("revision", "3")])
@pytest.mark.parametrize("case,state,reason", VARIANTS)
def test_shared_envelope_contract(key, bad, case, state, reason):
    r = row(note="TEST-ONLY checked")
    if case == "missing": del r[key]
    elif case != "valid": r[key] = None if case == "null" else bad
    g = run(lp.DirectRecords([r], {}))
    if case == "valid": assert g.get("leaf")[0].value == "TEST-ONLY checked"
    else: diagnostic(g, "universe", (0, key), state, reason)

@pytest.mark.parametrize("key,bad", [("payload", 7), ("sha256", 8)])
@pytest.mark.parametrize("case,state,reason", VARIANTS)
def test_shared_raw_envelope_contract(key, bad, case, state, reason):
    r = row(note="TEST-ONLY checked")
    if case == "missing": del r[key]
    elif case != "valid": r[key] = None if case == "null" else bad
    g = run(lp.DirectRecords([r], {}))
    if case == "valid": assert g.get("leaf")[0].value == "TEST-ONLY checked"
    else: diagnostic(g, "Evidence:TEST-ONLY root@3", (key,), state, reason)

@pytest.mark.parametrize("case,state,reason", VARIANTS)
@pytest.mark.parametrize("operand", ["membership", "scope", "inventory-member", "roots", "declarations"])
def test_shared_container_contract(adapter, case, state, reason, operand):
    media = row(ref("MediaAsset", "TEST-ONLY scope", 9)); member = row(media=pin(media)["ref"], note="TEST-ONLY checked")
    bad = None if case == "null" else 4
    if operand == "membership":
        if case == "missing": member = row(note="TEST-ONLY checked")
        elif case != "valid": member = row(media=bad)
    scopes = {"media": pin(media)}; ds = [collection()]; roots = {"root": ref()}; inv = {"leaf": [ref()]}
    if operand == "scope" and case != "valid": scopes = {} if case == "missing" else {"media": bad}
    if operand == "inventory-member" and case != "valid": inv = {"leaf": [{} if case == "missing" else bad]}
    if operand == "roots":
        ds = [declaration()]
        if case != "valid": roots = {} if case == "missing" else bad
    if operand == "declarations" and case != "valid": ds = le._MISSING if case == "missing" else bad
    source = lp.DirectRecords([media, member], inv) if operand == "inventory-member" else adapter([media, member], inv)
    g = run(source, ds, roots, scopes)
    if case == "valid": assert g.diagnostics == ()
    elif operand == "membership": diagnostic(g, "Evidence:TEST-ONLY root@3", ("media",), state, reason)
    elif operand == "scope": diagnostic(g, "scopes", ("media",), state, reason)
    elif operand == "inventory-member": diagnostic(g, "reference", ("kind",) if case == "missing" else (), state, reason)
    elif operand == "roots" and case != "missing": issue(first(g), "roots", ("root",) if case == "missing" else (), state, reason)
    elif operand == "roots": diagnostic(g, "roots", ("root",), state, reason)
    else: issue(first(g), "declarations", (), state, reason)

@pytest.mark.parametrize("damage", ["empty", "other-scope", "bad-member", "missing-scope", "wrong-scope-kind", "wrong-source-kind"])
def test_shared_scoped_collection_controls(adapter, damage):
    media = row(ref("MediaAsset", "TEST-ONLY scope", 9)); other = row(ref("MediaAsset", "TEST-ONLY other", 10))
    rows = [media, other]; scopes = {"media": pin(media)}; ds = [collection()]; inv = {"leaf": []}
    if damage == "other-scope": rows.append(row(media=pin(other)["ref"]))
    if damage == "bad-member": rows.append(row(media=pin(media)["ref"]) | {"sha256": "c" * 64})
    if damage == "missing-scope": ds = [collection() | {"scope": "none"}]
    if damage == "wrong-scope-kind": scopes["media"] = pin(row(ref("Evidence", "TEST-ONLY wrong", 11))); rows.append(row(ref("Evidence", "TEST-ONLY wrong", 11)))
    if damage == "wrong-source-kind": ds = [declaration(kind="MediaAsset")]; rows.append(row(note="TEST-ONLY checked"))
    g = run(adapter(rows, inv), ds, scopes=scopes)
    if damage in ("empty", "other-scope"): assert g.get("leaf")[0].value == () and g.diagnostics == ()
    elif damage == "bad-member": diagnostic(g, "Evidence:TEST-ONLY root@3", ("sha256",), "INTEGRITY_FAILURE", "stored digest mismatch")
    elif damage == "missing-scope": diagnostic(g, "declarations", ("leaf", "scope"), "INTEGRITY_FAILURE", "collection requires scope")
    else: diagnostic(g, "reference", ("kind",), "INTEGRITY_FAILURE", "unsupported value")

def test_shared_retained_enumeration(tmp_path, monkeypatch):
    with le.RawReader(tmp_path / "TEST-ONLY absent") as reader:
        issue(reader.rows(), "store", (), "UNKNOWN", "store unavailable")
        g = run(reader, [collection()]); diagnostic(g, "store", (), "UNKNOWN", "store unavailable")
    assert not (tmp_path / "TEST-ONLY absent").exists()
    class Broken:
        def execute(self, sql): raise sqlite3.OperationalError("TEST-ONLY PRIVATE path")
    reader = le.RawReader(tmp_path); reader._db = Broken(); reader._issue = None
    issue(reader.rows(), "store", (), "INTEGRITY_FAILURE", "malformed store structure")

def test_shared_all_metadata_boundary_consumption(monkeypatch):
    seen = []; original = le.field
    def observe(raw, path, contract, *, subject):
        seen.append((subject, path)); return original(raw, path, contract, subject=subject)
    monkeypatch.setattr(le, "field", observe)
    run(lp.DirectRecords([row(note="TEST-ONLY checked")], {}))
    assert [p for s, p in seen if s == "declarations"] == [(), (), ("name",), ("group",), ("source",), ("kind",),
        ("path",), ("contract",), ("mode",), ("target",), ("scope",), ("depends",), ()]

def test_shared_diagnostics_repeat_and_order(adapter):
    media = row(ref("MediaAsset", "TEST-ONLY scope", 9)); member = row(media=None)
    results = [run(adapter(rows, {"leaf": []}), [collection()], scopes={"media": pin(media)}) for rows in ([media, member], [member, media])]
    expected = (le.EvidenceResult("UNKNOWN", "Evidence:TEST-ONLY root@3", ("media",), "null required field"),)
    assert results[0].diagnostics == results[1].diagnostics == expected

def test_shared_empty_collection_dependency(adapter):
    media = row(ref("MediaAsset", "TEST-ONLY scope", 9))
    g = run(adapter([media], {"leaf": []}), [collection(), declaration("child", source="leaf", depends=("leaf",))], scopes={"media": pin(media)})
    assert g.diagnostics == () and g.get("child") == ()

@pytest.mark.parametrize("bad", [None, {}, [], False])
def test_shared_malformed_dependency_never_crashes(bad):
    g = run(lp.DirectRecords([], {}), [declaration(depends=(bad,))])
    issue(first(g), "declarations", (0, "depends", 0), "UNKNOWN" if bad is None else "INTEGRITY_FAILURE",
          "null required field" if bad is None else "wrong type")

def test_shared_dependent_source_kind(adapter):
    source = row(link=ref(), note="TEST-ONLY checked")
    g = run(adapter([source]), [declaration(path=("link",), mode="ref", contract=le.MAPPING),
            declaration("different", source="leaf", depends=("leaf",), kind="MediaAsset")])
    diagnostic(g, "Evidence:TEST-ONLY root@3", ("note",), "INTEGRITY_FAILURE", "unsupported value")

@pytest.mark.parametrize("case,state,reason", VARIANTS)
def test_shared_parent_traversal(adapter, case, state, reason):
    data = {} if case == "missing" else {"items": None if case == "null" else {} if case == "malformed" else [{"count": 0}]}
    g = run(adapter([row(**data)]), [declaration(path=("items", 0, "count"), contract=le.Contract((int,), minimum=0))])
    if case == "valid": assert g.get("leaf")[0].value == 0
    else: diagnostic(g, "Evidence:TEST-ONLY root@3", ("items", 0, "count"), state, "malformed container" if case == "malformed" else reason)

# Each mutant is a disposable in-memory module copy; accepted source and tests stay intact.
MUTATIONS = [
    ("lp", 'result = record.field(d["path"], d["contract"])', 'cache = locals().get("cache", {}); key = (record.subject, d["path"]); result = cache[key] if key in cache else record.field(d["path"], d["contract"]); cache[key] = result', 'test_shared_repeated_field_contract or test_shared_every_active_boundary', 'path-only-cache'),
    ("lp", 'result = record.field(d["path"], d["contract"])', 'cache = locals().get("cache", {}); key = (record.subject, d["path"], d["contract"]); result = cache[key] if key in cache else record.field(d["path"], d["contract"]); cache[key] = result', 'test_shared_every_active_boundary', 'same-contract-cache'),
    ("lp", 'diagnostics.append(_bad(name, d["path"], "dependency unavailable", "UNKNOWN"))', 'pass', 'test_shared_dependency_unavailable', 'dependency-unavailable'),
    ("lp", 'if key in seen:', 'if False:', 'test_shared_universe_guards', 'duplicate-identity'),
    ("lp", 'if shape.state != "AVAILABLE":', 'if False:', 'test_shared_universe_guards', 'envelope-shape'),
    ("lp", 'if part.state != "AVAILABLE":', 'if False:', 'test_shared_envelope_contract and null', 'envelope-components'),
    ("lp", 'if name not in self.declared:', 'if False:', 'test_shared_access_is_declared_and_consumed', 'undeclared-access'),
    ("lp", 'if set(self._values) != set(self.declared) or self.consumed != self.declared:', 'if False:', 'test_shared_access_is_declared_and_consumed', 'unconsumed-access'),
    ("lp", 'if self.diagnostics: raise', 'if False: raise', 'test_shared_traversal_contract and null', 'unavailable-access'),
    ("lp", 'if d["name"] in specs:', 'if False:', 'test_shared_duplicate_declarations_and_valid_dependencies', 'duplicate-declaration'),
    ("lp", 'fail("declarations", (i, "depends"), "unresolved dependency")', 'pass', 'test_shared_declaration_graph', 'unresolved-dependency'),
    ("lp", 'fail("declarations", (i, "source"), "source must be a declared dependency or root")', 'pass', 'test_shared_declaration_graph', 'source-dependency'),
    ("lp", 'fail("declarations", (), "declaration cycle"); break', 'break', 'test_shared_declaration_graph', 'cycle'),
    ("lp", 'consumed.append(name)', 'pass', 'test_shared_access_is_declared_and_consumed', 'consumption'),
    ("lp", 'value=safe', 'value=raw', 'test_checked_output_has_no_unchecked_descendants', 'container-projection'),
    ("lp", 'if scope_nodes and target != scope_nodes[0][0]:', 'if False:', 'test_shared_scope_correspondence and identity', 'correspondence'),
    ("lp", 'if d["scope"] == "none": fail', 'if False: fail', 'test_shared_scoped_collection_controls and missing-scope', 'collection-scope'),
    ("lp", 'if len(set(declared_members)) != len(declared_members):', 'if False:', 'test_shared_collection_completeness and duplicate', 'inventory-duplicate'),
    ("lp", 'if inventory is not None and len(diagnostics) == start and tuple(sorted(declared_members)) != members:', 'if False:', 'test_shared_collection_completeness and omitted', 'inventory-membership'),
    ("lp", 'choices=(target,)', 'choices=tuple(le.ARTIFACT_TYPES)', 'test_shared_edge_obligations and wrong-kind', 'target-kind'),
    ("lp", 'choices=(d["kind"],)', 'choices=tuple(le.ARTIFACT_TYPES)', 'test_shared_dependent_source_kind', 'source-kind'),
    ("lp", '        if d["scope"] != "none":\n            scope_map', '        if False:\n            scope_map', 'test_shared_scope_correspondence and null', 'scope-consumption'),
    ("lp", 'if request["kind"] == d["kind"]:', 'if False:', 'test_shared_scoped_collection_controls and bad-member', 'member-integrity'),
    ("lp", 'if shape.state != "AVAILABLE":', 'if False:', 'test_shared_universe_guards and row', 'enumeration-element'),
    ("le", 'version = 2 if kind in ("IntentSpecV2", "IntentBinding", "RelationClaimV2") else 1', 'version = 1', 'test_shared_v2_versions', 'v2-version'),
    ("le", 'if stored_hash is not None and stored_hash != digest:', 'if False:', 'test_shared_identity_mismatch_and_record_failure and sha256', 'stored-integrity'),
    ("le", 'if supplied_hash is not None and supplied_hash != digest:', 'if False:', 'test_shared_edge_obligations and bad-pin', 'pin-integrity'),
    ("le", 'if value is not None and value != expected: fail((name,), "payload identity mismatch")', 'if False: fail((name,), "payload identity mismatch")', 'test_shared_identity_mismatch_and_record_failure and not sha256', 'payload-identity'),
    ("lp", 'scope=le.Contract((str,), choices=("none", "media", "intent"))', 'scope=le.TEXT', 'test_shared_metadata_vocabulary', 'scope-vocabulary'),
    ("lp", 'fail("declarations", (i, "source"), "source is not a record dependency")', 'pass', 'test_shared_source_declaration_semantics and scalar-source', 'record-source'),
    ("lp", 'if d["name"] in roots or d["name"] in ("root", "universe"):', 'if False:', 'test_shared_source_declaration_semantics and shadow', 'source-shadow'),
    ("lp", 'check(group, (), le.TEXT, "group")', 'pass', 'test_shared_group_identity_contract', 'group-identity'),
    ("lp", 'INVENTORY = (', 'METADATA.pop("scope")\nINVENTORY = (', 'test_shared_inventory_exact', 'inventory-declaration'),
    ("lp", 'for j, dep in enumerate(d["depends"]): check(dep, (), le.TEXT, "declarations", (i, "depends", j))', 'pass', 'test_shared_malformed_dependency_never_crashes', 'dependency-component'),
    ("lp", 'check(part, (), le.Contract((str, int), minimum=0) if type(part) is int else le.Contract((str,)),\n                  "declarations", (i, "path", j))', 'pass', 'test_shared_declaration_graph', 'path-component'),
    ("le", 'if self._issue is not None: return self._issue', 'if self._issue is not None: return field([], (), SEQUENCE, subject="universe")', 'test_shared_retained_enumeration', 'enumeration-unavailable'),
    ("le", 'return self._store_error(exc)', 'return field([], (), SEQUENCE, subject="universe")', 'test_shared_retained_enumeration', 'enumeration-integrity'),

    ("lp", 'fail("declarations", (i, "source"), "collection requires universe source")', 'pass', 'test_shared_collection_declaration_semantics', 'collection-source'),
    ("lp", 'fail("declarations", (i, "target"), "scope target kind mismatch")', 'pass', 'test_shared_collection_declaration_semantics', 'scope-target'),
    ("lp", 'if d["mode"] == "field": fail', 'if False: fail', 'test_shared_collection_declaration_semantics', 'field-scope'),
    ("lp", 'if check(item, (), le.MAPPING, "declarations", (i,)) is None: continue', 'pass', 'test_shared_outer_containers and declaration and null', 'declaration-container'),
    ("lp", 'scope_map = check(scopes, (), le.MAPPING, "scopes")', 'scope_map = scopes', 'test_shared_outer_containers and scopes and null', 'scope-container'),
    ("lp", 'inventory_map = check(source.inventory, (), le.MAPPING, "inventory")', 'inventory_map = source.inventory', 'test_shared_outer_containers and inventory and null', 'inventory-container'),
    ("lp", 'tuple(sorted(scope_ids.items())) if not diagnostics else ()', 'tuple(sorted(scope_ids.items()))', 'test_shared_group_identifies_only_checked_scope', 'failed-scope-output'),

    ("lp", 'result = record.field(d["path"], d["contract"])', 'result = le.field(record.diagnostic_raw, d["path"], d["contract"], subject=record.subject)', 'test_shared_access_is_declared_and_consumed', 'actual-field-consumption'),
    ("lp", 'if (r["kind"], r["id"], r["revision"]) == (kind, identity, revision)', 'if (r["kind"], r["id"]) == (kind, identity)', 'test_shared_exact_non_head_control', 'exact-direct-revision'),

    ("lp", 'd["name"] in ("root", "universe")', 'd["name"] == "universe"', 'test_shared_root_name_reserved_without_root_input', 'reserved-root-name'),
]

@pytest.mark.parametrize("module,old,new,selection,guard", MUTATIONS, ids=[m[4] for m in MUTATIONS])
def test_shared_guard_deletion(module, old, new, selection, guard):
    import os
    from pathlib import Path
    import subprocess
    import sys
    program = '''import json, sys, pytest
from pathlib import Path
from eval_lab import lint_evidence as le
if sys.argv[1] == "le":
    source = Path(le.__file__).read_text(); assert source.count(sys.argv[2]) == 1
    exec(compile(source.replace(sys.argv[2], sys.argv[3]), le.__file__, "exec"), le.__dict__)
from eval_lab import lint_prerequisites as lp
if sys.argv[1] == "lp":
    source = Path(lp.__file__).read_text(); assert source.count(sys.argv[2]) == 1
    exec(compile(source.replace(sys.argv[2], sys.argv[3]), lp.__file__, "exec"), lp.__dict__)
class Outcome:
    errors = []
    messages = []
    def pytest_runtest_makereport(self, item, call):
        if call.excinfo: self.errors.append((call.when, call.excinfo.type.__name__))
        if call.excinfo: self.messages.append(str(call.excinfo.value))
outcome = Outcome()
code = pytest.main(["tests/test_lint_prerequisites.py", "-q", "-p", "no:cacheprovider", "-k", sys.argv[4]], plugins=[outcome])
assert code == 1 and outcome.errors and all(when == "call" and kind in ("AssertionError", "Failed") for when, kind in outcome.errors), (code, outcome.errors)
expected = {"path-only-cache": {"per-declaration boundary obligations": 2, "second declaration contract": 2},
            "same-contract-cache": {"per-declaration boundary obligations": 2}, "dependency-unavailable": {"dependency unavailable diagnostic required": 6}}.get(sys.argv[5])
if expected:
    assert {fragment: sum(fragment in message for message in outcome.messages) for fragment in expected} == expected and len(outcome.messages) == sum(expected.values()), outcome.messages
print("TEST-ONLY mutation killed by expected assertions")
'''
    result = subprocess.run([sys.executable, "-c", program, module, old, new, selection, guard], cwd=Path(__file__).resolve().parents[1],
        env=dict(os.environ, PYTHONPATH="src", PYTHONDONTWRITEBYTECODE="1"), text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, guard + "\n" + result.stdout + result.stderr

@pytest.mark.parametrize("key,value", [("scope", "TEST-ONLY unknown"), ("mode", "TEST-ONLY unknown"),
    ("kind", "TEST-ONLY unknown"), ("target", "TEST-ONLY unknown"), ("group", "TEST-ONLY wrong group")])
def test_shared_metadata_vocabulary(key, value):
    g = run(lp.DirectRecords([row(note="TEST-ONLY checked")], {}), [declaration(**{key: value})])
    issue(first(g), "declarations", (0, key), "INTEGRITY_FAILURE", "unsupported value")

@pytest.mark.parametrize("damage,path,reason", [("scalar-source", (1, "source"), "source is not a record dependency"),
    ("shadow", (0, "name"), "declaration shadows source")])
def test_shared_source_declaration_semantics(damage, path, reason):
    ds = [declaration(), declaration("next", source="leaf", depends=("leaf",))] if damage == "scalar-source" else [declaration("root")]
    g = run(lp.DirectRecords([row(note="TEST-ONLY checked")], {}), ds)
    issue(first(g), "declarations", path, "INTEGRITY_FAILURE", reason)

@pytest.mark.parametrize("scope,kind", [("media", "MediaAsset"), ("intent", "IntentSpecV2")])
@pytest.mark.parametrize("damage", ["pin", "kind"])
def test_shared_scope_integrity(adapter, scope, kind, damage):
    target = row(ref(kind, "TEST-ONLY scope", 9)); other = row(ref("Hypothesis", "TEST-ONLY unrelated", 12))
    expected = pin(target) | {"sha256": "b" * 64} if damage == "pin" else pin(other)
    g = run(adapter([row(link=pin(target)), target, other]),
        [declaration(path=("link",), contract=le.MAPPING, mode="pin", target=kind, scope=scope)], scopes={scope: expected})
    if damage == "pin": diagnostic(g, kind + ":TEST-ONLY scope@9", ("sha256",), "INTEGRITY_FAILURE", "pin digest mismatch")
    else: diagnostic(g, "reference", ("kind",), "INTEGRITY_FAILURE", "unsupported value")

def test_shared_unconsumed_sibling_blocks_access():
    g = run(lp.DirectRecords([row(note="TEST-ONLY checked")], {}), [declaration(), declaration("sibling")])
    g._values.pop("sibling")
    exact_error(lambda: g.get("leaf"), RuntimeError, "unconsumed prerequisite")

def test_shared_group_identity_contract():
    source = lp.DirectRecords([], {})
    for value, state, reason in [(le._MISSING, "UNKNOWN", "missing required field"), (None, "UNKNOWN", "null required field"),
                                  (4, "INTEGRITY_FAILURE", "wrong type")]:
        g = lp.prepare(source, [], {}, {}, group=value)
        issue(first(g), "group", (), state, reason)

@pytest.mark.parametrize("changes,path,reason", [({"source": "root"}, (0, "source"), "collection requires universe source"),
    ({"target": "Evidence"}, (0, "target"), "scope target kind mismatch"),
    ({"mode": "field", "source": "root"}, (0, "scope"), "field scope belongs on its record dependency")])
def test_shared_collection_declaration_semantics(changes, path, reason):
    media = row(ref("MediaAsset", "TEST-ONLY scope", 9))
    g = run(lp.DirectRecords([media, row(media=pin(media)["ref"])] if changes.get("mode") == "field" else [media],
                             {"leaf": []}), [collection() | changes], scopes={"media": pin(media)})
    issue(first(g), "declarations", path, "INTEGRITY_FAILURE", reason)

@pytest.mark.parametrize("operand", ["declaration", "scopes", "inventory"])
@pytest.mark.parametrize("case,state,reason", VARIANTS)
def test_shared_outer_containers(operand, case, state, reason):
    media = row(ref("MediaAsset", "TEST-ONLY scope", 9)); ds = [collection()]; scopes = {"media": pin(media)}; inv = {"leaf": []}
    value = le._MISSING if case == "missing" else None if case == "null" else []
    if case != "valid":
        if operand == "declaration": ds = le._MISSING if case == "missing" else [value]
        elif operand == "scopes": scopes = value
        else: inv = value
    source = lp.DirectRecords([media], {})
    source.inventory = inv  # Missing sentinel represents an absent raw inventory, not a JSON value.
    g = run(source, ds, scopes=scopes)
    if case == "valid": assert g.diagnostics == ()
    else: issue(first(g), "declarations" if operand == "declaration" else operand, (0,) if operand == "declaration" and case != "missing" else (), state, reason)

def test_shared_exact_non_head_control(adapter):
    old = row(ref("MediaAsset", "TEST-ONLY media", 5), note="TEST-ONLY old")
    head = row(ref("MediaAsset", "TEST-ONLY media", 6), note="TEST-ONLY head")
    g = run(adapter([row(link=pin(old)), old, head]), [declaration(path=("link",), contract=le.MAPPING, mode="pin", target="MediaAsset"),
            declaration("label", source="leaf", depends=("leaf",), kind="MediaAsset")])
    assert g.diagnostics == ()
    assert g.get("label")[0].value == "TEST-ONLY old" and g.get("leaf")[0].value == ("MediaAsset", "TEST-ONLY media", 5)

def test_shared_every_active_boundary(adapter, monkeypatch):
    observed = {}; checked = []; original = le.field; original_record = le.RawRecord.field
    def trace(raw, path, contract, *, subject):
        observed.setdefault(subject, Counter())[path] += 1
        return original(raw, path, contract, subject=subject)
    def record_trace(record, path, contract):
        checked.append((record.subject, path, contract))
        return original_record(record, path, contract)
    monkeypatch.setattr(le, "field", trace)
    monkeypatch.setattr(le.RawRecord, "field", record_trace)
    media = row(ref("MediaAsset", "TEST-ONLY media", 5), note="TEST-ONLY media label")
    root = row(note="TEST-ONLY root label", media=pin(media)["ref"], link=pin(media))
    ds = [declaration(), declaration("edge", path=("link",), contract=le.MAPPING, mode="pin", target="MediaAsset", scope="media"),
          collection() | {"name": "members"}, declaration("label", source="edge", depends=("edge",), kind="MediaAsset"),
          declaration("repeat", contract=le.Contract((str,), choices=("TEST-ONLY root label",))),
          declaration("repeat_again", contract=le.Contract((str,), choices=("TEST-ONLY root label",)))]
    source = adapter([root, media], {"members": [ref()]})
    g = run(source, ds, scopes={"media": pin(media)})
    assert g.consumed == ("edge", "label", "leaf", "members", "repeat", "repeat_again")
    assert g.get("label")[0].value == "TEST-ONLY media label" and g.get("members")[0].value == (("Evidence", "TEST-ONLY root", 3),)
    # Independent ordered declaration slots: edge, leaf, members, repeat, repeat_again, label.
    assert checked == [
        ("Evidence:TEST-ONLY root@3", ("link",), le.Contract((dict,))),
        ("Evidence:TEST-ONLY root@3", ("note",), le.Contract((str,), nonempty=True)),
        ("Evidence:TEST-ONLY root@3", ("media",), le.Contract((dict,))),
        ("Evidence:TEST-ONLY root@3", ("note",), le.Contract((str,), choices=("TEST-ONLY root label",))),
        ("Evidence:TEST-ONLY root@3", ("note",), le.Contract((str,), choices=("TEST-ONLY root label",))),
        ("MediaAsset:TEST-ONLY media@5", ("note",), le.Contract((str,), nonempty=True))], "per-declaration boundary obligations"
    expected = {
        "group": {(): 1}, "roots": {(): 1, ("root",): 4}, "universe": {(): 3, ("kind",): 2, ("id",): 2, ("revision",): 2},
        "declarations": {(): 14, ("name",): 6, ("group",): 6, ("source",): 6, ("kind",): 6, ("path",): 6, ("contract",): 6, ("mode",): 6, ("target",): 6, ("scope",): 6, ("depends",): 6},
        "reference": {(): 9, ("kind",): 18, ("id",): 18, ("revision",): 18, ("ref",): 6, ("sha256",): 3},
        "scopes": {(): 2, ("media",): 2},
        "Evidence:TEST-ONLY root@3": {(): 10, ("kind",): 5, ("id",): 10, ("revision",): 10, ("payload",): 5, ("schema_version",): 5, ("sha256",): 5, ("note",): 3, ("media",): 1, ("link",): 1},
        "MediaAsset:TEST-ONLY media@5": {(): 5, ("kind",): 4, ("id",): 8, ("revision",): 8, ("payload",): 4, ("schema_version",): 4, ("sha256",): 4, ("note",): 1}}
    if isinstance(source, lp.DirectRecords):
        expected.update(inventory={(): 1, ("members",): 1}, universe={(): 6, ("kind",): 4, ("id",): 4, ("revision",): 4},
                        reference={(): 10, ("kind",): 20, ("id",): 20, ("revision",): 20, ("ref",): 6, ("sha256",): 3})
        expected["Evidence:TEST-ONLY root@3"] = {(): 11, ("kind",): 6, ("id",): 12, ("revision",): 12, ("payload",): 6, ("schema_version",): 6, ("sha256",): 6, ("note",): 3, ("media",): 1, ("link",): 1}
    assert observed == expected

@pytest.mark.parametrize("required", ["TEST-ONLY observed", "TEST-ONLY different"])
def test_shared_repeated_field_contract(adapter, required):
    root = ref("Evidence", "TEST-ONLY repeated contract", 17)
    g = run(adapter([row(root, note="TEST-ONLY observed")]), [declaration("a-text"),
        declaration(contract=le.Contract((str,), choices=(required,)))], roots={"root": root})
    if required == "TEST-ONLY observed":
        assert g.diagnostics == () and g.get("a-text")[0].value == g.get("leaf")[0].value == "TEST-ONLY observed"
    else:
        assert g.diagnostics == (le.EvidenceResult("INTEGRITY_FAILURE", "Evidence:TEST-ONLY repeated contract@17", ("note",), "unsupported value"),), "second declaration contract"
        exact_error(lambda: g.get("leaf"), ValueError, "unavailable prerequisite")

@pytest.mark.parametrize("case,state,reason", VARIANTS)
def test_shared_dependency_unavailable(adapter, case, state, reason):
    root = ref("Evidence", "TEST-ONLY dependency diagnostic", 23)
    roots = {} if case == "missing" else {"root": None if case == "null" else 19 if case == "malformed" else root}
    g = run(adapter([row(root, note="TEST-ONLY dependency present")]), roots=roots)
    if case == "valid": assert g.diagnostics == () and g.get("leaf")[0].value == "TEST-ONLY dependency present"
    else:
        assert g.diagnostics == (le.EvidenceResult("UNKNOWN", "leaf", ("note",), "dependency unavailable"),
            le.EvidenceResult(state, "roots", ("root",), reason)), "dependency unavailable diagnostic required"
        exact_error(lambda: g.get("leaf"), ValueError, "unavailable prerequisite")

def test_shared_retained_enumeration_snapshot(adapter, monkeypatch):
    media = row(ref("MediaAsset", "TEST-ONLY scope", 9)); reader = adapter([media], {"leaf": []})
    if isinstance(reader, lp.DirectRecords): return  # Direct universe preservation is covered separately.
    with sqlite3.connect(reader.root / "pilot.sqlite") as db:
        # The reader's transaction must see the established empty member collection.
        db.execute("PRAGMA busy_timeout=1")
        with pytest.raises(sqlite3.OperationalError, match="database is locked"):
            db.execute("INSERT INTO artifacts VALUES(:kind,:id,:revision,:sha256,:payload)", row(media=pin(media)["ref"]))
            db.commit()
        db.rollback()
    g = run(reader, [collection()], scopes={"media": pin(media)})
    assert g.get("leaf")[0].value == ()

def test_shared_group_identifies_only_checked_scope():
    media = row(ref("MediaAsset", "TEST-ONLY scope", 9))
    g = run(lp.DirectRecords([media], {"leaf": []}), [collection()], scopes={"media": pin(media)})
    assert g.scope == (("media", ("MediaAsset", "TEST-ONLY scope", 9)),)
    broken = run(lp.DirectRecords([media], {}), [collection()], scopes={"media": pin(media)})
    assert broken.scope == ()
    diagnostic(broken, "inventory", ("leaf",), "UNKNOWN", "missing required field")

@pytest.mark.parametrize("operand", ["universe", "inventory"])
def test_shared_direct_missing_inputs(operand):
    media = row(ref("MediaAsset", "TEST-ONLY scope", 9))
    source = lp.DirectRecords() if operand == "universe" else lp.DirectRecords([media])
    g = run(source) if operand == "universe" else run(source, [collection()], scopes={"media": pin(media)})
    diagnostic(g, operand, (), "UNKNOWN", "missing required field")

def test_shared_failed_preparation_preserves_inputs(adapter):
    rows = [row(note=None)]; before = deepcopy(rows); source = adapter(rows, {})
    retained = isinstance(source, le.RawReader) and not isinstance(source, lp.DirectRecords)
    stored = (source.root / "pilot.sqlite").read_bytes() if retained else None
    g = run(source)
    diagnostic(g, "Evidence:TEST-ONLY root@3", ("note",), "UNKNOWN", "null required field")
    assert rows == before
    if retained: assert (source.root / "pilot.sqlite").read_bytes() == stored
    else: assert source._universe == before

def test_shared_root_name_reserved_without_root_input():
    media = row(ref("MediaAsset", "TEST-ONLY scope", 9))
    g = run(lp.DirectRecords([media], {"root": []}), [collection() | {"name": "root"}], roots={}, scopes={"media": pin(media)})
    issue(first(g), "declarations", (0, "name"), "INTEGRITY_FAILURE", "declaration shadows source")
