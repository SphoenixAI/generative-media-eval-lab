# Private decision policies and terminal verdicts

L06 consumes pinned human evaluations. It never derives human intent fulfillment,
salvage judgments or hypothesis relevance from media or prose. The supplied tests
are TEST-ONLY declarations; no production policy is installed or selected by default.
Fixture success does not establish useful decisions on real media.

`eval-pilot schema` includes DecisionPolicy, TerminalVerdict and decision-preview forms.
Use `--root PRIVATE_WORKSPACE --author HUMAN decision-policy --file POLICY.json`
to import a complete human policy, or `terminal-verdict CLIP --file VERDICT.json`
to import a complete human verdict. `decision-preview CLIP --file INPUT.json` opens
an existing database read-only and prints only derived fields. It writes nothing.
The input form is the verdict without technical_integrity, decision, flags or
application-recorded tool_version. Preview does not submit a human verdict.

Policy fields include id, version, exact UseContext scope, author and ordered rules.
Version equals artifact revision. Every rule has a unique id, action and optional
`when` conjunction. Exactly one unconditional rule must come last. First match wins.
Actions are SHIP, HOLD, REPAIR, REGENERATE and INVESTIGATE. Supported conditions:

- `priority_status: [PRIORITY, STATUS]` matches both on the same criterion.
- `worst: [DIMENSION, MINIMUM]` compares known deviations in ordinal order
  NONE, MINOR, MATERIAL, SEVERE, CATASTROPHIC. UNKNOWN never satisfies a threshold.
- `provenance: [CLASS, ...]` matches one permitted intent provenance class.
- `salvage_guess` matches the explicit human value.
- `unresolved_at_least` counts unique declared-relevant hypotheses with status
  literally `unresolved`. Other statuses and empty relevance lists do not count.
- `unknown_must` matches missing assessments, UNKNOWN assessments, empty support
  or UNKNOWN supporting observations for any MUST criterion.

No expressions or callbacks are evaluated. Unknown names and invalid operands fail.
Policies cannot SHIP with unknown MUST evidence or excuse material deviations under
RECONSTRUCTED/PROMPT_ONLY intent. CONTEMPORANEOUS excuses retain their flag.
Other actions remain operational decisions; they do not change any evaluation.

Verdicts pin exact clip/media, intent/binding, policy, observations, assessments and
hypotheses. Each hypothesis relevance entry has criterion_ids and a nonblank
rationale. Its source must match the clip's pinned legacy intent and media; relevance
maps it to v2 criteria without asserting the two intent revisions are equivalent.
One selected assessment per criterion is allowed. Its supporting observations must
be retained, and additional observations contribute to worst-case integrity.
Each dimension retains both its worst known deviation and an unknown marker.
An entirely unobserved dimension is UNKNOWN. Selection is not exhaustive coverage.
Human intent_fulfillment and salvage_guess are required, including explicit UNKNOWN.
An override needs action, nonblank reason and author; it preserves the policy result.

Admission recomputes integrity, flags, first matching rule and input hash and rejects
mismatches. The SHA-256 input envelope uses the existing constrained canonical JSON
codec: schema_version=1; exact clip/media/intent/binding/policy source pins; sorted
assessment/observation pins; policy id/version; criteria priority/status pairs in
criterion-ID order; all dimension integrity summaries; provenance, salvage_guess,
unresolved count and unknown_must; author, intent_fulfillment and sorted relevance.
Relevance criterion IDs and set-like selections are sorted by canonical bytes/ID;
policy rule order is preserved in its pinned digest. Source digests retain original
float-valued records without placing floats in this envelope. Verdict IDs, creation
times, revision metadata and overrides are excluded. Fixed inputs replay identically;
new IDs, clocks, human reliability and policy usefulness are not deterministic claims.

Corrections append revisions with immediate predecessor pins and revision_reason.
Verdict clip/media and intent/binding context stay fixed across revisions. Private
show/snapshot discover exact clip/media verdict histories and their dependencies,
including direct repository admissions. Frozen exports and public/embed allowlists
are unchanged. The unchanged Phase 2 engine is the legacy “intent-blind default”
only with respect to v2 provenance, assessments and policies: it DOES read legacy
IntentSpec applicability and authority. Missing legacy intent is not a valid call;
missing intent/evidence remains UNKNOWN, without a fabricated terminal verdict.
Legacy provisional PASS is not SHIP. See `docs/scoring.md` for the existing engine.
