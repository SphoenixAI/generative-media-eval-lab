# Review packet

step | item | decision | Rv In Rl PQ Ac Sc | passed tests | gate | research C/X/O/U | flags
--- | --- | --- | --- | --- | --- | --- | ---
0006 | L02 | INTEGRATE | 4 4 4 3 3 4 | 460 | True | 8/0/0/0 | flags: 7
0007 | L03 | INTEGRATE | 4 3 4 4 4 4 | 548 | True | 25/0/0/1 | flags: 7
0008 | L04 | REVERT | 4 2 4 2 4 4 | 638 | True | 12/0/0/0 | flags: 5
0009 | L11 | REVERT | 4 4 2 4 4 4 | 700 | True | 0/0/0/0 | flags: 5
0010 | L04 | REVERT | 4 4 4 3 2 4 | 674 | True | 14/0/0/2 | flags: 5

## Loop health

- Consecutive non-integrations since RESUME: 0; trailing RF: 0.
- Product retries: L02: 1, L04: 1.
- BLOCKED: none.
- Last stop reason: consecutive non-integrations after step 0010; subsequently authorized to resume under A2.

## New this step

- Checked I1-I16 against the diff and relevant code paths: no demonstrated invariant violation. No real-media authoring, UNKNOWN conversion, history overwrite, protected/harness edit, judgment-engine change, new runtime network/dependency, test weakening, public exposure or DEFERRED implementation was
- External claims remain research requests; nothing outside the supplied folder was read. The report also embeds a builder self-assessment; its scores were not used as evidence.
- Independent validation comprised full diff/file inspection, Python syntax parsing, hash and size checks, and execution of extracted parsing guards. The supplied 674-test pass and mutation results were not independently reproduced.
- MINOR_TEST_ORACLE_GAP: Add a literal expected candidate-order assertion after construction and reopen; existing selection comparisons cannot detect input reordering.

## Open issues

- tree/tests/test_intent_v2.py:201-202 (steps 0006): MINOR production_quality: tree/tests/test_intent_v2.py:201-202: the initial-predecessor negative case reuses persisted revision 1 and accepts any ValueError. Removing only the initial-predecessor guard would still permit an immutable-revision conflict to satisfy this assertion.
- tree/loop/reports/STEP-0006-L02.md:37-51 (steps 0006): MINOR accuracy: External API, release and standards claims at tree/loop/reports/STEP-0006-L02.md:37-51 and :176-183 require independent source verification; supplied CONFIRMED labels were not treated as independent evidence.
- tree/src/eval_lab/seals.py:135 (steps 0007): MINOR intention: tree/src/eval_lab/seals.py:135 validates rows before filtering their source paths. An unrelated corrupt seal makes an unknown-ID lookup return INTEGRITY_FAILURE instead of the planned UNKNOWN; reproduced with the actual verifier and mocked boundaries.
- tests/test_generation.py:183 (steps 0010): MINOR production_quality: tests/test_generation.py:183 checks revision continuity, random_draw and reopened canonical equality, but never compares stored candidate order against independently specified input order.
- tree/src/eval_lab/pilot.py:338; tree/src/eval_lab/pilot_domain.py:150; tree/loop/proposals/STEP-0009.toml:3 (steps 0009): R1-F1 remains unresolved. Dataset snapshot discovery starts from dataset submissions, sessions, derivatives and bindings, then follows outgoing references. RelationClaimV2 is neither discovered directly nor admitted through PilotSubmission. Consequently, a stored v2 relation poin
- tree/src/eval_lab/relation_v2.py:111; tree/src/eval_lab/pilot.py:338; tree/src/eval_lab/pilot_domain.py:150 (steps 0009): RelationClaimV2 is persisted but cannot enter the existing dataset snapshot discovery path. Snapshot roots include submissions, sessions, derivatives and bindings; submission envelopes reject RelationClaimV2, and reference traversal only follows outgoing links. A relation pointin

## Standing limitations

- VALIDATION_LIMITATION: 11 recorded flags.
- RESEARCH_PENDING: 6 recorded flags.
- PUBLIC_PROSE: 13 recorded flags.
- HOME_PATH: 4 recorded flags.

Proposals awaiting approval: P0008-1: Normalize unpacked arrays before JsonValue validation; P0009-1: Include applicable RelationClaimV2 history in private dataset snapshots; WP07: Model-based instrument adapters; A3-01: Evidence partitions and withheld-context challenges; A3-02: Decision-relevance router; A3-03: Shared perception cache with evidence lineage; A3-04: Counterfactual tests of stated reasons; A3-05: Backed spans and evidence-carrying judgments; A3-06: Instrument validation ladder; A3-07: Labeling import adapter (Ultralytics, Roboflow, others)

Calibration self-minus-independent mean: 0.9. Reverts: 5/10.

Rubric A2: accuracy covers builder/enhancer content only; scores before and after A2 are not directly comparable.

Step 0002 remains ABANDONED: HARNESS_INFRASTRUCTURE_FAILURE: duplicate model-authored research claim ids. Product retry charged: False.

Step 0005 remains REVERT: HARNESS_POLICY_FALSE_REVERT: research actionability / enhancer resolution mismatch. Product retry charged: False.

Step 0010 remains REVERT: HARNESS_POLICY_FALSE_REVERT: evaluator accuracy scored harness-written research bookkeeping. Product retry charged: False.

Step 0010 remains RESUME: A2 groups A-C validated; authorized recovery of L04. Product retry charged: False.

- Which integrated change most likely violates an invariant?
- Which research verdict is weakest?
- What should be deferred?
