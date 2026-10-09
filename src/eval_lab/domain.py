"""Typed immutable snapshots. Inferences are claims, never promoted to observations."""

from datetime import datetime, timezone
from enum import StrEnum
from hashlib import sha256
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Score = Annotated[int, Field(strict=True, ge=0, le=4)]
Confidence = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
NonEmpty = Annotated[str, Field(min_length=1)]


class Value(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class Ref(Value):
    kind: NonEmpty
    id: NonEmpty
    revision: Annotated[int, Field(strict=True, ge=1)] = 1


class Artifact(Value):
    id: NonEmpty
    revision: Annotated[int, Field(strict=True, ge=1)] = 1
    schema_version: Literal[1] = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def timezone_required(self):
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must have timezone")
        for field, expected in REFERENCE_KINDS.get(type(self).__name__, {}).items():
            value = getattr(self, field)
            refs = value if isinstance(value, tuple) else (() if value is None else (value,))
            if any(ref.kind != expected for ref in refs):
                raise ValueError(f"{field} must reference {expected}")
        if isinstance(self, (HumanRating, PairwiseRating)) and self.revision != 1:
            raise ValueError("ratings are immutable submissions; corrections require a future adjudication record")
        return self

    @property
    def ref(self) -> Ref:
        return Ref(kind=type(self).__name__, id=self.id, revision=self.revision)

    def canonical(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), allow_nan=False)

    @property
    def digest(self) -> str:
        return sha256(self.canonical().encode()).hexdigest()


class Dimension(StrEnum):
    PROMPT = "prompt_adherence"
    SUBJECT = "subject_consistency"
    SEMANTIC = "semantic_consistency"
    TEMPORAL = "temporal_consistency"
    GEOMETRY = "temporal_geometry"
    MOTION = "motion_plausibility"
    OCCLUSION = "occlusion_consistency"
    LIGHTING = "lighting_continuity"
    CAMERA = "camera_language"
    COMPOSITION = "composition"
    ARTIFACT = "artifacting"
    AESTHETIC = "aesthetic_quality"
    EDITABILITY = "editability"


class Criterion(Value):
    dimension: Dimension
    applicability: Literal["required", "optional", "not_applicable"] = "required"
    rationale: NonEmpty
    acceptance: NonEmpty


class IntentSpec(Artifact):
    owner: NonEmpty
    objective: NonEmpty
    audience: NonEmpty
    context: NonEmpty
    constraints: tuple[str, ...] = ()
    prohibited_outcomes: tuple[str, ...] = ()
    criteria: tuple[Criterion, ...]
    authority: Literal["human_declared", "agent_proposed"]
    approved_by: str | None = None
    supersedes: Ref | None = None

    @model_validator(mode="after")
    def unique_criteria(self):
        if not self.criteria or len({x.dimension for x in self.criteria}) != len(self.criteria):
            raise ValueError("criteria must be nonempty and unique")
        if self.authority == "human_declared" and not self.approved_by:
            raise ValueError("declared intent needs an accountable approver")
        return self


class PromptSpec(Artifact):
    original_prompt: NonEmpty
    normalized_prompt: NonEmpty
    intent: Ref
    requested_subjects: tuple[str, ...] = ()
    requested_actions: tuple[str, ...] = ()
    requested_camera: tuple[str, ...] = ()
    requested_style: tuple[str, ...] = ()
    requested_environment: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    negative_constraints: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


class MediaAsset(Artifact):
    type: Literal["image", "video"]
    storage_reference: NonEmpty
    checksum: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    duration: Annotated[float, Field(gt=0)] | None = None
    fps: Annotated[float, Field(gt=0)] | None = None
    width: Annotated[int, Field(strict=True, gt=0)]
    height: Annotated[int, Field(strict=True, gt=0)]
    provenance: Literal["uploaded", "generated", "synthetic_fixture"]
    rights_status: Literal["unknown", "owner_asserted", "licensed"] = "unknown"

    @model_validator(mode="after")
    def video_metadata(self):
        if self.type == "video" and (self.duration is None or self.fps is None):
            raise ValueError("video requires duration and fps")
        if self.type == "image" and (self.duration is not None or self.fps is not None):
            raise ValueError("still image must not claim temporal metadata")
        return self


class Parameter(Value):
    name: NonEmpty
    value: str | int | float | bool | None


class ModelRun(Artifact):
    model_name: NonEmpty
    model_version: NonEmpty
    provider: NonEmpty
    prompt: Ref
    media: Ref
    seed: int | None = None
    generation_parameters: tuple[Parameter, ...] = ()
    generated_at: datetime
    lineage_group: NonEmpty


