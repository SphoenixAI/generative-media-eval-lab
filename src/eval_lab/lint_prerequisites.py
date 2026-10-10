"""Private shared preparation, never an all-rule context or readiness result.

Declarations are explicit raw dictionaries, not domain models. Each names its
source (root alias or dependency), kind/path/contract, mode, target and scope.
Ref/pin outputs can feed dependent declarations; collection outputs are exact
members whose membership Ref at path matches a checked media/intent scope pin.
DirectRecords accepts TEST-ONLY JSON envelopes and per-collection Ref inventories.
Its universe attests only supplied synthetic scope, never real-case completeness.
Later rule groups must declare their own fields and semantic correspondence.
"""
from copy import deepcopy
from dataclasses import dataclass
from . import lint_evidence as le

KINDS = le.Contract((str,), choices=tuple(le.ARTIFACT_TYPES))
METADATA = dict(name=le.TEXT, group=le.TEXT, source=le.TEXT, kind=KINDS, path=le.SEQUENCE,
                contract=le.Contract((le.Contract,)), mode=le.Contract((str,), choices=("field", "ref", "pin", "collection")),
                target=KINDS, scope=le.Contract((str,), choices=("none", "media", "intent")), depends=le.SEQUENCE)
IDENTITY = dict(kind=KINDS, id=le.TEXT, revision=le.REVISION)
INVENTORY = ("declarations", *METADATA, "path.component", "depends.component", "roots", "source.kind",
             "universe", "envelope", *IDENTITY, "payload", "payload.id", "payload.revision", "schema_version",
             "sha256", "reference", "reference.kind", "reference.id", "reference.revision", "pin.ref", "pin.sha256",
             "scopes", "scope.pin", "scope.kind", "membership", "inventory", "inventory.member")


def _bad(subject, path, reason, state="INTEGRITY_FAILURE"):
    return le.EvidenceResult(state, subject, path, reason)


def _identities(result):
    if result.state != "AVAILABLE": return result
    values = []; seen = set()
    for i, row in enumerate(result.value):
        shape = le.field(row, (), le.MAPPING, subject="universe")
        if shape.state != "AVAILABLE": return le.EvidenceResult(shape.state, "universe", (i,), shape.reason)
        parts = []
        for key, contract in IDENTITY.items():
            part = le.field(row, (key,), contract, subject="universe")
            if part.state != "AVAILABLE": return le.EvidenceResult(part.state, "universe", (i, key), part.reason)
            parts.append(part.value)
        key = tuple(parts)
        if key in seen: return _bad("universe", (i,), "duplicate exact identity")
        seen.add(key); values.append(dict(zip(IDENTITY, parts)))
    return le.EvidenceResult("AVAILABLE", "universe", (), value=sorted(values, key=lambda r: tuple(r.values())))


class DirectRecords(le.RawReader):
    """Read-only TEST-ONLY universe, sharing RawReader's exact integrity verifier."""
    def __init__(self, rows=le._MISSING, inventory=le._MISSING):
        self._universe = rows if rows is le._MISSING else deepcopy(rows)
        self.inventory = inventory if inventory is le._MISSING else deepcopy(inventory)
        result = _identities(self.rows())
        self._issue = result if result.state != "AVAILABLE" else None

    def rows(self):
        return le.field(self._universe, (), le.SEQUENCE, subject="universe")

    def _fetch(self, kind, identity, revision):
        return [r for r in self._universe if (r["kind"], r["id"], r["revision"]) == (kind, identity, revision)]


@dataclass
class _Group:
    group: str
    diagnostics: tuple
    declared: tuple
    consumed: tuple
    visited: tuple
    _values: dict
    scope: tuple = ()

    def get(self, name):
        if name not in self.declared: raise KeyError("undeclared prerequisite")
        if set(self._values) != set(self.declared) or self.consumed != self.declared: raise RuntimeError("unconsumed prerequisite")
        if self.diagnostics: raise ValueError("unavailable prerequisite")
        return self._values[name]


