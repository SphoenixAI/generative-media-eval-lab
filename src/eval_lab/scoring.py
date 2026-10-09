from typing import Literal
from .domain import Dimension, DimensionScore, IntentSpec, Rubric, Value


class Verdict(Value):
    status: Literal["PASS", "REVIEW", "FAILED", "UNKNOWN"]
    recommendation: Literal["REGENERATE", "HUMAN_REVIEW", "NONE"]
    critical_dimensions: tuple[Dimension, ...]
    missing_dimensions: tuple[Dimension, ...]
    explanation: str


def evaluate(scores: tuple[DimensionScore, ...], rubric: Rubric, intent: IntentSpec) -> Verdict:
    if len({s.dimension for s in scores}) != len(scores):
        raise ValueError("duplicate scores")
    defs = {d.dimension: d for d in rubric.dimensions}
    criteria = {c.dimension: c for c in intent.criteria}
    if set(criteria) - set(defs) or {s.dimension for s in scores} - set(criteria):
        raise ValueError("scores/intent outside rubric")
    supplied = {s.dimension: s for s in scores}
    missing, critical, regenerate, review = [], [], False, False
    for dimension, c in criteria.items():
        s = supplied.get(dimension)
        if c.applicability == "not_applicable":
            if s is not None and s.status != "not_applicable":
                raise ValueError("cannot score an inapplicable criterion")
            continue
        if s is not None and s.status == "not_applicable":
            raise ValueError("only declared intent can exclude a criterion")
        if s is None or s.status == "abstain":
            if c.applicability == "required":
                missing.append(dimension)
            continue
        rule = defs[dimension]
        if rule.hard_fail_at_or_below is not None and s.score <= rule.hard_fail_at_or_below:
            critical.append(dimension)
        if rule.regenerate_at_or_below is not None and s.score <= rule.regenerate_at_or_below:
            regenerate = True
        review |= s.score <= 2
    if critical:
        return Verdict(status="FAILED", recommendation="REGENERATE" if regenerate else "HUMAN_REVIEW",
            critical_dimensions=tuple(critical), missing_dimensions=tuple(missing), explanation="Critical failure veto; aesthetics cannot cancel it. Unscored dimensions remain unknown.")
    if missing or intent.authority != "human_declared" or not any(c.applicability == "required" for c in intent.criteria):
        return Verdict(status="UNKNOWN", recommendation="HUMAN_REVIEW", critical_dimensions=(), missing_dimensions=tuple(missing), explanation="Required evidence or approved applicable intent is missing.")
    return Verdict(status="REVIEW" if review else "PASS", recommendation="HUMAN_REVIEW" if review else "NONE",
        critical_dimensions=(), missing_dimensions=(), explanation="Dimension-level provisional rubric result; not a production release approval.")
