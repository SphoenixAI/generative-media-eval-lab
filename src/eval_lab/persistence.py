"""Append-only typed snapshots with SQL referential integrity and a portable schema.

No domain logic depends on SQLite. JSON stores typed, validated snapshots, not
arbitrary domain dictionaries. Public serializers never expose this representation.
"""
from collections.abc import Iterator
import json
from sqlalchemy import (Column, Integer, String, Text, Table, MetaData,
    ForeignKeyConstraint, create_engine, select, event)
from sqlalchemy.pool import StaticPool
from .domain import ARTIFACT_TYPES, Artifact, Ref, Value, Evidence, HumanRating, AgentAssessment, EvaluationRound, PairwiseRating, ModelRun, EvaluatorVersion, HypothesisGraph, Hypothesis, RelationClaim, EvaluationCase
from . import pilot_domain  # register additive Pilot 0 types without altering v1 snapshots
from .domain import CompetingSet
from . import intent_v2

metadata = MetaData()
artifacts = Table("artifacts", metadata,
    Column("kind", String, primary_key=True), Column("id", String, primary_key=True),
    Column("revision", Integer, primary_key=True), Column("sha256", String(64), nullable=False),
    Column("payload", Text, nullable=False))
references = Table("artifact_references", metadata,
    Column("kind", String, primary_key=True), Column("id", String, primary_key=True), Column("revision", Integer, primary_key=True),
    Column("target_kind", String, primary_key=True), Column("target_id", String, primary_key=True), Column("target_revision", Integer, primary_key=True),
    ForeignKeyConstraint(["kind", "id", "revision"], ["artifacts.kind", "artifacts.id", "artifacts.revision"]),
    ForeignKeyConstraint(["target_kind", "target_id", "target_revision"], ["artifacts.kind", "artifacts.id", "artifacts.revision"]))
schema = Table("schema_migrations", metadata, Column("version", Integer, primary_key=True))
submission_keys = Table("submission_keys", metadata, Column("semantic_key", Text, primary_key=True),
    Column("kind", String, nullable=False), Column("id", String, nullable=False), Column("revision", Integer, nullable=False),
    ForeignKeyConstraint(["kind", "id", "revision"], ["artifacts.kind", "artifacts.id", "artifacts.revision"]))


def refs_in(value: object) -> Iterator[Ref]:
    if isinstance(value, Ref):
        yield value
    elif isinstance(value, Value):
        for name in type(value).model_fields:
            yield from refs_in(getattr(value, name))
    elif isinstance(value, tuple):
        for item in value:
            yield from refs_in(item)


