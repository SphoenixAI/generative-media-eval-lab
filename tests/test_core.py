import asyncio
import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from fastapi.testclient import TestClient
from eval_lab.api import app
from eval_lab.domain import *
from eval_lab.fixtures import seed, requests_for, STAMP
from eval_lab.persistence import Repository
from eval_lab.scoring import evaluate
from eval_lab.presentation import serialize_case, submit_pairwise, assigned_runs
from eval_lab.demo import run_demo
from eval_lab.agreement import rating_matrix
from eval_lab.swarm import BoundedSwarm


@pytest.fixture
def lab():
    repo=Repository()
    data=seed(repo)
    yield repo,data
    repo.close()


def scored(d,score):
    return DimensionScore(dimension=d,status="scored",score=score,confidence=.5,evidence=(Ref(kind="Evidence",id="test"),),rationale="Test observation")


@pytest.mark.parametrize("dimension",list(Dimension))
def test_every_rubric_dimension_has_unique_anchors(lab,dimension):
    rule=next(x for x in lab[1]["rubric"].dimensions if x.dimension==dimension)
    assert len(set(rule.anchors))==5


def test_beauty_cannot_hide_prompt_failure(lab):
    _,d=lab
    scores=tuple(scored(dim,0 if dim==Dimension.PROMPT else 4) for dim in Dimension)
    result=evaluate(scores,d["rubric"],d["intent"])
    assert result.status=="FAILED"
    assert result.critical_dimensions==(Dimension.PROMPT,)


def test_geometry_failure_requires_regeneration_even_with_missing_scores(lab):
    _,d=lab
    result=evaluate((scored(Dimension.GEOMETRY,0),),d["rubric"],d["intent"])
    assert result.status=="FAILED" and result.recommendation=="REGENERATE"
    assert len(result.missing_dimensions)==12


def test_missing_evidence_is_unknown(lab):
    _,d=lab
    assert evaluate((),d["rubric"],d["intent"]).status=="UNKNOWN"
    scores=tuple(DimensionScore(dimension=x,status="abstain",rationale="Unavailable") for x in Dimension)
    assert evaluate(scores,d["rubric"],d["intent"]).status=="UNKNOWN"


def test_intent_can_exclude_physics_for_declared_surreal_scene(lab):
    _,d=lab
    criteria=tuple(c.model_copy(update={"applicability":"not_applicable","rationale":"Declared surreal topology"}) if c.dimension==Dimension.GEOMETRY else c for c in d["intent"].criteria)
    intent=d["intent"].model_copy(update={"criteria":criteria})
    scores=tuple(DimensionScore(dimension=x,status="not_applicable",rationale="Surreal intent") if x==Dimension.GEOMETRY else scored(x,4) for x in Dimension)
    assert evaluate(scores,d["rubric"],intent).status=="PASS"
    with pytest.raises(ValueError):
        evaluate(scores,d["rubric"],d["intent"])


def test_unapproved_intent_cannot_pass(lab):
    _,d=lab
    proposed=d["intent"].model_copy(update={"authority":"agent_proposed","approved_by":None})
    assert evaluate(tuple(scored(x,4) for x in Dimension),d["rubric"],proposed).status=="UNKNOWN"


@pytest.mark.parametrize("score",[-1,5,True,2.5])
def test_score_validation(score):
    with pytest.raises(ValidationError):
        scored(Dimension.PROMPT,score)


def test_scored_result_requires_evidence():
    with pytest.raises(ValidationError):
        DimensionScore(dimension=Dimension.PROMPT,status="scored",score=4,confidence=.9,rationale="Unsupported claim")


def test_abstention_cannot_carry_a_number():
    with pytest.raises(ValidationError):
        DimensionScore(dimension=Dimension.PROMPT,status="abstain",score=0,rationale="Unavailable")


