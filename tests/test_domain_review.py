"""Independent regression probes for admission, evidence and ontology boundaries.

These exercise authored records, never perception or real participant agreement.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError

from eval_lab.domain import (
    Criterion, Dimension, DimensionScore, EvaluationCase, EvaluationDimension,
    EvaluationRound, Evidence, HumanRater, HumanRating, Hypothesis,
    HypothesisGraph, IntentSpec, MediaAsset, ModelRun, PairwiseRating, PromptSpec,
    RelationClaim, Rubric,
)
from eval_lab.persistence import Repository
from eval_lab.presentation import assigned_runs, serialize_case
from eval_lab.rubrics import initial_rubric
from eval_lab.scoring import evaluate


NOW = datetime(2026, 10, 6, tzinfo=timezone.utc)


def seed_review(repo):
    rubric = initial_rubric()
    intent = IntentSpec(
        id="boundary-intent", created_at=NOW, owner="creator", objective="A red dog walks",
        audience="production reviewer", context="realistic shot", authority="human_declared",
        approved_by="creator", criteria=(Criterion(dimension=Dimension.PROMPT,
            rationale="Required action", acceptance="The requested dog walks"),),
    )
    prompt = PromptSpec(id="boundary-prompt", created_at=NOW, original_prompt="A red dog walks",
        normalized_prompt="red dog; walks", intent=intent.ref)
    for item in (rubric, intent, prompt):
        repo.put(item)
    assets, runs, evidence = [], [], []
    for n in range(2):
        asset = MediaAsset(id=f"boundary-asset-{n}", created_at=NOW, type="video",
            storage_reference=f"fixture://review-{n}", checksum=str(n) * 64,
            duration=2, fps=24, width=256, height=256, provenance="synthetic_fixture")
        run = ModelRun(id=f"boundary-run-{n}", created_at=NOW, model_name="fixture",
            model_version=str(n), provider="mock", prompt=prompt.ref, media=asset.ref,
            generated_at=NOW, lineage_group="review-author")
        ev = Evidence(id=f"boundary-evidence-{n}", created_at=NOW, media=asset.ref,
            observation="Authored walk assertion", source="synthetic_fixture", method="fixture",
            coverage="interval", timestamp_start=0, timestamp_end=2,
            author="review-author", independence_group="review-author")
        for item in (asset, run, ev):
            repo.put(item)
        assets.append(asset)
        runs.append(run)
        evidence.append(ev)
    rater = HumanRater(id="boundary-rater", created_at=NOW,
        anonymous_id="review-person", calibration_state="uncalibrated")
    rnd = EvaluationRound(id="boundary-round", created_at=NOW,
        candidate_model_runs=tuple(run.ref for run in runs), rubric=rubric.ref,
        assignment_seed="private-review-assignment")
    case = EvaluationCase(id="boundary-case", created_at=NOW, title="Reveal only after voting",
        description="Authored fixture", model_runs=rnd.candidate_model_runs, intent=intent.ref,
        rubric=rubric.ref, public_visibility="curated", project_case_slug="boundary-case")
    for item in (rater, rnd, case):
        repo.put(item)
    return SimpleNamespace(repo=repo, rubric=rubric, intent=intent, prompt=prompt,
        assets=assets, runs=runs, evidence=evidence, rater=rater, round=rnd, case=case)


@pytest.fixture
def lab():
    repo = Repository()
    try:
        yield seed_review(repo)
    finally:
        repo.close()


def rating(lab, id="boundary-rating", **changes):
    score = DimensionScore(dimension=Dimension.PROMPT, status="scored", score=4,
        confidence=0.5, evidence=(lab.evidence[0].ref,), rationale="Synthetic observed assertion")
    result = HumanRating(id=id, created_at=NOW, rater=lab.rater.ref,
        model_run=lab.runs[0].ref, rubric=lab.rubric.ref, round=lab.round.ref,
        dimension_scores=(score,))
    # This intentionally exercises the persistence revalidation boundary as well.
    return result.model_copy(update=changes)


def pairwise(lab, id="boundary-pair", **changes):
    result = PairwiseRating(id=id, created_at=NOW, rater=lab.rater.ref,
        round=lab.round.ref, choice="tie", rationale="No preference under stated objective",
        ordered_runs=assigned_runs(lab.round, lab.rater.ref))
    return result.model_copy(update=changes)


def hypothesis(lab):
    return Hypothesis(id="boundary-hypothesis", created_at=NOW, intent=lab.intent.ref,
        observed_problem="Apparent sliding", proposed_cause="Camera-relative illusion",
        supporting_evidence=(lab.evidence[0].ref,), evidence_required=("Stable reference",),
        discriminating_test="Compare contact to reference", predicted_observation="Stable contact",
        falsifying_observation="Motion against the stationary ground")


def relation(lab, target):
    return RelationClaim(id="boundary-relation", created_at=NOW,
        subject=lab.evidence[0].ref, predicate="supports", object=target.ref,
        intent=lab.intent.ref, epistemic_status="asserted", evidence=(lab.evidence[0].ref,),
        asserted_by="reviewer", purpose="Distinguish apparent from actual sliding",
        scope="this declared realistic shot", valid_from=NOW)


@pytest.mark.parametrize("field", ["rater", "model_run", "rubric", "round"])
def test_existing_wrong_kind_cannot_become_a_rating_reference(lab, field):
    with pytest.raises(ValueError):
        lab.repo.put(rating(lab, **{field: lab.assets[0].ref}))
    assert not lab.repo.all("HumanRating")


def test_prompt_cannot_use_existing_media_as_its_intent(lab):
    with pytest.raises(ValueError):
        lab.repo.put(lab.prompt.model_copy(update={"id": "wrong-intent", "intent": lab.assets[0].ref}))


@pytest.mark.parametrize("field", ["supporting_evidence", "contradicting_evidence"])
def test_hypothesis_evidence_cannot_point_at_a_rubric(lab, field):
    with pytest.raises(ValueError):
        lab.repo.put(hypothesis(lab).model_copy(update={field: (lab.rubric.ref,)}))


def test_relation_evidence_cannot_point_at_a_rubric(lab):
    target = hypothesis(lab)
    lab.repo.put(target)
    with pytest.raises(ValueError):
        lab.repo.put(relation(lab, target).model_copy(update={"evidence": (lab.rubric.ref,)}))


@pytest.mark.parametrize("factory", [rating, pairwise], ids=["dimensions", "pairwise"])
def test_historical_open_round_cannot_admit_after_current_round_closed(lab, factory):
    lab.repo.put(lab.round.model_copy(update={"revision": 2, "status": "closed"}))
    with pytest.raises(ValueError):
        lab.repo.put(factory(lab))


@pytest.mark.parametrize("factory", [rating, pairwise], ids=["dimensions", "pairwise"])
def test_rater_calibration_revision_does_not_create_another_person(lab, factory):
    original = factory(lab)
    lab.repo.put(original)
    revised_rater = lab.rater.model_copy(update={"revision": 2, "calibration_state": "calibrated"})
    lab.repo.put(revised_rater)
    with pytest.raises((ValueError, IntegrityError)):
        lab.repo.put(factory(lab, id="duplicate-calibration", rater=revised_rater.ref))
    assert len(lab.repo.all(type(original).__name__)) == 1


@pytest.mark.parametrize("factory", [rating, pairwise], ids=["dimensions", "pairwise"])
def test_round_revision_does_not_create_another_voting_opportunity(lab, factory):
    original = factory(lab)
    lab.repo.put(original)
    revised_round = lab.round.model_copy(update={"revision": 2})
    lab.repo.put(revised_round)
    with pytest.raises((ValueError, IntegrityError)):
        lab.repo.put(factory(lab, id="duplicate-round-revision", round=revised_round.ref))
    assert len(lab.repo.all(type(original).__name__)) == 1


@pytest.mark.parametrize("factory", [rating, pairwise], ids=["dimensions", "pairwise"])
def test_submitted_ratings_cannot_be_revised_into_extra_observations(lab, factory):
    original = factory(lab)
    digest = lab.repo.put(original)
    assert lab.repo.put(original) == digest  # exact replay is idempotent
    with pytest.raises(ValueError):
        lab.repo.put(original.model_copy(update={"revision": 2}))
    assert len(lab.repo.all(type(original).__name__)) == 1


def test_assignment_is_stable_across_nonsemantic_rater_and_round_revisions(lab):
    expected = assigned_runs(lab.round, lab.rater.ref)
    for revision in range(2, 18):
        rnd = lab.round.model_copy(update={"revision": revision})
        rater_ref = lab.rater.ref.model_copy(update={"revision": revision})
        assert assigned_runs(rnd, rater_ref) == expected


def test_prior_reveal_is_not_reset_by_rater_or_round_revision(lab):
    lab.repo.put(pairwise(lab))
    revised_rater = lab.rater.model_copy(update={"revision": 2, "calibration_state": "calibrated"})
    revised_round = lab.round.model_copy(update={"revision": 2})
    lab.repo.put(revised_rater)
    lab.repo.put(revised_round)
    payload = serialize_case(lab.repo, lab.case.ref, revised_round.ref, revised_rater.ref)
    assert payload["stage"] == "revealed"
    assert payload["your_evaluation"]["choice"] == "tie"


def test_foreign_clip_evidence_cannot_support_a_dimension_rating(lab):
    original = rating(lab)
    foreign = original.dimension_scores[0].model_copy(update={"evidence": (lab.evidence[1].ref,)})
    with pytest.raises(ValueError):
        lab.repo.put(original.model_copy(update={"dimension_scores": (foreign,)}))


@pytest.mark.parametrize("hard_fail,regenerate", [(None, 0), (0, 2), (1, 2)])
def test_regeneration_threshold_cannot_silently_exceed_failure_threshold(hard_fail, regenerate):
    with pytest.raises(ValueError):
        EvaluationDimension(dimension=Dimension.GEOMETRY, description="Spatial continuity",
            family="temporal_physical", anchors=("0", "1", "2", "3", "4"),
            hard_fail_at_or_below=hard_fail, regenerate_at_or_below=regenerate,
            boundary_note="Repair policy is a named decision rule")


def test_valid_regeneration_threshold_controls_the_recommendation(lab):
    definition = EvaluationDimension(dimension=Dimension.GEOMETRY, description="Spatial continuity",
        family="temporal_physical", anchors=("0", "1", "2", "3", "4"),
        hard_fail_at_or_below=2, regenerate_at_or_below=1,
        boundary_note="A production policy, not proof that every repair is impossible")
    rubric = Rubric(id="regeneration-policy", created_at=NOW, version="1",
        dimensions=(definition,), rationale="Explicit threshold ordering")
    intent = lab.intent.model_copy(update={"criteria": (Criterion(dimension=Dimension.GEOMETRY,
        rationale="Realistic continuous geometry", acceptance="Stable scene geometry"),)})
    for value, recommendation in ((2, "HUMAN_REVIEW"), (1, "REGENERATE"), (0, "REGENERATE")):
        score = DimensionScore(dimension=Dimension.GEOMETRY, status="scored", score=value,
            confidence=0.5, evidence=(lab.evidence[0].ref,), rationale="Synthetic threshold boundary")
        verdict = evaluate((score,), rubric, intent)
        assert verdict.status == "FAILED"
        assert verdict.recommendation == recommendation


def graph(lab, target, edge):
    return HypothesisGraph(id="boundary-graph", created_at=NOW, intent=lab.intent.ref,
        root_observation="Apparent sliding", nodes=(lab.evidence[0].ref, target.ref),
        edges=(edge,), unresolved_questions=("Need a world-fixed reference",))


def test_graph_requires_persisted_edge_evidence_record(lab):
    target = hypothesis(lab)
    lab.repo.put(target)
    edge = relation(lab, target)
    with pytest.raises((KeyError, ValueError)):
        lab.repo.put(graph(lab, target, edge))


def test_graph_cannot_rewrite_a_persisted_relation_at_the_same_revision(lab):
    target = hypothesis(lab)
    lab.repo.put(target)
    edge = relation(lab, target)
    lab.repo.put(edge)
    forged = edge.model_copy(update={"purpose": "Invent a different reason using the same identity"})
    with pytest.raises(ValueError):
        lab.repo.put(graph(lab, target, forged))
    assert lab.repo.get(edge.ref).digest == edge.digest


def test_matching_relation_snapshot_round_trips_in_graph(lab):
    target = hypothesis(lab)
    lab.repo.put(target)
    edge = relation(lab, target)
    lab.repo.put(edge)
    original = graph(lab, target, edge)
    lab.repo.put(original)
    restored = lab.repo.get(original.ref)
    assert restored.edges[0].digest == lab.repo.get(edge.ref).digest


def test_relation_cannot_relabel_another_hypothesis_intent(lab):
    other_intent = lab.intent.model_copy(update={"id": "other-intent", "objective": "Deliberate impossible motion"})
    lab.repo.put(other_intent)
    target = hypothesis(lab).model_copy(update={"intent": other_intent.ref, "supporting_evidence": ()})
    lab.repo.put(target)
    with pytest.raises(ValueError):
        lab.repo.put(relation(lab, target))


def test_hypothesis_cannot_reuse_evidence_from_a_different_declared_intent(lab):
    other_intent = lab.intent.model_copy(update={"id": "other-intent", "objective": "Deliberate impossible motion"})
    lab.repo.put(other_intent)
    with pytest.raises(ValueError):
        lab.repo.put(hypothesis(lab).model_copy(update={"intent": other_intent.ref}))


def test_concurrent_duplicate_submissions_commit_at_most_one_observation(tmp_path, monkeypatch):
    # Force both admission checks to finish before either insert, reproducing the
    # precise race that a read-then-write duplicate scan cannot protect against.
    url = "sqlite:///" + str(tmp_path / "admission.sqlite")
    owner = Repository(url)
    lab = seed_review(owner)
    peers = (Repository(url), Repository(url))
    gate = Barrier(2, timeout=5)
    validate = Repository._validate_links

    def synchronized_validation(self, item):
        result = validate(self, item)
        if isinstance(item, HumanRating) and item.id.startswith("race-"):
            gate.wait()
        return result

    monkeypatch.setattr(Repository, "_validate_links", synchronized_validation)

    def submit(n):
        try:
            peers[n].put(rating(lab, id=f"race-{n}"))
            return "accepted"
        except (ValueError, IntegrityError):
            return "rejected"

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(submit, range(2)))
        assert sorted(outcomes) == ["accepted", "rejected"]
        committed = owner.all("HumanRating")
        assert len(committed) == 1
        assert committed[0].rater.id == lab.rater.id
    finally:
        for repo in (*peers, owner):
            repo.close()


def test_round_closure_between_validation_and_insert_prevents_new_admission(lab, monkeypatch):
    validate = Repository._validate_links

    def close_after_validation(self, item):
        result = validate(self, item)
        if isinstance(item, HumanRating):
            self.put(lab.round.model_copy(update={"revision": 2, "status": "closed"}))
        return result

    monkeypatch.setattr(Repository, "_validate_links", close_after_validation)
    with pytest.raises(ValueError):
        lab.repo.put(rating(lab))
    assert not lab.repo.all("HumanRating")
    assert lab.repo.latest(lab.round.ref).status == "closed"
