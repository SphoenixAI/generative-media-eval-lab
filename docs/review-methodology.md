# Independent methodology and domain review

Review date: 2026-10-06. Scope: `domain.py`, `persistence.py`, `scoring.py`, related presentation identity behavior, and the research claims in `docs/research/methods-standards.md`. The reviewer did not edit implementation code. All observations below concern a local deterministic backend with authored records.

## Evidence and current disposition

The first independent reproduction used an in-memory repository and demonstrated that a MediaAsset could be recorded as a human rater, a Rubric could be recorded as hypothesis evidence, a historical open-round revision could admit a vote after closure, a rater calibration revision could create a duplicate observation, and a rating revision could appear as an additional observation. Those were implementation defects, not merely methodological preferences.

The implementer corrected these boundaries. The independently authored `tests/test_domain_review.py` initially passed **29 tests** after the fixes. A further interleaving probe identified a close-versus-admission race, which the implementer then fixed. The final independent run passed **30 tests in 0.39 seconds** using `.venv/bin/python -m pytest tests/test_domain_review.py -q`. The root agent owns the project-wide final test run and overall harness disposition.

Verified resolved in the 29-test run:

1. **Reference meaning**: an existing object of the wrong type cannot occupy rater, run, rubric, round, intent or evidence fields. Persistence also revalidates objects created with unchecked model-copy updates.
2. **Historical lifecycle bypass**: new dimension and pairwise ratings against an old open revision are denied when the current round is closed.
3. **Stable participant identity**: a rater calibration revision or round revision does not create another voting opportunity. Ratings remain one immutable submission; exact retries are idempotent.
4. **Blind assignment and exposure**: side assignment and previously revealed state survive nonsemantic rater and round revisions.
5. **Evidence scope**: a rating cannot cite another output's evidence; hypotheses cannot claim supporting evidence from another declared intent; relations cannot relabel a hypothesis's intent.
6. **Regeneration policy**: invalid regeneration/failure threshold ordering is rejected. A valid policy distinguishes human review from regeneration at its stated boundary.
7. **Graph identity**: an embedded relation must exist in persistence and match that exact revision's digest. The graph cannot silently rewrite a persisted claim's purpose.
8. **Concurrent duplicate submission**: a forced race where both validators finish before either inserts commits exactly one rating in a file-backed SQLite database. This tests the race the original read-before-write duplicate scan missed.

Further finding resolved:

- **Closure after validation, before insertion**: the first probe failed because a rating could pass link validation, the round could then close, and the rating could still commit. The repository now serializes SQLite writers with an immediate transaction and rechecks current round state before inserting a new rating. `test_round_closure_between_validation_and_insert_prevents_new_admission` passes and confirms that the rejected submission leaves no rating behind. The concurrency claim remains limited to the tested SQLite backend.

## Research fact checking

The methodology review distinguished canonical frequency-based ordinal alpha from squared-score interval alpha, provided the original published missing-data oracle matrix, and specified that fixture agreement cannot establish human reliability. The main implementation agent owns the numerical oracle tests.

The source sweep checked official documents and version histories after discovery. It corrected a secondary C2PA release-date error, stale details from an older judge-consensus paper version, and draft-versus-final standards status. A second researcher then found that the initial P.910 citation was superseded. Reopening both ITU records verified **P.910 (07/2026), approved 2026-07-29, in force**, and **P.910 (10/2023), superseded**. Both the research report and source register were corrected. The new edition's detailed clause changes were not inspected, and no edition-specific conformity claim is made.

This independent source correction is evidence that the review process found a mistake. It is not evidence that every source or technical claim is now error-free.

## Approval meaning and limits

A passing domain suite supports a bounded local software pilot. It does not establish valid video perception, calibrated confidence, independent human agreement, production-safe anonymity, certified standards compliance, causal identification, accurate VFX effort estimates or measured workflow improvement.

The database race probe covers two concurrent SQLite submissions and the closure interleaving it explicitly constructs. It does not validate a distributed deployment or PostgreSQL isolation. Authentication, untrusted multiuser service behavior and deployment are separate acceptance work.

The next empirical study should compare a competent manual checklist, one evaluator using the same checklist, and the specialist system on held-out media. Measure reviewer effort and missed consequential failures together. Preserve ties, abstentions and negative results. Agent agreement remains an input to review, never a replacement for independent outcome evidence.
