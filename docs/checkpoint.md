# Phase 4 checkpoint — 2026-10-06

**Result: APPROVED_FOR_OFFLINE_TESTING.** Scientific/empirical status: **NEEDS_HUMAN_VALIDATION**. The implementation stops at the brief's Phase 4 boundary. No live inference, real media study, paid execution, public deployment or Git publication occurred.

## Research and independent review

Three specialist agents researched media benchmarks/models, measurement/standards/ontology, and agent harnesses/practitioner methods. They then conducted a separate freshness sweep, source fact checks and cross-review. Registers contain **83 distinct primary URLs across 33 domains**, with access dates and claim limitations. Coverage reaches **October 6, 2026**, including available early-October work; it does not cover the rest of October or claim an exhaustive internet search. [Research manifest](../outputs/research-manifest.json).

The primary comparisons include VBench/VBench2, EvalCrafter, T2V-CompBench, VideoScore, compositional image evaluation, physical/dynamic video tests, RAVEN-Eval, newer typography/audio/intelligence benchmarks, current vendor/open-weight candidate models, human annotation statistics, NIST/ITU/ISO/W3C/C2PA scope, and recent judge-consensus/harness practice. [Full synthesis](research/synthesis.md), [model and benchmark report](research/media-methods.md), [standards report](research/methods-standards.md), [agent report](research/agent-harness.md).

Source review corrected stale paper-version details, C2PA dating, early-access versus available model claims, and ITU-T P.910's superseded edition. The current P.910 catalog points to July 2026. These corrections and remaining source limits are in the [independent fact-check](research/independent-fact-check.md). No paper's experiments were replicated or its numerical gains imported as this system's performance.

## Architecture created

One Python package separates typed domain values, persistence, versioned rubrics, scoring, agreement, provider contracts, bounded specialists, disagreement, presentation and validation. SQLite is the verified database; SQLAlchemy provides the migration boundary. Thirteen evaluation dimensions have behavioral 0–4 anchors. Intent determines applicability and missing evidence remains unknown. [Architecture](architecture.md).

Seventeen persisted artifact types are implemented: IntentSpec, PromptSpec, MediaAsset, ModelRun, Rubric, Evidence, HumanRater, HumanRating, PairwiseRating, EvaluationRound, EvaluatorVersion, Hypothesis, RelationClaim, HypothesisGraph, AgentAssessment, Disagreement and EvaluationCase. Supporting value types include Criterion, EvaluationDimension, DimensionScore, Ref and Parameter. Later gold, adjudication, drift/regression and production intervention artifacts remain documented contracts.

Relations carry intent, purpose, epistemic status, author, evidence, scope and validity. They connect evidence to competing explanations and those explanations to the goal they serve. Typed edges and provenance do not imply causal truth, authenticated authority or formal OWL/SHACL conformance.

The initial directory was empty. Added source/modules, five test files, locked package configuration, research registers, methodology/architecture documents, checkpoint/review records, and generated demo/approval examples. See the [README tree](../README.md) and [file manifest](../outputs/file-manifest.json) for the concrete inventory. No existing project code was replaced.

## Executed validation

The final locked-environment harness ran **142 tests: 142 passed, 0 failed, 0 errors, 0 skipped**. **Seven gates passed** and **four of four local software mutations were caught**. The two independent database/demo runs produced identical canonical outputs. The checked source digest is:

`d21debe14d30ce6bbc25b094c2c3b51c1ed0c4293fe357160db1bbb7ad5967af`

The exact manifest, runtime versions, test output, gate outcomes and mutation details are in [approval.json](../outputs/approval.json). Python 3.12.14 was used. One dependency warning notes deprecated httpx use in Starlette's test client; all endpoint checks passed. The environment was checked with `uv sync --frozen --extra test --offline` before the final harness.

Agreement implementation was checked against Krippendorff's original worked example and an independent library on missing-data matrices. Original nominal/ordinal/interval reference values are approximately 0.743/0.815/0.849. This validates the numerical implementation, not real annotator reliability. Demo agreement uses just two authored units and must not be presented as a measured study result.

