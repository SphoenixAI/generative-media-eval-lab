# Hypotheses: Phase 4 structures, Phase 5 execution

Implemented records preserve observed problem, proposed mechanism, supporting and contradicting evidence, required evidence, discriminating test proposal, prediction, falsifier, intent and unresolved status. Relation claims distinguish an assertion from an observation and preserve scope, purpose, author and validity interval.

The sample sliding graph contains camera-motion and foot-contact alternatives. Both remain proposals. Recording a predicted outcome is not running a test; no confidence update or causal discovery engine exists at this checkpoint.

Phase 5 should register a controlled test before execution: hypotheses discriminated, one intended manipulated variable, required held-constant factors, measurement instrument and coverage, predicted and falsifying outcomes, limits and authority. Preserve failed or inconclusive tests. A static-camera regeneration changes the generated sample as well as camera instructions; treat that confounding explicitly and use multiple controlled replicates rather than attributing causality to one improved clip.

Do not store hidden chain-of-thought. Keep observations, concise rationale, competing claims, test specification, outcome and uncertainty.

## Human-declared hypothesis sets

`CompetingSet` records ordered `members` and explicit boolean `exclusive` and
`exhaustive` declarations under one pinned intent revision. Named members are
exact existing hypothesis revisions; at least one is required. A hypothesis
identity cannot appear twice, even at different revisions.

An exhaustive set automatically includes one structural `RESIDUAL` member with
the description `none of the listed causes`. This is not a substantive cause or
an evidence-backed hypothesis: it has no confidence, evidence, prediction,
falsifier or status. Non-exhaustive sets contain no residual. Confidence remains
attached to each claim, including unknown (`null`) values; it is never summed,
normalized, averaged or complemented for the residual.

Create a blank form with `eval-pilot draft competing-set --output set.json`.
Fill `members` with short hypothesis IDs (for example, `h1` or `h2@1`) and choose
both flags explicitly. Then submit it with:

```sh
eval-pilot --root /path/to/private-workspace --author YOUR_NAME competing-set CLIP --id causes --file set.json
```

An optional `--session ID` attaches the submission to an active authoring session.
Unqualified IDs resolve once to the latest revision; stored pins never float.
Repeating the set ID appends a revision with an exact `supersedes` predecessor.
Private `show`, snapshots and snapshot exports include the submitted sets and
their referenced history. Public/embed output does not expose them.

Human relation forms also accept `compatible_with` and `refines`, with two
distinct hypothesis identities under the same pinned intent. They remain claims,
never observations. Compatibility is unordered for conflict checking; refinement
records only the supplied subject-to-object direction and infers no other edges.
An exclusive set rejects compatibility between its exact pinned named members,
in either admission order. All retained set and relation revisions participate:
changing a set does not erase its earlier constraint, and a newer hypothesis
revision does not inherit membership. SQLite serializes these admission checks
inside its write transaction. These declarations establish neither causal truth
nor empirical completeness, and produce no quality verdict or confidence update.

## Private qualitative test plans

`TestPlan` declares a future test; importing, inspecting, classifying or freezing
it never runs generation, sampling or a HUMAN/INSTRUMENT measurement. Instrument
protocols are inert human declarations. No observation, outcome, confidence,
hypothesis status, evaluation or decision is inferred or modified.

Import complete human JSON with `test-plan --file FILE`. Supply `id`, `author`
(matching `--author`), `competing_set`, `arms`, `measurement`,
`outcome_categories` and `predictions`. `revision` defaults to 1; later revisions
require an immediate same-ID `predecessor`. Both references use
`{"ref":{"kind":"KIND","id":"ID","revision":1},"sha256":"DIGEST"}`;
revision is explicit, and SHA-256 is the retained artifact digest. The set kind
is CompetingSet, the predecessor kind is TestPlan. Neither pin floats to latest.
`created_at` may be supplied with a timezone; otherwise it is recorded locally.

Each arm has a unique nonblank `id`, nonblank `description`, and an explicit
`generation_plan_ref`: null or an exact GenerationPlan pin. Any referenced arm
requires `sample_design`, including mixed null/referenced arms. When supplied,
sample design has exactly one positive integer `n_per_arm` or nonblank
`stopping_rule`, plus a nonblank `decision_rule`. This records the human rule;
it does not judge statistical adequacy. At least one arm and outcome is required.
Measurement has `kind` (HUMAN or INSTRUMENT) and a nonblank `protocol`.

