"""Agreement on ordinal categories; no pooled dimensions or synthetic probabilities."""
from collections import Counter
from itertools import combinations
from math import isfinite
from typing import Literal
from .domain import Dimension, HumanRating, Value


class AgreementResult(Value):
    metric: str
    value: float | None
    reason: str | None = None
    units_used: int
    units_excluded: int
    ratings_used: int
    pairs_used: int
    uncertainty: Literal["not_estimated"] = "not_estimated"


def _units(data: list[list[int | None]]) -> tuple[list[list[int]], int]:
    cleaned = []
    for unit in data:
        for x in unit:
            if x is not None and (type(x) is not int or not 0 <= x <= 4):
                raise ValueError("ratings must be integer 0-4 or None")
        cleaned.append([x for x in unit if x is not None])
    usable = [u for u in cleaned if len(u) >= 2]
    return usable, len(cleaned) - len(usable)


def percent_agreement(data: list[list[int | None]]) -> AgreementResult:
    units, excluded = _units(data)
    pairs = [p for u in units for p in combinations(u, 2)]
    return AgreementResult(metric="pair_weighted_exact_agreement", value=sum(a == b for a,b in pairs)/len(pairs) if pairs else None,
        reason=None if pairs else "no_pairable_units", units_used=len(units), units_excluded=excluded,
        ratings_used=sum(map(len, units)), pairs_used=len(pairs))


def krippendorff_alpha(data: list[list[int | None]], level: Literal["ordinal", "nominal", "interval"] = "ordinal") -> AgreementResult:
    """Rows are units, columns raters. Ordinal uses pooled-marginal distance.

    Single-rating units contribute neither coincidences nor expected marginals.
    Undefined De=0 is None even when observed labels are unanimous.
    """
    if level not in ("ordinal", "nominal", "interval"):
        raise ValueError("unsupported alpha level")
    units, excluded = _units(data)
    counts = Counter(x for u in units for x in u)
    n = sum(counts.values())
    pairs = sum(len(u)*(len(u)-1)//2 for u in units)
    base = dict(metric=f"krippendorff_alpha_{level}", units_used=len(units), units_excluded=excluded, ratings_used=n, pairs_used=pairs)
    if n < 2:
        return AgreementResult(value=None, reason="no_pairable_units", **base)

    def distance(a: int, b: int) -> float:
        if a == b:
            return 0.
        if level == "nominal":
            return 1.
        if level == "interval":
            return float((a-b)**2)
        low, high = sorted((a,b))
        return float((sum(counts[c] for c in counts if low <= c <= high) - (counts[low]+counts[high])/2)**2)

    observed = sum(sum(distance(a,b) for i,a in enumerate(u) for j,b in enumerate(u) if i != j)/(len(u)-1) for u in units)/n
    expected = sum(counts[a]*counts[b]*distance(a,b) for a in counts for b in counts if a != b)/(n*(n-1))
    if expected == 0:
        return AgreementResult(value=None, reason="zero_expected_disagreement", **base)
    value = 1 - observed/expected
    if not isfinite(value):
        raise ValueError("nonfinite agreement result")
    return AgreementResult(value=value, **base)


def cohens_kappa(pairs: list[tuple[int | None, int | None]], weighting: Literal["nominal", "quadratic"] = "nominal") -> AgreementResult:
    if weighting not in ("nominal", "quadratic"):
        raise ValueError("unsupported weighting")
    if any(len(p) != 2 for p in pairs):
        raise ValueError("Cohen's kappa requires exactly two raters")
    units, excluded = _units([list(p) for p in pairs])
    n = len(units)
    base = dict(metric=f"cohens_kappa_{weighting}", units_used=n, units_excluded=excluded, ratings_used=2*n, pairs_used=n)
    if not n:
        return AgreementResult(value=None, reason="no_pairable_units", **base)
    left, right = Counter(u[0] for u in units), Counter(u[1] for u in units)
    dist = (lambda a,b: float(a != b)) if weighting == "nominal" else (lambda a,b: (a-b)**2/16)
    observed = sum(dist(a,b) for a,b in units)/n
    expected = sum(left[a]*right[b]*dist(a,b) for a in left for b in right)/(n*n)
    return AgreementResult(value=1-observed/expected if expected else None, reason=None if expected else "zero_expected_disagreement", **base)


def rating_matrix(ratings: tuple[HumanRating, ...], dimension: Dimension) -> list[list[int | None]]:
    if not ratings:
        return []
    if len({r.rubric for r in ratings}) != 1 or len({r.round for r in ratings}) != 1:
        raise ValueError("do not pool rubric versions or rounds")
    raters = sorted({r.rater.id for r in ratings})
    units = sorted({r.model_run for r in ratings}, key=lambda r: (r.id, r.revision))
    cells = {}
    for rating in ratings:
        key = (rating.model_run, rating.rater.id)
        if key in cells:
            raise ValueError("duplicate rater/unit")
        selected = next((s for s in rating.dimension_scores if s.dimension == dimension), None)
        cells[key] = selected.score if selected and selected.status == "scored" else None
    return [[cells.get((unit, rater)) for rater in raters] for unit in units]
