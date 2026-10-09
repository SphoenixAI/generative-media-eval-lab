# Pilot 0: first human-authored real-media cases

Phase 4 was accepted. Pilot 0 adds local file evidence and a private CLI authoring workflow. It does not execute Phases 5+, run a multimodal judge, create gold references, run hypothesis tests, detect regressions, estimate VFX work or publish real media.

The prepared `pilot-local` workspace starts with **zero selected clips and zero substantive judgments**. Sphoenix supplies the 12–20 selections, creative intentions, observations, hypotheses, relation purposes, proposed tests and confidence revisions. Blank forms deliberately fail validation until completed. The automated tests use generated technical video patterns with test-only text, never empirical pilot cases.

## Setup and first clip

Run commands from the repository:

```sh
cd generative-media-eval-lab
.venv/bin/eval-pilot doctor
.venv/bin/eval-pilot init pilot0
```

The checked ffmpeg/ffprobe executables are installed locally in `.tools`. On another Apple Silicon Mac, `python3 scripts/install_media_tools.py` downloads the same third-party builds and verifies their published SHA-256 checksums. Alternatively install FFmpeg yourself or set absolute `EVAL_LAB_FFMPEG` and `EVAL_LAB_FFPROBE` paths. Every ingestion/extraction records the executed binary's hash and full version/build string. `uv sync --frozen --extra test` installs the Python environment; there are no new Python runtime dependencies.

### 1. Register your selected file

Replace the path and label with your selection. The label is an identifier, not a judgment. Unknown generator or generation time stays unknown; importing a file does not fabricate a ModelRun.

```sh
.venv/bin/eval-pilot register pilot0 clip01 '/absolute/path/to/your-clip.mp4' --label 'Your neutral clip label'
.venv/bin/eval-pilot open clip01
.venv/bin/eval-pilot start clip01
```

Copy the returned `session-...` ID for later `--session` arguments. The timer measures your authoring session, not an experimental condition A. Pause it during unrelated work:

```sh
.venv/bin/eval-pilot pause SESSION_ID
.venv/bin/eval-pilot resume SESSION_ID
```

Registration copies the file into the private managed store, verifies its bytes against the original, and persists ffprobe metadata plus the complete decoded video timeline. The original outside the project is not modified. `--selection-reason`, `--provenance-note` and `--rights-status` accept your own metadata; no rights or generation provenance is inferred. Each distinct byte-identical source counts only once in a dataset.

### 2. Declare the intended creative context

```sh
.venv/bin/eval-pilot draft intent --output pilot-local/inputs/clip01-intent.json
open -e pilot-local/inputs/clip01-intent.json
```

Fill the objective, audience and context in your own words. Fill each applicable criterion's `dimension`, `applicability`, rationale and observable acceptance requirement. Add or remove criterion rows according to the intended shot. Valid dimensions are listed in [the existing rubric](rubric-design.md) and the JSON schema. A surreal or deliberately unstable shot must be judged against your declared intent. Then save:

```sh
.venv/bin/eval-pilot intent clip01 --file pilot-local/inputs/clip01-intent.json
```

The CLI records human-declared intent and your author name; this is local authorship attribution, not identity authentication. Use global `--author NAME` before a subcommand if someone else is writing. Later intent changes require a `revision_reason`; prior intent, clip and dataset revisions remain available. A changed context does not silently reinterpret prior hypotheses.

### 3. Inspect exact timestamps and record an observation

All annotation times are seconds relative to the **first decoded video frame**. Do not derive them from rounded average FPS. Original-player offsets may differ; the ingestion records the source PTS offset. For a desired timestamp, `open --at` opens a PNG of the first frame beginning at or after that time and prints both requested and actual timestamps.

```sh
.venv/bin/eval-pilot open clip01 --at 0.5
.venv/bin/eval-pilot frames clip01 --at 0 0.5 1
.venv/bin/eval-pilot draft observation --output pilot-local/inputs/clip01-o1.json
open -e pilot-local/inputs/clip01-o1.json
```

Choose sample times inside your actual clip. In the form, write the observation and its start/end interval. Confidence is optional and remains uncalibrated. To attach an extracted image, copy its `derivative_id` and `frame_index` into the form. Use the **actual** image timestamp within the observation interval. Frames are optional if you viewed the original interval directly; a still image cannot establish continuous motion.

```sh
.venv/bin/eval-pilot observe clip01 --id o1 --file pilot-local/inputs/clip01-o1.json --session SESSION_ID
```

