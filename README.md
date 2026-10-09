# Sphoenix Generative Media Evaluation Lab

A backend for inspecting whether generated media satisfies an explicit intention, what failed, which evidence supports that judgment, and where humans and instruments disagree.

**Status: Phase 4 accepted; Pilot 0 local infrastructure ready.** The accepted synthetic demo remains intact. Local video ingestion and a private human-authoring CLI are now available; the pilot starts empty and Sphoenix supplies the real selections and judgments. There is no live model adapter, paid inference or deployed public service. Phases 5+ remain deferred.

Start with the [Pilot 0 first-clip workflow](docs/pilot0.md). Run `.venv/bin/eval-pilot doctor`, then register your first manually selected clip. The [Pilot 0 report](docs/pilot0-report.md) describes the file pipeline, validation and remaining decisions. Earlier reports below remain historical Phase 4 evidence.

## Read first

- [Research synthesis and measurable acceptance plan](docs/research/synthesis.md)
- [Media benchmarks and current model candidates](docs/research/media-methods.md)
- [Human evaluation, ontology and standards](docs/research/methods-standards.md)
- [Agent harness research and practitioner methods](docs/research/agent-harness.md)
- [Independent source fact-check and corrections](docs/research/independent-fact-check.md)
- [Phase 4 checkpoint report](docs/checkpoint.md)

Research has a **2026-10-06** cutoff, three parallel research tracks, a separate recent-paper/model sweep, and an independent claim review. Registers preserve primary URLs, dates, claims and limitations. Freshness is bounded by sources checked, not a promise of exhaustive internet coverage or local model availability.

## Run

Python 3.12 or newer; `uv.lock` pins the resolved environment. No model credentials required.

```sh
uv sync --frozen --extra test
uv run --frozen --extra test pytest -q
uv run --frozen --extra test eval-lab --output outputs/demo.json
uv run --frozen --extra test eval-lab-check --output outputs/approval.json
```

The project environment already contains the dependencies. Without uv:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m eval_lab.demo --output outputs/demo.json
.venv/bin/python -m eval_lab.harness --output outputs/approval.json
```

The CLI uses an ephemeral SQLite database by default. `--db /absolute/path/demo.sqlite` retains the append-only records. Replaying identical fixture data is idempotent. Do not use authored demo seeds, synthetic identities or this API stub as a production service.

## What is implemented

- Frozen, typed, versioned domain snapshots with canonical hashes, linked intent and evidentiary claims.
- SQLAlchemy/SQLite persistence, foreign keys, unique submission keys, initial schema version, and SQLite append-only triggers.
- Thirteen dimensions with behavioral 0–4 anchors; intent-specific applicability, explicit abstention, critical-failure veto and provisional regeneration policy.
- Human/pairwise rating records, stable blinded assignment, tie/cannot-determine distinction, ordinal alpha, nominal/quadratic kappa and exact agreement.
- Thirteen bounded deterministic specialists; validated output contracts, pinned fixture rules and rubric, exact-input cache, call/time limits and traces.
- Disagreement proposals, two competing hypothesis records and an intention-bearing graph. No hypothesis tests executed.
- Public/embed allowlist serializers using the same stored case; reveal follows a stored session rating. Health and deny-execution FastAPI stubs only.
- Reproducible demonstration, adversarial tests, independent review and an offline approval harness with negative controls.

## Layout

```text
src/eval_lab/
  domain.py          # intention, evidence, rubric, rating, claims, graph
  persistence.py     # typed snapshots, SQL links, admission invariants
  rubrics.py         # explicit provisional anchors and thresholds
  scoring.py         # critical veto, unknown, review, pass
  agreement.py       # exact agreement, kappa, frequency-ordinal alpha
  providers.py       # protocols and clearly synthetic provider
  swarm.py           # finite independent first passes and traces
  disagreement.py    # conflict representation, never ground truth
  presentation.py    # public/embed projections and reveal contract
  api.py             # boundary stubs, live execution denied
  fixtures.py        # twelve authored scenario records
  demo.py            # Phase 1–4 end-to-end walkthrough
  harness.py         # tests, replay, guards and scoped approval
tests/               # implementation and independent-review regressions
docs/research/       # evidence, comparisons, freshness/fact-check sweeps
outputs/             # actual generated demo and approval artifacts
```

One backend serves all planned surfaces. Providers, site integrations, public hosting and later gold/regression/VFX engines remain behind the Phase 4 checkpoint. [Architecture](docs/architecture.md), [ontology](docs/ontology.md), [roadmap](docs/roadmap.md).

## What passing means

`APPROVED_FOR_OFFLINE_TESTING` means the scoped executable checks passed for the recorded source digest. `NEEDS_HUMAN_VALIDATION` remains true. Agreement among coding agents or fixture judges does not validate a visual judgment, demonstrate human-time savings, establish causality, or authorize production deployment.

Before a live pilot, compare trained-human-only, one qualified judge plus human, and bounded specialists plus human at comparable quality/resource budgets. Include a flat-evidence-log comparison to test whether the intent graph adds value. Measure missed severe failures first, then review time, cost and rework. Preserve negative or inconclusive results.
