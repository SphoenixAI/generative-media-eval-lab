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

