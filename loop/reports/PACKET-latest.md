# Review packet

step | item | decision | Rv In Rl PQ Ac Sc | passed tests | gate | research C/X/O/U | flags
--- | --- | --- | --- | --- | --- | --- | ---
0028 | L12-A2c | REVERT | 4 4 4 4 4 4 | 5100 | True | 2/0/0/9 | flags: 1
0029 | L12-A2c | INTEGRATE | 4 4 4 4 4 4 | 5100 | True | 2/0/0/0 | flags: 1
0030 | L12-A2d | REVERT | 4 1 4 1 4 4 | 6179 | False | 2/0/0/0 | flags: 4
0031 | L12-A2d | SPLIT | ? ? ? ? ? ? | 0 | False | 0/0/0/0 | flags: 0
0032 | L12-A2d1 | REVERT | 4 1 2 1 4 4 | 5252 | False | 0/0/0/0 | flags: 3

## Loop health

- Consecutive non-integrations since RESUME: 0; trailing RF: 0.
- Product retries: L02: 1, L04: 1, L10: 1, L12: 1, L12-A2: 1, L12-A2d: 1, L12-A2d1: 1.
- BLOCKED: none.
- Last stop reason: consecutive non-integrations.

## New this step

- Full pytest execution was unavailable: the accessible interpreter lacks pytest, pydantic and sqlalchemy. Independent probes executed actual boundary, reader, preparation and accounting code with unavailable imports stubbed; SQLite probes were in-memory, not on-disk retained tests.
- Recomputed diff.patch SHA-256 and confirmed it matches diff_sha256.txt.
- Reviewed I1-I16 against the diff and supplied evidence. No demonstrated invariant violation warrants a zero score. External main/pilot-local state was not independently inspected.

## Open issues

- tree/tests/test_intent_v2.py:201-202 (steps 0006): MINOR production_quality: tree/tests/test_intent_v2.py:201-202: the initial-predecessor negative case reuses persisted revision 1 and accepts any ValueError. Removing only the initial-predecessor guard would still permit an immutable-revision conflict to satisfy this assertion.
- tree/loop/reports/STEP-0006-L02.md:37-51 (steps 0006): MINOR accuracy: External API, release and standards claims at tree/loop/reports/STEP-0006-L02.md:37-51 and :176-183 require independent source verification; supplied CONFIRMED labels were not treated as independent evidence.
- tree/src/eval_lab/seals.py:135 (steps 0007): MINOR intention: tree/src/eval_lab/seals.py:135 validates rows before filtering their source paths. An unrelated corrupt seal makes an unknown-ID lookup return INTEGRITY_FAILURE instead of the planned UNKNOWN; reproduced with the actual verifier and mocked boundaries.
- production_quality (steps 0011): MINOR production_quality: test_lifecycle_contract_constructor_and_copied_admission now provides 22 targeted cases with fresh IDs, valid referenced artifacts, specific ValidationError messages, nonadmission assertions and valid controls.
- tree/tests/test_relation_v2_snapshots.py:44 (steps 0017): MINOR production_quality: tree/tests/test_relation_v2_snapshots.py:44 does not independently prove direct-reference discovery: its declared intent is already in the original closure and its evidence media is in the dataset.
- tests/test_resolution_workflow.py:164-169 (steps 0018): MINOR production_quality: tests/test_resolution_workflow.py:164-169 does not independently prove revision-invariant instrument units: the repeated Evidence identity guard also satisfies its broad 'duplicate sample unit' assertion. An implementation that changes unit identity only
- src/eval_lab/lint_context.py:97-98; tests/test_lint_rule_manifest.py:280-287 (steps 0032): Independent role primitive-access accounting remains absent. audit rejects owner='role', and audit_role_access does not exist. E5/E6/W2/W3 therefore have declaration strings and access primitives without accounting that establishes their required reads. Both adapter instances of 
- src/eval_lab/lint_rule_manifest.py:47-67; tests/test_lint_rule_manifest.py:269-277 (steps 0032): The required inventory remains incomplete. COMPUTED is absent, leaving Evidence digest inputs and TestPlan authored-content operands undeclared. CompetingSet members declare mapping shape, kind and residual description but no conditional exact Hypothesis reference. The literal te
- src/eval_lab/lint_context.py:120-152; tests/test_lint_rule_manifest.py:290-295 (steps 0032): prepare checks scope pins and enumerates kinds but discards collection results. It never establishes root membership relative to scope or records active/inactive rule obligations. Receipt has no inactive accounting, and both checked-inactivity sentinel instances fail. The uncondi
- src/eval_lab/lint_rule_manifest.py:111-144; src/eval_lab/lint_rule_expansion.py:9-19; src/eval_lab/lint_context.py:90-116 (steps 0032): Expected obligations remain a manually executed recipe rather than a complete expansion of active declarations. The manifest supplies contracts only for paths requested by that recipe; nothing reconciles required declarations against requested paths. Fresh direct and in-memory SQ
- tests/test_lint_rule_manifest.py:47-102,138-163,220-249; src/eval_lab/lint_role_prerequisites.py:18-48 (steps 0032): New-validator coverage remains incomplete. The role field matrix tests only Hypothesis.confidence; role edge resolution, exact-history access and prediction-key handling lack isolated valid/negative controls. Accounting controls still lack unread-declaration and per-association s
- src/eval_lab/lint_context.py:97-98; tests/test_lint_rule_manifest.py:272-279 (steps 0032): There is no independent role-access expansion. audit rejects owner='role' immediately, and audit_role_access does not exist. Consequently E5/E6/W2/W3 have declaration strings and callable primitives but no accounting that establishes their required primitive accesses. Both adapte
- src/eval_lab/lint_rule_manifest.py:47-67; tests/test_lint_rule_manifest.py:261-269 (steps 0032): The claimed all-rule inventory is incomplete. COMPUTED is absent, so Evidence digest inputs and TestPlan authored-content operands are not declared as required by the sealed plan and the failing computed-input sentinel. CompetingSet.members also declares only mapping shape, kind 
- src/eval_lab/lint_context.py:120-152; tests/test_lint_rule_manifest.py:282-287 (steps 0032): prepare validates scope pins and enumerates kinds, then discards the collection results. It neither establishes root membership relative to the checked scope nor records checked active/inactive rule obligations. Receipt has no inactive accounting, and both checked-inactivity sent
- src/eval_lab/lint_rule_manifest.py:111-144; src/eval_lab/lint_rule_expansion.py:12-19; src/eval_lab/lint_context.py:99-116 (steps 0032): Expected obligations are a second manually executed recipe, not an exhaustive expansion of declarations. The manifest supplies a contract only after a recipe requests a path; nothing reconciles declared active fields with requested paths. In isolated direct and SQLite-reader prob
- tests/test_lint_rule_manifest.py:47-102,136-162,216-241; src/eval_lab/lint_role_prerequisites.py:18-48 (steps 0032): Focused controls do not cover every newly introduced validator and access branch as sealed. The new role field matrix exercises only Hypothesis.confidence; role edge resolution, exact-history access and prediction-key path handling have no isolated valid/negative controls. Accoun