class EvaluationDimension(Value):
    dimension: Dimension
    description: NonEmpty
    family: Literal["instruction", "temporal_physical", "craft"]
    anchors: tuple[str, str, str, str, str]  # index is ordinal category, NOT interval utility
    hard_fail_at_or_below: Score | None = None
    regenerate_at_or_below: Score | None = None
    boundary_note: NonEmpty

    @model_validator(mode="after")
    def threshold_order(self):
        if self.regenerate_at_or_below is not None and (self.hard_fail_at_or_below is None or self.regenerate_at_or_below > self.hard_fail_at_or_below):
            raise ValueError("regeneration threshold must also trigger hard failure")
        if any(not a.strip() for a in self.anchors):
            raise ValueError("behavioral anchors cannot be blank")
        return self


class Rubric(Artifact):
    version: NonEmpty
    dimensions: tuple[EvaluationDimension, ...]
    rationale: NonEmpty
    supersedes: Ref | None = None

    @model_validator(mode="after")
    def unique_dimensions(self):
        if not self.dimensions or len({d.dimension for d in self.dimensions}) != len(self.dimensions):
            raise ValueError("dimensions must be nonempty and unique")
        return self


class Evidence(Artifact):
    media: Ref
    observation: NonEmpty
    timestamp_start: Annotated[float, Field(ge=0)] | None = None
    timestamp_end: Annotated[float, Field(ge=0)] | None = None
    source: Literal["human_observation", "instrument", "synthetic_fixture"]
    method: NonEmpty
    coverage: Literal["full_clip", "sampled_frames", "interval", "unknown"]
    sampling_manifest: tuple[float, ...] = ()
    author: NonEmpty
    independence_group: NonEmpty

    @model_validator(mode="after")
    def valid_time(self):
        if (self.timestamp_start is None) != (self.timestamp_end is None):
            raise ValueError("timecode requires both start and end")
        if self.timestamp_start is not None and self.timestamp_end < self.timestamp_start:
            raise ValueError("inverted timecode")
        if self.coverage == "interval" and self.timestamp_start is None:
            raise ValueError("interval coverage requires timecodes")
        if self.coverage == "sampled_frames" and not self.sampling_manifest:
            raise ValueError("sampled coverage needs a sampling manifest")
        if any(t < 0 for t in self.sampling_manifest):
            raise ValueError("negative sample time")
        return self


class DimensionScore(Value):
    dimension: Dimension
    status: Literal["scored", "abstain", "not_applicable"]
    score: Score | None = None
    confidence: Confidence | None = None
    confidence_kind: Literal["self_reported_uncalibrated"] = "self_reported_uncalibrated"
    evidence: tuple[Ref, ...] = ()
    failure_tags: tuple[str, ...] = ()
    rationale: NonEmpty

    @model_validator(mode="after")
    def score_contract(self):
        if self.status == "scored":
            if self.score is None or self.confidence is None or not self.evidence:
                raise ValueError("scored result needs score, confidence and evidence")
        elif self.score is not None or self.confidence is not None:
            raise ValueError("abstention/N-A must not invent score or confidence")
        if any(e.kind != "Evidence" for e in self.evidence):
            raise ValueError("evidence references must name Evidence")
        return self


class HumanRater(Artifact):
    anonymous_id: NonEmpty
    calibration_state: Literal["uncalibrated", "in_progress", "calibrated"]


class HumanRating(Artifact):
    rater: Ref
    model_run: Ref
    rubric: Ref
    round: Ref
    dimension_scores: tuple[DimensionScore, ...]
    notes: str = ""

    @model_validator(mode="after")
    def unique_scores(self):
        if len({s.dimension for s in self.dimension_scores}) != len(self.dimension_scores):
            raise ValueError("duplicate rating dimension")
        return self


class PairwiseRating(Artifact):
    rater: Ref
    round: Ref
    choice: Literal["A", "B", "tie", "cannot_determine"]
    ordered_runs: tuple[Ref, Ref]  # authoritative assignment, never supplied by public client
    rationale: NonEmpty

    @model_validator(mode="after")
    def different_runs(self):
        if self.ordered_runs[0] == self.ordered_runs[1]:
            raise ValueError("pair must contain distinct runs")
        return self


