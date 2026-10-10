# Review packet

step | item | decision | Rv In Rl PQ Ac Sc | passed tests | gate | research C/X/O/U | flags
--- | --- | --- | --- | --- | --- | --- | ---
0018 | L10 | INTEGRATE | 4 4 4 3 4 4 | 1214 | True | 0/0/0/0 | flags: 3
0019 | L12 | REVERT | 4 0 4 2 2 4 | 1293 | True | 0/0/0/1 | flags: 5
0020 | L12 | SPLIT | ? ? ? ? ? ? | 0 | False | 0/0/0/0 | flags: 0
0021 | L12-A | SPLIT | ? ? ? ? ? ? | 0 | False | 0/0/0/0 | flags: 0
0022 | L12-A1 | INTEGRATE | 4 4 4 4 4 4 | 1391 | True | 8/0/0/0 | flags: 2

## Loop health

- Consecutive non-integrations since RESUME: 0; trailing RF: 0.
- Product retries: L02: 1, L04: 1, L10: 1, L12: 1.
- BLOCKED: none.
- Last stop reason: R0 invariant failure.

## New this step

- Independent full-suite execution was unavailable: the accessible Python lacks SQLAlchemy, and filesystem permissions are read-only. In-memory checks used isolated imports and a lightweight test runner; they do not establish full application integration or filesystem snapshot behavior.
- Scope of acceptance is L12-A1 only. All-rule declarations, exhaustive rule contracts, ready=false integration and snapshot persistence remain obligations of the approved later children.

## Open issues

- tree/tests/test_intent_v2.py:201-202 (steps 0006): MINOR production_quality: tree/tests/test_intent_v2.py:201-202: the initial-predecessor negative case reuses persisted revision 1 and accepts any ValueError. Removing only the initial-predecessor guard would still permit an immutable-revision conflict to satisfy this assertion.
- tree/loop/reports/STEP-0006-L02.md:37-51 (steps 0006): MINOR accuracy: External API, release and standards claims at tree/loop/reports/STEP-0006-L02.md:37-51 and :176-183 require independent source verification; supplied CONFIRMED labels were not treated as independent evidence.
- tree/src/eval_lab/seals.py:135 (steps 0007): MINOR intention: tree/src/eval_lab/seals.py:135 validates rows before filtering their source paths. An unrelated corrupt seal makes an unknown-ID lookup return INTEGRITY_FAILURE instead of the planned UNKNOWN; reproduced with the actual verifier and mocked boundaries.
- production_quality (steps 0011): MINOR production_quality: test_lifecycle_contract_constructor_and_copied_admission now provides 22 targeted cases with fresh IDs, valid referenced artifacts, specific ValidationError messages, nonadmission assertions and valid controls.
- tree/tests/test_relation_v2_snapshots.py:44 (steps 0017): MINOR production_quality: tree/tests/test_relation_v2_snapshots.py:44 does not independently prove direct-reference discovery: its declared intent is already in the original closure and its evidence media is in the dataset.
- tests/test_resolution_workflow.py:164-169 (steps 0018): MINOR production_quality: tests/test_resolution_workflow.py:164-169 does not independently prove revision-invariant instrument units: the repeated Evidence identity guard also satisfies its broad 'duplicate sample unit' assertion. An implementation that changes unit identity only

## Standing limitations

- VALIDATION_LIMITATION: 27 recorded flags.
- RESEARCH_PENDING: 9 recorded flags.
- PUBLIC_PROSE: 23 recorded flags.
- HOME_PATH: 4 recorded flags.

Proposals awaiting approval: P0008-1: Normalize unpacked arrays before JsonValue validation; P0009-1: Include applicable RelationClaimV2 history in private dataset snapshots; WP07: Model-based instrument adapters; A3-01: Evidence partitions and withheld-context challenges; A3-02: Decision-relevance router; A3-03: Shared perception cache with evidence lineage; A3-04: Counterfactual tests of stated reasons; A3-05: Backed spans and evidence-carrying judgments; A3-06: Instrument validation ladder; A3-07: Labeling import adapter (Ultralytics, Roboflow, others)

Calibration self-minus-independent mean: 0.8888888888888888. Reverts: 7/22.

Rubric A2: accuracy covers builder/enhancer content only; scores before and after A2 are not directly comparable.

Step 0002 remains ABANDONED: HARNESS_INFRASTRUCTURE_FAILURE: duplicate model-authored research claim ids. Product retry charged: False.

Step 0005 remains REVERT: HARNESS_POLICY_FALSE_REVERT: research actionability / enhancer resolution mismatch. Product retry charged: False.

Step 0010 remains REVERT: HARNESS_POLICY_FALSE_REVERT: evaluator accuracy scored harness-written research bookkeeping. Product retry charged: False.

Step 0010 remains RESUME: A2 groups A-C validated; authorized recovery of L04. Product retry charged: False.

Step 0019 remains RESUME: Step 0019 reviewed: genuine L12 I2 failure reverted; fail-closed contract, standing rule and R0P validated.. Product retry charged: False.

- Which integrated change most likely violates an invariant?
- Which research verdict is weakest?
- What should be deferred?
