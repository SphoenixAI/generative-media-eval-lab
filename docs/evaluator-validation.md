# Offline approval and evaluator validation

The implemented harness assesses local software contracts and authored fixtures. It never approves the validity of a real media judge, certifies human consensus, authorizes deployment or establishes that a swarm improves human work.

Run the real harness from the project environment:

```sh
.venv/bin/python -m eval_lab.harness --output outputs/approval.json
```

The process returns exit code zero only for `APPROVED_FOR_OFFLINE_TESTING`; other results return one. Its report always includes `empirical_validation: NEEDS_HUMAN_VALIDATION`, `deployment_authorized: false` and zero configured paid calls. Zero is fixture-mode evidence, not a production invoice measurement.

## Evidence collected

The harness launches pytest through the current Python interpreter as a subprocess, with a 120-second timeout and a temporary JUnit XML report. Counts come from the XML, are checked against testcase records and are combined with the subprocess exit status. Missing or invalid XML, no executed tests, timeout, failures, errors or skipped tests block approval. Tests call gate functions directly and never invoke this subprocess runner recursively.

It runs the backend demo twice using two newly created SQLite repository instances, with no shared cache or database. Canonical JSON outputs must match, and both report zero paid calls. This demonstrates deterministic synthetic workflow replay. It does not show deterministic vendor inference or numerical reliability of real annotators.

Five direct behavioral gates check catastrophic veto, missing required judgment, evidence requirements, rubric pinning and delayed public/embed reveal. Four temporary callable mutants deliberately remove the catastrophic veto, bypass evidence parsing, silently normalize a mismatched rubric hash, and expose results before submission. The same assertions run against the production callable and mutant. Production must pass and each mutant must trigger its intended behavioral assertion. An unrelated mutant crash is not counted as successful detection. These are local software mutations, not adversarial media or empirical evaluator validation.

The report hashes path/content pairs under `src` and `tests`, plus `pyproject.toml` and `uv.lock` if present. Generated Python caches and `*.egg-info` packaging metadata directories are excluded; packaging can rewrite these generated files without changing the source under test. It records Python and relevant package versions. A second source digest must match the first; edits during execution block approval. The manifest links evidence to the inspected source tree but is not a signed attestation, a dependency lock or a guarantee against a malicious host.

## What remains human validation

The next empirical study needs independently sourced, rights-cleared media; a declared production task; rubric calibration; a hidden holdout separated by prompt/media lineage; and a competent human-only and single-judge-plus-human baseline. Specialists must earn their extra latency and cost through improved severe-failure detection, useful interventions or reduced human review time at a predeclared quality level.

Measure false negatives, false alarms, abstention and coverage, dimension agreement, confidence calibration, evidence grounding, subgroup performance, reviewer minutes and actual inference cost. Preserve disagreement and adverse results. Shared model errors mean thirteen specialist names do not constitute thirteen independent votes. Consensus is not an acceptance gate.

Future live adapters also need enforced tool permissions and budgets outside model output, media-checksum verification, temporal coverage checks, output-size limits, rate limits, operational authentication, privacy controls and provider cancellation. The fixture workflow's `asyncio` timeout is cooperative. The pytest timeout bounds its direct subprocess; neither mechanism is a sandbox for untrusted application code or proof that remote side effects stopped.

The current evidence scope and exact results are in `outputs/approval.json` after the final harness run. Passing an earlier report does not approve later source edits or turn provisional media judgments into ground truth.
