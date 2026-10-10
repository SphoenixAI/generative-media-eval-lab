# Review packet

step | item | decision | Rv In Rl PQ Ac Sc | passed tests | gate | research C/X/O/U | flags
--- | --- | --- | --- | --- | --- | --- | ---
0026 | L12-A2b | INTEGRATE | 4 4 4 4 4 4 | 2955 | True | 0/0/0/0 | flags: 4
0027 | L12-A2c | REVERT | 4 2 4 2 4 4 | 5088 | True | 2/0/0/0 | flags: 3
0028 | L12-A2c | REVERT | 4 4 4 4 4 4 | 5100 | True | 2/0/0/9 | flags: 1
0029 | L12-A2c | INTEGRATE | 4 4 4 4 4 4 | 5100 | True | 2/0/0/0 | flags: 1
0030 | L12-A2d | REVERT | 4 1 4 1 4 4 | 6179 | False | 2/0/0/0 | flags: 4

## Loop health

- Consecutive non-integrations since RESUME: 1; trailing RF: 0.
- Product retries: L02: 1, L04: 1, L10: 1, L12: 1, L12-A2: 1, L12-A2d: 1.
- BLOCKED: none.
- Last stop reason: STOP_AFTER_STEP file exists.

## New this step

- Independent executions used actual preparation, reader, canonicalization and test functions with substituted import wiring, an artifact-kind registry and manual parameterization. SQLite databases were in memory with query_only enabled. These checks do not establish installed-package or on-disk retai
- Reviewed I1-I16 against the diff and relevant behavior. No score-zero invariant violation is established: the change adds private partial preparation without judgment authoring, history writes, operational decisions, averaging, probability arithmetic, runtime networking, public serialization, test w
- Supplied gate.json also reports blocking G12 approval failure. Its G5/G6/G14 checks pass, but external repository and filesystem state was not independently inspected outside the permitted folder.
- The accessible Python lacks pytest, pydantic and SQLAlchemy. Full-suite results are supplied gate evidence, not an independently rerun suite.

## Open issues

- tree/tests/test_intent_v2.py:201-202 (steps 0006): MINOR production_quality: tree/tests/test_intent_v2.py:201-202: the initial-predecessor negative case reuses persisted revision 1 and accepts any ValueError. Removing only the initial-predecessor guard would still permit an immutable-revision conflict to satisfy this assertion.
- tree/loop/reports/STEP-0006-L02.md:37-51 (steps 0006): MINOR accuracy: External API, release and standards claims at tree/loop/reports/STEP-0006-L02.md:37-51 and :176-183 require independent source verification; supplied CONFIRMED labels were not treated as independent evidence.
- tree/src/eval_lab/seals.py:135 (steps 0007): MINOR intention: tree/src/eval_lab/seals.py:135 validates rows before filtering their source paths. An unrelated corrupt seal makes an unknown-ID lookup return INTEGRITY_FAILURE instead of the planned UNKNOWN; reproduced with the actual verifier and mocked boundaries.
- production_quality (steps 0011): MINOR production_quality: test_lifecycle_contract_constructor_and_copied_admission now provides 22 targeted cases with fresh IDs, valid referenced artifacts, specific ValidationError messages, nonadmission assertions and valid controls.
- tree/tests/test_relation_v2_snapshots.py:44 (steps 0017): MINOR production_quality: tree/tests/test_relation_v2_snapshots.py:44 does not independently prove direct-reference discovery: its declared intent is already in the original closure and its evidence media is in the dataset.
- tests/test_resolution_workflow.py:164-169 (steps 0018): MINOR production_quality: tests/test_resolution_workflow.py:164-169 does not independently prove revision-invariant instrument units: the repeated Evidence identity guard also satisfies its broad 'duplicate sample unit' assertion. An implementation that changes unit identity only
- tests/test_lint_context.py:14-16; src/eval_lab/lint_role_prerequisites.py:319-322 (steps 0030): F0030-R1-001 remains unresolved. There is no all-rule composition module, production rule manifest, checked complete scope or independent expected-consumption audit. The candidate still returns only a partial role group. All 30 conjunction tests fail in the supplied gate. A propo
- src/eval_lab/lint_role_prerequisites.py:235-236; tests/test_lint_role_prerequisites.py:247-275 (steps 0030): The alternative endpoint-kind guard applies independently to legacy and v2 relations, but its isolated negative tests only RelationClaim. In independent direct and in-memory SQLite executions, bypassing rejection only for RelationClaimV2 left all 540 parameterized role cases pass
- tests/test_lint_context.py:14-16; src/eval_lab/lint_role_prerequisites.py:300-312 (steps 0030): The required all-rule composition layer does not exist. The only new implementation returns a partial role group; there is no production rule manifest, checked complete scope, independent expected-consumption inventory or conjunction with the temporal and warrant groups. All 30 c

## Standing limitations

- VALIDATION_LIMITATION: 35 recorded flags.
- RESEARCH_PENDING: 9 recorded flags.
- PUBLIC_PROSE: 23 recorded flags.
- HOME_PATH: 4 recorded flags.

Proposals awaiting approval: P0008-1: Normalize unpacked arrays before JsonValue validation; P0009-1: Include applicable RelationClaimV2 history in private dataset snapshots; WP07: Model-based instrument adapters; A3-01: Evidence partitions and withheld-context challenges; A3-02: Decision-relevance router; A3-03: Shared perception cache with evidence lineage; A3-04: Counterfactual tests of stated reasons; A3-05: Backed spans and evidence-carrying judgments; A3-06: Instrument validation ladder; A3-07: Labeling import adapter (Ultralytics, Roboflow, others); P0023-1: Decompose L12-A2 acceptance so focused validator controls fit bounded steps; P0030-1: Replan the remaining role controls and independent all-rule conjunction without reducing acceptance; P0030-2: Preserve blocking F0030-R1-001 and authorize an acceptance-preserving replan

Calibration self-minus-independent mean: 0.3333333333333333. Reverts: 11/30.

Rubric A2: accuracy covers builder/enhancer content only; scores before and after A2 are not directly comparable.

Step 0002 remains ABANDONED: HARNESS_INFRASTRUCTURE_FAILURE: duplicate model-authored research claim ids. Product retry charged: False.

Step 0005 remains REVERT: HARNESS_POLICY_FALSE_REVERT: research actionability / enhancer resolution mismatch. Product retry charged: False.

Step 0010 remains REVERT: HARNESS_POLICY_FALSE_REVERT: evaluator accuracy scored harness-written research bookkeeping. Product retry charged: False.

Step 0010 remains RESUME: A2 groups A-C validated; authorized recovery of L04. Product retry charged: False.

Step 0019 remains RESUME: Step 0019 reviewed: genuine L12 I2 failure reverted; fail-closed contract, standing rule and R0P validated.. Product retry charged: False.

Step 0028 remains RESUME: Steps 0027–0028 RF caused by the enhancer prompt-size harness defect, fixed in fa775547f6c1a0e8e42eeed8db4eb4831c244bd1; not Codex or product failures.. Product retry charged: False.

- Which integrated change most likely violates an invariant?
- Which research verdict is weakest?
- What should be deferred?