class Repository:
    def __init__(self, url: str = "sqlite://"):
        kw = {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}} if url == "sqlite://" else {}
        self.engine = create_engine(url, **kw)
        if self.engine.dialect.name == "sqlite":
            @event.listens_for(self.engine, "connect")
            def foreign_keys(dbapi, _):
                dbapi.execute("PRAGMA foreign_keys=ON")
        metadata.create_all(self.engine)
        with self.engine.begin() as conn:
            versions = conn.execute(select(schema.c.version)).scalars().all()
            if versions and versions != [1]:
                raise ValueError("unsupported schema migration version")
            if not versions:
                conn.execute(schema.insert().values(version=1))
            if self.engine.dialect.name == "sqlite":
                for table in ("artifacts", "artifact_references", "submission_keys"):
                    for action in ("UPDATE", "DELETE"):
                        conn.exec_driver_sql(f"CREATE TRIGGER IF NOT EXISTS no_{action.lower()}_{table} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'append-only'); END")

    @staticmethod
    def key(ref: Ref):
        return (artifacts.c.kind == ref.kind) & (artifacts.c.id == ref.id) & (artifacts.c.revision == ref.revision)

    def get(self, ref: Ref) -> Artifact:
        with self.engine.connect() as conn:
            row = conn.execute(select(artifacts).where(self.key(ref))).mappings().one_or_none()
        if row is None:
            raise KeyError(ref)
        result = ARTIFACT_TYPES[ref.kind].model_validate_json(row["payload"])
        if result.digest != row["sha256"]:
            raise ValueError("snapshot integrity failure")
        return result

    def all(self, kind: str) -> tuple[Artifact, ...]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(artifacts.c.id, artifacts.c.revision).where(artifacts.c.kind == kind).order_by(artifacts.c.id, artifacts.c.revision)).all()
        return tuple(self.get(Ref(kind=kind, id=r.id, revision=r.revision)) for r in rows)

    def latest(self, ref: Ref) -> Artifact:
        with self.engine.connect() as conn:
            revision = conn.execute(select(artifacts.c.revision).where((artifacts.c.kind == ref.kind) & (artifacts.c.id == ref.id)).order_by(artifacts.c.revision.desc())).scalars().first()
        if revision is None:
            raise KeyError(ref)
        return self.get(Ref(kind=ref.kind, id=ref.id, revision=revision))

    def _validate_links(self, item: Artifact):
        for ref in set(refs_in(item)):
            self.get(ref)  # no dangling, floating-latest or cross-kind references
        if isinstance(item, Evidence):
            asset = self.get(item.media)
            if item.media.kind != "MediaAsset":
                raise ValueError("evidence requires media asset")
            times = item.sampling_manifest + (() if item.timestamp_end is None else (item.timestamp_end,))
            if times and (asset.duration is None or max(times) > asset.duration):
                raise ValueError("evidence exceeds media duration")
        if isinstance(item, ModelRun):
            if item.prompt.kind != "PromptSpec" or item.media.kind != "MediaAsset":
                raise ValueError("model run reference kinds")
        if isinstance(item, EvaluatorVersion):
            if self.get(item.rubric).digest != item.rubric_digest:
                raise ValueError("evaluator rubric digest mismatch")
        if isinstance(item, (HumanRating, AgentAssessment)):
            run = self.get(item.model_run)
            rubric = self.get(item.rubric)
            prompt = self.get(run.prompt)
            intent = self.get(prompt.intent)
            scores = item.dimension_scores if isinstance(item, HumanRating) else (item.result,)
            from .scoring import evaluate
            evaluate(tuple(scores), rubric, intent)
            for score in scores:
                for evidence_ref in score.evidence:
                    if self.get(evidence_ref).media != run.media:
                        raise ValueError("evidence belongs to another output")
            if isinstance(item, HumanRating):
                rnd = self.get(item.round)
                if item.model_run not in rnd.candidate_model_runs or item.rubric != rnd.rubric or self.latest(item.round).status != "open":
                    raise ValueError("rating outside open round")
                for old in self.all("HumanRating"):
                    if (old.rater.id, old.model_run, old.round.id) == (item.rater.id, item.model_run, item.round.id) and old.id != item.id:
                        raise ValueError("duplicate rater/unit")
            else:
                evaluator = self.get(item.evaluator)
                if evaluator.rubric != item.rubric or evaluator.rubric_digest != rubric.digest:
                    raise ValueError("evaluator/rubric mismatch")
        if isinstance(item, EvaluationRound):
            runs = [self.get(r) for r in item.candidate_model_runs]
            if len({r.prompt for r in runs}) != 1:
                raise ValueError("comparison must use the same versioned prompt")
            if item.revision > 1:
                prior = self.get(Ref(kind="EvaluationRound", id=item.id, revision=item.revision-1))
                if (prior.candidate_model_runs, prior.rubric, prior.assignment_seed) != (item.candidate_model_runs, item.rubric, item.assignment_seed) or prior.status == "closed":
                    raise ValueError("round protocol immutable; closed round cannot reopen")
        if isinstance(item, PairwiseRating):
            rnd = self.get(item.round)
            if self.latest(item.round).status != "open" or set(item.ordered_runs) != set(rnd.candidate_model_runs):
                raise ValueError("invalid pairwise round")
            from .presentation import assigned_runs
            if item.ordered_runs != assigned_runs(rnd, item.rater):
                raise ValueError("pairwise ordering was not server assigned")
            for old in self.all("PairwiseRating"):
                if old.rater.id == item.rater.id and old.round.id == item.round.id and old.id != item.id:
                    raise ValueError("duplicate pairwise submission")
        if isinstance(item, Hypothesis):
            for evidence in item.supporting_evidence + item.contradicting_evidence:
                media = self.get(evidence).media
                if not self.media_has_intent(media,item.intent):
                    raise ValueError("hypothesis evidence is outside declared intent")
        if isinstance(item, CompetingSet):
            if any(self.get(member).intent != item.intent for member in item.members if isinstance(member, Ref)):
                raise ValueError("competing set members must share its pinned intent")
        if isinstance(item, RelationClaim):
            evidence_refs = set(item.evidence) | ({item.subject} if item.subject.kind == "Evidence" else set())
            for evidence_ref in evidence_refs:
                media = self.get(evidence_ref).media
                if not self.media_has_intent(media,item.intent):
                    raise ValueError("relation evidence is outside declared intent")
            for ref in (item.subject, item.object):
                obj = self.get(ref)
                if isinstance(obj, Hypothesis) and obj.intent != item.intent:
                    raise ValueError("relation crosses intent without explicit mapping")
                if ref.kind == "IntentSpec" and ref != item.intent:
                    raise ValueError("relation intent mismatch")
        if isinstance(item, HypothesisGraph):
            for edge in item.edges:
                if self.get(edge.ref).digest != edge.digest:
                    raise ValueError("embedded edge differs from persisted claim")
            for ref in item.nodes:
                node = self.get(ref)
                if isinstance(node, Hypothesis) and node.intent != item.intent:
                    raise ValueError("graph contains cross-intent hypothesis")
        if isinstance(item, EvaluationCase):
            if len(set(item.published_assessments)) != len(item.published_assessments):
                raise ValueError("duplicate published assessment")
            for ref in item.published_assessments:
                assessment = self.get(ref)
                if assessment.model_run not in item.model_runs or assessment.rubric != item.rubric:
                    raise ValueError("published assessment outside case scope")
            for run_ref in item.model_runs:
                run = self.get(run_ref)
                if self.get(run.prompt).intent != item.intent:
                    raise ValueError("case run has incompatible intent")
            if item.hypothesis_graph and self.get(item.hypothesis_graph).intent != item.intent:
                raise ValueError("case graph has incompatible intent")
        pilot_domain.validate_pilot_links(self,item)

    def media_has_intent(self, media: Ref, intent: Ref) -> bool:
        return (any(self.get(run.prompt).intent==intent for run in self.all("ModelRun") if run.media==media)
            or any(clip.intent==intent for clip in self.all("PilotClip") if clip.media==media))

    @staticmethod
    def _validate_competing_admission(conn, item):
        """Read retained constraints inside the writer transaction, never via latest."""
        if isinstance(item, CompetingSet) and item.exclusive:
            sets = (item,)
            rows = conn.execute(select(artifacts.c.payload).where(artifacts.c.kind == "RelationClaim")).scalars()
            claims = tuple(RelationClaim.model_validate_json(row) for row in rows)
        elif isinstance(item, RelationClaim) and item.predicate == "compatible_with":
            claims = (item,)
            rows = conn.execute(select(artifacts.c.payload).where(artifacts.c.kind == "CompetingSet")).scalars()
            sets = tuple(CompetingSet.model_validate_json(row) for row in rows)
        else:
            return
        for group in sets:
            if not group.exclusive:
                continue
            members = {member for member in group.members if isinstance(member, Ref)}
            for claim in claims:
                if claim.predicate == "compatible_with" and {claim.subject, claim.object} <= members:
                    raise ValueError("compatible_with conflicts with an exclusive competing set's pinned members")

    @staticmethod
    def _validate_intent_admission(conn, item):
        if not isinstance(item, (intent_v2.IntentSpecV2, intent_v2.IntentBinding)):
            return
        def get(ref):
            row = conn.execute(select(artifacts).where(Repository.key(ref))).mappings().one()
            result = ARTIFACT_TYPES[ref.kind].model_validate_json(row["payload"])
            if result.digest != row["sha256"]:
                raise ValueError("snapshot integrity failure")
            return result
        rows = conn.execute(select(artifacts.c.payload).where(artifacts.c.kind == "IntentBinding")).scalars()
        history = tuple(intent_v2.IntentBinding.model_validate_json(row) for row in rows)
        intent_v2.validate_admission(item, get, history)

    def put(self, item: Artifact) -> str:
        if type(item).__name__ not in ARTIFACT_TYPES:
            raise TypeError("unregistered artifact")
        # Revalidate even if a caller used Pydantic model_copy(update=...).
        item = type(item).model_validate(item.model_dump(mode="json"))
        try:
            existing = self.get(item.ref)
        except KeyError:
            existing = None
        if existing is not None:
            if existing.digest != item.digest:
                raise ValueError("immutable revision conflict; append a new revision")
            return existing.digest
        self._validate_links(item)
        with self.engine.begin() as conn:
            if self.engine.dialect.name == "sqlite":
                # Serialize writers before checking mutable admission state. A closure
                # cannot slip between validation and insertion on the tested backend.
                conn.exec_driver_sql("BEGIN IMMEDIATE")
            if isinstance(item, (HumanRating, PairwiseRating)):
                row = conn.execute(select(artifacts.c.payload).where((artifacts.c.kind == "EvaluationRound") & (artifacts.c.id == item.round.id)).order_by(artifacts.c.revision.desc())).scalars().first()
                if row is None or EvaluationRound.model_validate_json(row).status != "open":
                    raise ValueError("rating outside open round at commit")
            old = conn.execute(select(artifacts.c.sha256).where(self.key(item.ref))).scalar_one_or_none()
            if old:
                if old != item.digest:
                    raise ValueError("immutable revision conflict; append a new revision")
                return old
            revisions = conn.execute(select(artifacts.c.revision).where((artifacts.c.kind == item.ref.kind) & (artifacts.c.id == item.id))).scalars().all()
            if item.revision != (max(revisions, default=0) + 1):
                raise ValueError("revisions must be appended without gaps")
            self._validate_competing_admission(conn, item)
            self._validate_intent_admission(conn, item)
            conn.execute(artifacts.insert().values(kind=item.ref.kind, id=item.id, revision=item.revision, sha256=item.digest, payload=item.canonical()))
            if isinstance(item, (HumanRating, PairwiseRating)):
                unit = item.model_run.model_dump(mode="json") if isinstance(item, HumanRating) else "pair"
                key = json.dumps([item.ref.kind, item.rater.id, item.round.id, unit], sort_keys=True)
                conn.execute(submission_keys.insert().values(semantic_key=key, kind=item.ref.kind, id=item.id, revision=item.revision))
            for ref in set(refs_in(item)):
                conn.execute(references.insert().values(kind=item.ref.kind, id=item.id, revision=item.revision,
                    target_kind=ref.kind, target_id=ref.id, target_revision=ref.revision))
        return item.digest

    def close(self):
        self.engine.dispose()