## Standing limitations

- VALIDATION_LIMITATION: 37 recorded flags.
- RESEARCH_PENDING: 9 recorded flags.
- PUBLIC_PROSE: 23 recorded flags.
- HOME_PATH: 4 recorded flags.

Proposals awaiting approval: P0008-1: Normalize unpacked arrays before JsonValue validation; P0009-1: Include applicable RelationClaimV2 history in private dataset snapshots; WP07: Model-based instrument adapters; A3-01: Evidence partitions and withheld-context challenges; A3-02: Decision-relevance router; A3-03: Shared perception cache with evidence lineage; A3-04: Counterfactual tests of stated reasons; A3-05: Backed spans and evidence-carrying judgments; A3-06: Instrument validation ladder; A3-07: Labeling import adapter (Ultralytics, Roboflow, others); P0023-1: Decompose L12-A2 acceptance so focused validator controls fit bounded steps; P0030-1: Replan the remaining role controls and independent all-rule conjunction without reducing acceptance; P0030-2: Preserve blocking F0030-R1-001 and authorize an acceptance-preserving replan

Calibration self-minus-independent mean: -0.08333333333333333. Reverts: 12/32.

Rubric A2: accuracy covers builder/enhancer content only; scores before and after A2 are not directly comparable.

Step 0002 remains ABANDONED: HARNESS_INFRASTRUCTURE_FAILURE: duplicate model-authored research claim ids. Product retry charged: False.

Step 0005 remains REVERT: HARNESS_POLICY_FALSE_REVERT: research actionability / enhancer resolution mismatch. Product retry charged: False.

Step 0010 remains REVERT: HARNESS_POLICY_FALSE_REVERT: evaluator accuracy scored harness-written research bookkeeping. Product retry charged: False.

Step 0010 remains RESUME: A2 groups A-C validated; authorized recovery of L04. Product retry charged: False.

Step 0019 remains RESUME: Step 0019 reviewed: genuine L12 I2 failure reverted; fail-closed contract, standing rule and R0P validated.. Product retry charged: False.

Step 0028 remains RESUME: Steps 0027–0028 RF caused by the enhancer prompt-size harness defect, fixed in fa775547f6c1a0e8e42eeed8db4eb4831c244bd1; not Codex or product failures.. Product retry charged: False.

Step 0032 remains RESUME: Human reviewed Step 0032. Authorize one bounded L12-A2d1 retry targeting the five unresolved evaluator findings. Prior R1 decisions and retry accounting remain unchanged.. Product retry charged: False.

- Which integrated change most likely violates an invariant?
- Which research verdict is weakest?
- What should be deferred?
