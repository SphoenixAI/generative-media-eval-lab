# Build loop amendment A5: parallel build lanes, serial integration (2026-10-10)

Sphoenix approves this file by handing it to you. Every rule in A2, A2.1 and A4 still applies.

State when this was written: the loop is stopped at `2bcac80` after the R0 at step 0019 (L12). No runner is active.

**What this file does:**
- **Phase 1:** applies the step-0019 fixes, puts L16 and L15 next, and restarts the serial loop.
- **Phase 2:** while the loop runs, you build the next items in parallel lanes and write a small intake change to the harness.
- **Phase 3:** at a step boundary, the loop starts taking finished lane work. Each piece still gets a fresh gate and evaluation on the current head.

Work happens in parallel. Integration stays serial, and the gate, the evaluator and the decision rules stay unchanged.

## Phase 1. Step-0019 fixes and restart (do first)

Step 0019 is a real L12 failure. Do not reclassify it, do not rewrite its evidence, and leave its product retry charged.

### 1.1 L12 fail-closed evidence boundary

Append this acceptance string to L12; do not edit existing ones:

"Every input any lint rule relies on passes through one shared availability boundary before the rule may produce a clean result. The boundary returns AVAILABLE(value); UNKNOWN(reason) for missing, null or unavailable evidence; or INTEGRITY_FAILURE(reason) for malformed, wrong-type, impossible or corrupt evidence. Only AVAILABLE inputs can support a clean result. UNKNOWN and INTEGRITY_FAILURE each make the result not ready and produce an explicit diagnostic. UNKNOWN never becomes zero, a pass, COMPLETE or ready=true, and INTEGRITY_FAILURE is never coerced into UNKNOWN or a valid value. Each lint rule declares the fields it requires. One shared, parameterized contract test feeds each declared field as missing, null, malformed (where it can be represented) and a valid boundary value, and asserts that only usable evidence can yield a clean result. Where normal admission prevents malformed data, the test exercises the raw read path that can meet corrupted retained data."

Use the lab's existing INTEGRITY_FAILURE status. Do not add a separate INVALID vocabulary.

If L12 would exceed 900 changed lines, split it with the existing split mechanism. Never trim tests to fit.

### 1.2 Standing fail-closed rule

Add this to `prompts/builder_build.md`, `prompts/enhancer.md`, and the intention and production-quality anchors in `RUBRIC.md`:

"Any code path that can decide readiness, completion, a verdict or an operational decision declares the inputs it requires and tests each one as missing, null and malformed. Missing or unavailable evidence yields UNKNOWN or incomplete. Malformed or integrity-invalid evidence yields INTEGRITY_FAILURE. Neither may produce a pass, COMPLETE, SHIP, ready=true or any equivalent clean outcome. Prefer a shared, parameterized contract test over duplicated cases (I2)."

Note the rubric change in the packet.

### 1.3 Narrow R0 into R0 and R0P

**R0 still stops the loop for:**
- a G6 or G14 failure;
- a protected-artifact mutation;
- a forbidden or private path mutation;
- a main or remote integrity concern;
- any score of 0 that names I1, I4, I10, I11, I12, I14, I15 or I16;
- any failure to return the worktree to the known-good base.

**New rule R0P.** A score of 0 that names only I2, I3, I5, I6, I7, I8, I9 or I13 becomes R0P, but only after the candidate is reverted and a post-revert gate confirms all of these:
- G5 protected hashes unchanged;
- G6 forbidden paths untouched;
- G14 main ref and pilot-local listing unchanged;
- the worktree clean at the base commit.

**R0P behaves like this:**
- decision REVERT;
- charges the product retry;
- does not stop the loop;
- the normal retry limits and the consecutive-non-integration stop still apply.

If the post-revert gate fails, escalate to R0 and stop.

Document the known limit: tests run without a sandbox, so side effects outside the checked paths cannot be proven absent.

Add tests for both paths. Update the decision table in `INSTRUCTIONS.md` and the dry-run fixtures.

### 1.4 Order: L16, then L15

Change L15 and L16 to priority P0. Add a one-time scheduling preference, for example a `--prefer L16` run option built on the existing `prefer` mechanism: when L16 is eligible, choose it before L15. Do not add a false dependency to force this order.

L16 is the synthetic JSON the project page will consume. L15 is the operator guide for the first real case.

### 1.5 Validate, then resume, then restart

1. Commit each change.
2. Run `loop/tests` and the full dry run.
3. Verify protected hashes, `main`, and a clean worktree.
4. Only after all of that passes, append a RESUME event:
   - `authorized_by`: "Sphoenix, 2026-10-10"
   - `reason`: "Step 0019 reviewed: genuine L12 I2 failure reverted; fail-closed contract, standing rule and R0P validated."
   - `after_step`: 19
5. Push, then restart without recovery flags:

```sh
cd "/Users/sphoenix/Desktop/Content Evaluator - loop"
export EVAL_LAB_FFMPEG="/Users/sphoenix/Desktop/Content Evaluator/.tools/ffmpeg"
export EVAL_LAB_FFPROBE="/Users/sphoenix/Desktop/Content Evaluator/.tools/ffprobe"
/usr/bin/caffeinate -i "/Users/sphoenix/Desktop/Content Evaluator - loop-env/bin/python" loop/run.py --max-steps 24 --until 07:30 --prefer L16
```

If 1.4 implemented the preference under another flag name, use that name.

`next` skips the item it just reverted, so the first step may be WP01 or WP02. L12 follows with its earlier findings attached. Either order is fine.

