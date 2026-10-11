5. Step protocol (write this into loop/LOOP.md)
Phase	Who	Output
P0 Preflight	run.py	clean tree; branch synced; lock
P1 Select	loopctl next, start	step number; harness snapshot; report skeleton
P2 Plan	builder (plan call)	## Plan, or a split file
P3 Seal	loopctl seal-plan	plan hash in RUNS
P4 Probe and build	builder (build call)	probes; tests first; smallest change; self-evaluation JSON
P5 Verify	loopctl export, gate	eval view; gate_r1.json
P6 Independent evaluation	evaluator	eval_r1.json
P7 Research	loopctl research-view, researcher	research.json
P8 Report v1	loopctl report	report sections
P9 Enhance (when triggered)	enhancer	enhancement.json; plan amendments
P10 Re-verify and re-evaluate	loopctl gate, evaluator	gate_r2.json; eval_r2.json
P11 Decide	loopctl decide	decision and the rule that fired
P12 Finish	loopctl finish, run.py	commit; push; INDEX; PACKET

Landscape scan, every fifth step. Search the last 60 days for:

generative video evaluation;
human evaluation protocols for generative media;
reliability of model judges, and selective evaluation;
evaluation conditioned on intent or context;
provenance and annotation standards.

Record at most five findings in research/landscape.md, each with a relevance note.


Graceful stop: create loop/STOP_AFTER_STEP to finish the active step and stop at the next boundary. It never interrupts a role. Remove it before an authorized restart. loop/STOP remains the immediate stop.

R0P rollback boundary: initial R0 -> preserve pre-revert evidence -> revert -> verify frozen G5/G6/G14 and clean exact base -> R0P only if proven. Otherwise stop under R0. This does not establish absence of side effects outside checked paths.

For the authorized application path, use --critical-path L12,L16,L15. Split children stay within that path; blocked prerequisites stop rather than selecting unrelated work. Completion stops at a step boundary before any WP item.

Harness scaling fix (2026-10-10): role attachments use deterministic 16 KiB per-attachment and 64 KiB combined soft caps. All G-check IDs, statuses, blocking flags and details; evaluator blocking/unresolved findings; action-required research; and every prior-attempt blocking finding are retained verbatim. Passed per-test records become a count. Failed/error IDs are sorted, sampled at 50, and accompanied by their total and full evidence path. Optional narrative yields to mandatory content. Over-cap mandatory content is included and measured in step.json attachment_compaction/advisory_compaction. Full source files and their hashes/sizes remain available. This is transport only; decisions still consume complete evidence.

Advisory CLI output now contains the compact gate summary and full_result_path. Every invocation writes a separate full RUNS/STEP/advisory/gate_rR-attempt-NNN.json and summary sidecar. No authoritative gate file is written or replaced. Builder/enhancer receive additional write access only to that advisory subfolder. Existing authoritative gate/decision interfaces remain unchanged.
