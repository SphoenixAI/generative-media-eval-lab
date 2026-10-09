"""Reproducible no-network Phase 4 walkthrough."""
import argparse
import asyncio
import json
from pathlib import Path
from .agreement import cohens_kappa, krippendorff_alpha, percent_agreement, rating_matrix
from .disagreement import disagreements
from .domain import Dimension, Hypothesis, HypothesisGraph, RelationClaim
from .fixtures import SCENARIOS, STAMP, requests_for, seed
from .persistence import Repository
from .presentation import serialize_case, submit_pairwise
from .scoring import evaluate
from .swarm import BoundedSwarm


def make_graph(repo, data):
    ev, intent = data["evidence"]["physics_only"], data["intent"]
    hypotheses = []
    for name, cause, prediction, falsification in (
        ("camera", "Camera movement creates apparent sliding", "Apparent sliding disappears after camera compensation", "Sliding remains in stable world coordinates"),
        ("contact", "Foot contact is inconsistent with ground", "Feet move against stable ground during contact", "Contacts remain fixed after correcting camera motion"),
    ):
        h = Hypothesis(id="hypothesis-"+name, created_at=STAMP, intent=intent.ref, observed_problem="Subject appears to slide",
            proposed_cause=cause, evidence_required=("Dense ground/contact tracks with camera motion estimates",),
            supporting_evidence=(ev.ref,), discriminating_test="Compare static-camera or stabilized view with visible ground grid; proposal only",
            predicted_observation=prediction, falsifying_observation=falsification)
        repo.put(h)
        hypotheses.append(h)
    edges = []
    for h in hypotheses:
        for predicate, source, target in (("supports", ev.ref, h.ref), ("motivated_by", h.ref, intent.ref)):
            edge = RelationClaim(id=f"edge-{h.id}-{predicate}", created_at=STAMP, subject=source, predicate=predicate, object=target,
                intent=intent.ref, epistemic_status="proposed", evidence=(ev.ref,), asserted_by="fixture-author",
                purpose="Distinguish causes to preserve the intended shot", scope="Synthetic diagnostic illustration", valid_from=STAMP)
            repo.put(edge)
            edges.append(edge)
    graph = HypothesisGraph(id="graph-slide", created_at=STAMP, intent=intent.ref, root_observation="Subject appears to slide",
        nodes=(ev.ref, intent.ref)+tuple(h.ref for h in hypotheses), edges=tuple(edges),
        unresolved_questions=("Does camera compensation preserve or remove sliding?", "No experiment executed at Phase 4"))
    repo.put(graph)
    return graph


async def run_demo(repo: Repository) -> dict:
    data = seed(repo)
    swarm = BoundedSwarm(data["provider"])
    agents, traces, verdicts = [], [], {}
    for code, _, _, _ in SCENARIOS:
        result = await swarm.run(requests_for(repo,data,code), data["runs"][code], data["version"], created_at=STAMP)
        for assessment in result.assessments:
            repo.put(assessment)
        agents.extend(result.assessments)
        traces.extend(result.trace)
        verdicts[code] = evaluate(tuple(a.result for a in result.assessments), data["rubric"], data["intent"]).model_dump(mode="json")
    conflicts = disagreements(data["ratings"], tuple(agents), created_at=STAMP)
    for conflict in conflicts:
        repo.put(conflict)
    graph = make_graph(repo,data)
    data["case"] = data["case"].model_copy(update={"revision": 2, "published_assessments": tuple(a.ref for a in agents if a.model_run in data["case"].model_runs)})
    repo.put(data["case"])
    matrix = rating_matrix(data["ratings"],Dimension.PROMPT)
    args = (repo,data["case"].ref,data["round"].ref,data["raters"][0].ref)
    before = serialize_case(*args)
    submit_pairwise(repo,data["round"].ref,data["raters"][0].ref,"cannot_determine","Synthetic workflow submission only",created_at=STAMP)
    public, embed = serialize_case(*args), serialize_case(*args,mode="embed")
    # Deterministic replay must preserve assessments and make no extra provider calls.
    repeated = await swarm.run(requests_for(repo,data,"beautiful_wrong"),data["runs"]["beautiful_wrong"],data["version"],created_at=STAMP)
    return {
        "phase_completed": 4,
        "evidence_scope": "SYNTHETIC_SOFTWARE_FIXTURES_ONLY",
        "model_calls_paid": 0,
        "fixtures": len(SCENARIOS), "human_rating_fixture_records": len(data["ratings"]),
        "agent_assessments": len(agents), "specialists_per_case": 13,
        "replay_provider_calls": repeated.calls,
        "rubric_digest": data["rubric"].digest, "evaluator_digest": data["version"].digest,
        "verdicts": verdicts,
        "agreement": {
            "notice": "Two authored units; numerical fixture results are not empirical inter-rater reliability.",
            "ordinal_alpha": krippendorff_alpha(matrix).model_dump(),
            "exact_agreement": percent_agreement(matrix).model_dump(),
            "cohens_kappa_first_two_raters": cohens_kappa([tuple(u[:2]) for u in matrix]).model_dump(),
        },
        "disagreements": [c.model_dump(mode="json") for c in conflicts],
        "hypothesis_graph": graph.model_dump(mode="json"),
        "public_before_submission": before, "public_after_submission": public, "embed_after_submission": embed,
        "trace_states": sorted({t.state for t in traces}),
        "not_implemented": ["real media interpretation", "gold-set adjudication", "regression or drift inference", "VFX cost engine", "hypothesis test execution", "public authentication/hosting", "polished frontend"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", help="SQLite path; defaults to ephemeral in-memory database")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    repo = Repository("sqlite:///"+str(Path(args.db).resolve()) if args.db else "sqlite://")
    try:
        result = asyncio.run(run_demo(repo))
    finally:
        repo.close()
    serialized = json.dumps(result, indent=2, sort_keys=True)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(serialized)
        print(json.dumps({"phase":4,"fixtures":result["fixtures"],"agent_assessments":result["agent_assessments"],"paid_calls":0,"replay_calls":result["replay_provider_calls"],"output":str(args.output)}))
    else:
        print(serialized,end="")


if __name__ == "__main__":
    main()
