# Research actionability policy correction

Sphoenix authorized this correction after reviewing Step 0005. Relevance (`affects_this_step`) is independent of mandatory corrective work (`action_required`). The strict schema requires both booleans and a nonblank action or no-action rationale; required work must be relevant. No default actionability is inferred from verdicts or newer-practice notes. The researcher supplies the judgment; the harness checks the contract and applies it deterministically. Historical research lacking this field is preserved, not silently reclassified.

The enhancer trigger and R4 now consume `action_required=true`. Evaluator findings, prior-finding statuses, all other decision rules, gates, protected paths, limits and human checkpoints remain unchanged. Reports and ledger rows retain contextual claims and the new field.

Step 0005 remains REVERT / R4. An append-only policy classification credits exactly one product retry, making L02 PENDING with one retry. L07 remains integrated. All 499 original historical evidence files remain byte-identical.

## New tests

`test_actionability.py` adds 15 tests: confirmed without new practice; confirmed contextual practice; confirmed material practice; contradicted reliance; outdated reliance; unverifiable shipped fact; partial vs complete resolutions; bounded unverifiable assumption; evaluator/gate/prior-finding preservation; historical Step 0005 old-R4 vs corrected-R6 replay; missing/wrong boolean; irrelevant required action; blank rationale; contextual ledger/report persistence; append-only idempotent retry credit and eligibility.

`test_patch_recovery.py` adds four tests: exact reconstruction and historical-report preservation; hash mismatch without mutation; incompatible-base fallback; cross-item recovery rejection. Existing assertions are retained; synthetic inputs explicitly declare actionability under the new schema.

## Recovery protocol

The operator may request one recovery with `--recover-step` and `--recover-sha256`. The harness reconstructs the complete historical exported diff against its recorded base in a disposable clone and demands the supplied SHA-256. That original diff includes the historical report, so only matching src/tests/docs changes are applied to the current worktree, with their own byte comparison. The old report is never overwritten. The original sealed plan is copied to the NEW step report. A fresh read-only builder self-review, authoritative gates, independent evaluator, canonical research, optional enhancer and fresh decision follow. No prior scores or decisions are reused. Hash mismatch or an incompatible product base falls back to the ordinary fresh-build path. The recovery request is consumed once; subsequent items follow the unchanged queue.

All 107 harness tests passed before committing this correction. The full dry-run result is recorded separately before real recovery begins.
