# Review packet

step | item | decision | Rv In Rl PQ Ac Sc | passed tests | gate | research C/X/O/U | flags
--- | --- | --- | --- | --- | --- | --- | ---
0019 | L12 | REVERT | 4 0 4 2 2 4 | 1293 | True | 0/0/0/1 | flags: 5
0020 | L12 | SPLIT | ? ? ? ? ? ? | 0 | False | 0/0/0/0 | flags: 0
0021 | L12-A | SPLIT | ? ? ? ? ? ? | 0 | False | 0/0/0/0 | flags: 0
0022 | L12-A1 | INTEGRATE | 4 4 4 4 4 4 | 1391 | True | 8/0/0/0 | flags: 2
0023 | L12-A2 | REVERT | 4 2 2 2 4 4 | 1505 | True | 0/0/0/0 | flags: 4

## Loop health

- Consecutive non-integrations since RESUME: 1; trailing RF: 0.
- Product retries: L02: 1, L04: 1, L10: 1, L12: 1, L12-A2: 1.
- BLOCKED: none.
- Last stop reason: R0 invariant failure.

## New this step

- Independently computed the diff SHA-256 and confirmed it matches diff_sha256.txt.
- Reviewed I1-I16 against changed paths and behavior. The preparation gaps threaten evidence and provenance guarantees, but this layer emits no readiness or verdict result; no score-zero invariant violation is asserted. No authored-history writes, judgment creation, aggregation, probability arithmetic
- The attachment probes executed actual preparation/reader functions with repository-supplied schemas and equivalent substitutes for selected MediaAsset/Evidence fields. They are isolated standard-library checks, not full installed-package integration tests.
- The supplied gate reports 1505 passing tests. This is harness evidence; the full suite was not independently rerun.

## Open issues

- tree/tests/test_intent_v2.py:201-202 (steps 0006): MINOR production_quality: tree/tests/test_intent_v2.py:201-202: the initial-predecessor negative case reuses persisted revision 1 and accepts any ValueError. Removing only the initial-predecessor guard would still permit an immutable-revision conflict to satisfy this assertion.
- tree/loop/reports/STEP-0006-L02.md:37-51 (steps 0006): MINOR accuracy: External API, release and standards claims at tree/loop/reports/STEP-0006-L02.md:37-51 and :176-183 require independent source verification; supplied CONFIRMED labels were not treated as independent evidence.
- tree/src/eval_lab/seals.py:135 (steps 0007): MINOR intention: tree/src/eval_lab/seals.py:135 validates rows before filtering their source paths. An unrelated corrupt seal makes an unknown-ID lookup return INTEGRITY_FAILURE instead of the planned UNKNOWN; reproduced with the actual verifier and mocked boundaries.
- production_quality (steps 0011): MINOR production_quality: test_lifecycle_contract_constructor_and_copied_admission now provides 22 targeted cases with fresh IDs, valid referenced artifacts, specific ValidationError messages, nonadmission assertions and valid controls.
- tree/tests/test_relation_v2_snapshots.py:44 (steps 0017): MINOR production_quality: tree/tests/test_relation_v2_snapshots.py:44 does not independently prove direct-reference discovery: its declared intent is already in the original closure and its evidence media is in the dataset.
- tests/test_resolution_workflow.py:164-169 (steps 0018): MINOR production_quality: tests/test_resolution_workflow.py:164-169 does not independently prove revision-invariant instrument units: the repeated Evidence identity guard also satisfies its broad 'duplicate sample unit' assertion. An implementation that changes unit identity only
- src/eval_lab/lint_prerequisites.py:230-254,295-411 (steps 0023): F0023-R1-001 remains unresolved. Nullable derivative presence is treated as optional regardless of frame_indices. There is no PilotSubmission attachment branch requiring the derivative, validating selected indices or establishing attachment correspondence. An isolated execution o
- src/eval_lab/lint_prerequisites.py:328-337 (steps 0023): F0023-R1-002 remains unresolved. BindingContext preparation checks FirstView presence and time but never compares its content identity with the binding. A correctly pinned FirstView for different content can supply chronology when its timestamp matches. Traversing its media and r
- tests/test_lint_prerequisites.py:84-89,118-135,315-402 (steps 0023): F0023-R1-004 remains unresolved despite the new timestamp controls. Several rejection guards still lack isolated negative tests, including binding seal intent mismatch, binding origin anchors mismatch and run link context mismatch. Removing those guards would not alter the curren
- src/eval_lab/lint_prerequisites.py:229-253,294-410 (steps 0023): PilotSubmission.derivative is always treated as optionally absent. No preparation branch makes it required when frame_indices is nonempty, validates the selected indices against the derivative, or establishes the attachment's media correspondence. Consequently, a submission with 
- src/eval_lab/lint_prerequisites.py:327-346 (steps 0023): BindingContext replay checks a referenced FirstView's created_at against binding.first_view_at but never checks that the FirstView media/registration identify the binding's content. An unrelated, correctly pinned FirstView with the same timestamp can therefore supply usable chron
- tests/test_lint_prerequisites.py:84-89,315-326,358-402 (steps 0023): The focused tests do not satisfy A2 oracle rule 4 or the sealed requirement to cover each new branch/adapter. For example, no negative case exercises binding registration mismatch, binding chronology time mismatch, binding seal intent mismatch, binding origin anchors mismatch, or

## Standing limitations

- VALIDATION_LIMITATION: 28 recorded flags.
- RESEARCH_PENDING: 9 recorded flags.
- PUBLIC_PROSE: 23 recorded flags.
- HOME_PATH: 4 recorded flags.

Proposals awaiting approval: P0008-1: Normalize unpacked arrays before JsonValue validation; P0009-1: Include applicable RelationClaimV2 history in private dataset snapshots; WP07: Model-based instrument adapters; A3-01: Evidence partitions and withheld-context challenges; A3-02: Decision-relevance router; A3-03: Shared perception cache with evidence lineage; A3-04: Counterfactual tests of stated reasons; A3-05: Backed spans and evidence-carrying judgments; A3-06: Instrument validation ladder; A3-07: Labeling import adapter (Ultralytics, Roboflow, others); P0023-1: Decompose L12-A2 acceptance so focused validator controls fit bounded steps

Calibration self-minus-independent mean: 0.6666666666666666. Reverts: 8/23.

Rubric A2: accuracy covers builder/enhancer content only; scores before and after A2 are not directly comparable.

Step 0002 remains ABANDONED: HARNESS_INFRASTRUCTURE_FAILURE: duplicate model-authored research claim ids. Product retry charged: False.

Step 0005 remains REVERT: HARNESS_POLICY_FALSE_REVERT: research actionability / enhancer resolution mismatch. Product retry charged: False.

Step 0010 remains REVERT: HARNESS_POLICY_FALSE_REVERT: evaluator accuracy scored harness-written research bookkeeping. Product retry charged: False.

Step 0010 remains RESUME: A2 groups A-C validated; authorized recovery of L04. Product retry charged: False.

Step 0019 remains RESUME: Step 0019 reviewed: genuine L12 I2 failure reverted; fail-closed contract, standing rule and R0P validated.. Product retry charged: False.

- Which integrated change most likely violates an invariant?
- Which research verdict is weakest?
- What should be deferred?