def _declarations(raw, roots, group, check, fail):
    items = check(raw, (), le.SEQUENCE, "declarations")
    if items is None: return {}
    specs = {}
    for i, item in enumerate(items):
        if check(item, (), le.MAPPING, "declarations", (i,)) is None: continue
        d = {key: check(item, (key,), contract if key != "group" else le.Contract((str,), choices=(group,)),
                        "declarations", (i, key)) for key, contract in METADATA.items()}
        if any(value is None for value in d.values()): continue
        if d["mode"] == "collection" and d["source"] != "universe":
            fail("declarations", (i, "source"), "collection requires universe source")
        if d["scope"] != "none":
            if d["mode"] == "field": fail("declarations", (i, "scope"), "field scope belongs on its record dependency")
            if d["target"] != ("MediaAsset" if d["scope"] == "media" else "IntentSpecV2"):
                fail("declarations", (i, "target"), "scope target kind mismatch")
        for j, part in enumerate(d["path"]):
            check(part, (), le.Contract((str, int), minimum=0) if type(part) is int else le.Contract((str,)),
                  "declarations", (i, "path", j))
        for j, dep in enumerate(d["depends"]): check(dep, (), le.TEXT, "declarations", (i, "depends", j))
        if any(type(dep) is not str for dep in d["depends"]): continue
        if d["name"] in roots or d["name"] in ("root", "universe"): fail("declarations", (i, "name"), "declaration shadows source")
        if d["name"] in specs: fail("declarations", (i, "name"), "duplicate declaration")
        specs[d["name"]] = d
    # Validate dependency topology independently of raw graph references.
    for i, d in enumerate(specs.values()):
        if d["source"] in specs and specs[d["source"]]["mode"] == "field":
            fail("declarations", (i, "source"), "source is not a record dependency")
        if any(type(dep) is not str or dep not in specs for dep in d["depends"]):
            fail("declarations", (i, "depends"), "unresolved dependency")
        if d["source"] != "root" and d["source"] not in roots and d["source"] not in d["depends"] and not (d["mode"] == "collection" and d["source"] == "universe"):
            fail("declarations", (i, "source"), "source must be a declared dependency or root")
    ordered = {}
    while len(ordered) < len(specs):
        pending = [n for n in sorted(specs) if n not in ordered and all(dep in ordered for dep in specs[n]["depends"])]
        if not pending:
            fail("declarations", (), "declaration cycle"); break
        ordered.update((n, specs[n]) for n in pending)
    return ordered