Every observation is stored as existing Evidence plus a human submission envelope that pins authorship, optional confidence, frame manifest and session. Missing/corrupt media or attached frames are `UNKNOWN` availability, never score zero or pass. Authored history is preserved even if a file later becomes unavailable.

### 4. Author competing hypotheses and discriminating-test proposals

```sh
.venv/bin/eval-pilot draft hypothesis --output pilot-local/inputs/clip01-h1.json
.venv/bin/eval-pilot draft hypothesis --output pilot-local/inputs/clip01-h2.json
open -e pilot-local/inputs/clip01-h1.json pilot-local/inputs/clip01-h2.json
```

For each hypothesis, supply your proposed cause, observation, evidence required, test that would distinguish alternatives, predicted observation and falsifier. Use local observation IDs such as `"o1"` in supporting/contradicting evidence lists. Optional `"o1@1"` pins an explicit revision. No content is suggested or authored by a model.

```sh
.venv/bin/eval-pilot hypothesis clip01 --id h1 --file pilot-local/inputs/clip01-h1.json --session SESSION_ID
.venv/bin/eval-pilot hypothesis clip01 --id h2 --file pilot-local/inputs/clip01-h2.json --session SESSION_ID
.venv/bin/eval-pilot draft relation --output pilot-local/inputs/clip01-r1.json
open -e pilot-local/inputs/clip01-r1.json
```

The relation form names a subject and object by local ID, with their kinds. Available forms include evidence `supports`/`contradicts` a hypothesis; hypothesis `alternative_to` another hypothesis; hypothesis `motivated_by` the special object `"intent"`; evidence `fulfills`/`violates` intent. Supply purpose, scope and supporting references yourself. The relation automatically pins the clip's declared intent, and remains a human assertion rather than a proven causal observation.

```sh
.venv/bin/eval-pilot relate clip01 --id r1 --file pilot-local/inputs/clip01-r1.json --session SESSION_ID
```

Create additional relation forms/IDs for the connections you actually intend. Proposed tests are recorded only; none are executed.

### 5. Revise confidence only after supplying new evidence

Create another observation such as `o2` with its own timestamped evidence, then:

```sh
.venv/bin/eval-pilot draft confidence --output pilot-local/inputs/clip01-h1-revision.json
open -e pilot-local/inputs/clip01-h1-revision.json
```

Supply the new confidence (or null if unknown), your reason, `new_evidence` IDs, and whether it is supporting, contradicting or context-only. The same already-used evidence cannot be passed off as newly supplied evidence.

```sh
.venv/bin/eval-pilot revise-confidence clip01 --hypothesis h1 --file pilot-local/inputs/clip01-h1-revision.json
.venv/bin/eval-pilot finish SESSION_ID
.venv/bin/eval-pilot show clip01
.venv/bin/eval-pilot status pilot0
```

The prior hypothesis revision remains unchanged. Existing relations still point to the revision you originally selected; explicitly author a new relation if it should target the revised hypothesis. No confidence update is calculated automatically.

### 6. Freeze a local review snapshot

```sh
.venv/bin/eval-pilot snapshot pilot0 --id first-case --output pilot-local/snapshots/first-case.json
.venv/bin/eval-pilot manifest pilot0 --output pilot-local/snapshots/dataset-after-first-case.json
```

A draft dataset can be snapshotted with one clip. `ready pilot0` requires 12–20 distinct selected clips, verified sources and human intent for every clip. Ready means collection requirements met, not an evaluated model or completed comparison.

```sh
.venv/bin/eval-pilot ready pilot0
```

Snapshot records pin exact artifact revisions and hashes, including referenced human records and derivatives. Later annotations, confidence revisions, intent changes or extractions cannot change a prior export. Use a new snapshot ID/output path for the next checkpoint; existing files are never overwritten by CLI output commands. Snapshots are **private local exports**, not publication. The accepted public/embed serializer still rejects real media; its explicit publication snapshot semantics are unchanged.

## Media pipeline

```text
manually selected local file
  -> bounded copy into staging
  -> original/copy SHA-256 verification and source-change check
  -> ffprobe stream metadata + decoded frame PTS index
  -> validated MediaAsset + MediaIngestion + raw probe hash
  -> atomic filesystem bundle and append-only database records
  -> explicit timestamp request
  -> first frame onset >= request; software decode by frame index
  -> PNG checksum + requested/actual times + recipe/tool fingerprint
  -> DerivativeManifest
  -> human Evidence / Hypothesis / RelationClaim + submission attribution
  -> explicit immutable local snapshot
```

