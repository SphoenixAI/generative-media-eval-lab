SYNTHETIC DRY-RUN ONLY. Verify bootstrap bookkeeping without product changes.

Relevance: NORTH_STAR.md requires an auditable gate before product development.

Acceptance criteria:
- loop/tests pass.
- The gate passes on unchanged product code.
- baseline.json matches a fresh test run.

Method claims: none

Invariants at risk: I4 accepted artifacts; I11 tests; I15 main; I16 fixed judge.
Expected changes: this step report only.
Out of scope: product code, real media, substantive judgments, protected artifacts, and harness edits.
