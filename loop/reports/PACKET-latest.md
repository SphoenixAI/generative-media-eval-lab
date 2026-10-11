# Review packet

step | item | decision | Rv In Rl PQ Ac Sc | passed tests | gate | research C/X/O/U | flags
--- | --- | --- | --- | --- | --- | --- | ---
0029 | L12-A2c | INTEGRATE | 4 4 4 4 4 4 | 5100 | True | 2/0/0/0 | flags: 1
0030 | L12-A2d | REVERT | 4 1 4 1 4 4 | 6179 | False | 2/0/0/0 | flags: 4
0031 | L12-A2d | SPLIT | ? ? ? ? ? ? | 0 | False | 0/0/0/0 | flags: 0
0032 | L12-A2d1 | REVERT | 4 1 2 1 4 4 | 5252 | False | 0/0/0/0 | flags: 3
0033 | L12-A2d1 | REVERT | 4 1 2 2 4 4 | 5485 | True | 0/0/0/0 | flags: 5

## Loop health

- Consecutive non-integrations since RESUME: 1; trailing RF: 0.
- Product retries: L02: 1, L04: 1, L10: 1, L12: 1, L12-A2: 1, L12-A2d: 1, L12-A2d1: 2.
- BLOCKED: L12-A2d1.
- Last stop reason: once complete.

## New this step

- Independent probes executed actual boundary, reader and accounting source with unavailable registration/model imports substituted. SQLite probes used in-memory databases and actual RawReader methods; they do not verify the on-disk read-only session lifecycle.
- Independently verified the patch SHA-256 and exact contents of all changed files.
- Reviewed I1-I16 against the changed paths and behavior. Found no real judgment creation, authored-history mutation, protected/harness edit, existing-test weakening, network dependency, public serializer change, deferred implementation or Git action. Complete semantic support remains denied; no score
- The enhancer's REJECTED_WITH_REASON entries acknowledge valid unresolved findings and an unapplied repair. They do not justify REJECTION_ACCEPTED or DEFERRAL_ACCEPTED.
- The supplied gate reports 5485 passing tests. Full pytest was not independently runnable because the available Python lacks pytest and project dependencies.

## Open issues

- tree/tests/test_intent_v2.py:201-202 (steps 0006): MINOR production_quality: tree/tests/test_intent_v2.py:201-202: the initial-predecessor negative case reuses persisted revision 1 and accepts any ValueError. Removing only the initial-predecessor guard would still permit an immutable-revision conflict to satisfy this assertion.
- tree/loop/reports/STEP-0006-L02.md:37-51 (steps 0006): MINOR accuracy: External API, release and standards claims at tree/loop/reports/STEP-0006-L02.md:37-51 and :176-183 require independent source verification; supplied CONFIRMED labels were not treated as independent evidence.
- tree/src/eval_lab/seals.py:135 (steps 0007): MINOR intention: tree/src/eval_lab/seals.py:135 validates rows before filtering their source paths. An unrelated corrupt seal makes an unknown-ID lookup return INTEGRITY_FAILURE instead of the planned UNKNOWN; reproduced with the actual verifier and mocked boundaries.
- production_quality (steps 0011): MINOR production_quality: test_lifecycle_contract_constructor_and_copied_admission now provides 22 targeted cases with fresh IDs, valid referenced artifacts, specific ValidationError messages, nonadmission assertions and valid controls.
- tree/tests/test_relation_v2_snapshots.py:44 (steps 0017): MINOR production_quality: tree/tests/test_relation_v2_snapshots.py:44 does not independently prove direct-reference discovery: its declared intent is already in the original closure and its evidence media is in the dataset.
- tests/test_resolution_workflow.py:164-169 (steps 0018): MINOR production_quality: tests/test_resolution_workflow.py:164-169 does not independently prove revision-invariant instrument units: the repeated Evidence identity guard also satisfies its broad 'duplicate sample unit' assertion. An implementation that changes unit identity only
- src/eval_lab/lint_context.py:73-79; src/eval_lab/lint_rule_expansion.py:38-44 (steps 0033): Actual temporal/warrant consumption is still disconnected from observed accounting. Both ledgers run Expansion, while the real preparer contributes only diagnostics. In fresh direct and in-memory SQLite probes, bypassing the temporal Evidence.coverage read with the valid literal 
- src/eval_lab/lint_rule_expansion.py:150-155; src/eval_lab/lint_role_prerequisites.py:34-44 (steps 0033): Exact-history access still discards the resolved target without expanding its required operands. Fresh full role-profile probes accepted missing, null and string-valued predecessor confidence with empty diagnostics and successful support on both isolated adapters. No predecessor 
- src/eval_lab/lint_rule_expansion.py:93-127; tests/test_lint_rule_manifest.py:338-345 (steps 0033): Checked applicability still lacks derivative activation based on frame_indices. In fresh probes on both adapters, a submission with checked empty frame_indices and explicitly null derivative passed the existing temporal preparer but received UNKNOWN/null required field from the n
- src/eval_lab/lint_rule_manifest.py:42-47; src/eval_lab/lint_context.py:102-114 (steps 0033): EvidenceArm and InstrumentRun membership checks only evidence.media and omits plan.competing_set.intent. Fresh direct and SQLite probes classified both root kinds as active despite null plans, with only media identity as justification. Consequently unavailable or mismatched inten
- src/eval_lab/lint_context.py:134-146 (steps 0033): Scoped preparation retains only each root audit's diagnostics. It drops expected, observed and checked_inactive. Fresh probes produced 8 expected, 8 observed and 4 inactive entries for an individual Evidence audit, then zero entries in all three fields after scoped preparation ma
- tests/test_lint_rule_manifest.py:231-255,372-387; src/eval_lab/lint_rule_expansion.py:176-190 (steps 0033): Computed-output execution still lacks deletion-sensitive acceptance coverage. Tests assert operand rejection and generic support without requiring Evidence.digest or TestPlan.authored output obligations. Independently deleting the entire computed loop in memory left all 83 comput

## Standing limitations

- VALIDATION_LIMITATION: 39 recorded flags.
- RESEARCH_PENDING: 9 recorded flags.
- PUBLIC_PROSE: 23 recorded flags.
- HOME_PATH: 4 recorded flags.

Proposals awaiting approval: P0008-1: Normalize unpacked arrays before JsonValue validation; P0009-1: Include applicable RelationClaimV2 history in private dataset snapshots; WP07: Model-based instrument adapters; A3-01: Evidence partitions and withheld-context challenges; A3-02: Decision-relevance router; A3-03: Shared perception cache with evidence lineage; A3-04: Counterfactual tests of stated reasons; A3-05: Backed spans and evidence-carrying judgments; A3-06: Instrument validation ladder; A3-07: Labeling import adapter (Ultralytics, Roboflow, others); P0023-1: Decompose L12-A2 acceptance so focused validator controls fit bounded steps; P0030-1: Replan the remaining role controls and independent all-rule conjunction without reducing acceptance; P0030-2: Preserve blocking F0030-R1-001 and authorize an acceptance-preserving replan

Calibration self-minus-independent mean: 0.041666666666666664. Reverts: 13/33.

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
