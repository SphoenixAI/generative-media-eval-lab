# Intent v2 and local provenance

`IntentSpecV2` is an additive domain API in `eval_lab.intent_v2`, with `schema_version=2`.
It requires an owner, objective, `use_context` (surface, audience, FEED/STUDIO viewing profile),
and nonempty criteria. Each criterion has a unique ID, dimension, MUST/SHOULD/COULD/WONT
priority, acceptance, rejection and human-authored tolerance text. Several criteria may
address the same dimension. Expected deviations name a criterion in this exact revision
and use its dimension. Required text cannot be blank; dimensions have no SENSITIVE or
INVARIANT labels. Every revision, including the first, requires SERENDIPITY, CLARIFICATION,
CORRECTION or SCOPE_CHANGE as `revision_reason`. Successors pin the immediate predecessor's
exact reference and SHA-256. Constructors check structure; repository admission also
verifies every referenced digest and consecutive history, including copied nested inputs.

A concrete TEST-ONLY example, using an in-memory repository:

```python
from eval_lab.persistence import Repository
from eval_lab.intent_v2 import IntentSpecV2, Pin

repo = Repository()
first = IntentSpecV2(
    id="TEST-ONLY-intent", owner="TEST-ONLY", objective="TEST-ONLY motion example",
    revision_reason="CLARIFICATION",
    use_context={"surface": "TEST-ONLY", "audience": "TEST-ONLY", "viewing_profile": "FEED"},
    criteria=[{"id": "motion", "dimension": "motion_plausibility", "priority": "MUST",
               "acceptance": "TEST-ONLY continuous motion", "rejection": "TEST-ONLY jump",
               "tolerance": "TEST-ONLY no visible discontinuity"}])
repo.put(first)
second = first.model_copy(update={"revision": 2, "revision_reason": "CORRECTION",
    "predecessor": Pin(ref=first.ref, sha256=first.digest)})
repo.put(second)  # revalidates copied fields and checks the predecessor digest
repo.close()
```

`IntentBinding` pins the intent, original media and original `MediaIngestion`, whose
`created_at` is the registration anchor. Its `provenance` property is computed, never an
input field. Optional `SealEvidence` and `PlanEvidence` are immutable embedded values:
they pin exact intent revisions; the plan also pins its bound registration. They are an
internal seam for later lifecycle work, not authenticated seals or a generation-plan
workflow. No CLI accepts trusted timestamps or computed provenance. Event instants must
include timezones and normalize to UTC; absent optional facts remain absent.

| Class | What it records | What it does not prove |
| --- | --- | --- |
| SEALED | The exact revision's seal precedes a plan listing it, and that bound plan precedes registration; both comparisons are strict. | That generation occurred after sealing, or that the result is acceptable. |
| CONTEMPORANEOUS | SEALED fails, but the exact revision was sealed strictly before the first logged view. | That no earlier unlogged viewing occurred. |
| RECONSTRUCTED | No qualifying chronology, including never-sealed revisions and legacy intents. | That the intent governed generation. |
| PROMPT_ONLY | An explicit declaration, allowed only for FOUND clips bound to v2 intent. | Verified contemporaneous intent or an excuse for a deviation. |

Missing first-view evidence cannot establish contemporaneity; independently qualifying
SEALED evidence still suffices. Equal times do not satisfy strict comparisons. An earlier
revision's seal or another registration's plan cannot establish the required ordering.
Local timestamps cannot prove generation order without an external witness: a previously
generated clip could be registered after a new seal and plan. This implementation supplies
no witness, clock authentication, or quality verdict. Under I7, RECONSTRUCTED and PROMPT_ONLY
cannot excuse material deviations; CONTEMPORANEOUS requires a flag. Acceptability remains
a separate, unimplemented operation here, and missing judgment evidence stays UNKNOWN.

Binding history is append-only, with immutable media/registration pins, registration time
and origin. Successors may stay in their class or move SEALED → CONTEMPORANEOUS/RECONSTRUCTED,
CONTEMPORANEOUS → RECONSTRUCTED, or PROMPT_ONLY → RECONSTRUCTED; all other changes fail.
Validated source-checksum equality groups byte-identical aliases into one binding lineage,
even when both IDs and alias registration times differ. This conservative local policy
does not establish a common generation event. Different bytes may have independent lineages.
Admission checks this policy within the SQLite writer transaction. Private `snapshot` and
`export-snapshot` retain all relevant binding revisions and pinned dependency closure,
including a binding first recorded against aliases. Frozen exports keep their earlier pins.
Public/embed serializers are unchanged; private exports must not be published as public data.

Pilot 0's `IntentSpec`, `PilotWorkspace.intent` and `eval-pilot intent` remain legacy v1
authoring paths. `LegacyIntentView(source=repo.get(ref))` reads them as RECONSTRUCTED without
rewriting their canonical payloads, references or digests or inventing v2 metadata. Bindings
to v1 always derive RECONSTRUCTED; changing to a v2 intent cannot raise an existing lineage.
Use the v2 domain API for the new contract; this step adds no v2 authoring CLI or migration.