def test_frozen_and_extra_fields(lab):
    _,d=lab
    with pytest.raises(ValidationError):
        d["rubric"].version="changed"
    with pytest.raises(ValidationError):
        scored(Dimension.PROMPT,4).model_validate({**scored(Dimension.PROMPT,4).model_dump(),"chain_of_thought":"must not store"})


def test_append_only_rubric_and_evaluator_versions(lab):
    repo,d=lab
    old=d["rubric"]
    with pytest.raises(ValueError,match="immutable"):
        repo.put(old.model_copy(update={"rationale":"silently changed"}))
    revised=old.model_copy(update={"revision":2,"version":"0.2.0","supersedes":old.ref,"rationale":"Explicit revision"})
    repo.put(revised)
    assert repo.get(old.ref).digest==old.digest
    assert repo.get(d["version"].ref).rubric==old.ref
    assert repo.get(revised.ref).digest!=old.digest
    changed=d["version"].model_copy(update={"prompt_version":"silently changed"})
    with pytest.raises(ValueError,match="immutable"):
        repo.put(changed)


def test_sql_update_and_delete_denied(lab):
    repo,_=lab
    for sql in ("UPDATE artifacts SET sha256='tampered'", "DELETE FROM artifacts"):
        with pytest.raises(IntegrityError):
            with repo.engine.begin() as conn:
                conn.execute(text(sql))


def test_reopen_persistent_database(tmp_path):
    url="sqlite:///"+str(tmp_path/"lab.sqlite")
    repo=Repository(url)
    data=seed(repo)
    digest=data["rubric"].digest
    repo.close()
    reopened=Repository(url)
    assert reopened.get(data["rubric"].ref).digest==digest
    assert len(reopened.all("HumanRating"))==6
    reopened.close()


def test_evidence_timecodes_bound_to_media(lab):
    repo,d=lab
    ev=d["evidence"]["camera_only"]
    with pytest.raises(ValueError,match="duration"):
        repo.put(ev.model_copy(update={"id":"invalid-interval","timestamp_end":100}))
    with pytest.raises(ValidationError):
        Evidence.model_validate({**ev.model_dump(),"timestamp_start":4,"timestamp_end":2})


def test_no_dangling_references(lab):
    repo,d=lab
    with pytest.raises(KeyError):
        repo.put(d["prompt"].model_copy(update={"id":"dangling","intent":Ref(kind="IntentSpec",id="missing")}))


def test_duplicate_rating_and_pooled_rounds_rejected(lab):
    repo,d=lab
    rating=d["ratings"][0]
    with pytest.raises(ValueError,match="duplicate"):
        repo.put(rating.model_copy(update={"id":"duplicate"}))
    with pytest.raises(ValueError,match="duplicate"):
        rating_matrix((rating,rating),Dimension.PROMPT)
    with pytest.raises(ValueError,match="pool"):
        rating_matrix((rating,rating.model_copy(update={"round":Ref(kind="EvaluationRound",id="other")})),Dimension.PROMPT)


def test_blind_payload_excludes_private_and_judge_information(lab):
    repo,d=lab
    payload=serialize_case(repo,d["case"].ref,d["round"].ref,d["raters"][0].ref)
    raw=json.dumps(payload)
    for secret in ("PRIVATE", "synthetic-generator", "agent_scores", "human_score_distributions", "fixture://", "evidence-", "run-", "assignment_seed", "beautiful_wrong"):
        assert secret not in raw
    assert payload["title"]=="Blind comparison" and payload["stage"]=="blind"
    assert "cannot_determine" in payload["choices"]


def test_reveal_requires_authoritative_submission_for_that_rater(lab):
    repo,d=lab
    args=(repo,d["case"].ref,d["round"].ref,d["raters"][0].ref)
    submit_pairwise(repo,d["round"].ref,d["raters"][1].ref,"tie","Fixture",created_at=STAMP)
    assert serialize_case(*args)["stage"]=="blind"
    submit_pairwise(repo,d["round"].ref,d["raters"][0].ref,"cannot_determine","Fixture",created_at=STAMP)
    public=serialize_case(*args)
    embed=serialize_case(*args,mode="embed")
    assert public["stage"]=="revealed"
    assert public["your_evaluation"]["choice"]=="cannot_determine"
    assert {**embed,"mode":"public"}==public
    assert "PRIVATE" not in json.dumps(public)


