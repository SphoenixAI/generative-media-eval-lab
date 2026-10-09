"""Author-created test records. These are not video assets or human research data."""
from datetime import datetime, timezone
from hashlib import sha256
from .domain import *
from .persistence import Repository
from .rubrics import initial_rubric
from .providers import DeterministicFixtureProvider, EvaluationRequest

STAMP = datetime(2026, 10, 6, tzinfo=timezone.utc)

# Cases cover boundaries without pretending to validate automatic visual perception.
SCENARIOS = (
    ("beautiful_wrong", "Beautiful but prompt-inaccurate", {Dimension.PROMPT: 0, Dimension.AESTHETIC: 4}, "Central requested red dog is absent; a polished unrelated animal appears."),
    ("correct_plain", "Poor aesthetics with correct prompt adherence", {Dimension.PROMPT: 4, Dimension.AESTHETIC: 1}, "Requested dog and action are present; visual treatment is flat."),
    ("geometry_collapse", "Good composition, catastrophic geometry", {Dimension.COMPOSITION: 4, Dimension.GEOMETRY: 0}, "Ground grid and subject topology fold discontinuously."),
    ("camera_only", "Camera failure without physics failure", {Dimension.CAMERA: 1, Dimension.MOTION: 4, Dimension.GEOMETRY: 4}, "World-relative contacts remain coherent while the camera framing jumps."),
    ("physics_only", "Physics failure without camera failure", {Dimension.CAMERA: 4, Dimension.MOTION: 0}, "Static camera and grid remain stable while feet slide against ground."),
    ("identity_drift", "Subject identity drift", {Dimension.SUBJECT: 0}, "Subject identity changes after occlusion without requested transformation."),
    ("easy_fix", "Easy repair candidate", {Dimension.ARTIFACT: 3, Dimension.EDITABILITY: 3}, "Small peripheral artifact outside protected action area."),
    ("expensive_fix", "Expensive repair candidate", {Dimension.ARTIFACT: 1, Dimension.EDITABILITY: 1}, "Recurring local warp crosses a moving silhouette."),
    ("regenerate", "Must-regenerate policy fixture", {Dimension.GEOMETRY: 0, Dimension.EDITABILITY: 0}, "Essential scene topology changes throughout the shot."),
    ("vague_rubric", "Human disagreement about polish", {Dimension.AESTHETIC: 2}, "Stylized palette invites different audience preferences."),
    ("judge_disagrees", "Mock judge differs from reference annotation", {Dimension.MOTION: 4}, "Synthetic reference says foot sliding; mock deliberately misses it."),
    ("regression_fixture", "Candidate regression fixture", {Dimension.GEOMETRY: 0, Dimension.AESTHETIC: 4}, "Candidate is polished but geometry breaks; regression engine is deferred."),
)