def prepare(source, declarations, roots, scopes, *, group):
    """Prepare only declared shared values. Diagnostics deny all consumer support.

    The group and checked scope are explicit; neither attests all-rule coverage.
    Container support is keys/indices, not descendants. Empty declarations remain
    an explicitly limited group; they cannot establish lint completion. Every
    declaration is consumed, including unavailable dependency paths. Revisited
    exact records never bypass a different field, target-kind or pin obligation.
    """
    diagnostics = []; values = {}; nodes = {}; seen = set(); consumed = []; scope_ids = {}
    def take(result):
        if result.state != "AVAILABLE": diagnostics.append(result)
        return result.value
    def check(raw, path, contract, subject, location=None):
        r = le.field(raw, path, contract, subject=subject)
        if location is not None: r = le.EvidenceResult(r.state, subject, location, r.reason, r.value)
        return take(r)
    def fail(subject, path, reason): diagnostics.append(_bad(subject, path, reason))
    def resolve(request, pinned, target):
        # Reader verifies all Ref/Pin components, raw metadata, stored and supplied hashes.
        record = source.read(request, pinned=pinned)
        diagnostics.extend(record.diagnostics)
        raw_ref = check(request, ("ref",), le.MAPPING, "reference") if pinned else request
        kind = check(raw_ref, ("kind",), le.Contract((str,), choices=(target,)), "reference")
        identity_value = check(raw_ref, ("id",), le.TEXT, "reference")
        revision = check(raw_ref, ("revision",), le.REVISION, "reference")
        if kind is None or identity_value is None or revision is None: return []
        identity = (kind, identity_value, revision)
        seen.add(identity)
        return [(identity, record)]
    check(group, (), le.TEXT, "group")
    checked_roots = check(roots, (), le.MAPPING, "roots")
    specs = _declarations(declarations, checked_roots or {}, group, check, fail)
    declared = tuple(sorted(specs))
    if diagnostics: return _Group(group, tuple(diagnostics), declared, (), (), {})
    for name, d in specs.items():
        start = len(diagnostics); out = []; destinations = []
        scope_nodes = []
        if d["scope"] != "none":
            scope_map = check(scopes, (), le.MAPPING, "scopes")
            request = check(scope_map, (d["scope"],), le.MAPPING, "scopes") if scope_map is not None else None
            if request is not None:
                scope_nodes = resolve(request, True, "MediaAsset" if d["scope"] == "media" else "IntentSpecV2")
                if scope_nodes: scope_ids[d["scope"]] = scope_nodes[0][0]
        if d["mode"] == "collection":
            refs = take(_identities(source.rows()))
            candidates = []
            for request in refs if refs is not None else []:
                if request["kind"] == d["kind"]: candidates.extend(resolve(request, False, d["kind"]))
        elif d["source"] in nodes: candidates = nodes[d["source"]]
        else:
            request = check(checked_roots, (d["source"],), le.MAPPING, "roots")
            candidates = resolve(request, False, d["kind"]) if request is not None else []
        if not candidates and d["mode"] != "collection" and d["source"] not in nodes:
            diagnostics.append(_bad(name, d["path"], "dependency unavailable", "UNKNOWN"))
        for identity, record in candidates:
            check(identity[0], (), le.Contract((str,), choices=(d["kind"],)), record.subject, d["path"])
            result = record.field(d["path"], d["contract"])
            raw = take(result)
            if result.state != "AVAILABLE": continue
            if d["mode"] == "field":
                safe = tuple(sorted(raw)) if type(raw) is dict else tuple(range(len(raw))) if type(raw) in (list, tuple) else raw
                out.append(le.EvidenceResult("AVAILABLE", record.subject, d["path"], value=safe))
            else:
                targets = resolve(raw, d["mode"] == "pin", d["target"])
                if targets:
                    target = targets[0][0]
                    if d["mode"] == "collection":
                        if scope_nodes and target == scope_nodes[0][0]: destinations.append((identity, record))
                    else:
                        if scope_nodes and target != scope_nodes[0][0]: fail(record.subject, d["path"], "scope correspondence mismatch")
                        destinations.extend(targets)
                        out.append(le.EvidenceResult("AVAILABLE", record.subject, d["path"], value=target))
        if d["mode"] == "collection":
            if d["scope"] == "none": fail("declarations", (name, "scope"), "collection requires scope")
            members = tuple(sorted(identity for identity, _ in destinations))
            if isinstance(source, DirectRecords):
                inventory_map = check(source.inventory, (), le.MAPPING, "inventory")
                inventory = check(inventory_map, (name,), le.SEQUENCE, "inventory") if inventory_map is not None else None
                declared_members = []
                for request in inventory if inventory is not None else []:
                    found = resolve(request, False, d["kind"])
                    if found: declared_members.append(found[0][0])
                if len(set(declared_members)) != len(declared_members): fail("inventory", (name,), "duplicate inventory member")
                if inventory is not None and len(diagnostics) == start and tuple(sorted(declared_members)) != members:
                    fail("inventory", (name,), "inventory membership mismatch")
            out.append(le.EvidenceResult("AVAILABLE", "collection:" + name, (), value=members))
        nodes[name] = destinations
        values[name] = tuple(out)
        consumed.append(name)
    diagnostics.sort(key=lambda r: (r.subject, repr(r.path), r.state, r.reason))
    return _Group(group, tuple(diagnostics), declared, tuple(sorted(consumed)), tuple(sorted(seen)), values,
                  tuple(sorted(scope_ids.items())) if not diagnostics else ())
