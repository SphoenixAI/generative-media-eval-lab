# Scoring and decision policy

The 0–4 scale encodes ordered behavioral anchors: catastrophic, severe, material, minor, pass. It does not assert equal distances between categories. Do not report “18% quality improvement” from an ordinal mean. Aesthetic preference and instruction failure remain separate.

Each scored dimension requires evidence, a score, a rationale and confidence labeled `self_reported_uncalibrated`. Abstention carries no score. `not_applicable` follows the declared intent; the evaluator cannot remove a difficult requirement. Missing required scores yield `UNKNOWN`, except an already observed critical failure remains `FAILED` with missing dimensions still listed.

The provisional v0.1 policy fails prompt adherence at 0–1, subject consistency at 0, and temporal geometry at 0. Geometry 0 additionally suggests regeneration. These are lab policy choices based on the brief, not universal industry cutoffs. A regeneration threshold must also fall inside its hard-fail threshold. Required noncritical scores 0–2 trigger human review. All required scores 3–4 can yield a provisional pass only for human-declared intent. No required applicable criteria yields unknown, not a vacuous pass.

The local simulator can assign scores because its evidence and rule outputs were authored together. It does not prove that the evidence is visible in actual media or that the threshold is suitable for a real production. VFX recommendations require later human-qualified repair outcomes. See [rubric design](rubric-design.md) and [validation](evaluator-validation.md).
