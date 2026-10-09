# Human evaluation: current contract and study requirements

Phase 4 implements records and deterministic agreement calculations. Its seeded human ratings are authored fixtures. No participants have been recruited, no real clips are being assessed and no empirical consensus or rater reliability is established.

## Blind comparison

An `EvaluationRound` pins candidate runs and rubric. Candidates must share an exact prompt revision. The generic record supports two or more candidates; the A/B presentation helper requires exactly two. A private assignment seed and stable rater identity determine reproducible side order. Calibration or round revisions do not change the displayed pairing or reset prior reveal state.

`PairwiseRating` preserves four responses: `A`, `B`, `tie`, and `cannot_determine`. A tie expresses equivalent preference under the evaluation objective; inability to determine a preference is a coverage issue. Neither is a dimension score or proof that either output passes. The server-side serializer omits results before a stored eligible submission and reveals only allowlisted fixture results afterward.

The presentation contract assumes a trusted application service binds the session to the rater reference. The demo's rater identifier is not public-user authentication. No production anonymous-voting or anti-abuse service is claimed. Media tokens currently represent fixtures without playable media.

## Dimension ratings and admission

`HumanRating` stores one participant's dimension scores for one run, round and rubric. Dimensions cannot repeat within a rating. A scored result requires integer 0–4, rationale, evidence and self-reported uncalibrated confidence. `abstain` and `not_applicable` preserve null scores; application of `not_applicable` must agree with the declared intent.

Stable rater identity, exact run and round identity determine submission uniqueness. A participant cannot cast another observation by changing calibration revision. Ratings cannot be revised; a future adjudication record will represent corrections. The repository denies new ratings when the current round is closed, even when the request points to an old open revision. Exact already-stored records remain retrievable.

## Agreement that is implemented

`rating_matrix` selects one dimension from ratings sharing one exact rubric and round reference. Rows represent model-run units; columns represent stable rater IDs. Repeated rater/unit cells are rejected. Missing dimensions, abstentions and non-applicable judgments become missing values rather than zero. Callers must select compatible data before constructing a matrix.

`percent_agreement` reports **pair-weighted exact agreement**: each usable within-unit rater pair contributes equally. It is not equal weighting of clips when rater counts differ.

`krippendorff_alpha` supports nominal, ordinal and interval variants. The default ordinal implementation uses cumulative marginal-frequency distance. Interval alpha uses squared numeric differences and is explicitly a different instrument. Units with fewer than two usable ratings contribute neither observed coincidences nor expected marginals. Results retain excluded-unit and used-rating/pair counts. Empty pairable data or zero expected disagreement produces a null value with a reason. Negative agreement is retained.

`cohens_kappa` expects exactly two raters per unit and supports nominal or quadratic weighting. These are distinct measures with different assumptions. All current agreement results explicitly report `uncertainty="not_estimated"`. Bootstrap intervals, crossed-rater inference, ICC, pairwise ranking and calibrated probability metrics are not implemented.

## Before interpreting real judgments

Train raters using examples excluded from protected audit data. Define the unit of analysis, intended users, playback conditions, independence, exclusions and missingness reasons. Keep teaching, development, calibration and audit roles separate. Obtain judgments independently before revealing model identity or other judgments.

For regression studies, preserve prompt clustering and paired model comparisons. Do not count frames or multiple dimensions as independent videos. Report support, prevalence, coverage and uncertainty alongside agreement. Public volunteer ratings and calibrated production-reviewer ratings should remain identifiable analysis strata.

A high agreement coefficient does not prove that the rubric captures the useful task. The next empirical acceptance study must measure missed consequential failures and human review effort against a competent manual checklist and a single-evaluator baseline. See `research/methods-standards.md` for sources and the proposed study design.