class EvaluationRound(Artifact):
    candidate_model_runs: tuple[Ref, ...]
    rubric: Ref
    blinded: Literal[True] = True
    assignment_seed: NonEmpty  # private; server generates in real deployments
    status: Literal["open", "closed"] = "open"

    @model_validator(mode="after")
    def candidates_unique(self):
        if len(self.candidate_model_runs) < 2 or len(set(self.candidate_model_runs)) != len(self.candidate_model_runs):
            raise ValueError("round needs distinct candidates")
        return self


class EvaluatorVersion(Artifact):
    provider: NonEmpty
    model: NonEmpty
    model_snapshot: NonEmpty
    prompt_version: NonEmpty
    prompt_template: NonEmpty
    configuration: tuple[Parameter, ...] = ()
    rubric: Ref
    rubric_digest: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    lineage_group: NonEmpty
    code_version: NonEmpty


class Hypothesis(Artifact):
    intent: Ref
    observed_problem: NonEmpty
    proposed_cause: NonEmpty
    confidence: Confidence | None = None
    confidence_kind: Literal["subjective_unvalidated"] = "subjective_unvalidated"
    supporting_evidence: tuple[Ref, ...] = ()
    contradicting_evidence: tuple[Ref, ...] = ()
    evidence_required: tuple[str, ...]
    discriminating_test: NonEmpty
    predicted_observation: NonEmpty
    falsifying_observation: NonEmpty
    status: Literal["proposed", "under_test", "supported", "contradicted", "unresolved"] = "proposed"


class ResidualMember(Value):
    """Structural remainder, not an authored hypothesis or a confidence estimate."""
    kind: Literal["RESIDUAL"]
    description: Literal["none of the listed causes"]


class CompetingSet(Artifact):
    intent: Ref
    members: tuple[Ref | ResidualMember, ...]
    exclusive: Annotated[bool, Field(strict=True)]
    exhaustive: Annotated[bool, Field(strict=True)]
    supersedes: Ref | None = None

    @model_validator(mode="after")
    def set_contract(self):
        named = tuple(member for member in self.members if isinstance(member, Ref))
        if not named or any(member.kind != "Hypothesis" for member in named):
            raise ValueError("members require at least one named Hypothesis reference")
        if len({member.id for member in named}) != len(named):
            raise ValueError("duplicate hypothesis identity in members")
        residual_count = len(self.members) - len(named)
        if residual_count > 1 or (residual_count and not self.exhaustive):
            raise ValueError("exactly one RESIDUAL is permitted only in an exhaustive set")
        if self.exhaustive and not residual_count:
            residual = ResidualMember(kind="RESIDUAL", description="none of the listed causes")
            object.__setattr__(self, "members", self.members + (residual,))
        predecessor = Ref(kind="CompetingSet", id=self.id, revision=self.revision - 1) if self.revision > 1 else None
        if self.supersedes != predecessor:
            raise ValueError("set revisions must pin their immediate predecessor with supersedes")
        return self


class RelationClaim(Artifact):
    subject: Ref
    predicate: Literal["supports", "contradicts", "motivated_by", "fulfills", "violates", "alternative_to", "compatible_with", "refines"]
    object: Ref
    intent: Ref
    epistemic_status: Literal["observed", "asserted", "proposed"]
    evidence: tuple[Ref, ...]
    asserted_by: NonEmpty
    purpose: NonEmpty
    scope: NonEmpty
    valid_from: datetime
    valid_until: datetime | None = None
    confidence: Confidence | None = None

    @model_validator(mode="after")
    def relation_contract(self):
        expected = {
            "supports": ("Evidence", "Hypothesis"),
            "contradicts": ("Evidence", "Hypothesis"),
            "motivated_by": ("Hypothesis", "IntentSpec"),
            "fulfills": ("Evidence", "IntentSpec"),
            "violates": ("Evidence", "IntentSpec"),
            "alternative_to": ("Hypothesis", "Hypothesis"),
            "compatible_with": ("Hypothesis", "Hypothesis"),
            "refines": ("Hypothesis", "Hypothesis"),
        }
        if (self.subject.kind, self.object.kind) != expected[self.predicate]:
            raise ValueError("relation domain/range violation")
        if self.intent.kind != "IntentSpec":
            raise ValueError("relation must carry intent")
        if self.epistemic_status == "observed" and not self.evidence:
            raise ValueError("observed relation needs evidence")
        if self.predicate in ("compatible_with", "refines") and self.subject.id == self.object.id:
            raise ValueError("hypothesis cannot relate to itself")
        if self.predicate in ("supports", "contradicts", "motivated_by", "alternative_to", "compatible_with", "refines") and self.epistemic_status == "observed":
            raise ValueError("hypothesis relations are claims, not observations")
        if self.valid_from.tzinfo is None or (self.valid_until is not None and (self.valid_until.tzinfo is None or self.valid_until <= self.valid_from)):
            raise ValueError("invalid validity interval")
        return self


