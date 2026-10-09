# Sphoenix Generative Media Evaluation Lab

Can ambiguous generative-media failures be converted into evidence-linked, reproducible, actionable evaluation?

This lab records what someone observed, the competing explanations, the evidence behind each claim, and the creative intention that makes a judgment relevant. It is a local Python backend and CLI.

**Status · October 8, 2026**

- Phase 4 and Pilot 0 infrastructure accepted.
- **209 tests passed; 0 failed; 0 skipped.** Seven validation gates passed; four deliberate software mutations were caught. [Validation record](outputs/loop/front-door-validation.json).
- **0 published real-media results.** The checked examples use synthetic judgments and generated technical video fixtures.
- No live model judges, measured workflow advantage, or claims of superiority. The intent study is designed, not run.

## Three minutes

Read the [Pilot 0 report](docs/pilot0-report.md) for the implemented boundary and the [first-clip guide](docs/pilot0.md) for the human workflow. After setup, run:

```sh
.venv/bin/eval-pilot doctor
.venv/bin/python -m pytest -q
.venv/bin/eval-pilot --help
```

Passing these checks establishes software behavior. It does not validate a perceptual judgment or demonstrate scientific or production effectiveness.

## Setup

Use Python 3.12 or newer and `uv`. From the repository root:

```sh
uv sync --frozen --extra test
```

Media tests and ingestion require both `ffmpeg` and `ffprobe`. On Apple Silicon macOS, the optional installer downloads third-party builds and checks pinned SHA-256 values:

```sh
python3 scripts/install_media_tools.py
```

On other platforms, install those tools separately. The CLI discovers them through `PATH` or absolute `EVAL_LAB_FFMPEG` and `EVAL_LAB_FFPROBE` paths. The recorded validation used Python 3.12.14 and FFmpeg 9.0 on macOS; other platforms have not been validated here. No model credentials are required.

## What exists

- Verified local video copies, ffprobe metadata, decoded timestamps, deterministic frame extraction, and derivative manifests. Reproducibility checks use the recorded toolchain.
- Human-authored intent, observations, hypotheses, relation claims, test proposals, and confidence revisions. Sphoenix supplies every substantive real-media judgment.
- Versioned records, append-only SQLite storage, and snapshots that pin revisions and hashes. Missing evidence remains `UNKNOWN`.
- Synthetic scoring and disagreement demonstrations with critical-failure vetoes. The fixture specialists are authored rules, not independent perceptual judges.

Private clips and annotations stay in the ignored `pilot-local/` workspace. Public/embed serializers are fixture-only. Derivative PNGs are not a color-managed HDR viewing workflow. The [architecture](docs/architecture.md) and [Pilot 0 guide](docs/pilot0.md) document these limits.

## Roadmap

The evaluated build loop is planned, not running. Next: Pilot 0.1 intent sealing and explicit test/resolution records; three human-authored cases; validated instruments; then studies. Each later stage needs separate approval.

The first planned study compares no intent, true intent, and decoy intent to test whether unstated intent explains some evaluator disagreement. The lab's thesis must remain useful if that effect is small. No participants or results are reported. See the [roadmap](docs/roadmap.md).

Live providers, gold sets, regression/VFX engines, instrument execution, and a frontend remain deferred. Research references have an [October 6, 2026 cutoff](docs/research/synthesis.md).

## License

No project license has been selected yet.