## Phase 2. Parallel lanes and the intake change (while the loop runs)

### 2.1 Why this design

Measured over steps 0012 to 0019:
- the builder (plan and build) takes 17 to 29 minutes of each step;
- evaluator, researcher and enhancer take another 7 to 26 minutes.

Building ahead in parallel removes most of the builder time from the serial path. Integration, gate and evaluation stay serial and run on the real current head.

This does not shorten L12 to L16, because L16 depends on L12. It speeds up the witness and SC tracks.

### 2.2 The intake change to the harness (build it beside the loop, not inside it)

Build this on a separate local branch in its own worktree, never on `loop/integration` while the loop runs. Validate it with `loop/tests` and a dry run in a temporary clone. It merges in Phase 3.

**Intake queue.** Candidates live under `<RUNS>/intake/<ITEM>-<UTC timestamp>/`, outside the repository. Each holds:
- `candidate.json`: item, lane id, the base commit the lane built on, the files touched, `patch_sha256`, `created_at`.
- `plan.md`: a Plan written under `prompts/builder_plan.md` rules, including verbatim acceptance strings and a Prior attempts mapping if the item has prior attempts.
- `product.patch`: changes under `src/`, `tests/`, `docs/` and `schemas/` only. Never `loop/**`, `pilot-local/`, `.tools/`, AGENTS.md or media files.

**Selection.** `next` prefers an eligible item that has a ready candidate, oldest first. Otherwise it selects as before. The A2 `prefer` behaviour must cover both `next` and `start`.

**Pre-check.** Before `start`, run.py checks the patch hash and runs `git apply --check --3way` against the current head. A candidate that fails is marked STALE in its folder and skipped. No step starts, and nothing is charged. Its lane rebases it and requeues it.

**Intake step:**
1. `start` as usual.
2. Install `plan.md` as the step's `## Plan`, then `seal-plan` it.
3. Apply the patch with `--3way` onto the current head.
4. Run the build role as a read-only review, the same pattern as `recovery_review`.
5. Continue exactly as a normal step: gate, evaluator, research view, researcher, enhancer if triggered, round 2, decide, finish.

The evaluator always judges the patch on the current head, so nothing is re-evaluated after the fact.

**Provenance.** `step.json` and the report's Tools line record the lane id, candidate hash and base commit.

**Tests and dry run:**
- a candidate integrates;
- a stale candidate is skipped without a step;
- a patch touching `loop/**` is rejected before start;
- a hash mismatch is rejected.

Add a dry-run variant in which one TEST-ONLY intake candidate is the single integrated step.

### 2.3 Lanes (operator work, Codex subagents)

Every lane follows these rules:
- **Workspace:** a separate worktree, such as `Content Evaluator - lane-<ITEM>`, on a local branch `lane/<ITEM>` created from the latest `loop/integration` head. Lane branches stay local; do not push them.
- **Dependencies first:** a lane may start only when every dependency of its item is DONE on that head. Never build against interfaces that do not exist yet.
- **Same rules as the builder:** follow `prompts/builder_plan.md` and `prompts/builder_build.md`, including the A2 test-oracle rules and the 1.2 fail-closed rule. Run the advisory gate from the lane worktree, with the same harness.
- **Never touch** `loop/**`, `pilot-local/`, `.tools/`, `main` or `loop/integration`.
- **One owner per candidate:** a lane's lead agent may use subagents for sub-parts, but one agent owns and assembles the candidate.
- **Concurrency:** at most 3 build lanes at once. The loop is one more Codex consumer. If Codex reports rate limits, pause the lanes first; the loop has priority, and three Codex failures in a row stop it.
- **Reservations:** before a lane starts, record its expected files in `<RUNS>/intake/RESERVATIONS.json`. Two lanes may share `persistence.py`, `pilot.py`, `pilot_domain.py` or `pilot_cli.py` only through small hunks that do not overlap. If a 3-way apply fails, STALE handles it.

**Lanes to start now** (all their dependencies are DONE):
- **Lane A: WP02,** the instrument contract and the two dependency-free instruments, using the cross-checked Sharma fixture.
- **Lane B: WP01,** witness sessions with exposure channels.
- **Lane C: L13, then L14** (small and independent).
- **Prep lane, no product code: SC01 to SC04.** Write, outside the repository in `Content Evaluator - loop-prep/SC/`:
  - the interface requirements SC needs from WP03 and WP05;
  - adversarial case matrices;
  - hand-computed expected outputs;
  - the strict schema drafts.

  When SC items run, their prompts may point to these files as data, not instructions.

**Later lanes, opened as dependencies become DONE:**
1. WP01 and WP02 → WP03 and WP04;
2. WP03 → SC01, SC02 and WP06;
3. WP03 and WP04 → WP05;
4. WP05 → SC03 and SC04;
5. last, WP08.

Do not create a lane for an item the loop is building, or has built, in the same period.

## Phase 3. Switch the loop to intake

At a step boundary, using `loop/STOP_AFTER_STEP`:
1. Merge the validated intake branch into `loop/integration`.
2. Run `loop/tests` and the full dry run.
3. Push and restart with the Phase 1 command.

From then on the loop takes ready candidates first and builds items itself only when no candidate is ready.

## Report

- **Phase 1:** commits, test counts, dry-run result, the R0 and R0P tests added, the RESUME event, the first step after the restart, and the runner PID.
- **Phase 2:** lanes started, and candidates queued or marked STALE.
- **Phase 3:** the merge commit, validation, and the first intake step.
