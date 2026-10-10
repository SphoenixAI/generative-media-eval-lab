7. Rubric and decision rules

The scale matches the Lab's own:

Score	Meaning	Effect
4 PASS	No material issue	Integrate
3 MINOR	Small issue, logged	Integrate
2 MATERIAL	Must be fixed in this step	Enhance, otherwise revert
1 SEVERE	Wrong in a way the fixes did not rescue	Revert
0 CATASTROPHIC	An invariant is violated, named in a blocking finding	Revert and stop the loop
Dimension	A 4 looks like	A 2 looks like	A 1 looks like	A 0 looks like
Relevance	On the critical path to the north star; the diff stays inside the item	Tangential work mixed in	Mostly off-item	DEFERRED work (I14)
Intention	Sealed criteria met as written; invariants honored; the loophole audit is clean	A criterion unmet or quietly reinterpreted	Several criteria unmet	An invariant violated
Relation	New types linked, pinned, versioned, persisted, included in snapshots and linted	A new type orphaned, or a reference left floating	References that break existing records	Authored history overwritten (I3)
Production quality	Positive, negative and edge-case tests; clear errors; typed; docs and help updated; deterministic	Negative tests or docs missing	Tests fail or are flaky	A test weakened to make a run pass (I11)
Accuracy	Builder/enhancer code, tests, docs, CLI help, Plan and Probes agree with checkable evidence; external claims are routed to research without a score penalty	A builder-authored claim contradicts checkable evidence or misstates built behavior	A contradicted claim shipped	Synthetic output presented as real results (I1, I12)
Scope	The smallest change that meets the criteria	Gold-plating	Large unrequested additions	DEFERRED work built (I14)

The decision is deterministic and never averages. The final round is round 2 if it ran, and round 1 otherwise. The first matching rule fires:

Rule	Condition	Decision
R0	A final score of 0 backed by a finding that names an invariant, or a G6 or G14 failure in any round	REVERT, and stop the loop
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
