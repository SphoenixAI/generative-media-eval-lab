"""Finite, independent first-pass specialists. No debate, recursion or paid execution."""
import asyncio
import time
from typing import Literal
from pydantic import Field
from .domain import AgentAssessment, Dimension, DimensionScore, EvaluatorVersion, ModelRun, Ref, Value
from .providers import EvaluationRequest, MultimodalEvaluatorProvider

AGENTS = {
    Dimension.PROMPT: "PromptAdherenceAgent", Dimension.TEMPORAL: "TemporalConsistencyAgent",
    Dimension.GEOMETRY: "TemporalGeometryAgent", Dimension.CAMERA: "CameraLanguageAgent",
    Dimension.MOTION: "MotionPhysicsAgent", Dimension.SUBJECT: "SubjectConsistencyAgent",
    Dimension.ARTIFACT: "ArtifactDetectionAgent", Dimension.COMPOSITION: "CompositionAgent",
    Dimension.EDITABILITY: "VFXSalvageAgent", Dimension.SEMANTIC: "SemanticConsistencyAgent",
    Dimension.OCCLUSION: "OcclusionConsistencyAgent", Dimension.LIGHTING: "LightingContinuityAgent",
    Dimension.AESTHETIC: "AestheticQualityAgent",
}
DEFERRED_ROLES = ("AdversarialPromptAgent", "BiasCalibrationAgent", "RegressionSentinelAgent", "AdjudicationAgent")


class SwarmBudget(Value):
    max_calls: int = Field(default=13, ge=0, le=13, strict=True)
    per_call_timeout_seconds: float = Field(default=1, gt=0, le=60)
    total_timeout_seconds: float = Field(default=15, gt=0, le=120)
    max_cost_usd: Literal[0] = 0


class TraceStep(Value):
    dimension: Dimension
    state: Literal["completed", "cached", "abstained", "budget_exhausted", "timeout", "invalid_output", "provider_error"]
    request_hash: str
    note: str


class SwarmResult(Value):
    assessments: tuple[AgentAssessment, ...]
    trace: tuple[TraceStep, ...]
    calls: int
    paid_calls: Literal[0] = 0
    acceptance: Literal["HUMAN_VALIDATION_REQUIRED"] = "HUMAN_VALIDATION_REQUIRED"


class BoundedSwarm:
    def __init__(self, provider: MultimodalEvaluatorProvider, budget: SwarmBudget | None = None):
        self.provider = provider
        self.budget = budget or SwarmBudget()
        self.cache: dict[tuple[str, str, str], DimensionScore] = {}

    async def run(self, requests: tuple[EvaluationRequest, ...], run: ModelRun, version: EvaluatorVersion, *, created_at) -> SwarmResult:
        if self.provider.mode != "deterministic_fixture":
            raise PermissionError("Phase 4 denies all live/paid provider execution")
        if len(requests) > 13 or len({r.dimension for r in requests}) != len(requests):
            raise ValueError("specialist plan must be bounded with unique dimensions")
        if version.model != self.provider.identity:
            raise ValueError("provider does not match pinned evaluator version")
        for request in requests:
            if request.rubric_digest != version.rubric_digest:
                raise ValueError("request rubric digest does not match evaluator")
            if any(e.media != run.media for e in request.evidence):
                raise ValueError("request evidence belongs to another media output")
        output, trace, calls = [], [], 0
        started = time.monotonic()
        for request in requests:
            key = (self.provider.identity, version.digest, request.digest)
            state, note = "completed", "Validated structured fixture result"
            remaining = self.budget.total_timeout_seconds - (time.monotonic()-started)
            if key in self.cache:
                score, state = self.cache[key], "cached"
            elif calls >= self.budget.max_calls or remaining <= 0:
                score, state = self._abstain(request, "Bounded execution exhausted"), "budget_exhausted"
            else:
                calls += 1
                try:
                    raw = await asyncio.wait_for(self.provider.assess(request), min(remaining, self.budget.per_call_timeout_seconds))
                    score = DimensionScore.model_validate(raw.model_dump() if isinstance(raw, DimensionScore) else raw)
                    allowed = {e.ref for e in request.evidence}
                    if score.dimension != request.dimension or set(score.evidence) - allowed:
                        raise ValueError("wrong dimension or fabricated evidence")
                    criterion = next(c for c in request.intent.criteria if c.dimension == request.dimension)
                    if (criterion.applicability == "not_applicable") != (score.status == "not_applicable"):
                        raise ValueError("provider changed applicability")
                    if score.status == "scored" and not request.evidence:
                        raise ValueError("evidence-free score")
                    self.cache[key] = score
                    if score.status == "abstain":
                        state = "abstained"
                except TimeoutError:
                    score, state = self._abstain(request, "Provider timeout"), "timeout"
                except (ValueError, TypeError, AttributeError):
                    score, state = self._abstain(request, "Provider contract rejected"), "invalid_output"
                except Exception:
                    # Do not persist arbitrary provider exception strings/secrets in public traces.
                    score, state = self._abstain(request, "Provider failed"), "provider_error"
            note = score.rationale if state != "completed" else note
            trace.append(TraceStep(dimension=request.dimension, state=state, request_hash=request.digest, note=note))
            output.append(AgentAssessment(id=f"agent-{run.id}-r{run.revision}-{version.id}-v{version.revision}-{request.dimension}-{request.digest}", created_at=created_at,
                agent_name=AGENTS[request.dimension], evaluator=version.ref, model_run=run.ref, rubric=version.rubric,
                result=score, alternative_hypotheses=("Camera-relative appearance may differ from world motion",) if request.dimension == Dimension.MOTION else (),
                suggested_test="Inspect full temporal coverage and compare a controlled alternative; human approval required for execution.",
                recommended_intervention="Human review of evidence and declared intent", source_mode="deterministic_fixture", request_hash=request.digest))
        return SwarmResult(assessments=tuple(output), trace=tuple(trace), calls=calls)

    @staticmethod
    def _abstain(request, reason):
        return DimensionScore(dimension=request.dimension, status="abstain", rationale=reason)
