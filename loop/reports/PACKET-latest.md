# Review packet

step | item | decision | Rv In Rl PQ Ac Sc | passed tests | gate | research C/X/O/U | flags
--- | --- | --- | --- | --- | --- | --- | ---
0013 | L06 | INTEGRATE | 4 4 4 4 4 4 | 862 | True | 12/0/0/0 | flags: 7
0014 | L08 | INTEGRATE | 4 4 4 4 4 4 | 970 | True | 6/0/0/0 | flags: 3
0015 | L09 | INTEGRATE | 4 4 4 4 4 4 | 1040 | True | 0/0/0/0 | flags: 3
0016 | L10 | REVERT | 4 2 4 2 2 4 | 1125 | True | 0/0/0/0 | flags: 5
0017 | L11 | INTEGRATE | 4 4 4 3 4 4 | 1112 | True | 0/0/0/0 | flags: 6

## Loop health

- Consecutive non-integrations since RESUME: 0; trailing RF: 0.
- Product retries: L02: 1, L04: 1, L10: 1.
- BLOCKED: none.
- Last stop reason: STOP_AFTER_STEP file exists.

## New this step

- FILE-LIST VARIANCE: tree/src/eval_lab/pilot_cli.py was not in the sealed Plan's estimated file list; its changes are limited to snapshot/export help.
- Independent pytest execution was unavailable; supplied gate results are reported evidence, not an independent rerun.
- Lint integration remains assigned to L12; no existing lint integration point was found.
- MINOR TEST GAP: direct-reference discovery needs an assertion that cannot also pass through intent/media matching.

## Open issues

- tree/tests/test_intent_v2.py:201-202 (steps 0006): MINOR production_quality: tree/tests/test_intent_v2.py:201-202: the initial-predecessor negative case reuses persisted revision 1 and accepts any ValueError. Removing only the initial-predecessor guard would still permit an immutable-revision conflict to satisfy this assertion.
- tree/loop/reports/STEP-0006-L02.md:37-51 (steps 0006): MINOR accuracy: External API, release and standards claims at tree/loop/reports/STEP-0006-L02.md:37-51 and :176-183 require independent source verification; supplied CONFIRMED labels were not treated as independent evidence.
- tree/src/eval_lab/seals.py:135 (steps 0007): MINOR intention: tree/src/eval_lab/seals.py:135 validates rows before filtering their source paths. An unrelated corrupt seal makes an unknown-ID lookup return INTEGRITY_FAILURE instead of the planned UNKNOWN; reproduced with the actual verifier and mocked boundaries.
- production_quality (steps 0011): MINOR production_quality: test_lifecycle_contract_constructor_and_copied_admission now provides 22 targeted cases with fresh IDs, valid referenced artifacts, specific ValidationError messages, nonadmission assertions and valid controls.
- tree/tests/test_relation_v2_snapshots.py:44 (steps 0017): MINOR production_quality: tree/tests/test_relation_v2_snapshots.py:44 does not independently prove direct-reference discovery: its declared intent is already in the original closure and its evidence media is in the dataset.
- src/eval_lab/resolutions.py:131-137; src/eval_lab/persistence.py:218-223; tests/test_resolutions.py:274-290 (steps 0016): Resolution checks a reconstructed TestPlan rather than the retained frozen JSON. Delete a default-valued field such as schema_version or tool_version from a valid frozen row while retaining its stored hashes. Repository.get and the transactional getter first call model_validate_j

## Standing limitations

- VALIDATION_LIMITATION: 22 recorded flags.
- RESEARCH_PENDING: 9 recorded flags.
- PUBLIC_PROSE: 21 recorded flags.
- HOME_PATH: 4 recorded flags.

Proposals awaiting approval: P0008-1: Normalize unpacked arrays before JsonValue validation; P0009-1: Include applicable RelationClaimV2 history in private dataset snapshots; WP07: Model-based instrument adapters; A3-01: Evidence partitions and withheld-context challenges; A3-02: Decision-relevance router; A3-03: Shared perception cache with evidence lineage; A3-04: Counterfactual tests of stated reasons; A3-05: Backed spans and evidence-carrying judgments; A3-06: Instrument validation ladder; A3-07: Labeling import adapter (Ultralytics, Roboflow, others)

Calibration self-minus-independent mean: 0.7666666666666667. Reverts: 6/17.

Rubric A2: accuracy covers builder/enhancer content only; scores before and after A2 are not directly comparable.

Step 0002 remains ABANDONED: HARNESS_INFRASTRUCTURE_FAILURE: duplicate model-authored research claim ids. Product retry charged: False.

Step 0005 remains REVERT: HARNESS_POLICY_FALSE_REVERT: research actionability / enhancer resolution mismatch. Product retry charged: False.

Step 0010 remains REVERT: HARNESS_POLICY_FALSE_REVERT: evaluator accuracy scored harness-written research bookkeeping. Product retry charged: False.

Step 0010 remains RESUME: A2 groups A-C validated; authorized recovery of L04. Product retry charged: False.

- Which integrated change most likely violates an invariant?
- Which research verdict is weakest?
- What should be deferred?
