from itertools import groupby
from .domain import AgentAssessment, Dimension, Disagreement, HumanRating


def disagreements(humans: tuple[HumanRating, ...], agents: tuple[AgentAssessment, ...], *, created_at, severe_gap: int = 2) -> tuple[Disagreement, ...]:
    if not 1 <= severe_gap <= 4:
        raise ValueError("invalid disagreement gap")
    records = [(h.model_run, h.rubric, s.dimension, s, h.ref) for h in humans for s in h.dimension_scores]
    records += [(a.model_run, a.rubric, a.result.dimension, a.result, a.ref) for a in agents]
    keys = {(r, rubric, d) for r,rubric,d,_,_ in records}
    out = []
    for run, rubric, dimension in sorted(keys, key=lambda k: (k[0].id, k[1].id, k[1].revision, k[2])):
        group = [(s,ref) for r,v,d,s,ref in records if (r,v,d) == (run,rubric,dimension)]
        scores = tuple(s.score for s,_ in group if s.status == "scored")
        abstention = any(s.status == "abstain" for s,_ in group)
        if len(set(scores)) < 2 and not abstention:
            continue
        gap = max(scores)-min(scores) if len(scores) >= 2 else 0
        types = ["insufficient_evidence"] if abstention else []
        types += ["subjective_preference"] if dimension in (Dimension.AESTHETIC, Dimension.COMPOSITION) else ["ambiguous_generation", "calibration_issue"]
        out.append(Disagreement(id=f"disagreement-{run.id}-{rubric.id}-{rubric.revision}-{dimension}", created_at=created_at,
            model_run=run, dimension=dimension, assessment_refs=tuple(ref for _,ref in group), observed_scores=scores,
            proposed_types=tuple(types), adjudication_required=gap >= severe_gap or abstention,
            reason=f"Observed ordinal span {gap}; proposed categories require human review. Agreement is not independent correctness."))
    return tuple(out)