def seed(repo: Repository) -> dict:
    rubric = initial_rubric()
    intent = IntentSpec(id="intent-crossing", created_at=STAMP, owner="fixture-author", objective="Show a red dog crossing a stable ground grid",
        audience="production reviewer", context="Realistic continuous static-camera shot",
        constraints=("Preserve dog identity", "Static camera", "Realistic geometry"),
        criteria=tuple(Criterion(dimension=d, rationale="Applies to this declared realistic test shot", acceptance="Meet the relevant rubric anchor") for d in Dimension),
        authority="human_declared", approved_by="fixture-author")
    prompt = PromptSpec(id="prompt-crossing", created_at=STAMP, original_prompt="A red dog walks across a stable ground grid in a single static-camera realistic shot.",
        normalized_prompt="red dog; walk; ground grid; static camera; continuous; realistic", intent=intent.ref,
        requested_subjects=("red dog",), requested_actions=("walk across grid",), requested_camera=("static",))
    for artifact in (rubric, intent, prompt):
        repo.put(artifact)
    runs, evidence, rules = {}, {}, {}
    for code, title, overrides, observation in SCENARIOS:
        asset = MediaAsset(id="media-"+code, created_at=STAMP, type="video", storage_reference="fixture://"+code,
            checksum=sha256((code+observation).encode()).hexdigest(), duration=6, fps=24, width=1280, height=720,
            provenance="synthetic_fixture", rights_status="owner_asserted")
        run = ModelRun(id="run-"+code, created_at=STAMP, model_name="synthetic-generator", model_version=code,
            provider="fixture", prompt=prompt.ref, media=asset.ref, generated_at=STAMP, lineage_group="single-fixture-author")
        ev = Evidence(id="evidence-"+code, created_at=STAMP, media=asset.ref, observation=observation,
            timestamp_start=0, timestamp_end=6, source="synthetic_fixture", method="Authored scenario assertion; no decoded frames", coverage="interval",
            author="fixture-author", independence_group="single-fixture-author")
        for artifact in (asset, run, ev):
            repo.put(artifact)
        runs[code], evidence[code] = run, ev
        for d in Dimension:
            rules[(code,d)] = overrides.get(d, 4)
    provider = DeterministicFixtureProvider(rules)
    version = EvaluatorVersion(id="mock-evaluator", created_at=STAMP, provider="fixture", model=provider.identity,
        model_snapshot=provider.identity, prompt_version="0.1.0", prompt_template="Return authored ordinal fixture rule; abstain without evidence.",
        rubric=rubric.ref, rubric_digest=rubric.digest, lineage_group="single-fixture-author", code_version="0.1.0")
    repo.put(version)
    selected = (runs["beautiful_wrong"].ref, runs["correct_plain"].ref)
    rnd = EvaluationRound(id="round-demo", created_at=STAMP, candidate_model_runs=selected, rubric=rubric.ref, assignment_seed="synthetic-demo-seed-not-for-production")
    case = EvaluationCase(id="case-demo", created_at=STAMP, title="A beautiful output can fail its brief", description="Synthetic workflow case", model_runs=selected,
        intent=intent.ref, rubric=rubric.ref, public_visibility="curated", featured_in_think_with_me=True, project_case_slug="demo-comparison",
        private_notes="PRIVATE_SENTINEL: never reveal this note")
    repo.put(rnd)
    repo.put(case)
    raters, ratings = [], []
    for i in range(3):
        rater = HumanRater(id=f"rater-{i}", created_at=STAMP, anonymous_id=f"synthetic-{i}", calibration_state="uncalibrated")
        repo.put(rater)
        raters.append(rater)
        for code in ("beautiful_wrong", "correct_plain"):
            scores = []
            for d in Dimension:
                score = rules[(code,d)]
                if code == "beautiful_wrong" and d == Dimension.PROMPT:
                    score = (0, 1, 3)[i]  # explicitly conflicting authored opinions
                scores.append(DimensionScore(dimension=d, status="scored", score=score, confidence=0.5, evidence=(evidence[code].ref,), rationale="Authored human-rating fixture, not a real participant."))
            rating = HumanRating(id=f"human-{i}-{code}", created_at=STAMP, rater=rater.ref, model_run=runs[code].ref, rubric=rubric.ref, round=rnd.ref, dimension_scores=tuple(scores), notes="PRIVATE_RATER_NOTE")
            repo.put(rating)
            ratings.append(rating)
    return dict(rubric=rubric, intent=intent, prompt=prompt, runs=runs, evidence=evidence, provider=provider, version=version, round=rnd, case=case, raters=tuple(raters), ratings=tuple(ratings))


def requests_for(repo: Repository, data: dict, code: str) -> tuple[EvaluationRequest, ...]:
    run = data["runs"][code]
    asset = repo.get(run.media)
    return tuple(EvaluationRequest(media_checksum=asset.checksum, prompt_text=data["prompt"].original_prompt,
        intent=data["intent"], rubric_digest=data["rubric"].digest, dimension=d, evidence=(data["evidence"][code],), fixture_code=code) for d in Dimension)
