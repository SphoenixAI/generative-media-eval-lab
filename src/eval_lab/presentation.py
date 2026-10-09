"""Allowlist-only presentation contracts. Authentication/hosting are later phases.

The caller must be a trusted application service binding authenticated/anonymous
session identity to rater_ref. Never accept a public caller's arbitrary rater ID.
"""
import hashlib
import hmac
from typing import Literal
from .domain import EvaluationCase, EvaluationRound, PairwiseRating, Ref
from .persistence import Repository


def _token(round: EvaluationRound, value: str) -> str:
    return hmac.new(round.assignment_seed.encode(), value.encode(), hashlib.sha256).hexdigest()


def assigned_runs(round: EvaluationRound, rater: Ref) -> tuple[Ref, Ref]:
    if len(round.candidate_model_runs) != 2:
        raise ValueError("A/B assignment requires exactly two outputs")
    identity = rater.id
    ordered = sorted(round.candidate_model_runs, key=lambda r: _token(round, identity+r.model_dump_json()))
    return tuple(ordered)


def submit_pairwise(repo: Repository, round_ref: Ref, rater_ref: Ref, choice: Literal["A", "B", "tie", "cannot_determine"], rationale: str, *, created_at) -> PairwiseRating:
    rnd = repo.get(round_ref)
    repo.get(rater_ref)
    rating = PairwiseRating(id="pair-"+_token(rnd, rater_ref.id), created_at=created_at,
        rater=rater_ref, round=round_ref, choice=choice, rationale=rationale, ordered_runs=assigned_runs(rnd, rater_ref))
    repo.put(rating)
    return rating


def serialize_case(repo: Repository, case_ref: Ref, round_ref: Ref, rater_ref: Ref, *, mode: Literal["public", "embed"] = "public") -> dict:
    if mode not in ("public", "embed"):
        raise PermissionError("administrative serialization is not a public presentation mode")
    case, rnd = repo.get(case_ref), repo.get(round_ref)
    if not isinstance(case, EvaluationCase) or not isinstance(rnd, EvaluationRound):
        raise ValueError("wrong presentation object types")
    if case.public_visibility != "curated":
        raise PermissionError("case is not curated")
    if set(case.model_runs) != set(rnd.candidate_model_runs) or case.rubric != rnd.rubric:
        raise ValueError("case/round mismatch")
    if rater_ref.kind != "HumanRater":
        raise ValueError("presentation requires a human rater session")
    repo.get(rater_ref)
    order = assigned_runs(rnd, rater_ref)
    if any(repo.get(repo.get(run).media).provenance != "synthetic_fixture" for run in order):
        raise ValueError("Phase 4 presentation supports synthetic fixtures only")
    submissions = [r for r in repo.all("PairwiseRating") if r.round.id == round_ref.id and r.rater.id == rater_ref.id]
    revealed = bool(submissions)
    prompt = repo.get(repo.get(order[0]).prompt)
    payload = {
        "schema_version": 1, "mode": mode, "slug": case.project_case_slug,
        "title": case.title if revealed else "Blind comparison",
        "prompt": prompt.original_prompt, "stage": "revealed" if revealed else "blind",
        "fixture_notice": "Synthetic records only; no playable media or validated human consensus.",
        "outputs": [{"label": label, "presentation_token": _token(rnd, rater_ref.id+run.model_dump_json()), "media_state": "fixture_no_media"} for label,run in zip(("A", "B"),order)],
        "choices": ["A", "B", "tie", "cannot_determine"],
    }
    if revealed:
        # Public aliases only. No notes, raw hypotheses, storage references, model parameters,
        # rater IDs, private traces, confidence or embedded domain objects.
        payload["your_evaluation"] = {"choice": submissions[0].choice}
        payload["results"] = []
        for label,run in zip(("A", "B"),order):
            assessments = [repo.get(ref) for ref in case.published_assessments if repo.get(ref).model_run == run]
            human = [h for h in repo.all("HumanRating") if h.model_run == run and h.round.id == rnd.id and h.rubric == case.rubric]
            payload["results"].append({"label": label,
                "agent_scores": [{"dimension": a.result.dimension.value, "status": a.result.status, "score": a.result.score, "source_mode": a.source_mode, "evaluator_digest": repo.get(a.evaluator).digest} for a in assessments],
                "human_score_distributions": {d.value: {str(s): sum(x.score == s and x.status == "scored" for h in human for x in h.dimension_scores if x.dimension == d) for s in range(5)} for d in {x.dimension for h in human for x in h.dimension_scores}},
            })
        payload["remaining_uncertainty"] = "Fixture judgments do not establish media quality, human reliability or evaluator validity."
    return payload
