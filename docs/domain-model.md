# Domain model and persistence

The implemented model contains registered artifact types plus typed value objects. Core definitions live in `src/eval_lab/domain.py`, with additive Pilot 0 and intent v2 modules; storage and relationship checks live in `src/eval_lab/persistence.py`. See [Intent v2 and derived provenance](intent-provenance.md) for exact revision pins, legacy compatibility and private binding history.

## Records that exist

- **IntentSpec, PromptSpec** define the evaluation purpose and the requested content, with versioned intent references.
- **MediaAsset, ModelRun** connect media metadata and a checksum to a provider/model version, prompt, parameters, generation time and lineage. Fixtures use `fixture://` locations; no playable video is supplied.
- **Rubric** contains typed `EvaluationDimension` values, five anchors per dimension, hard-failure and regeneration policy thresholds, a version label and rationale.
- **Evidence** records timecoded observations and sampling coverage with source/method/author metadata.
- **HumanRater, HumanRating, PairwiseRating, EvaluationRound** represent participants, dimension judgments, A/B/tie/cannot-determine responses and the blinded comparison protocol.
- **EvaluatorVersion, AgentAssessment** pin a provider/model snapshot, prompt template/version, configuration, code version and rubric digest to structured assessment output and its request hash.
- **Hypothesis, RelationClaim, HypothesisGraph** preserve competing explanations, intentional relationships and evidence references without implementing a causal or experiment engine.
- **Disagreement** records scored differences, proposed disagreement categories and a human-adjudication flag. Its classification remains a proposal.
- **EvaluationCase** binds compatible runs, intent, rubric and an optional hypothesis graph to private/curated presentation metadata. Its `published_assessments` tuple selects exact `AgentAssessment` revisions for presentation and defaults to empty.

Supporting value types include `Ref`, `Criterion`, `Parameter`, `EvaluationDimension` and `DimensionScore`. Unknown fields are rejected, scores are strict integers from 0 through 4, and nonfinite numeric values are rejected. Every scored dimension requires evidence, rationale and a confidence value labeled self-reported and uncalibrated. Abstention and non-applicability cannot carry an invented score or confidence.

## Identity and immutability

Artifact identity is `(kind, id, revision)`. References name exact revisions, not a floating latest version. Canonical JSON and SHA-256 provide snapshot-integrity checks. Frozen typed objects, revalidation on persistence and append-only SQLite triggers prevent ordinary mutation of stored snapshots. This detects tampering with content without a corresponding digest update; it is not cryptographic signing or protection against an administrator who can replace the database.

Most artifacts may append consecutive revisions. Human and pairwise ratings are immutable one-time submissions at revision 1. Corrections require a future adjudication workflow rather than adding another observation. Exact replays return the original digest; conflicting content at an existing identity is rejected.

An evaluation round's candidates, rubric and assignment seed cannot change in a later revision, and a closed round cannot reopen. Current lifecycle state determines admission while historical protocol references remain inspectable.

## Storage boundary

SQLAlchemy defines `artifacts`, `artifact_references`, `submission_keys` and `schema_migrations`. Validated JSON snapshots are stored with explicit SQL reference edges. Foreign keys protect reference existence. Application validators additionally enforce semantic reference kinds, same-output evidence, compatible intent and embedded graph-edge integrity. A relation's evidence, including an evidence subject, must trace to a model run using its declared intent. A case's published assessments must be unique, reference its exact model runs and use its rubric.

Semantic submission keys prevent a calibration revision or round revision from creating duplicate human observations. SQLite immediate writer transactions and a commit-time round-state check protect the tested closure and duplicate races. `Repository.all(kind)` returns every stored revision; consumers must choose their intended versions. Rating consumers are protected from revision double counting because rating revisions are prohibited.

Schema version 1 is bootstrapped and unknown migration versions are rejected. This is not a complete migration runner. SQLAlchemy provides a path to PostgreSQL, but PostgreSQL triggers, writer isolation, migration tooling and load behavior have not been validated. The in-memory repository is for deterministic tests; the file-backed SQLite path is the tested concurrent-writer boundary.

The Phase 4 presentation serializer accepts only assets marked `synthetic_fixture`. It keeps assessments hidden until a human submission and then exposes only the case's explicitly published selection, with evaluator digests. The demo appends case revision 2 to select its assessment results; a new assessment on a matching run does not automatically enter that selection. These are local fixture contracts, not public media delivery or authenticated publication.

## Deliberately absent after Phase 4

There are no implemented GoldExample, Adjudication, BenchmarkSuite, RegressionReport or DriftReport engines; no completed VFX cost estimator; no authentication/authorization product; no real provider execution; no production media ingestion pipeline; and no final frontend. Any later-phase fixture labels or assessment recommendations demonstrate contract shape, not implementation of those subsystems.

The legacy ontology's approval and provenance labels are trusted authored inputs. Intent v2 binding provenance is derived from pinned local chronology, whose event evidence remains unauthenticated. A production service must bind users and agents to authenticated principals and enforce authority outside these local record constructors.
