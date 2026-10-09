# Review packet

step | item | decision | Rv In Rl PQ Ac Sc | passed tests | gate | research C/X/O/U | flags
--- | --- | --- | --- | --- | --- | --- | ---
0001 | L00 | INTEGRATE | 4 4 4 4 4 4 | 209 | True | 1/0/0/0 | Evaluation used supplied execution evidence and independent read-only comparisons; product and loop test suites were not rerun., Original advisory stdout, elapsed-time measurement, and fresh version-probe logs are not included in this folder; their historical execution details could not be independently reproduced.
0002 | L02 | ABANDONED | 4 4 2 2 4 4 | 428 | True | 0/0/0/0 | Independent full-suite execution unavailable: the available Python lacks Pydantic. Supplied gate results were inspected, not independently reproduced., PUBLIC_PROSE

Open flags: Evaluation used supplied execution evidence and independent read-only comparisons; product and loop test suites were not rerun., Independent full-suite execution unavailable: the available Python lacks Pydantic. Supplied gate results were inspected, not independently reproduced., Original advisory stdout, elapsed-time measurement, and fresh version-probe logs are not included in this folder; their historical execution details could not be independently reproduced., PUBLIC_PROSE

Proposals awaiting approval: none

Contradictions for review: none

Calibration gaps: [{"accuracy": 0, "intention": -2, "production_quality": 0, "relation": 0, "relevance": 0, "scope": 0}, {"accuracy": 0, "intention": 0, "production_quality": 2, "relation": 2, "relevance": 0, "scope": 0}]. Mean self-minus-independent: 0.16666666666666666.

Revert rate: 0/2 steps.

- Which integrated change most likely violates an invariant?
- Which research verdict is weakest?
- What should be deferred?
