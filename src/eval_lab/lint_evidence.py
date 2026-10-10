"""Private raw prerequisites for future lint rules, not a readiness evaluator.

Call field(raw, path, contract, subject=...) before using a required value. Only
AVAILABLE has a value; inspect state explicitly. A Contract checks the requested
field, not undeclared descendants or the truth/acceptability of a human claim.

With RawReader(root), read an explicit raw Ref, or read(pin, pinned=True). There
is no graph traversal or default revision. RawRecord.field uses the same boundary
and blocks support from damaged records. diagnostic_raw is an UNCHECKED defensive
copy for private diagnostics only; it must never be used as checked support.
Reads share one SQLite transaction. No Repository, schema creation or media reads
occur here. Hashes check retained consistency, not authorship or authenticity.
"""
from copy import deepcopy
from dataclasses import dataclass, field as member
from datetime import datetime
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import sqlite3
from typing import Literal
from .persistence import ARTIFACT_TYPES  # Register existing kinds; no repository construction.
from .test_plans import freeze_digest

PathParts = tuple[str | int, ...]
State = Literal["AVAILABLE", "UNKNOWN", "INTEGRITY_FAILURE"]
_MISSING = object()


def _text_problem(value):
    try: value.encode("utf-8")
    except UnicodeError: return "malformed text"
    return None


@dataclass(frozen=True)
class EvidenceResult:
    state: State
    subject: str
    path: PathParts
    reason: str = ""
    value: object = None

    def __bool__(self):
        raise TypeError("inspect state explicitly")


@dataclass(frozen=True)
class Contract:
    types: tuple[type, ...]
    minimum: int | float | None = None
    exclusive: bool = False
    choices: tuple | None = None
    nonempty: bool = False
    digest: bool = False
    unavailable: tuple = ()

    def problem(self, value):
        if type(value) not in self.types: return "wrong type"
        if type(value) is str and _text_problem(value): return "malformed text"
        if type(value) is float and not math.isfinite(value): return "nonfinite number"
        if self.minimum is not None and (value < self.minimum or self.exclusive and value == self.minimum):
            return "below minimum"
        if self.nonempty and (not value or isinstance(value, str) and not value.strip()): return "empty value"
        if self.choices is not None and value not in self.choices: return "unsupported value"
        if self.digest and re.fullmatch(r"[0-9a-f]{64}", value) is None: return "malformed digest"
        if type(value) is dict and any(type(k) is not str for k in value): return "mapping keys must be text"
        return None


TEXT = Contract((str,), nonempty=True)
BOOLEAN = Contract((bool,))
MAPPING = Contract((dict,))
SEQUENCE = Contract((list, tuple))
REVISION = Contract((int,), minimum=1)
DIGEST = Contract((str,), digest=True)


def field(raw: object, path: PathParts, contract: Contract, *, subject: str) -> EvidenceResult:
    """Presence and original types first; no defaults, coercion or truthiness."""
    value = raw
    for part in path:
        if value is _MISSING or value is None: break
        if type(part) is str and type(value) is dict:
            value = value.get(part, _MISSING)
        elif type(part) is int and type(value) in (list, tuple):
            value = value[part] if 0 <= part < len(value) else _MISSING
        else:
            return EvidenceResult("INTEGRITY_FAILURE", subject, path, "malformed container")
    if value is _MISSING: return EvidenceResult("UNKNOWN", subject, path, "missing required field")
    if value is None: return EvidenceResult("UNKNOWN", subject, path, "null required field")
    if any(type(value) is type(token) and value == token for token in contract.unavailable):
        return EvidenceResult("UNKNOWN", subject, path, "explicitly unavailable")
    reason = contract.problem(value)
    if reason is not None: return EvidenceResult("INTEGRITY_FAILURE", subject, path, reason)
    return EvidenceResult("AVAILABLE", subject, path, value=deepcopy(value))


