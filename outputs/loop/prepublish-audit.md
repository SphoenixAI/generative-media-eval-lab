# Pre-publication audit: 2026-10-08

Scope: Phase A, through H1 only. No publication is authorized by this report.

## Pre-A1 safety scan

PASS. Before the first commit, all 81 candidate files were checked for credential signatures and assignments, credential-bearing filenames, binary content, files over 5 MB, private material and sensitive prose. Every staged blob was then compared with that scan's SHA-256 inventory. No candidate failed. See [scan inventory](pre-a1-safety.json).

The private workspace was excluded as a whole and was neither opened nor modified. Local environments, caches, package metadata, third-party tools and the supplied instruction attachments were excluded from Git. The instruction attachments contain private delivery context and must remain outside reachable history. No pre-existing Git history was present.

## A2 formal audit

No credentials, secret values, private real media, private notes, or employer/application strategy were found in the tracked content. References to published vendor research and generic software application architecture are not employer strategy. Test-only PRIVATE_SENTINEL text and synthetic fixture identities are deliberate boundary checks, not private observations.

The .gitignore excludes the private workspace, .tools, .venv, caches, .env variants, private key extensions, loop/runs, loop/STOP and raw media; declared test-media paths have explicit exceptions. No raw media is currently tracked. A repository-local GitHub noreply address is used for new commits.

No tracked file exceeds 5 MB. The largest baseline file is uv.lock at 79,349 bytes. No third-party binary is tracked. The excluded ffmpeg and ffprobe executables are 52,070,376 and 51,878,936 bytes respectively; they remain local. The installer contains download URLs and published checksums, not bundled executables.

## Absolute local paths

The operator guide's checkout command was changed to a repository-relative example. No user home path remains in the current README or docs. Historical outputs contain one local checkout path in each of outputs/approval.json:90 and outputs/pilot0/approval.json:90, both dependency-warning logs. They reveal a local username/project folder, not a credential or private media location, and are not treated as publication blockers. Those protected files remain byte-for-byte unchanged. The baseline commit retains the former operator-guide checkout path; this historical path is also reported, not rewritten. Tool-version metadata in the historical Pilot 0 toolchain/readiness reports also contains the third-party build prefix /Volumes/tempdisk/sw. That is publisher build metadata, not a local private-data path; it remains unchanged. Generic /absolute/path examples are placeholders.

## Licensing and public documentation

No project license has been selected or added. Options for the owner include MIT, Apache-2.0, GPL-3.0, or no license for now. This is a pending owner decision. Third-party dependencies and locally installed tools retain their own licenses; no third-party source distribution or binary is being republished here. Research documents contain attributed links and bounded source excerpts. No media assets are included.

The front-door README was revised and independently evaluated twice in A4. Both rounds returned 4/4 in all six dimensions with no blocking findings. The reviewers inspected saved execution records and behavioral assertions; the orchestrating process ran the test suite. See [evaluation manifest](front-door-evaluation-manifest.json). Older checkpoint documents describe their dated states; they are not current live-service or scientific-result claims. Historical approval and Pilot 0 outputs are protected.

## Reachable history and H1

**PUBLICATION SAFETY: CLEAR.** No publication-blocking sensitive content was found. The [reachable-history scan](history-safety.json) inspected every tree/blob and commit metadata through the final content commit: three commits and 93 unique blobs. It found no credentials, private notes, private media, Pilot data, .env contents, binary payloads or sensitive strategy. Seven keyword matches were generic audit/evaluator criteria and were manually cleared. Historical home paths are listed above and in the scan. Subsequent audit-bookkeeping content is checked before push and the complete resulting history is rescanned before H1.

[Deterministic README checks](front-door-checks.json) passed. [Current test evidence](front-door-validation.json) records 209 passed, zero failed/errors/skipped, seven gates and four caught mutations. All 41 previously recorded source/test/schema/contract/output files remain byte-for-byte unchanged. No project license was added. No public visibility change is permitted before an explicit owner publication instruction.

These checks are a bounded publication review, not proof that every possible secret pattern can be recognized. No private workspace content was read or modified. No A6 runner, loop worktree, schedule or new product feature was created.
