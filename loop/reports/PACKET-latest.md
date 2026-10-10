# Review packet

step | item | decision | Rv In Rl PQ Ac Sc | passed tests | gate | research C/X/O/U | flags
--- | --- | --- | --- | --- | --- | --- | ---
0009 | L11 | REVERT | 4 4 2 4 4 4 | 700 | True | 0/0/0/0 | flags: 5
0010 | L04 | REVERT | 4 4 4 3 2 4 | 674 | True | 14/0/0/2 | flags: 5
0011 | L04 | INTEGRATE | 4 4 4 3 4 4 | 698 | True | 16/0/0/1 | flags: 5
0012 | L05 | INTEGRATE | 4 4 4 4 4 4 | 786 | True | 12/0/0/0 | flags: 5
0013 | L06 | INTEGRATE | 4 4 4 4 4 4 | 862 | True | 12/0/0/0 | flags: 7

## Loop health

- Consecutive non-integrations since RESUME: 0; trailing RF: 0.
- Product retries: L02: 1, L04: 1.
- BLOCKED: none.
- Last stop reason: STOP_AFTER_STEP file exists.

## New this step

- Checked I1-I9: TEST-ONLY authoring, UNKNOWN preservation, append-only history, protected-file boundaries, pinned acceptability, unchanged epistemic records, provenance guards, worst-case aggregation and absence of probability arithmetic. No demonstrated violation.
- Checked I10-I14 and I16: no runtime network/dependency additions, baseline-test weakening, public serializer expansion, deferred implementation or judge edits. Deterministic envelope behavior has a literal oracle.
- External claims were not independently verified outside the folder. research.json reports confirmation, but remains separate researcher-owned context.
- I15 historical Git actions cannot be independently established from this folder. Supplied G14 reports unchanged remote main and pilot listing.
- Independent execution did not cover Pydantic validation, repository integration or full pytest fixtures. The extracted-code checks used dependency-free record doubles; gate.json's 862 passing tests are supplied evidence.
- Independently recomputed the patch SHA-256 and confirmed it matches diff_sha256.txt.

## Open issues

- tree/tests/test_intent_v2.py:201-202 (steps 0006): MINOR production_quality: tree/tests/test_intent_v2.py:201-202: the initial-predecessor negative case reuses persisted revision 1 and accepts any ValueError. Removing only the initial-predecessor guard would still permit an immutable-revision conflict to satisfy this assertion.
- tree/loop/reports/STEP-0006-L02.md:37-51 (steps 0006): MINOR accuracy: External API, release and standards claims at tree/loop/reports/STEP-0006-L02.md:37-51 and :176-183 require independent source verification; supplied CONFIRMED labels were not treated as independent evidence.
- tree/src/eval_lab/seals.py:135 (steps 0007): MINOR intention: tree/src/eval_lab/seals.py:135 validates rows before filtering their source paths. An unrelated corrupt seal makes an unknown-ID lookup return INTEGRITY_FAILURE instead of the planned UNKNOWN; reproduced with the actual verifier and mocked boundaries.
- production_quality (steps 0011): MINOR production_quality: test_lifecycle_contract_constructor_and_copied_admission now provides 22 targeted cases with fresh IDs, valid referenced artifacts, specific ValidationError messages, nonadmission assertions and valid controls.
- tree/src/eval_lab/pilot.py:338; tree/src/eval_lab/pilot_domain.py:150; tree/loop/proposals/STEP-0009.toml:3 (steps 0009): R1-F1 remains unresolved. Dataset snapshot discovery starts from dataset submissions, sessions, derivatives and bindings, then follows outgoing references. RelationClaimV2 is neither discovered directly nor admitted through PilotSubmission. Consequently, a stored v2 relation poin
- tree/src/eval_lab/relation_v2.py:111; tree/src/eval_lab/pilot.py:338; tree/src/eval_lab/pilot_domain.py:150 (steps 0009): RelationClaimV2 is persisted but cannot enter the existing dataset snapshot discovery path. Snapshot roots include submissions, sessions, derivatives and bindings; submission envelopes reject RelationClaimV2, and reference traversal only follows outgoing links. A relation pointin

## Standing limitations

- VALIDATION_LIMITATION: 15 recorded flags.
- RESEARCH_PENDING: 9 recorded flags.
- PUBLIC_PROSE: 16 recorded flags.
- HOME_PATH: 4 recorded flags.

Proposals awaiting approval: P0008-1: Normalize unpacked arrays before JsonValue validation; P0009-1: Include applicable RelationClaimV2 history in private dataset snapshots; WP07: Model-based instrument adapters; A3-01: Evidence partitions and withheld-context challenges; A3-02: Decision-relevance router; A3-03: Shared perception cache with evidence lineage; A3-04: Counterfactual tests of stated reasons; A3-05: Backed spans and evidence-carrying judgments; A3-06: Instrument validation ladder; A3-07: Labeling import adapter (Ultralytics, Roboflow, others)

Calibration self-minus-independent mean: 0.4. Reverts: 5/13.

Rubric A2: accuracy covers builder/enhancer content only; scores before and after A2 are not directly comparable.

Step 0002 remains ABANDONED: HARNESS_INFRASTRUCTURE_FAILURE: duplicate model-authored research claim ids. Product retry charged: False.

Step 0005 remains REVERT: HARNESS_POLICY_FALSE_REVERT: research actionability / enhancer resolution mismatch. Product retry charged: False.

Step 0010 remains REVERT: HARNESS_POLICY_FALSE_REVERT: evaluator accuracy scored harness-written research bookkeeping. Product retry charged: False.

Step 0010 remains RESUME: A2 groups A-C validated; authorized recovery of L04. Product retry charged: False.

- Which integrated change most likely violates an invariant?
- Which research verdict is weakest?
- What should be deferred?
