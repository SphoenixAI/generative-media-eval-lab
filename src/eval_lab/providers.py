"""Provider contracts. No network implementation is installed or called."""
import asyncio
import json
from hashlib import sha256
from types import MappingProxyType
from typing import Protocol
from .domain import Dimension, DimensionScore, Evidence, IntentSpec, PromptSpec, Ref, Value


class EvaluationRequest(Value):
    media_checksum: str
    prompt_text: str
    intent: IntentSpec
    rubric_digest: str
    dimension: Dimension
    evidence: tuple[Evidence, ...]
    fixture_code: str | None = None
    # No generating provider, model ID, human score, gold answer, or other agent output.

    @property
    def digest(self):
        return sha256(self.model_dump_json().encode()).hexdigest()


class MultimodalEvaluatorProvider(Protocol):
    mode: str
    identity: str
    async def assess(self, request: EvaluationRequest) -> DimensionScore: ...


class GenerationProvider(Protocol):
    async def generate(self, prompt: PromptSpec, *, maximum_cost_usd: float) -> bytes: ...


class EmbeddingProvider(Protocol):
    async def embed(self, media_checksum: str) -> tuple[float, ...]: ...


class DeterministicFixtureProvider:
    """A workflow simulator, not a media judge. Fixture lookup is deliberately explicit."""
    mode = "deterministic_fixture"
    def __init__(self, rules: dict[tuple[str, Dimension], int]):
        self._rules = MappingProxyType(dict(rules))

    @property
    def identity(self):
        manifest = sorted((code, str(dimension), score) for (code, dimension), score in self._rules.items())
        return "fixture-specialists-v1:" + sha256(json.dumps(manifest, separators=(",", ":")).encode()).hexdigest()

    async def assess(self, request: EvaluationRequest) -> DimensionScore:
        await asyncio.sleep(0)
        criterion = next(c for c in request.intent.criteria if c.dimension == request.dimension)
        if criterion.applicability == "not_applicable":
            return DimensionScore(dimension=request.dimension, status="not_applicable", rationale=criterion.rationale)
        if (request.fixture_code, request.dimension) not in self._rules or not request.evidence:
            return DimensionScore(dimension=request.dimension, status="abstain", rationale="No synthetic rule or evidence available.")
        if any(e.source != "synthetic_fixture" for e in request.evidence):
            raise ValueError("fixture provider cannot evaluate real media")
        return DimensionScore(dimension=request.dimension, status="scored", score=self._rules[(request.fixture_code, request.dimension)],
            confidence=0.5, evidence=tuple(e.ref for e in request.evidence),
            rationale="Synthetic rule output for software testing; confidence is uncalibrated and is not a correctness probability.")
