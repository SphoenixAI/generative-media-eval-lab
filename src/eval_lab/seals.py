"""Private append-only local intent seals; integrity is not a quality verdict."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import sqlite3
from typing import Literal
from uuid import uuid4

from pydantic import Field, model_validator
from . import __version__
from .canonical_json import canonicalize, parse_json, file_digest
from .domain import Artifact, ARTIFACT_TYPES, Ref
from .intent_v2 import CheckedValue, Instant, IntentSpecV2, Pin, Text
from .pilot_domain import Hash


def source_intent(data) -> IntentSpecV2:
    required = {"id", "schema_version", "revision", "created_at"}
    if not isinstance(data, dict) or not required <= data.keys() or data["schema_version"] != 2:
        raise ValueError("seal-intent requires a complete IntentSpecV2 file with explicit id, "
            "schema_version=2, revision and created_at; legacy v1 forms use eval-pilot intent")
    if not isinstance(data["created_at"], str):
        raise ValueError("created_at must be a timezone-bearing timestamp string")
    return IntentSpecV2.model_validate(data)


class GitWitness(CheckedValue):
    """Declared metadata only; never resolved or authenticated remotely."""
    commit: str = Field(pattern=r"^[0-9a-f]{40}([0-9a-f]{24})?$")
    remote_url: Text


class SealRecord(Artifact, CheckedValue):
    revision: int = Field(default=1, strict=True, ge=1, le=1)
    file_sha256: Hash
    canonicalization: Literal["RFC8785"] = "RFC8785"
    number_profile: Literal["safe-integer-tokens-v1"] = "safe-integer-tokens-v1"
    sealed_at: Instant
    tool_version: Text
    source_path: Text
    canonical_source: str
    intent: Pin
    git_witness: GitWitness | None = None

    @model_validator(mode="after")
    def integrity(self):
        data = parse_json(self.canonical_source)
        canonical = canonicalize(data)
        intent = source_intent(data)
        if self.canonical_source != canonical.decode("utf-8") or sha256(canonical).hexdigest() != self.file_sha256:
            raise ValueError("canonical source/file digest mismatch")
        if self.intent != Pin(ref=intent.ref, sha256=intent.digest):
            raise ValueError("canonical source/intent pin mismatch")
        if not Path(self.source_path).is_absolute():
            raise ValueError("source_path must be absolute")
        if self.created_at != self.sealed_at:
            raise ValueError("seal event timestamps must agree")
        return self


ARTIFACT_TYPES["SealRecord"] = SealRecord


def seal_intent(root: Path, source: Path, *, git_commit: str | None = None,
                git_remote: str | None = None) -> SealRecord:
    """Read once, validate, import exact human input, then append a new event."""
    from .persistence import Repository
    from sqlalchemy.exc import SQLAlchemyError
    if (git_commit is None) != (git_remote is None):
        raise ValueError("--git-commit and --git-remote must be supplied together")
    witness = None if git_commit is None else GitWitness(commit=git_commit, remote_url=git_remote)
    source = source.resolve()
    data = parse_json(source.read_bytes())
    intent = source_intent(data)
    canonical = canonicalize(data)
    now = datetime.now(timezone.utc)
    seal = SealRecord(id="seal-" + uuid4().hex, created_at=now, sealed_at=now,
        file_sha256=sha256(canonical).hexdigest(), canonical_source=canonical.decode("utf-8"),
        tool_version=__version__, source_path=str(source), git_witness=witness,
        intent=Pin(ref=intent.ref, sha256=intent.digest))
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    repo = Repository("sqlite:///" + str(root / "pilot.sqlite"))
    try:
        repo.put(intent)
        try:
            repo.put(seal)
        except (ValueError, KeyError, SQLAlchemyError) as exc:
            raise ValueError(f"intent {intent.id}@{intent.revision} retained; seal was not stored: {exc}") from exc
        return seal
    finally:
        repo.close()


def read_record(db, ref: Ref):
    row = db.execute("SELECT * FROM artifacts WHERE kind=? AND id=? AND revision=?",
        (ref.kind, ref.id, ref.revision)).fetchone()
    if row is None:
        raise ValueError("pinned artifact is missing")
    return checked_record(row)


def checked_record(row):
    item = ARTIFACT_TYPES[row["kind"]].model_validate_json(row["payload"])
    if (item.ref.kind, item.id, item.revision) != (row["kind"], row["id"], row["revision"]) or item.digest != row["sha256"]:
        raise ValueError("stored artifact integrity failure")
    return item


def verification_result(results: list[dict]) -> dict:
    statuses = {r["status"] for r in results}
    status = "INTEGRITY_FAILURE" if "INTEGRITY_FAILURE" in statuses else "UNKNOWN" if "UNKNOWN" in statuses else "VERIFIED"
    return {"status": status, "seals": results, "quality_verdict": "UNKNOWN"}


def verify_seal(root: Path, target: str) -> dict:
    """Verify an exact seal ID or every retained seal for an original source path."""
    def result(status, message, seal_id=None):
        return {"seal_id": seal_id, "status": status, "detail": message}
    database = root.resolve() / "pilot.sqlite"
    if not database.is_file():
        return verification_result([result("UNKNOWN", "seal database is unavailable")])
    db = None
    try:
        db = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        db.execute("BEGIN")  # One read snapshot, with no repository initialization.
        rows = db.execute("SELECT * FROM artifacts WHERE kind='SealRecord' ORDER BY id,revision").fetchall()
        exact = [row for row in rows if row["id"] == target]
        path = str(Path(target).resolve()) if not exact else None
        results = []
        sources = {}
        for row in exact or rows:
            try:
                seal = checked_record(row)
                if not exact and seal.source_path != path:
                    continue
                intent = read_record(db, seal.intent.ref)
                if intent.digest != seal.intent.sha256:
                    raise ValueError("pinned intent digest mismatch")
                # The recorded resolved path stays fixed even if a symlink changes.
                source = Path(seal.source_path)
                if source not in sources:
                    try:
                        sources[source] = file_digest(source.read_bytes())
                    except (OSError, ValueError) as exc:
                        sources[source] = exc
                current = sources[source]
                if isinstance(current, Exception):
                    raise current
                if current != seal.file_sha256:
                    raise ValueError("current source file digest mismatch")
                results.append(result("VERIFIED", "stored seal, exact intent pin and current source verified", seal.id))
            except OSError as exc:
                results.append(result("UNKNOWN", f"source unavailable: {exc}", row["id"]))
            except (ValueError, KeyError, TypeError) as exc:
                results.append(result("INTEGRITY_FAILURE", str(exc), row["id"]))
        return verification_result(results or [result("UNKNOWN", "seal ID or source path is not sealed")])
    except sqlite3.OperationalError as exc:
        unavailable = "locked" in str(exc) or "unable to open" in str(exc)
        return verification_result([result("UNKNOWN" if unavailable else "INTEGRITY_FAILURE", str(exc))])
    except (sqlite3.DatabaseError, ValueError) as exc:
        return verification_result([result("INTEGRITY_FAILURE", str(exc))])
    except OSError as exc:
        return verification_result([result("UNKNOWN", str(exc))])
    finally:
        if db is not None:
            db.close()
