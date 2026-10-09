# Pilot 0 infrastructure checkpoint

**Ready for Sphoenix's first human-authored real-media case.** No pilot media has been selected on Sphoenix's behalf. The initialized private dataset is empty. No substantive observations, hypotheses, intent declarations or confidence judgments have been authored by Codex for that dataset.

The accepted Phase 4 implementation and its historical outputs remain available. Pilot 0 is the specifically authorized local evidence extension; Phases 5+ remain deferred. No live multimodal provider, automated real-media judge, gold set, regression/VFX engine, test execution engine or polished frontend was added.

## Files changed

Added runtime modules:

- `src/eval_lab/media.py`: verified copying/hashing, ffprobe metadata/timeline, frame extraction, integrity verification and derivative manifests.
- `src/eval_lab/pilot_domain.py`: additive ingestion, derivative, selected-clip, dataset, human-submission, session and frozen-snapshot records.
- `src/eval_lab/pilot.py`: local registration, human authoring, confidence revisions, timing and snapshot workflow.
- `src/eval_lab/pilot_cli.py`: `eval-pilot` commands and blank-form/schema generation.

Modified `src/eval_lab/persistence.py` to register the additive types, validate their links and permit explicit human pilot intent to scope evidence without inventing a generator run. Accepted Phase 4 artifact schemas were left unchanged, preserving their canonical snapshot hashes.

Added `tests/test_media.py` and `tests/test_pilot.py`; added `scripts/install_media_tools.py`; added future comparison and outcome contracts in `pilot0/`; added generated schemas in `schemas/` and empty/blank examples in `examples/pilot0/`. Updated `pyproject.toml` for the CLI entry point, `.gitignore` for private media/tools, and `README.md` for the Pilot 0 entry point. The existing dependency lock remains valid; no new Python dependency was required.

Added [the operator guide](pilot0.md), this report, and machine-readable validation outputs under `outputs/pilot0/`. ffmpeg/ffprobe were installed only in the ignored `.tools` directory using pinned publisher checksums. Private data uses the ignored `pilot-local` directory. The directory has no Git repository/remote; no commit or publication was made.

## Media pipeline architecture

**Local source → verified managed copy → raw ffprobe metadata + decoded PTS index → timestamp request → indexed software decode → hashed PNG + derivative manifest → human-authored records → pinned private snapshot.**

SHA-256 verification binds both the retained original and each derivative. Tool hashes/build strings, probe checksum, extraction recipe, source integer PTS, clip-relative timestamps, dimensions, rotation and color metadata are retained. The first frame beginning at or after a requested timestamp is selected; average FPS is never used as a seek approximation. Requested and actual timestamps are separately visible. Repeated extraction under the same pinned build was checked for matching PNG bytes.

Inputs are bounded local files: one video stream, up to 2 GB, 300 seconds and 90,000 frames. Audio presence is metadata only. Missing/ambiguous timestamps, invalid inputs, decode errors, tampered files and out-of-range requests fail explicitly. An unavailable source or attachment becomes `UNKNOWN` evidence availability; no failure score is invented. Pilot 0 produces no automatic quality verdict.

Frame derivatives retain coded orientation, use RGB24 and have no tone mapping. Use the original for display/rotation, audio and color-sensitive judgments. Those transformations and duration estimates are explicit, rather than implying that a frame captures the entire temporal or color experience.

## Test evidence

**67 new tests; 209 total tests pass**, including the 142 accepted checks. Tests use actual ffmpeg/ffprobe execution on generated technical video files; these are codec fixtures, not the manually selected pilot sample. New checks include variable/nonzero timestamps, exact frame selection against an independent full decode, repeated-frame byte identity, rotations/audio metadata, source changes during copying, corruption/missing files, decoder errors/timeouts, input and time limits, authored-form validation, confidence revision history, session timing and frozen exports.

The final [approval report](../outputs/pilot0/approval.json) runs the existing bounded harness against the current source and test suite. It also checks the accepted synthetic demonstration, critical-failure/evidence/reveal guards and mutations. [Pilot readiness evidence](../outputs/pilot0/readiness.json) adds tool fingerprints, contract hashes and the empty real dataset status. The older `outputs/approval.json` remains historical Phase 4 evidence and was not overwritten.

Passing checks support local infrastructure readiness only. They do not validate the media rubric, a human reference, a model's judgments, confidence calibration or an efficiency advantage. One existing Starlette/httpx deprecation warning remains; endpoint tests pass.

## Sample dataset manifest schema

The [JSON Schema](../schemas/pilot0-dataset.schema.json) permits an empty draft and limits datasets to 20 clip references; `ready` requires at least 12. Runtime validation additionally checks unique file hashes, exact existing references, verified file availability and human intent for every ready clip. The [schema bundle](../schemas/pilot0-bundle.json) covers all new records and human input forms.

[The prepared empty manifest](../examples/pilot0/dataset.empty.json) contains:

```json
{
  "id": "pilot0",
  "revision": 1,
  "schema_version": 1,
  "owner": "Sphoenix",
  "state": "draft",
  "target_minimum": 12,
  "target_maximum": 20,
  "clips": []
}
```

The actual file also records `created_at`. Each later clip entry pins a PilotClip revision. That record links verified MediaAsset/MediaIngestion records, selector/label and human intent; derivative manifests and author submissions enter the private snapshot through exact references and hashes. No floating “latest” references are written into a snapshot. Real-media public/embed publication remains disabled.

## First-clip workflow

The [operator guide](pilot0.md#setup-and-first-clip) gives exact commands and form instructions. In order: register the selected local file; open it and start a session; fill and submit creative intent; inspect exact frame timestamps; fill and submit observation `o1`; author competing `h1`/`h2` hypotheses and their test predictions/falsifiers; connect them through human relation claims; add new observation `o2` before revising confidence; finish the timer; freeze `first-case` as a private snapshot.

Blank templates contain no suggested conclusions. Sphoenix supplies every substantive statement. The CLI preserves the text, authorship declaration, pinned context and evidence references, and appends revisions with rationale. Tests only exist as proposals. Human authorship is a local declaration, not authenticated identity or proof of how the text was written.

## Future experiments and unresolved decisions

[Four condition contracts](../pilot0/experimental-contracts.json) define A human only, B human + one evaluator, C human + specialists, and D the same specialists + the intent/hypothesis graph. All are unexecuted; current sessions are explicitly `PILOT0_AUTHORING`, not condition A. [Seven outcome definitions](../pilot0/outcome-contracts.json) specify reference agreement, active evaluation time, useful disagreement, classification accuracy, proposed-test quality, confidence calibration and rubric revision frequency with units, denominators and unknown states.

Before a comparative trial, choose the production task and clips, human reference/review procedure, critical-failure definition, viewing conditions, confidence-event wording, useful-disagreement criterion, counterbalancing and meaningful accuracy/time margins. Twelve to twenty manually selected clips establish feasibility and expose measurement problems; they do not establish population-level superiority. No condition is claimed better.

Operational limits still include single-operator use, separate filesystem/database commits, operator-controlled timing, no color-managed HDR workflow, and no authenticated publishing. These do not prevent beginning the first case. Further judging or architecture should wait for those human-authored cases and their observed needs.