def test_assignment_stable_balanced_and_rater_revision_independent(lab):
    _,d=lab
    rnd=d["round"]
    first=[assigned_runs(rnd,Ref(kind="HumanRater",id=str(i)))[0] for i in range(100)]
    assert 30<first.count(rnd.candidate_model_runs[0])<70
    r=d["raters"][0].ref
    assert assigned_runs(rnd,r)==assigned_runs(rnd,r.model_copy(update={"revision":2}))


def test_private_case_and_admin_mode_denied(lab):
    repo,d=lab
    private=d["case"].model_copy(update={"id":"private-case","public_visibility":"private"})
    repo.put(private)
    with pytest.raises(PermissionError):
        serialize_case(repo,private.ref,d["round"].ref,d["raters"][0].ref)
    with pytest.raises(PermissionError):
        serialize_case(repo,d["case"].ref,d["round"].ref,d["raters"][0].ref,mode="admin")


def test_paid_api_boundary_denied():
    client=TestClient(app)
    response=client.post("/private/execute",json={"provider":"paid","budget":999999})
    assert response.status_code==403
    assert client.get("/health").json()["paid_execution"] is False


def test_demo_independent_replay_and_boundaries():
    outputs=[]
    for _ in range(2):
        repo=Repository()
        outputs.append(asyncio.run(run_demo(repo)))
        repo.close()
    assert outputs[0]==outputs[1]
    demo=outputs[0]
    assert demo["phase_completed"]==4 and demo["fixtures"]==12 and demo["agent_assessments"]==156
    assert demo["replay_provider_calls"]==0 and demo["model_calls_paid"]==0
    assert demo["verdicts"]["geometry_collapse"]["recommendation"]=="REGENERATE"
    assert demo["disagreements"][0]["adjudication_required"]


def test_unpublished_agent_results_never_appear_in_curated_case(lab):
    repo,d=lab
    result=asyncio.run(BoundedSwarm(d["provider"]).run(requests_for(repo,d,"beautiful_wrong")[:1],d["runs"]["beautiful_wrong"],d["version"],created_at=STAMP))
    repo.put(result.assessments[0])
    submit_pairwise(repo,d["round"].ref,d["raters"][0].ref,"A","Fixture",created_at=STAMP)
    args=(repo,d["case"].ref,d["round"].ref,d["raters"][0].ref)
    assert all(not r["agent_scores"] for r in serialize_case(*args)["results"])
    published=d["case"].model_copy(update={"revision":2,"published_assessments":(result.assessments[0].ref,)})
    repo.put(published)
    shown=serialize_case(repo,published.ref,d["round"].ref,d["raters"][0].ref)
    scores=[s for r in shown["results"] for s in r["agent_scores"]]
    assert len(scores)==1 and scores[0]["evaluator_digest"]==d["version"].digest


def test_relational_support_cannot_borrow_cross_intent_evidence(lab):
    repo,d=lab
    other=d["intent"].model_copy(update={"id":"other-intent"})
    repo.put(other)
    h=Hypothesis(id="foreign",created_at=STAMP,intent=other.ref,observed_problem="Unclear",proposed_cause="Camera",evidence_required=("more",),discriminating_test="Compare",predicted_observation="Stable",falsifying_observation="Unstable")
    repo.put(h)
    edge=RelationClaim(id="bad-support",created_at=STAMP,subject=d["evidence"]["camera_only"].ref,predicate="supports",object=h.ref,intent=other.ref,
        epistemic_status="proposed",evidence=(),asserted_by="test",purpose="Cross intent should fail",scope="test",valid_from=STAMP)
    with pytest.raises(ValueError,match="outside declared intent"):
        repo.put(edge)