class HypothesisGraph(Artifact):
    intent: Ref
    root_observation: NonEmpty
    nodes: tuple[Ref, ...]
    edges: tuple[RelationClaim, ...]
    unresolved_questions: tuple[str, ...]

    @model_validator(mode="after")
    def graph_contract(self):
        if len(set(self.nodes)) != len(self.nodes):
            raise ValueError("duplicate node")
        for edge in self.edges:
            if edge.subject not in self.nodes or edge.object not in self.nodes:
                raise ValueError("dangling edge")
            if edge.intent != self.intent:
                raise ValueError("cross-intent edge requires explicit future mapping")
        return self


class AgentAssessment(Artifact):
    agent_name: NonEmpty
    evaluator: Ref
    model_run: Ref
    rubric: Ref
    result: DimensionScore
    alternative_hypotheses: tuple[str, ...] = ()
    suggested_test: NonEmpty
    recommended_intervention: NonEmpty
    post_production_fixability: Literal["POST_FIXABLE", "EXPENSIVE_POST_FIX", "REGENERATE", "UNKNOWN"] = "UNKNOWN"
    source_mode: Literal["deterministic_fixture", "live"]
    request_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class Disagreement(Artifact):
    model_run: Ref
    dimension: Dimension
    assessment_refs: tuple[Ref, ...]
    observed_scores: tuple[Score, ...]
    proposed_types: tuple[Literal["unclear_rubric", "subjective_preference", "ambiguous_generation", "calibration_issue", "multidimensional_failure", "insufficient_evidence", "irreducible_preference"], ...]
    classification_status: Literal["proposed_requires_human"] = "proposed_requires_human"
    adjudication_required: bool
    reason: NonEmpty


class EvaluationCase(Artifact):
    title: NonEmpty
    description: NonEmpty
    model_runs: tuple[Ref, ...]
    intent: Ref
    rubric: Ref
    hypothesis_graph: Ref | None = None
    published_assessments: tuple[Ref, ...] = ()
    public_visibility: Literal["private", "curated"] = "private"
    featured_in_think_with_me: bool = False
    project_case_slug: NonEmpty
    private_notes: str = ""


ARTIFACT_TYPES = {cls.__name__: cls for cls in (
    IntentSpec, PromptSpec, MediaAsset, ModelRun, Rubric, Evidence, HumanRater,
    HumanRating, PairwiseRating, EvaluationRound, EvaluatorVersion, Hypothesis,
    RelationClaim, HypothesisGraph, AgentAssessment, Disagreement, EvaluationCase, CompetingSet,
)}

REFERENCE_KINDS = {
    "IntentSpec": {"supersedes": "IntentSpec"},
    "PromptSpec": {"intent": "IntentSpec"},
    "ModelRun": {"prompt": "PromptSpec", "media": "MediaAsset"},
    "Rubric": {"supersedes": "Rubric"},
    "Evidence": {"media": "MediaAsset"},
    "HumanRating": {"rater": "HumanRater", "model_run": "ModelRun", "rubric": "Rubric", "round": "EvaluationRound"},
    "PairwiseRating": {"rater": "HumanRater", "round": "EvaluationRound", "ordered_runs": "ModelRun"},
    "EvaluationRound": {"candidate_model_runs": "ModelRun", "rubric": "Rubric"},
    "EvaluatorVersion": {"rubric": "Rubric"},
    "Hypothesis": {"intent": "IntentSpec", "supporting_evidence": "Evidence", "contradicting_evidence": "Evidence"},
    "CompetingSet": {"intent": "IntentSpec", "supersedes": "CompetingSet"},
    "RelationClaim": {"intent": "IntentSpec", "evidence": "Evidence"},
    "HypothesisGraph": {"intent": "IntentSpec"},
    "AgentAssessment": {"evaluator": "EvaluatorVersion", "model_run": "ModelRun", "rubric": "Rubric"},
    "Disagreement": {"model_run": "ModelRun"},
    "EvaluationCase": {"model_runs": "ModelRun", "intent": "IntentSpec", "rubric": "Rubric", "hypothesis_graph": "HypothesisGraph", "published_assessments": "AgentAssessment"},
}