Independent reviewers reproduced and helped correct wrong-kind references, historical round-closure bypass, duplicate votes after rater revision, double-counted rating revisions, incompatible regeneration thresholds, forged embedded graph claims, cache/rubric/evidence mismatches, and assessment identity collisions. A forced SQLite duplicate race and closure interleaving now pass. [Independent review](review-methodology.md).

## Demo and requested serialized examples

Command:

```sh
.venv/bin/python -m eval_lab.demo --output outputs/demo.json
```

Sample actual CLI output:

```json
{"phase":4,"fixtures":12,"agent_assessments":156,"paid_calls":0,"replay_calls":0,"output":"outputs/demo.json"}
```

Twelve scenario records cover beautiful-but-wrong, correct-but-plain, geometry collapse, camera-only failure, physics-only failure, identity drift, simple/expensive repair candidates, regeneration, vague-aesthetic disagreement, a deliberately wrong mock judge reference scenario, and a regression-policy fixture. They are metadata and authored observations; no playable media exists.

The selected prompt-adherence disagreement records synthetic human scores **0, 1, 3**, versus mock specialist **0**. The ordinal span of 3 requests human adjudication. Its proposed classifications remain `ambiguous_generation` and `calibration_issue`; the system does not infer the cause from the scores. Actual geometry catastrophe yields `FAILED`/`REGENERATE`, while high aesthetics cannot cancel prompt failure.

- [Full CLI result](../outputs/demo.json)
- [Blind public case before submission](../outputs/blind-case.json)
- [Public case after submission](../outputs/public-case.json)
- [Embed case from the same records](../outputs/embed-case.json)
- [Competing-hypothesis graph](../outputs/hypothesis-graph.json)

Before submission, both presentation modes omit judge scores and human distributions. Reveal requires a stored rating for the same stable rater/round identity. Published agent results are explicitly pinned to a case revision; unpublished reevaluations cannot silently appear. Public session authentication and media delivery are not implemented.

## Important design choices

1. **Intent before metrics.** A surreal shot may legitimately violate terrestrial physics; criteria and exclusions are declared before evaluation.
2. **Evidence before scoring.** Absence is not a zero or a pass. Confidence is explicitly uncalibrated.
3. **No universal average.** Critical failure vetoes survive strong aesthetics. Ordinal labels do not become interval percentages.
4. **No consensus certification.** Thirteen fixture roles share authored rules. Their agreement supplies no independent correctness evidence.
5. **Finite automation.** Trusted async fixture calls have call/time limits, exact-input caching and structured failure states; no recursion or paid adapter exists.
6. **Explicit publication.** Public and embed outputs are allowlist projections of the same stored case, with publication snapshots.
7. **Independent usefulness test.** Compare human-only, single-judge assistance and specialists at matched budgets; separately test whether intent-bearing relations outperform a flat evidence log.

## Technical debt and assumptions

Actual media decoding, ffmpeg extraction, derivative manifests and temporal coverage sufficiency are not implemented. Fixture hashes represent authored scenario content, not verified media bytes. Fixed confidence values are demonstration data. Real judge grounding, calibrated probabilities, validated anchors and measured human-time savings remain unknown.

SQLite initialization records schema v1, but there is no later-version migration runner. PostgreSQL behavior, distributed concurrency, identity/privacy/consent, protected holdouts, durable queues, process-isolated providers, atomic paid budgets and remote cancellation require later work. The current mode flag and cooperative timeout are not a security sandbox. Local hashes and append-only triggers do not resist an administrator controlling the host.

The broad "first backend demo" in the master brief mentions later gold/regression/VFX and executed-test workflows. Its final first-execution/stop instructions explicitly limit this checkpoint to Phases 1–4. Those later workflows are documented, not misrepresented as complete. The product-engagement graph is deferred with Phase 9. No polished frontend was built.

## Decisions for the next separately scoped pilot

Choose the initial production user and shot types, rights-cleared media, intended artistic context, severe-defect consequences, reviewer population and time/cost limits. Then preregister meaningful quality and efficiency margins and size the study from the measured baseline. Humans retain authority over creative intent, disputed consequential judgments, rubric/gold changes and deployment scope.

The next step is a controlled real-media pilot, not a claim of maximum efficiency or future-proof correctness. The current code and harness are ready to test that proposition after the Phase 4 checkpoint is accepted.