@dataclass(frozen=True)
class RawRecord:
    subject: str
    diagnostics: tuple[EvidenceResult, ...] = ()
    _raw: object = member(default=None, repr=False)

    @property
    def diagnostic_raw(self):
        return deepcopy(self._raw)

    def field(self, path: PathParts, contract: Contract) -> EvidenceResult:
        result = field(self._raw, path, contract, subject=self.subject)
        if result.state == "AVAILABLE" and self.diagnostics:
            state = "INTEGRITY_FAILURE" if any(d.state == "INTEGRITY_FAILURE" for d in self.diagnostics) else "UNKNOWN"
            return EvidenceResult(state, self.subject, path, "record prerequisites failed")
        return result


    def presence(self, path: PathParts) -> EvidenceResult:
        """Explicit optional-slot membership; null is absence, never a field value."""
        parent = self.field(path[:-1], MAPPING)
        if parent.state != "AVAILABLE":
            return EvidenceResult(parent.state, self.subject, path, parent.reason)
        if path[-1] not in parent.value:
            return EvidenceResult("UNKNOWN", self.subject, path, "missing required field")
        result = field(parent.value[path[-1]] is not None, (), BOOLEAN, subject=self.subject)
        return EvidenceResult(result.state, self.subject, path, result.reason, result.value)


