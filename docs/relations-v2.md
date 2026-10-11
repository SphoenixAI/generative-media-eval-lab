# Private relation v2

`eval_lab.relation_v2.RelationClaimV2` stores supplied human-authored claims with `schema_version=2`. It does not generate judgments, validate argument truth, resolve hypotheses, or execute an operational purpose. Test fixtures are TEST-ONLY; real-clip content must be authored by a human.

The existing relation fields and predicates remain: `supports`, `contradicts`, `motivated_by`, `fulfills`, `violates`, `alternative_to`, `compatible_with`, `refines`. V1 records and their canonical bytes are unchanged. No v2 CLI authoring command or submission envelope is added.

Both purpose fields must be explicitly supplied, independently of the predicate:

- `epistemic_purpose`: `SUPPORT`, `RULE_OUT`, `DISCRIMINATE`, `LOCALIZE`, `EXPLAIN`, `QUALIFY`, `SCOPE`, `OPERATIONALIZE`.
- `operational_purpose`: `SHIP`, `REPAIR`, `REGENERATE`, `REVISE_RUBRIC`, `ADD_GOLD`, `RETRAIN_SIGNAL`, `INVESTIGATE`.

`intent` is an exact `Pin(ref=..., sha256=...)` for a retained `IntentSpecV2` or `IntentSpec`. `creative_anchor` is an ordered tuple of distinct nonblank criterion IDs from that exact v2 intent; it defaults to empty. A legacy intent permits only empty anchors. A criterion in another intent or revision cannot authorize an anchor.

`supports` and `contradicts` require a nonblank `warrant`; free-text `purpose` cannot replace it. `qualifier` and `rebuttal` are optional nonblank text. Omitted optional text remains `None`; supplied whitespace surrounding nonblank text is retained exactly. Purposes reject null, missing, blank, wrong-case, unknown and `UNSPECIFIED` values on v2 authoring.

Use `Repository.put(record)` for admission. Copied and deserialized inputs are revalidated. An Evidence subject is checked even when absent from `evidence`. V2-scoped evidence needs a retained `IntentBinding` with the same exact media reference and intent pin. Legacy evidence keeps its existing media-to-intent checks. Hypothesis endpoints retain their legacy intent reference and cannot be reinterpreted under v2. `fulfills` and `violates` permit v2 intent endpoints equal to the declared intent. Existing status, endpoint, interval and self-relation restrictions apply. No technical observation or acceptability assessment is created.

Revision 1 has no predecessor; each successor pins the immediate same-kind, same-ID revision and digest. Exact replay is idempotent, conflicting revisions fail, and earlier canonical bytes remain unchanged. `compatible_with` conflicts with retained exclusive competing sets for both relation versions, under the repository writer transaction.

`load_relation(repo, ref)` returns a retained v2 record or a frozen, unregistered `LegacyRelationView`. The v1 view delegates authored fields, reference, canonical bytes and digest to `source`; both new purposes are `UNSPECIFIED`, anchors are empty, and argument text is absent. Reading performs no migration or write.

Ordinary `PilotWorkspace.snapshot(dataset_id, id)` discovers applicable stored v2 relations without requiring submission envelopes. It first builds the dataset's existing exact outgoing closure. Relations qualify through an exact subject, object or evidence reference in that closure. An intent-only connection requires the declared exact intent in the closure and nonempty evidence media wholly within the original dataset clip/binding media context. Sharing an intent alone cannot import another clip's relation.

Incoming discovery runs once against the original context. Newly added dependencies do not seed additional incoming relations. Each selected revision contributes all outgoing dependencies, including its exact intent, evidence, endpoints and predecessor chain. Applicable retained revisions are included, not just the latest. Existing media verification, ordering and seal inclusion remain active.

`export_snapshot(id)` retains private relation payloads and pinned hashes under `PRIVATE_LOCAL_NOT_PUBLISHED`. Later relations and intents do not rewrite a previous snapshot. Public/embed serializers remain separate allowlists and do not expose these private fields. Missing evidence and quality verdicts remain UNKNOWN; these contracts provide no empirical media-quality validation.
