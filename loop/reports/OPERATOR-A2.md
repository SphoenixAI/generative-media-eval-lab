# Operator amendment A2 and A2.1

Authority: Sphoenix supplied BUILD_LOOP_AMENDMENT_2.md and BUILD_LOOP_AMENDMENT_2_1.md on 2026-10-09. The loop was stopped at b71ce77, with step 0010 last. No A2 work had been applied before receipt. Main stays at 0398762b9f32c6eef0366b576c5251016792354c.

## Harness validation groups

| Group | Commits | Harness tests | Full isolated dry run |
| --- | --- | --- | --- |
| A: M1-M3 and Section 3 | ff3022e, d7b1b25 | 116 passed | PASS, INTEGRATE/R6 |
| B: M4-M6 | ab7f6ba | 124 passed | PASS, INTEGRATE/R6 |
| C: M7-M8 | 2890543, addbefb | 128 passed | PASS, INTEGRATE/R6 |

The earlier harness suite had 107 tests. A2 adds 21. Dry runs use authored role fixtures, real gates and disposable Git repositories; they make zero model calls. They do not establish real-media validity. Group A's first check exposed a JSON-key-order assertion issue; Group C's first check exposed test paths using the macOS /var alias instead of resolved /private/var paths. Both were corrected before proceeding.

M9 is skipped in this amendment pass. Evaluator scratch confinement has not been implemented or demonstrated by a test. Existing read-only evaluation remains, and independent full-suite execution remains a stated limitation. This does not waive any gate.

## Approved backlog and proposals

Part 1 is 95afb63. Existing acceptance strings and approval fields are preserved. L11 gains private v2 relation snapshot coverage; L16 gains deterministic versioned JSON demo output. D01, D02, D04 and D07 retain DEFERRED approval with the narrow WP exceptions documented. P0009-1 is marked superseded in its notes, without changing approval.

WP01-WP06 and WP08 are APPROVED. WP07 remains PROPOSED. A2.1 adds scoped append-only validation, per-channel exposure, evidence dependency families, fixed human reveal protocols, and preservation of observations alongside contradictory evidence. It adds 16 acceptance strings to the new WP items. Sphoenix retains the human-only authorities stated in the amendments.

Part 2 is 5b75241. A3-01 through A3-07 remain PROPOSED/P2 with human review. They are never automatic implementation scope, never blockers for approved work, and require Sphoenix's H4 decision after L04-L12 and three human cases.

Both source amendments are copied byte-for-byte under loop/amendments/. Main's local copies are excluded locally, not committed on main.

## WP02 fixture

Commit 54a0d38 adds tests/fixtures/ciede2000_sharma2005.tsv. All 34 published pairs, 238 values, were compared as exact decimals against Table I in the authors' published paper, printed page 24 (PDF page 4). The table was also rendered and inspected. Only published numerical reference data is committed. Source URLs, access date and both downloaded-source digests are in the fixture header. Sources and extraction evidence are retained in <RUNS>/operator-A2/.

Source SHA-256: 44aebb39107128328add54fbef5ac8ee89909e50508f448a1580adea2058a4b8.
Fixture SHA-256: 00d1208c043ed91cff4bf1a16e01af12812727512a6b20247293fa11af51bce3.

## Step 0010 correction

All Section 3 conditions passed against tracked evidence:
- Round 2 has zero blocking findings and all three prior findings RESOLVED.
- Accuracy is the only score at or below 2.
- Its negative evidence concerns lines 182-204, inside the harness-written Research section (lines 179-207); the remaining accuracy bullet reports passed documentation checks.
- The original decision remains REVERT/R3. Its SHA-256 is 00e05efb7d8b2ee6640f44949f897d80757c2dbbe26efed3c0453f78d438b4dc.

An appended HARNESS_POLICY_FALSE_REVERT event restores L04 from BLOCKED/retries=2 to PENDING/retries=1, product_retry_charged=false, authorized by Sphoenix, amendment A2, 2026-10-09. A RESUME event follows step 0010. No historical decision, evaluation or report is rewritten.

The tracked export digest and retained RUNS patch both match ec08e8e49ce309b4857e7d5649a259638260e63cf0120f54478b4c708006da11. The restart prefers eligible L04, verifies that exact recovery, and performs fresh gates and evaluation in a new step. A hash mismatch falls back to a fresh build carrying earlier findings.

## Restart boundary

Push and restart are conditional on the final committed-head harness suite and full dry run. Final validation evidence and launch metadata belong in <RUNS>/operator-A2/ and <RUNS>/continuous-launch-A2.json. Continuous mode remains limited to 12 steps and 07:30 local time, retains existing stop conditions and checkpoints, and never merges or pushes main. No witness implementation or real-media judgment is authored by this operator amendment.
