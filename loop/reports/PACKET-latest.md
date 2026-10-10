# Review packet

step | item | decision | Rv In Rl PQ Ac Sc | passed tests | gate | research C/X/O/U | flags
--- | --- | --- | --- | --- | --- | --- | ---
0006 | L02 | INTEGRATE | 4 4 4 3 3 4 | 460 | True | 8/0/0/0 | Extracted-function checks used lightweight stand-ins and do not establish Pydantic validation, SQL concurrency or actual media-workspace execution., Full pytest and the builder's reported validation mutations were not independently reproduced: Pydantic, SQLAlchemy and pytest are unavailable., HOME_PATH, HOME_PATH: tree/loop/reports/STEP-0006-L02.md:204 contains absolute local paths., Minor test weakness: tree/tests/test_intent_v2.py:201-202 can reject the initial-predecessor case for an unrelated immutable-revision conflict., PUBLIC_PROSE, The supplied gate reports 460 passing tests; this was treated as reported evidence only. | flags: 7
0007 | L03 | INTEGRATE | 4 3 4 4 4 4 | 548 | True | 25/0/0/1 | HOME_PATH, HOME_PATH: The private step report contains local absolute paths., MINOR: tree/src/eval_lab/seals.py:135 validates unrelated rows before path filtering. Unknown IDs and unrelated paths can report INTEGRITY_FAILURE due to an unrelated corrupt seal. This round-1 minor issue remains., PUBLIC_PROSE, PUBLIC_PROSE: tree/docs/intent-seals.md adds public documentation., RESEARCH_PENDING: Outside sources were not accessed under the folder-only restriction. The report's research confirmations and release claims remain untrusted source assertions., VALIDATION_LIMITATION: 45 canonicalization cases ran through an assertion adapter, not pytest. Verification and snapshot probes executed actual extracted functions with mocked boundaries. Full model, persistence, media and CLI tests were not rerun. | flags: 7
0008 | L04 | REVERT | 4 2 4 2 4 4 | 638 | True | 12/0/0/0 | INVARIANT_AUDIT: checked I1-I16. No demonstrated violation: no real human judgments are authored; UNKNOWN remains separate; append-only guards and provenance nonpromotion remain; protected artifacts, evaluation logic, confidence arithmetic, dependencies, baseline tests and public serializers are unchanged. All DEFERRED items were checked. Historical Git actions cannot be independently established from this folder., PUBLIC_PROSE, PUBLIC_PROSE: generation-plans.md and pilot0.md changed., RESEARCH_BOUNDARY: outside claims were extracted without accessing material outside the evaluator folder., RUNTIME_TESTS_NOT_EXECUTED: available Python lacks pydantic, sqlalchemy and pytest. Supplied passing gate results remain builder-provided evidence. | flags: 5
0009 | L11 | REVERT | 4 4 2 4 4 4 | 700 | True | 0/0/0/0 | Independent pytest execution unavailable: the accessible interpreter lacks pytest, Pydantic and SQLAlchemy. Supplied gate results and the reported mutation experiment were not independently rerun., Lint remains assigned to L12 in tree/loop/backlog.toml:209; no existing lint integration point was found., PUBLIC_PROSE, PUBLIC_PROSE: tree/docs/relations-v2.md., The snapshot proposal is outside the sealed implementation file list and remains unimplemented. Its deferral is not accepted as satisfaction of the explicit snapshot requirement. | flags: 5
0010 | L04 | REVERT | 4 4 4 3 2 4 | 674 | True | 14/0/0/2 | Checked I1-I16 against the diff and relevant code paths: no demonstrated invariant violation. No real-media authoring, UNKNOWN conversion, history overwrite, protected/harness edit, judgment-engine change, new runtime network/dependency, test weakening, public exposure or DEFERRED implementation was found. External Git state was not verified., External claims remain research requests; nothing outside the supplied folder was read. The report also embeds a builder self-assessment; its scores were not used as evidence., Independent validation comprised full diff/file inspection, Python syntax parsing, hash and size checks, and execution of extracted parsing guards. The supplied 674-test pass and mutation results were not independently reproduced., MINOR_TEST_ORACLE_GAP: Add a literal expected candidate-order assertion after construction and reopen; existing selection comparisons cannot detect input reordering., PUBLIC_PROSE | flags: 5

## Loop health

- Consecutive non-integrations since RESUME: 0; trailing RF: 0.
- Product retries: L02: 1, L04: 1.
- BLOCKED: none.
- Last stop reason: none recorded.

## New this step

- Checked I1-I16 against the diff and relevant code paths: no demonstrated invariant violation. No real-media authoring, UNKNOWN conversion, history overwrite, protected/harness edit, judgment-engine change, new runtime network/dependency, test weakening, public exposure or DEFERRED implementation was
- External claims remain research requests; nothing outside the supplied folder was read. The report also embeds a builder self-assessment; its scores were not used as evidence.
- Independent validation comprised full diff/file inspection, Python syntax parsing, hash and size checks, and execution of extracted parsing guards. The supplied 674-test pass and mutation results were not independently reproduced.
- MINOR_TEST_ORACLE_GAP: Add a literal expected candidate-order assertion after construction and reopen; existing selection comparisons cannot detect input reordering.

## Open issues

- tree/tests/test_intent_v2.py:201-202 (steps 0006): MINOR production_quality: tree/tests/test_intent_v2.py:201-202: the initial-predecessor negative case reuses persisted revision 1 and accepts any ValueError. Removing only the initial-predecessor guard would still permit an immutable-revision conflict to satisfy this assertion.
- tree/loop/reports/STEP-0006-L02.md:37-51 (steps 0006): MINOR accuracy: External API, release and standards claims at tree/loop/reports/STEP-0006-L02.md:37-51 and :176-183 require independent source verification; supplied CONFIRMED labels were not treated as independent evidence.
- tree/src/eval_lab/seals.py:135 (steps 0007): MINOR intention: tree/src/eval_lab/seals.py:135 validates rows before filtering their source paths. An unrelated corrupt seal makes an unknown-ID lookup return INTEGRITY_FAILURE instead of the planned UNKNOWN; reproduced with the actual verifier and mocked boundaries.
- tree/tests/test_generation.py:137-146; tree/src/eval_lab/persistence.py:233-241 (steps 0008): The negative selection tests for missing coverage, overlapping kept/rejected entries, duplicate candidates and blank rejection reasons reuse TEST-ONLY-selection at revision 1 after that revision has already been stored. They assert only ValueError. If the partition validator is r
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