Outcome categories are unique nonblank strings. Predictions map every named
hypothesis ID in the exact set revision to a nonempty list of unique declared
outcome IDs. Unknown IDs, missing members and residual predictions are rejected.
For example, TEST-ONLY hypotheses A and B predicting respectively X and Y are
DECISIVE; both predicting X are NON_DIAGNOSTIC; A predicting X,Y with B predicting
Y is PARTIALLY_DIAGNOSTIC. An unused Z is separately UNPREDICTED in each example.
These labels describe declared overlap, not empirical power or causal truth.

Classification first checks whether all named prediction sets are identical
(always true for fewer than two named hypotheses), then whether every outcome
is compatible with at most one named hypothesis, then returns partial
classification. One identical pair among three hypotheses is insufficient for
NON_DIAGNOSTIC. Residuals are excluded and reported as `not testable by this plan`.
Compatible hypothesis IDs are sorted; outcomes and UNPREDICTED lists preserve
outcome-category order. Prediction-list order does not change the class.

```sh
eval-pilot --root ./private-workspace --author YOUR_NAME test-plan --file plan.json
eval-pilot --root ./private-workspace freeze-test-plan PLAN_ID@1
eval-pilot --root ./private-workspace verify-test-plan PLAN_ID@2 --file frozen.json
```

Only explicit freeze appends a frozen successor; stale drafts and already frozen
versions are rejected. The draft remains unchanged. Imports must omit
application-owned `frozen_at`, `frozen_digest` and `tool_version`. To revise a
frozen plan, import a new draft with the next revision and predecessor pin, then
freeze again. Local timestamps are not authenticated chronology or authorship.

The freeze digest hashes the complete frozen model JSON with only
`frozen_digest` omitted, using RFC8785 and the existing
`safe-integer-tokens-v1` profile. Identity, both timestamps, revision, predecessor,
set/generation pins, authored content, tool version and profile metadata are
covered. Arrays retain order; object key order and JSON whitespace do not matter.
Referenced records keep their separate historical artifact digests; confidence
values and generation settings are not copied into the freeze payload.

Verification reads an existing database without initializing or repairing it.
It checks retained artifact integrity, freeze digest and exact dependency closure;
an optional complete frozen file must also match the retained revision, even if
its altered digest has been recomputed. VERIFIED is integrity only; unavailable
evidence yields UNKNOWN, corruption yields INTEGRITY_FAILURE, and a draft yields
NOT_FROZEN. Those three statuses exit 2 and never return a diagnosticity claim.
Private `show` includes plans tied to the clip's retained intent revisions;
new snapshots include their histories and pinned dependencies. Old exports stay
fixed. Public/embed serialization omits these private declarations. `schema`
exposes the new record contract without modifying stored schema artifacts.

## Computed evidence roles

Roles are private, pair-specific computations on exact Evidence/Hypothesis pins.
`TEST_RESULT` requires a hypothesis revision created strictly before freeze and
named in the frozen plan's exact set, a checked evidence-to-arm link, evidence
created strictly after freeze, and either post-freeze source registration or a
retained post-freeze instrument run. `DISCOVERY` follows when evidence predates
the hypothesis or its explicitly pinned prompting observation cites it.
Otherwise the result is `SUPPORTING`, with a reason such as `EXISTING_CLIP`.
Missing necessary records or equal evidence/hypothesis timestamps produce
`UNKNOWN` with a null role; mismatched pins produce `INTEGRITY_FAILURE`.
A proven failed test predicate can make unavailable source chronology irrelevant.

Import complete associations with `evidence-arm --file FILE`,
`hypothesis-context --file FILE`, or `instrument-run --file FILE`. Each accepts
`id`, `author` matching `--author`, exact pins, and optional revision metadata.
Corrections append the next revision with `predecessor` and `revision_reason`;
the subject evidence/hypothesis pin cannot change. Omit application-owned
`created_at` (import time) and `tool_version`. No role/reason field is accepted.
`schema` exposes these contracts; existing stored schemas are unchanged.

EvidenceArm requires `evidence`, `plan`, `arm` and `clip`; optional `origin` pins
ClipOrigin (required for a declared generation arm), and `run` pins InstrumentRun.
HypothesisContext requires `hypothesis` and `observation`; that exact
TechnicalObservation must exist by hypothesis creation. InstrumentRun requires
`plan`, `arm`, `evidence`, `executed_at`, `tool`, `version`, `tool_sha256`,
`input_sha256` (source bytes) and `output_sha256` (Evidence artifact digest).
Execution cannot follow the evidence or import time. These are declared local
provenance records, not authenticated execution or instrument qualification.

