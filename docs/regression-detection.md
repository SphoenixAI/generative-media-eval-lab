# Regression and drift contracts: deferred Phase 7

The `regression_fixture` scenario exercises catastrophic veto despite high aesthetics. It does **not** compare model populations, estimate confidence intervals or detect statistical regression. No drift monitor runs.

A regression analysis must pin benchmark prompts, media sampling policy, generator snapshots, seeds where supported, rubric, evaluator and preprocessing. Report per-dimension category distributions, severe/catastrophic failure rates, pairwise preference including ties and abstention, slices and uncertainty. Pair comparisons by prompt family and account for repeated media/raters. Predeclare a practically meaningful deterioration, multiple-comparison policy and catastrophic-failure guard. Avoid calling random variation or a lower overall average a regression.

Evaluator drift is a separate comparison on a fixed canary and protected audit set: reference agreement, false-negative rate on critical defects, calibration, abstention, coverage, slice errors, output distribution and missingness. A changing distribution is a warning, not automatic proof of degraded correctness. Generator and evaluator upgrades must not change simultaneously in the attribution experiment.

Frozen history supports longitudinal comparison. A rolling challenge suite finds newly relevant failures and has its own version. Shadow qualification and rollback are planned; no automatic model adoption is implemented.
