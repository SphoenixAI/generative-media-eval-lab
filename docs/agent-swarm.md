# Phase 4 specialist workflow

The current swarm is an offline workflow simulator. It exercises structured contracts and failure handling using declared synthetic rules. It does not inspect pixels, run a language model, establish gold labels or validate a media evaluator's accuracy. `SwarmResult.acceptance` remains `HUMAN_VALIDATION_REQUIRED` even when every specialist agrees.

## Execution

`BoundedSwarm.run` receives a tuple of `EvaluationRequest` objects, a `ModelRun`, a pinned `EvaluatorVersion` and an explicit assessment timestamp. The registry maps thirteen evaluation dimensions to specialist names. It runs selected dimensions sequentially, with no debate, recursive spawning or specialist-to-specialist messages. Independent first pass means specialists do not receive one another's outputs; it does not imply independent statistical errors.

The registry contains PromptAdherence, TemporalConsistency, TemporalGeometry, CameraLanguage, MotionPhysics, SubjectConsistency, ArtifactDetection, Composition, VFXSalvage, SemanticConsistency, OcclusionConsistency, LightingContinuity and AestheticQuality roles. The VFX role currently returns an editability fixture score, with post-production fixability remaining `UNKNOWN`; it does not perform production cost estimation. AdversarialPrompt, BiasCalibration, RegressionSentinel and Adjudication are explicitly deferred roles, not implemented live agents.

Each request contains a media checksum, prompt text, complete intent snapshot, rubric digest, dimension, evidence snapshots and optional fixture code. It omits the generating model's name and provider, human ratings, gold answers and other agent assessments. This structural omission is not a proof against semantic leakage in arbitrary user-supplied text or fixture identifiers. Fixture codes deliberately identify rule cases and must never enter a real blinded benchmark.

## Bounds and failure behavior

The initial configurable bounds are at most thirteen unique dimensions, thirteen calls, a one-second per-call timeout and a fifteen-second total timeout by default. Configuration permits smaller call budgets and bounded timeout changes. A cache hit does not consume another provider-call count. A call attempt counts even if it times out or produces an invalid response. No automatic retries exist.

`asyncio.wait_for` supplies **cooperative cancellation**. It cannot forcibly stop blocking Python code, a provider that suppresses cancellation, native work or a separate remote service. Caller cancellation propagates instead of being reported as successful evaluation. There is no persistent checkpoint/resume system or guaranteed partial report on caller cancellation. Process isolation and actual provider-side cancellation are future requirements for untrusted or expensive execution.

Zero budget, exhausted time, a cooperative timeout, invalid provider output and provider exceptions produce an explicit abstention for affected dimensions. Already completed results remain in a normally returned partial result. Provider exception strings are replaced with generic failure messages so accidental secrets are not copied into traces. Returned rationale text is still untrusted data and must pass through curated serializers before publication.

`max_cost_usd` and `paid_calls` are fixed at zero, and a provider whose declared mode differs from `deterministic_fixture` is rejected. **This is fixture-mode policy, not production budget authority or an operating-system sandbox.** The Python provider object is trusted application code; a malicious object can lie about its mode or perform side effects before returning. Production enforcement will need provider allowlists, credentials scoped outside reviewers, real usage accounting and network/tool boundaries. No claim of a prompt-injection-proof live agent follows from the deterministic caption-injection test.

## Contract and cache

Structured results are reparsed through `DimensionScore`. Scored results require an integer category from zero through four, confidence and evidence references. Unknown fields, malformed numeric values, a different dimension, invented evidence references and changed applicability are rejected. Abstention and not-applicable results cannot invent a score or confidence. A successful result records a concise rationale, observable evidence references and version references; hidden chain-of-thought is neither requested nor stored.

The cache is local to the `BoundedSwarm` instance and has no durable or shared storage semantics. Its key contains provider identity, evaluator digest and request digest, so prompt, intent, evidence, checksum, fixture code and evaluator configuration changes can invalidate reuse. Cached artifacts represent replay rather than another independent trial. Cache hits preserve the underlying score and emit a `cached` trace step. There is no production cache eviction, cross-tenant cache policy or concurrent request coalescing in Phase 4.

The pinned evaluator records a rubric digest, and the workflow checks request agreement with that digest. Evidence must name the supplied model run's media. Fixture-rule snapshots participate in provider identity, and assessment identifiers include request identity, preventing a changed request from silently overwriting a previous assessment under the same ID. The workflow still receives a checksum rather than reading asset bytes: verifying a stored media file's hash and evidence timestamps against actual duration belongs to ingestion/persistence validation, not to the fixture lookup.

`DeterministicFixtureProvider` returns rule-based synthetic scores only, abstains when a rule or evidence is missing, respects declared not-applicable criteria and rejects real-observation evidence for scoring. Its confidence value is labeled self-reported and uncalibrated; it is not a probability of correctness. The generic suggested test and intervention text are fixture scaffolding, not executed experiments or individualized production advice.

## Review evidence and promotion boundary

`tests/test_swarm_review.py` contains independent probes for cache replay/invalidation, changed rule snapshots, request identity, foreign evidence, rubric mismatch, budget exhaustion, duplicate plans, live-mode denial, invalid scores, extra action fields, fabricated references, applicability changes, exception redaction, missing evidence, real-media rejection, inert caption instructions, cooperative timeout and caller cancellation. The executed test report, rather than this list, establishes which checks passed against a particular code revision.

Passing these probes supports offline contract testing. Before a real provider is enabled, separately measure temporal coverage, evidence grounding, judgment accuracy, calibration, severe-failure recall, human review time and the value of specialists against a competent single-judge baseline. Agent agreement alone cannot promote an evaluator or authorize deployment. The broader research and future approval design are in `research/agent-harness.md`.
