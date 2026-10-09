# Provisional rubric design

`initial_rubric()` in `src/eval_lab/rubrics.py` creates rubric version **0.1.0**. Its anchors are authored starting hypotheses, not a validated industry standard. Human calibration and real positive, negative and boundary examples are required before claims about reliable media-quality measurement.

## Dimensions and boundaries

The instruction family covers prompt adherence, subject consistency and semantic consistency. These distinguish satisfying explicit requirements, preserving the intended subject/state, and maintaining scene meaning.

The temporal/physical family covers temporal consistency, temporal geometry, motion plausibility, occlusion consistency and lighting continuity. A poor camera move alone does not establish a world-physics failure. Motion and occlusion claims require evidence covering the relevant transition; a sampled frame can miss the failure.

The craft family covers camera language, composition, artifacting, aesthetic quality and editability. Composition and aesthetics depend on declared audience and purpose. Editability means preserving the required shot within production constraints; the current score is provisional triage rather than a verified cost estimate.

Dimensions can overlap. The lab keeps the overlap visible and avoids a composite average that would count one failure several times or allow attractive images to cancel a catastrophic semantic error. Separability remains an empirical question: real examples must demonstrate the distinct information each dimension adds.

## Ordinal anchors

Each dimension has five behaviorally described anchors, ordered from 0 to 4:

- **0 — catastrophic:** the dimension fundamentally fails.
- **1 — severe:** a major failure defeats a substantial part of the intended result.
- **2 — material:** a consequential local or partial failure affects interpretation or use.
- **3 — minor:** a small deviation preserves the main intended result.
- **4 — pass:** no material failure within the assessed scope.

The dimension-specific text is authoritative for interpreting an individual score. Equal numerical steps do not assert equal increments of quality. Score 4 reflects available observations, not proof that an unobserved interval is defect-free. Missing evidence is an abstention, never a favorable score.

## Current decision policy

Initial hard-failure thresholds are prompt adherence at 1 or below, subject consistency at 0, and temporal geometry at 0. The geometry rule additionally recommends regeneration at 0. Other dimensions have no hard-failure threshold in the initial rubric. These are explicit provisional project policies.

The evaluator returns `FAILED` when an applicable hard-failure rule fires, while retaining any missing required dimensions. Without a hard failure, missing required judgments, only proposed intent, or the absence of any required criterion produces `UNKNOWN`. Otherwise a score of 2 or below produces `REVIEW`; remaining complete results produce `PASS`. A pass is a provisional rubric verdict and does not authorize production release.

A regeneration threshold must also trigger the hard-failure rule; invalid threshold ordering is rejected. Regeneration is a policy recommendation, not proof that repair is physically impossible or economically unreasonable under every production context.

## Intent controls applicability

An intent criterion can be required, optional or not applicable. Required omissions remain unknown. Optional omissions do not block completeness, but a scored optional dimension still participates in the stated failure/review policy. A declared non-applicable criterion cannot be assigned a normal score, and a judge cannot independently exclude a criterion the intent says applies.

A surreal brief may explicitly make ordinary-world geometry irrelevant; this does not waive subject identity, prompt fidelity or other requirements automatically. Applicability is configured, not inferred from the model's aesthetic preference. Current human approval fields are trusted fixture metadata, without authentication or production approval authority.

## Change control and later validation

Persist a new rubric revision for anchor or policy changes and pin evaluations to exact versions. `EvaluatorVersion` includes the rubric digest; the repository checks the match. Old assessments remain interpretable under their original instrument.

Before promoting new anchors, independently rate examples that isolate unique failures and ambiguous boundaries. Investigate disagreement, assess critical false negatives and test rubric paraphrases. Preserve irreducible preference differences instead of forcing a fabricated gold label. Gold-set management, rubric-change adjudication and statistical regression analysis are later phases and remain unimplemented here.
