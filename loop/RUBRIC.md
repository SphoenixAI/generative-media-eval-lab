7. Rubric and decision rules

The scale matches the Lab's own:

Score	Meaning	Effect
4 PASS	No material issue	Integrate
3 MINOR	Small issue, logged	Integrate
2 MATERIAL	Must be fixed in this step	Enhance, otherwise revert
1 SEVERE	Wrong in a way the fixes did not rescue	Revert
0 CATASTROPHIC	An invariant is violated, named in a blocking finding	Revert; stop unless post-revert R0P verification succeeds
Dimension	A 4 looks like	A 2 looks like	A 1 looks like	A 0 looks like
Relevance	On the critical path to the north star; the diff stays inside the item	Tangential work mixed in	Mostly off-item	DEFERRED work (I14)
Intention	Sealed criteria met as written; invariants honored; the loophole audit is clean	A criterion unmet or quietly reinterpreted	Several criteria unmet	An invariant violated
Intention fail-closed anchor: Standing fail-closed build rule (Sphoenix, 2026-10-10): Any path capable of deciding readiness, completion, verdict or operational action declares its required inputs and tests each under missing, null and malformed conditions. Missing/unavailable -> UNKNOWN/incomplete. Malformed/integrity-invalid -> INTEGRITY_FAILURE. Neither can produce PASS, COMPLETE, SHIP, ready=true or an equivalent clean state. Prefer a shared parameterized contract test. Do not introduce INVALID as a new state vocabulary.
Relation	New types linked, pinned, versioned, persisted, included in snapshots and linted	A new type orphaned, or a reference left floating	References that break existing records	Authored history overwritten (I3)
Production quality	Positive, negative and edge-case tests; clear errors; typed; docs and help updated; deterministic	Negative tests or docs missing	Tests fail or are flaky	A test weakened to make a run pass (I11)
Production quality fail-closed anchor: Standing fail-closed build rule (Sphoenix, 2026-10-10): Any path capable of deciding readiness, completion, verdict or operational action declares its required inputs and tests each under missing, null and malformed conditions. Missing/unavailable -> UNKNOWN/incomplete. Malformed/integrity-invalid -> INTEGRITY_FAILURE. Neither can produce PASS, COMPLETE, SHIP, ready=true or an equivalent clean state. Prefer a shared parameterized contract test. Do not introduce INVALID as a new state vocabulary.
Accuracy	Builder/enhancer code, tests, docs, CLI help, Plan and Probes agree with checkable evidence; external claims are routed to research without a score penalty	A builder-authored claim contradicts checkable evidence or misstates built behavior	A contradicted claim shipped	Synthetic output presented as real results (I1, I12)
Scope	The smallest change that meets the criteria	Gold-plating	Large unrequested additions	DEFERRED work built (I14)

The decision is deterministic and never averages. The final round is round 2 if it ran, and round 1 otherwise. The first matching rule fires:

Rule	Condition	Decision
R0	A final score of 0 backed by an invariant, or G6/G14 failure: remain R0 unless all R0P conditions below are proven after rollback	REVERT, stop the loop
R0P	Only I2/I3/I5/I6/I7/I8/I9/I13 score-zero candidate invariants, and verified rollback checks	REVERT, charge product retry, continue within ordinary limits
RF	A role failed or timed out	REVERT; no retry is charged
R1	The final gate has a blocking failure	REVERT
R2	Any other final 0, or any final 1	REVERT
R3	Any final score of 2	REVERT
R4	Any prior_findings entry is UNRESOLVED, or a blocking finding or research claim with action_required=true has no resolution	REVERT
R5	The evaluator's diff_sha256 does not match after one rerun	REVERT
R6	None of the above	INTEGRATE

Every REVERT except RF adds 1 to the item's retries. After max_retries_per_item, the item is BLOCKED until Sphoenix acts on it.

Flags never block integration. Sphoenix must clear them before merging into main.

Calibration. state.json keeps, for each dimension, the gap between the builder's self-score and the independent round-1 score. If the builder's mean overconfidence over the last five steps is above 1.0, the packet says so.


A2 accuracy boundary: harness-written report sections and researcher-owned verdicts are separate context, never builder accuracy evidence. Scores before and after A2 are not directly comparable.

A2 test-oracle rules:
1. Every rejection test asserts the specific error type and a message fragment, and uses fresh ids and revisions so no other rejection path can satisfy it.
2. Expected values are literals authored in the test, never computed by the code under test.
3. Fixtures use distinct values for every field the test must distinguish.
4. Each new validator has at least one test that fails when that validator is deleted. Name the test in self-evaluation evidence (or enhancement evidence for the enhancer).


Operator rule, Sphoenix 2026-10-10: R0P is a post-revert classification for a new candidate only. Every zero-scored dimension must have a finding naming an allowed invariant, and no finding may name another invariant. Autonomy/repository-integrity failures remain R0. Before rollback, retain the initial R0 decision, changed-path check, protected hashes and main/pilot-local integrity snapshot. After reverting, verify G5 protected hashes unchanged, G6 no forbidden candidate or remaining paths, G14 main refs and pilot-local listing unchanged from step start, and a clean worktree at the exact known-good base. Every executed gate round must also have passed G5/G6/G14; missing evidence, exceptions or unverifiable checks remain R0 and stop. R0P charges the ordinary product retry and counts toward consecutive non-integrations. Tests and these checks do not prove the absence of side effects outside the checked paths. Step 0019 is not reclassified or refunded.

Application ordering: L15 and L16 are P0. Once L12 is done, prefer eligible L16 before L15 without adding a dependency. The authorized run uses --critical-path L12,L16,L15: follow existing split children, advance only when the current item is complete, stop on blocked/unavailable critical work, and stop at the boundary after L15 completes. Never fall through to witness items or other backlog work. All existing retry, R0, RF, step/time and STOP limits remain.
