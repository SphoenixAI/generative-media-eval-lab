"""Pilot 0 file provenance and human workflow records; no automatic media judgments.

New artifact types leave accepted Phase 4 schemas/digests unchanged.
"""
from datetime import datetime
from typing import Annotated, Literal
from pydantic import ConfigDict, Field, model_validator
from .domain import Artifact, Value, Ref, NonEmpty, Confidence, ARTIFACT_TYPES, REFERENCE_KINDS

Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
ClipID = Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")]


class ToolIdentity(Value):
    name: Literal["ffmpeg", "ffprobe"]
    version: NonEmpty
    executable_sha256: Hash


class FrameTime(Value):
    index: Annotated[int, Field(ge=0)]
    pts: int
    source_seconds: float
    seconds: Annotated[float, Field(ge=0)]
    duration_seconds: Annotated[float, Field(gt=0)] | None = None


class VideoMetadata(Value):
    stream_index: int
    codec: NonEmpty
    container: NonEmpty
    width: Annotated[int, Field(gt=0)]
    height: Annotated[int, Field(gt=0)]
    duration_seconds: Annotated[float, Field(gt=0)]
    duration_basis: Literal["last_frame_duration", "last_interval_estimate", "average_fps_estimate"]
    average_fps: Annotated[float, Field(gt=0)]
    time_base: NonEmpty
    source_start_seconds: float
    variable_frame_rate: bool
    pixel_format: NonEmpty
    color_space: str | None = None
    color_transfer: str | None = None
    color_primaries: str | None = None
    color_range: str | None = None
    rotation_degrees: float = 0
    sample_aspect_ratio: str | None = None
    audio_present: bool
    frames: tuple[FrameTime, ...]

    @model_validator(mode="after")
    def frame_order(self):
        if not self.frames or self.frames[0].seconds != 0:
            raise ValueError("timeline must start at first decoded frame")
        if tuple(f.index for f in self.frames) != tuple(range(len(self.frames))):
            raise ValueError("noncontiguous decode index")
        if any(b.seconds <= a.seconds for a,b in zip(self.frames,self.frames[1:])):
            raise ValueError("nonincreasing frame timestamps cannot be addressed unambiguously")
        if self.frames[-1].seconds >= self.duration_seconds:
            raise ValueError("last frame exceeds media timeline")
        return self


class MediaIngestion(Artifact):
    media: Ref
    original_name: NonEmpty
    source_sha256: Hash
    source_size_bytes: Annotated[int, Field(gt=0)]
    original_relative_path: NonEmpty
    probe_relative_path: NonEmpty
    probe_sha256: Hash
    metadata: VideoMetadata
    probe_tool: ToolIdentity
    policy: Literal["pilot-local-video-v1"] = "pilot-local-video-v1"


class ExtractedFrame(Value):
    requested_seconds: Annotated[float, Field(ge=0)]
    frame_index: Annotated[int, Field(ge=0)]
    pts: int
    actual_seconds: Annotated[float, Field(ge=0)]
    relative_path: NonEmpty
    sha256: Hash
    width: Annotated[int, Field(gt=0)]
    height: Annotated[int, Field(gt=0)]


class DerivativeManifest(Artifact):
    ingestion: Ref
    media: Ref
    source_sha256: Hash
    tool: ToolIdentity
    policy: Literal["first-frame-at-or-after-v1"] = "first-frame-at-or-after-v1"
    transforms: Literal["software decode; one thread; coded orientation; RGB24 PNG; no tone mapping; no crop/scale"] = "software decode; one thread; coded orientation; RGB24 PNG; no tone mapping; no crop/scale"
    command_template: tuple[str, ...]
    frames: tuple[ExtractedFrame, ...]

    @model_validator(mode="after")
    def unique_targets(self):
        if not 1 <= len(self.frames) <= 256 or len({f.requested_seconds for f in self.frames}) != len(self.frames):
            raise ValueError("require 1-256 unique requested timestamps")
        return self


class PilotClip(Artifact):
    id: ClipID
    media: Ref
    ingestion: Ref
    selected_by: NonEmpty
    label: NonEmpty
    selection_reason: str | None = None
    intent: Ref | None = None
    provenance_note: str | None = None  # human-supplied; unknown generator stays unknown


