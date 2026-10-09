# Hypotheses: Phase 4 structures, Phase 5 execution

Implemented records preserve observed problem, proposed mechanism, supporting and contradicting evidence, required evidence, discriminating test proposal, prediction, falsifier, intent and unresolved status. Relation claims distinguish an assertion from an observation and preserve scope, purpose, author and validity interval.

The sample sliding graph contains camera-motion and foot-contact alternatives. Both remain proposals. Recording a predicted outcome is not running a test; no confidence update or causal discovery engine exists at this checkpoint.

Phase 5 should register a controlled test before execution: hypotheses discriminated, one intended manipulated variable, required held-constant factors, measurement instrument and coverage, predicted and falsifying outcomes, limits and authority. Preserve failed or inconclusive tests. A static-camera regeneration changes the generated sample as well as camera instructions; treat that confounding explicitly and use multiple controlled replicates rather than attributing causality to one improved clip.

Do not store hidden chain-of-thought. Keep observations, concise rationale, competing claims, test specification, outcome and uncertainty.

## Human-declared hypothesis sets

`CompetingSet` records ordered `members` and explicit boolean `exclusive` and
`exhaustive` declarations under one pinned intent revision. Named members are
exact existing hypothesis revisions; at least one is required. A hypothesis
identity cannot appear twice, even at different revisions.

An exhaustive set automatically includes one structural `RESIDUAL` member with
the description `none of the listed causes`. This is not a substantive cause or
an evidence-backed hypothesis: it has no confidence, evidence, prediction,
falsifier or status. Non-exhaustive sets contain no residual. Confidence remains
attached to each claim, including unknown (`null`) values; it is never summed,
normalized, averaged or complemented for the residual.

Create a blank form with `eval-pilot draft competing-set --output set.json`.
Fill `members` with short hypothesis IDs (for example, `h1` or `h2@1`) and choose
both flags explicitly. Then submit it with:

```sh
eval-pilot --root /path/to/private-workspace --author YOUR_NAME competing-set CLIP --id causes --file set.json
```

An optional `--session ID` attaches the submission to an active authoring session.
Unqualified IDs resolve once to the latest revision; stored pins never float.
Repeating the set ID appends a revision with an exact `supersedes` predecessor.
Private `show`, snapshots and snapshot exports include the submitted sets and
their referenced history. Public/embed output does not expose them.

Human relation forms also accept `compatible_with` and `refines`, with two
distinct hypothesis identities under the same pinned intent. They remain claims,
never observations. Compatibility is unordered for conflict checking; refinement
records only the supplied subject-to-object direction and infers no other edges.
An exclusive set rejects compatibility between its exact pinned named members,
in either admission order. All retained set and relation revisions participate:
changing a set does not erase its earlier constraint, and a newer hypothesis
revision does not inherit membership. SQLite serializes these admission checks
inside its write transaction. These declarations establish neither causal truth
nor empirical completeness, and produce no quality verdict or confidence update.
