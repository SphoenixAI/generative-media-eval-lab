# Review packet

step | item | decision | Rv In Rl PQ Ac Sc | passed tests | gate | research C/X/O/U | flags
--- | --- | --- | --- | --- | --- | --- | ---
0012 | L05 | INTEGRATE | 4 4 4 4 4 4 | 786 | True | 12/0/0/0 | flags: 5
0013 | L06 | INTEGRATE | 4 4 4 4 4 4 | 862 | True | 12/0/0/0 | flags: 7
0014 | L08 | INTEGRATE | 4 4 4 4 4 4 | 970 | True | 6/0/0/0 | flags: 3
0015 | L09 | INTEGRATE | 4 4 4 4 4 4 | 1040 | True | 0/0/0/0 | flags: 3
0016 | L10 | REVERT | 4 2 4 2 2 4 | 1125 | True | 0/0/0/0 | flags: 5

## Loop health

- Consecutive non-integrations since RESUME: 1; trailing RF: 0.
- Product retries: L02: 1, L04: 1, L10: 1.
- BLOCKED: none.
- Last stop reason: STOP_AFTER_STEP file exists.

## New this step

- Computed diff.patch SHA-256 matches diff_sha256.txt.
- Independent full-suite execution was unavailable: accessible Python lacks pydantic, and the workspace is read-only. gate.json reports 1125 passing tests; that count was not independently reproduced.
- Independently parsed all changed Python files and executed the extracted timestamp-receipt function: identical identities remain stable, while timestamp and revision changes invalidate the receipt. This did not execute Pydantic or repository admission.
- tests/test_resolution_workflow.py:157-175 does not independently prove run-revision collapse: its rejection repeats the same submitted evidence, and the original link sorts before the revision alias. A revision-sensitive unit implementation could still pass that rejection case.

## Open issues

- tree/tests/test_intent_v2.py:201-202 (steps 0006): MINOR production_quality: tree/tests/test_intent_v2.py:201-202: the initial-predecessor negative case reuses persisted revision 1 and accepts any ValueError. Removing only the initial-predecessor guard would still permit an immutable-revision conflict to satisfy this assertion.
- tree/loop/reports/STEP-0006-L02.md:37-51 (steps 0006): MINOR accuracy: External API, release and standards claims at tree/loop/reports/STEP-0006-L02.md:37-51 and :176-183 require independent source verification; supplied CONFIRMED labels were not treated as independent evidence.
- tree/src/eval_lab/seals.py:135 (steps 0007): MINOR intention: tree/src/eval_lab/seals.py:135 validates rows before filtering their source paths. An unrelated corrupt seal makes an unknown-ID lookup return INTEGRITY_FAILURE instead of the planned UNKNOWN; reproduced with the actual verifier and mocked boundaries.
- production_quality (steps 0011): MINOR production_quality: test_lifecycle_contract_constructor_and_copied_admission now provides 22 targeted cases with fresh IDs, valid referenced artifacts, specific ValidationError messages, nonadmission assertions and valid controls.
- tree/src/eval_lab/pilot.py:338; tree/src/eval_lab/pilot_domain.py:150; tree/loop/proposals/STEP-0009.toml:3 (steps 0009): R1-F1 remains unresolved. Dataset snapshot discovery starts from dataset submissions, sessions, derivatives and bindings, then follows outgoing references. RelationClaimV2 is neither discovered directly nor admitted through PilotSubmission. Consequently, a stored v2 relation poin
- tree/src/eval_lab/relation_v2.py:111; tree/src/eval_lab/pilot.py:338; tree/src/eval_lab/pilot_domain.py:150 (steps 0009): RelationClaimV2 is persisted but cannot enter the existing dataset snapshot discovery path. Snapshot roots include submissions, sessions, derivatives and bindings; submission envelopes reject RelationClaimV2, and reference traversal only follows outgoing links. A relation pointin
- src/eval_lab/resolutions.py:131-137; src/eval_lab/persistence.py:218-223; tests/test_resolutions.py:274-290 (steps 0016): Resolution checks a reconstructed TestPlan rather than the retained frozen JSON. Delete a default-valued field such as schema_version or tool_version from a valid frozen row while retaining its stored hashes. Repository.get and the transactional getter first call model_validate_j

## Standing limitations

- VALIDATION_LIMITATION: 21 recorded flags.
- RESEARCH_PENDING: 9 recorded flags.
- PUBLIC_PROSE: 19 recorded flags.
- HOME_PATH: 4 recorded flags.

Proposals awaiting approval: P0008-1: Normalize unpacked arrays before JsonValue validation; P0009-1: Include applicable RelationClaimV2 history in private dataset snapshots; WP07: Model-based instrument adapters; A3-01: Evidence partitions and withheld-context challenges; A3-02: Decision-relevance router; A3-03: Shared perception cache with evidence lineage; A3-04: Counterfactual tests of stated reasons; A3-05: Backed spans and evidence-carrying judgments; A3-06: Instrument validation ladder; A3-07: Labeling import adapter (Ultralytics, Roboflow, others)

Calibration self-minus-independent mean: 0.7333333333333333. Reverts: 6/16.

Rubric A2: accuracy covers builder/enhancer content only; scores before and after A2 are not directly comparable.

Step 0002 remains ABANDONED: HARNESS_INFRASTRUCTURE_FAILURE: duplicate model-authored research claim ids. Product retry charged: False.

Step 0005 remains REVERT: HARNESS_POLICY_FALSE_REVERT: research actionability / enhancer resolution mismatch. Product retry charged: False.

Step 0010 remains REVERT: HARNESS_POLICY_FALSE_REVERT: evaluator accuracy scored harness-written research bookkeeping. Product retry charged: False.

Step 0010 remains RESUME: A2 groups A-C validated; authorized recovery of L04. Product retry charged: False.

- Which integrated change most likely violates an invariant?
- Which research verdict is weakest?
- What should be deferred?