Use `eval-pilot --root ./private-workspace evidence-role --file pair.json`, where
pair.json contains only `evidence` and `hypothesis` pins in the format above.
Queries write nothing and do not initialize missing workspaces; UNKNOWN and
INTEGRITY_FAILURE exit 2. Context lineage heads apply corrections; all exact
plan/set/source pins and consulted dependencies are returned. Multiple links are
checked in stable kind/ID/revision order; the first qualifying link is identified.
Freeze/creation equality never qualifies as before/after. Original registrations
and earlier registrations of identical bytes prevent old sources becoming new.
First-view telemetry is clip-level access, not pair-level human exposure; neither
viewing again nor a later clip revision changes creation/registration chronology.
Private `show` and new snapshots retain applicable context histories and cross-clip
dependencies for replay. Earlier snapshots and public/embed payloads stay fixed.
Roles never change confidence, observations, test outcomes, acceptability or verdicts;
the separate human confidence-form `evidence_role` field retains its old meaning.

## Private resolution events

`eval-pilot --root ./private-workspace --author YOUR_NAME resolve --file result.json` appends a private `ResolutionEvent` from a human-declared outcome. It checks prediction compatibility, without inferring causal truth, acceptability, confidence or a verdict.

Human JSON requires `id`, matching `author`, exact frozen TestPlan `plan` pin, an `outcome` from its categories, and nonempty `evidence`, for example `[{"arm":"ARM_ID","evidence":{"ref":{"kind":"Evidence","id":"EVIDENCE_ID","revision":1},"sha256":"DIGEST"}}]`. Pins require explicit revisions and retained artifact hashes. A sample design requires a nonblank `decision_reason` connecting the outcome to its frozen `decision_rule`.

Every evidence/hypothesis pair must recompute as TEST_RESULT in the exact plan and arm. Link corrections apply before filtering; foreign plans cannot qualify. Every arm needs qualifying evidence; fixed `n_per_arm` applies separately to each arm, including mixed generation/non-generation plans. Without a sample design, require one qualifying sample per arm without claiming stochastic sufficiency. Shortfalls or absent role evidence remain UNKNOWN. Drafts, undeclared outcomes and invalid pins are rejected.

Sample units use checked source-byte SHA-256 for clips, collapsing frames, evidence/link aliases and repeated registrations. The post-freeze instrument-run alternative uses retained run IDs, collapsing revisions. Duplicate units and repeated Evidence IDs reject across all arms, even with distinct run IDs. These rules establish neither independence nor sample-size adequacy. Textual stopping designs require `stopping` with matching `author`, exact `plan`, `rule` text, all `arms`, exact Evidence pins in `samples`, `met: true` and nonblank `reason`. Arms and samples must match without duplicates. This retains the human declaration; software does not interpret or certify rule prose, or bypass fixed counts/TEST_RESULT.

Named members are RETAINED exactly when their predictions contain the outcome, otherwise ELIMINATED, in set order. Structural RESIDUAL stays RETAINED. An unpredicted outcome is explicit; a non-exhaustive set gains no residual. `mode: "INDETERMINATE"` requires nonblank `indeterminate_reason`; named members remain INDETERMINATE, the residual stays RETAINED, and all admission prerequisites still apply. Corrections require the next `revision`, exact same-ID `predecessor` pin and nonblank `revision_reason`; old events stay immutable.

Human JSON omits computed statuses, roles, units/counts, dependencies, hashes, versions and timestamps. Both preparation and transactional admission verify raw frozen-plan JSON before restoring defaults, then verify artifact hashes, dependency pins and explicit freeze transition; admission also rederives event fields. A process-local receipt binds the entire event and application timestamp; altered or unprepared events reject. This is local issuance integrity, not authenticated chronology or authorship. Receipts are private and are not persisted. Events retain input hashes, exact dependencies, `resolution-v1` and package versions. Replay uses captured dependencies, including excluded link heads, despite later revisions. Identical pinned inputs reproduce statuses, ordering, units and hashes; fresh timestamps are excluded. Private `show`, runtime `schema` and new snapshots include event history and cross-clip dependencies. Existing exports stay fixed. Public/embed omit events and private inputs/reasons in blind and revealed states. No authored hypothesis or judgment is changed.