class PilotDataset(Artifact):
    model_config = ConfigDict(json_schema_extra={"allOf":[{"if":{"properties":{"state":{"const":"ready"}},"required":["state"]},"then":{"properties":{"clips":{"minItems":12}}}}]})
    id: ClipID
    owner: NonEmpty
    state: Literal["draft", "ready"] = "draft"
    target_minimum: Literal[12] = 12
    target_maximum: Literal[20] = 20
    clips: tuple[Ref, ...] = Field(default=(),max_length=20)

    @model_validator(mode="after")
    def size_and_identity(self):
        if len(self.clips) > 20 or len({c.id for c in self.clips}) != len(self.clips):
            raise ValueError("dataset supports at most 20 distinct clips")
        if self.state == "ready" and len(self.clips) < 12:
            raise ValueError("ready dataset requires 12-20 manually selected clips")
        return self


class PilotSubmission(Artifact):
    clip: Ref
    author: NonEmpty
    authorship: Literal["human_entered"] = "human_entered"
    artifact: Ref
    derivative: Ref | None = None
    frame_indices: tuple[int, ...] = ()
    observation_confidence: Confidence | None = None
    confidence_meaning: Literal["subjective belief that the observation accurately describes visible media; uncalibrated"] = "subjective belief that the observation accurately describes visible media; uncalibrated"
    revision_reason: str | None = None
    new_evidence: tuple[Ref, ...] = ()
    session: Ref | None = None

    @model_validator(mode="after")
    def human_record(self):
        if self.revision != 1:
            raise ValueError("submission envelope is immutable; append another submission")
        if self.artifact.kind not in ("IntentSpec", "Evidence", "Hypothesis", "RelationClaim"):
            raise ValueError("unsupported pilot human artifact")
        if self.frame_indices and (self.derivative is None or self.artifact.kind != "Evidence"):
            raise ValueError("frame attachment needs evidence and derivative")
        if len(set(self.frame_indices)) != len(self.frame_indices):
            raise ValueError("duplicate frame index")
        return self


class PilotSession(Artifact):
    clip: Ref
    author: NonEmpty
    condition: Literal["PILOT0_AUTHORING"] = "PILOT0_AUTHORING"  # no comparison condition is running
    state: Literal["active", "paused", "finished"] = "active"
    started_at: datetime
    last_event_at: datetime
    active_seconds: Annotated[float, Field(ge=0)] = 0
    timing_method: Literal["operator-controlled UTC intervals; clock adjustments require review"] = "operator-controlled UTC intervals; clock adjustments require review"

    @model_validator(mode="after")
    def aware_times(self):
        if self.started_at.tzinfo is None or self.last_event_at.tzinfo is None or self.last_event_at < self.started_at:
            raise ValueError("invalid session clock interval")
        return self


class PinnedArtifact(Value):
    ref: Ref
    sha256: Hash


class PilotSnapshot(Artifact):
    dataset: Ref
    records: tuple[PinnedArtifact, ...]
    visibility: Literal["private_local"] = "private_local"


PILOT_TYPES = (MediaIngestion, DerivativeManifest, PilotClip, PilotDataset, PilotSubmission, PilotSession, PilotSnapshot)
ARTIFACT_TYPES.update({cls.__name__:cls for cls in PILOT_TYPES})
REFERENCE_KINDS.update({
    "MediaIngestion": {"media":"MediaAsset"},
    "DerivativeManifest": {"ingestion":"MediaIngestion", "media":"MediaAsset"},
    "PilotClip": {"media":"MediaAsset", "ingestion":"MediaIngestion", "intent":"IntentSpec"},
    "PilotDataset": {"clips":"PilotClip"},
    "PilotSubmission": {"clip":"PilotClip", "derivative":"DerivativeManifest", "new_evidence":"Evidence", "session":"PilotSession"},
    "PilotSession": {"clip":"PilotClip"},
    "PilotSnapshot": {"dataset":"PilotDataset"},
})