`media.py` owns bytes/tools; `pilot_domain.py` adds file/manifest/session records without changing accepted artifact schemas; `pilot.py` joins them to existing human domain objects; `pilot_cli.py` exposes the local workflow. Filesystem and database commits are separate: an interrupted registration can leave a verified unreferenced file bundle, which must not count as a selected case. This is a single-operator workflow, not a distributed ingestion service.

Supported intake is one local video stream, up to 2 GB, 300 seconds and 90,000 decoded frames. Audio presence is recorded but audio is not evaluated/extracted. Attached cover art is excluded. Ambiguous or missing timestamps, multiple video streams, decoder errors, URL/playlists and unsupported containers are rejected. A subprocess has a 120-second limit; no recursive tools or network fetches are available to the decoder command. These are bounded local operations, not a security sandbox for hostile media.

Frame manifests pin binary hash/build, source/probe hashes, integer PTS, time base, requested/actual relative timestamps, dimensions and recipe. Variable-rate clips use their decoded timeline. A request after the last frame onset is rejected even if it lies before the final frame's estimated end. Duration includes a recorded basis: decoded final-frame duration where available, otherwise a declared estimate. Average FPS is metadata, never the addressing rule.

Extraction preserves coded orientation and geometry, converts to RGB24 PNG, and applies no intentional crop, scale or tone mapping. Rotation, pixel format, color metadata and sample aspect ratio are retained in ingestion. Therefore, review the original for display orientation, audio and color/HDR judgments; derivatives do not establish a color-managed or exhaustive temporal observation. The chosen behavior follows the [ffprobe metadata interface](https://ffmpeg.org/ffprobe.html), [FFmpeg stream/rotation options](https://ffmpeg.org/ffmpeg.html) and [select filter](https://ffmpeg.org/ffmpeg-filters.html#select_002c-aselect). Reproducible PNG bytes were tested under the pinned local build, not promised across all platforms/builds.

## Manifest example and contracts

[Dataset JSON Schema](../schemas/pilot0-dataset.schema.json), [full schema bundle](../schemas/pilot0-bundle.json), [actual empty starter manifest](../examples/pilot0/dataset.empty.json), and [blank human forms](../examples/pilot0/intent.blank.json).

Each manifest holds `id`, `revision`, `created_at`, `owner`, `state`, fixed target bounds 12/20 and exact PilotClip references. A registered clip links a MediaAsset and MediaIngestion, selector, neutral label, optional human provenance/selection note and optional IntentSpec. The private snapshot recursively includes exact content and SHA-256 for those references; files remain in the managed store. Copy the whole private workspace for a backup, not just its JSON export. `pilot-local/` and `.tools/` are ignored by Git.

An illustrative clip-reference entry has this shape (not a registered or judged case):

```json
{"kind":"PilotClip","id":"clip01","revision":2}
```

The [four future comparison contracts](../pilot0/experimental-contracts.json) define A human only, B human + one evaluator, C human + specialists, and D the same specialists + intent/hypothesis graph. They share media, declared intent, rubric, task and evidence budget. C versus D isolates the graph's contribution as far as possible, and counts the cost of constructing/reviewing it. No condition has run or been claimed better. Pilot 0 graph authoring must not be reported as clean condition-A performance.

The [seven outcome contracts](../pilot0/outcome-contracts.json) define reference agreement, evaluation time, useful disagreement, failure classification, discriminating-test quality, confidence calibration and rubric revision frequency. They specify units, denominators, missingness and evidence required. Timing is available now; the other scientific outcomes require future human references or review procedures. Subjective confidence is not silently treated as a calibrated probability. With 12–20 manually selected clips, Pilot 0 is a feasibility/measurement design exercise, not a powered superiority study.

## Decisions still open

- Which real clips and production tasks belong in the first 12–20; their provenance/rights and relevant diversity.
- Which creative criteria apply, which failures matter, and how much ambiguity should remain unresolved.
- Future reference reviewers/adjudication procedure, confidence-event wording and what qualifies as a useful disagreement.
- Viewing conditions, including HDR/color-critical work and whether coded-orientation PNGs are sufficient for the first task.
- Later comparison assignment, carryover controls and meaningful accuracy/time margins.

These choices do not block starting the first human-authored case. No live judging, gold sets, regression/VFX engines or polished frontend should be added before those cases exist.
