import random
import numpy as np
import pytest
import krippendorff
from eval_lab.agreement import krippendorff_alpha, cohens_kappa, percent_agreement, rating_matrix

# Krippendorff's original computing note, p4. Values shifted 1..5 -> 0..4.
# https://www.asc.upenn.edu/sites/default/files/2021-03/Computing%20Krippendorff%27s%20Alpha-Reliability.pdf
RATERS = [
    [1,2,3,3,2,1,4,1,2,None,None,None],
    [1,2,3,3,2,2,4,1,2,5,None,3],
    [None,3,3,3,2,3,4,2,2,5,1,None],
    [1,2,3,3,2,4,4,1,2,5,1,None],
]
UNITS = [[x-1 if x is not None else None for x in u] for u in zip(*RATERS)]


@pytest.mark.parametrize("level,expected", [("nominal",.743), ("ordinal",.815), ("interval",.849)])
def test_original_published_alpha_oracle(level,expected):
    result=krippendorff_alpha(UNITS,level)
    assert result.value == pytest.approx(expected,abs=.0005)
    assert result.ratings_used == 40
    assert result.units_excluded == 1


@pytest.mark.parametrize("level", ["ordinal","nominal","interval"])
def test_alpha_against_independent_library_with_missingness(level):
    rng=random.Random(47)
    for _ in range(30):
        matrix=[[rng.choice([None,0,1,2,3,4]) for _ in range(4)] for _ in range(15)]
        oracle=np.array([[np.nan if x is None else x for x in row] for row in matrix],dtype=float).T
        expected=krippendorff.alpha(reliability_data=oracle,level_of_measurement=level,value_domain=np.arange(5))
        assert krippendorff_alpha(matrix,level).value == pytest.approx(expected,abs=1e-12)


@pytest.mark.parametrize("data,reason", [([],"no_pairable_units"),([[1,None]],"no_pairable_units"),([[4,4],[4,4]],"zero_expected_disagreement")])
def test_alpha_undefined_is_not_perfect_agreement(data,reason):
    result=krippendorff_alpha(data)
    assert result.value is None and result.reason==reason


@pytest.mark.parametrize("bad", [True,False,1.0,-1,5,"3",float("nan")])
def test_invalid_scores_rejected(bad):
    with pytest.raises(ValueError):
        krippendorff_alpha([[bad,1]])


def test_exact_agreement_and_kappa_hand_computed():
    pairs=[(0,0),(0,1),(1,1),(1,0)]
    assert percent_agreement([list(p) for p in pairs]).value == .5
    assert cohens_kappa(pairs).value == 0
    assert cohens_kappa([(0,0),(4,4)]).value == 1
    assert cohens_kappa([(0,4),(4,0)],"quadratic").value == -1
    assert cohens_kappa([(4,4)]).value is None


def test_alpha_invariant_to_rater_and_unit_order():
    assert krippendorff_alpha(UNITS).value == pytest.approx(krippendorff_alpha([list(reversed(u)) for u in reversed(UNITS)]).value)