def _decode(source):
    """Ordinary artifact JSON allows finite fractions, unlike frozen-plan JSON."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    def number(token):
        value = float(token)
        if not math.isfinite(value): raise ValueError("nonfinite number")
        return value
    raw = json.loads(source, object_pairs_hook=pairs, parse_constant=number, parse_float=number)
    pending = [raw]
    while pending:
        value = pending.pop()
        if type(value) is dict: pending.extend(value); pending.extend(value.values())
        elif type(value) is list: pending.extend(value)
        elif type(value) is str and _text_problem(value): raise ValueError("malformed text")
    return raw


class RawReader:
    """One existing store/snapshot per context manager; every exit closes it."""
    def __init__(self, root):
        self.root = Path(root)
        self._db = None
        self._issue = EvidenceResult("UNKNOWN", "store", (), "session unavailable")

    def __enter__(self):
        if self._db is not None: raise RuntimeError("reader session already open")
        try:
            database = self.root.resolve() / "pilot.sqlite"
            if not database.is_file():
                self._issue = EvidenceResult("UNKNOWN", "store", (), "store unavailable")
                return self
            self._db = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
            self._db.row_factory = sqlite3.Row
            self._db.execute("BEGIN")
            versions = [r[0] for r in self._db.execute("SELECT version FROM schema_migrations")]
            if len(versions) != 1 or type(versions[0]) is not int or versions[0] != 1:
                self._issue = EvidenceResult("INTEGRITY_FAILURE", "store", (), "incompatible store version")
            else:
                self._db.execute("SELECT kind,id,revision,sha256,payload FROM artifacts LIMIT 0")
                self._issue = None
        except (OSError, sqlite3.Error) as exc:
            self._issue = self._store_error(exc)
        if self._issue is not None and self._db is not None:
            self._db.close(); self._db = None
        return self

    @staticmethod
    def _store_error(exc):
        code = getattr(exc, "sqlite_errorcode", 0) & 0xff
        unavailable = isinstance(exc, OSError) or code in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED, sqlite3.SQLITE_CANTOPEN)
        return EvidenceResult("UNKNOWN" if unavailable else "INTEGRITY_FAILURE", "store", (),
                              "store unavailable" if unavailable else "malformed store structure")

    def __exit__(self, *exc):
        if self._db is not None: self._db.close()
        self._db = None
        self._issue = EvidenceResult("UNKNOWN", "store", (), "session unavailable")

    def rows(self):
        """Private raw enumeration in this same read-only snapshot; never completeness by fiat."""
        if self._issue is not None: return self._issue
        try:
            rows = [dict(r) for r in self._db.execute("SELECT kind,id,revision,sha256,payload FROM artifacts")]
            return field(rows, (), SEQUENCE, subject="universe")
        except (OSError, sqlite3.Error) as exc:
            return self._store_error(exc)

    def _fetch(self, kind, identity, revision):
        return self._db.execute("SELECT kind,id,revision,sha256,payload FROM artifacts WHERE kind=? AND id=? AND revision=?",
                                (kind, identity, revision)).fetchmany(2)

    def read(self, request: object, *, pinned: bool = False) -> RawRecord:
        """Resolve only this explicit Ref/Pin, never dictionaries inside data."""
        diagnostics = []
        subject = "reference"
        def check(raw, path, contract):
            result = field(raw, path, contract, subject=subject)
            if result.state != "AVAILABLE": diagnostics.append(result)
            return result.value
        def fail(path, reason):
            diagnostics.append(EvidenceResult("INTEGRITY_FAILURE", subject, path, reason))
        check(request, (), MAPPING)
        if diagnostics: return RawRecord(subject, tuple(diagnostics))
        if set(request) - ({"ref", "sha256"} if pinned else {"kind", "id", "revision"}):
            fail((), "unexpected reference keys")
        supplied_hash = check(request, ("sha256",), DIGEST) if pinned else None
        reference = check(request, ("ref",), MAPPING) if pinned else request
        if diagnostics: return RawRecord(subject, tuple(diagnostics))
        if set(reference) - {"kind", "id", "revision"}: fail(("ref",), "unexpected reference keys")
        kind = check(reference, ("kind",), Contract((str,), choices=tuple(ARTIFACT_TYPES)))
        identity = check(reference, ("id",), TEXT)
        revision = check(reference, ("revision",), REVISION)
        if diagnostics: return RawRecord(subject, tuple(diagnostics))
        subject = f"{kind}:{identity}@{revision}"
        if self._issue is not None: return RawRecord(subject, (self._issue,))
        try:
            rows = self._fetch(kind, identity, revision)
            if not rows: return RawRecord(subject, (EvidenceResult("UNKNOWN", subject, (), "missing exact target"),))
            if len(rows) != 1:
                fail((), "duplicate exact target")
                return RawRecord(subject, tuple(diagnostics))
            row = dict(rows[0])
            for name, expected, contract in (("kind", kind, TEXT), ("id", identity, TEXT), ("revision", revision, REVISION)):
                value = check(row, (name,), contract)
                if value is not None and value != expected: fail((name,), "row identity mismatch")
            source = check(row, ("payload",), TEXT)
            if source is None: return RawRecord(subject, tuple(diagnostics))
            try:
                raw = _decode(source)
            except (ValueError, RecursionError) as exc:
                reason = str(exc) if str(exc) in ("duplicate JSON key", "nonfinite number", "malformed text") else "malformed JSON"
                fail(("payload",), reason)
                return RawRecord(subject, tuple(diagnostics))
            check(raw, (), MAPPING)
            if type(raw) is not dict: return RawRecord(subject, tuple(diagnostics))
            version = 2 if kind in ("IntentSpecV2", "IntentBinding", "RelationClaimV2") else 1
            for name, expected, contract in (("id", identity, TEXT), ("revision", revision, REVISION),
                                             ("schema_version", version, Contract((int,), choices=(version,)))):
                value = check(raw, (name,), contract)
                if value is not None and value != expected: fail((name,), "payload identity mismatch")
            stored_hash = check(row, ("sha256",), DIGEST)
            digest = sha256(json.dumps(raw, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
            if stored_hash is not None and stored_hash != digest: fail(("sha256",), "stored digest mismatch")
            if supplied_hash is not None and supplied_hash != digest: fail(("sha256",), "pin digest mismatch")
            if kind == "TestPlan":
                # Explicit null/null is an unfrozen draft. Missing keys are not.
                if not ("frozen_at" in raw and "frozen_digest" in raw and raw["frozen_at"] is None and raw["frozen_digest"] is None):
                    stamp = check(raw, ("frozen_at",), TEXT)
                    frozen_hash = check(raw, ("frozen_digest",), DIGEST)
                    if stamp is not None:
                        try:
                            if datetime.fromisoformat(stamp).tzinfo is None: raise ValueError()
                        except ValueError: fail(("frozen_at",), "malformed freeze time")
                    if frozen_hash is not None:
                        try:
                            if freeze_digest(raw) != frozen_hash: fail(("frozen_digest",), "frozen digest mismatch")
                        except (ValueError, TypeError, OverflowError): fail(("frozen_digest",), "malformed frozen payload")
            return RawRecord(subject, tuple(diagnostics), raw)
        except (OSError, sqlite3.Error) as exc:
            return RawRecord(subject, (self._store_error(exc),))
        except (ValueError, TypeError, OverflowError, RecursionError):
            fail((), "malformed retained payload")
            return RawRecord(subject, tuple(diagnostics))