def validate_pilot_links(repo,item):
    """Referential and semantic checks; filesystem verification stays in media service."""
    if isinstance(item,MediaIngestion):
        media=repo.get(item.media)
        if media.checksum!=item.source_sha256 or media.provenance!="uploaded" or media.duration!=item.metadata.duration_seconds:
            raise ValueError("ingestion/media mismatch")
    if isinstance(item,DerivativeManifest):
        ingestion=repo.get(item.ingestion)
        if item.media!=ingestion.media or item.source_sha256!=ingestion.source_sha256:
            raise ValueError("derivative/media mismatch")
        for f in item.frames:
            if f.frame_index>=len(ingestion.metadata.frames):
                raise ValueError("derivative frame index outside timeline")
            actual=ingestion.metadata.frames[f.frame_index]
            if f.pts!=actual.pts or f.actual_seconds!=actual.seconds or f.actual_seconds<f.requested_seconds:
                raise ValueError("derivative timestamp mismatch")
    if isinstance(item,PilotClip):
        if repo.get(item.ingestion).media!=item.media:
            raise ValueError("clip ingestion/media mismatch")
        if item.revision>1:
            prior=repo.get(Ref(kind="PilotClip",id=item.id,revision=item.revision-1))
            if (prior.media,prior.ingestion,prior.selected_by)!=(item.media,item.ingestion,item.selected_by):
                raise ValueError("clip file identity is immutable; register a new clip")
    if isinstance(item,PilotDataset):
        checksums=[repo.get(repo.get(c).media).checksum for c in item.clips]
        if len(set(checksums))!=len(checksums):
            raise ValueError("duplicate media bytes are not independent clips")
        if item.state=="ready" and any(repo.get(c).intent is None for c in item.clips):
            raise ValueError("ready dataset needs human intent for every clip")
    if isinstance(item,PilotSubmission):
        clip=repo.get(item.clip)
        artifact=repo.get(item.artifact)
        if item.artifact.kind=="Evidence" and (artifact.media!=clip.media or artifact.author!=item.author or artifact.source!="human_observation"):
            raise ValueError("submission evidence/author mismatch")
        if item.artifact.kind=="IntentSpec" and (clip.intent!=artifact.ref or artifact.approved_by!=item.author or artifact.authority!="human_declared"):
            raise ValueError("submission intent/author mismatch")
        if item.artifact.kind in ("Hypothesis","RelationClaim") and artifact.intent!=clip.intent:
            raise ValueError("submission has different declared intent")
        if item.artifact.kind=="RelationClaim" and artifact.asserted_by!=item.author:
            raise ValueError("relation author mismatch")
        if item.artifact.kind=="Hypothesis" and item.artifact.revision>1 and (not item.revision_reason or not item.new_evidence):
            raise ValueError("revised judgment needs human rationale and new evidence")
        for ref in item.new_evidence:
            if repo.get(ref).media!=clip.media:
                raise ValueError("new evidence belongs to another clip")
        if item.derivative:
            manifest=repo.get(item.derivative)
            if manifest.media!=clip.media or item.artifact.kind!="Evidence":
                raise ValueError("attachment belongs to another clip or is not an observation")
            selected=[f for f in manifest.frames if f.frame_index in item.frame_indices]
            if set(item.frame_indices)-{f.frame_index for f in selected}:
                raise ValueError("attachment frame not in derivative manifest")
            if artifact.timestamp_start is None or any(not artifact.timestamp_start<=f.actual_seconds<=artifact.timestamp_end for f in selected):
                raise ValueError("attached frame outside evidence interval")
        if item.session:
            session=repo.get(item.session)
            if session.clip.id!=clip.id or session.author!=item.author:
                raise ValueError("session/annotation mismatch")
    if isinstance(item,PilotSession) and item.revision>1:
        prior=repo.get(Ref(kind="PilotSession",id=item.id,revision=item.revision-1))
        if prior.state=="finished" or (prior.clip,prior.author,prior.started_at,prior.condition)!=(item.clip,item.author,item.started_at,item.condition):
            raise ValueError("session identity immutable or already finished")
        if item.last_event_at<prior.last_event_at or item.active_seconds<prior.active_seconds:
            raise ValueError("invalid session clock progression")
    if isinstance(item,PilotSnapshot):
        if len({p.ref for p in item.records})!=len(item.records):
            raise ValueError("duplicate snapshot record")
        if item.dataset not in {p.ref for p in item.records}:
            raise ValueError("snapshot omits dataset")
        for pinned in item.records:
            if repo.get(pinned.ref).digest!=pinned.sha256:
                raise ValueError("snapshot content digest mismatch")
