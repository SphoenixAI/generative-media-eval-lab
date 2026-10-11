6. Invariants

I1. Human judgment is human. For real clips, the loop never creates or edits any of the following:

observations;
hypotheses;
intents or criteria;
relations;
confidence revisions;
assessments;
verdicts;
decision policies;
test outcomes.

It never writes inside pilot-local/. Fixtures use generated test patterns and text marked TEST-ONLY.

I2. Missing evidence is UNKNOWN. Nothing converts UNKNOWN into 0, a pass, or a default verdict.

I3. History is append-only. Revisions pin their predecessors. Nothing authored is overwritten or deleted.

I4. Accepted artifacts stay fixed. Protected files change only through an item Sphoenix has approved that lists them in authorized_protected.

I5. Measurement is not acceptability. A technical observation never references intent. An acceptability judgment always references a pinned intent revision.

I6. Epistemic state is not operational state. Decision policies consume evaluations and never modify them. Unresolved hypotheses can coexist with a decision.

I7. Only sealed intent excuses a deviation. RECONSTRUCTED and PROMPT_ONLY intent cannot make a material deviation acceptable. CONTEMPORANEOUS intent can, with a flag.

I8. No average hides a failure. Aggregates keep the worst case for each dimension. No decision uses a mean.

I9. No false precision. Confidence is an uncalibrated value attached to a single claim. There is no probability arithmetic across hypotheses, and no numeric information gain, until Sphoenix approves a calibrated type.

I10. No live models or network access in runtime code. No new runtime dependency without an approved item.

I11. Tests are never weakened. Removing, renaming, skipping, xfailing or loosening a test requires an approved item.

I12. Public surfaces stay sanitized. Public and embed serializers never emit real media, private notes or unpublished data.

I13. Reproducible by construction. Record tool versions and hashes. Anything claimed deterministic has a test proving it.

I14. Scope is fixed. DEFERRED items are never built.

I15. main belongs to Sphoenix.

The loop never pushes to main and never merges its own pull request.
Nobody force-pushes any branch.
Outside the loop, Codex changes main only when Sphoenix explicitly instructs it in chat.

I16. The judge is fixed inside the loop.

The builder and the enhancer never edit the harness code, prompts, schemas, rubric, invariants, baselines or north star.
Only loopctl's own bookkeeping writes to these files, together with bootstrap --rebaseline after main is merged, and sessions that Sphoenix starts.

loop runs follow loop/LOOP.md
