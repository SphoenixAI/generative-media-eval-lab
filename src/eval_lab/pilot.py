"""Local single-operator authoring service. Human content enters through typed forms."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import uuid
from typing import Literal

from pydantic import Field, model_validator
from .domain import Value, NonEmpty, Confidence, Criterion, IntentSpec, Evidence, Hypothesis, RelationClaim, Ref, CompetingSet
from .pilot_domain import PilotClip, PilotDataset, PilotSubmission, PilotSession, PilotSnapshot, PinnedArtifact
from .persistence import Repository, refs_in
from .media import MediaStore, MediaError, within


class IntentInput(Value):
    objective: NonEmpty
    audience: NonEmpty
    context: NonEmpty
    constraints: tuple[str,...] = ()
    prohibited_outcomes: tuple[str,...] = ()
    criteria: tuple[Criterion,...]
    revision_reason: str | None = None


class ObservationInput(Value):
    observation: NonEmpty
    timestamp_start: float = Field(ge=0)
    timestamp_end: float = Field(ge=0)
    confidence: Confidence | None = None
    derivative_id: str | None = None
    frame_indices: tuple[int,...] = ()


class HypothesisInput(Value):
    observed_problem: NonEmpty
    proposed_cause: NonEmpty
    confidence: Confidence | None = None
    supporting_evidence: tuple[str,...] = ()
    contradicting_evidence: tuple[str,...] = ()
    evidence_required: tuple[str,...]
    discriminating_test: NonEmpty
    predicted_observation: NonEmpty
    falsifying_observation: NonEmpty


class CompetingSetInput(Value):
    members: tuple[NonEmpty, ...] = Field(min_length=1)
    exclusive: bool = Field(strict=True)
    exhaustive: bool = Field(strict=True)


class RelationInput(Value):
    subject: NonEmpty  # o1 / h1 / intent; kind specified below
    subject_kind: Literal["Evidence","Hypothesis"]
    predicate: Literal["supports","contradicts","motivated_by","fulfills","violates","alternative_to","compatible_with","refines"]
    object: NonEmpty
    object_kind: Literal["Hypothesis","IntentSpec"]
    evidence: tuple[str,...] = ()
    purpose: NonEmpty
    scope: NonEmpty
    confidence: Confidence | None = None


class ConfidenceInput(Value):
    confidence: Confidence | None
    reason: NonEmpty
    new_evidence: tuple[str,...] = Field(min_length=1)
    evidence_role: Literal["supporting","contradicting","context_only"]


INPUT_TYPES={"intent":IntentInput,"observation":ObservationInput,"hypothesis":HypothesisInput,"relation":RelationInput,"confidence":ConfidenceInput,"competing-set":CompetingSetInput}
TEMPLATES={
    "intent":{"objective":"","audience":"","context":"","constraints":[],"prohibited_outcomes":[],"criteria":[{"dimension":None,"applicability":"required","rationale":"","acceptance":""}]},
    "observation":{"observation":"","timestamp_start":None,"timestamp_end":None,"confidence":None,"derivative_id":None,"frame_indices":[]},
    "hypothesis":{"observed_problem":"","proposed_cause":"","confidence":None,"supporting_evidence":[],"contradicting_evidence":[],"evidence_required":[""],"discriminating_test":"","predicted_observation":"","falsifying_observation":""},
    "relation":{"subject":"","subject_kind":"Evidence","predicate":"supports","object":"","object_kind":"Hypothesis","evidence":[],"purpose":"","scope":"","confidence":None},
    "confidence":{"confidence":None,"reason":"","new_evidence":[],"evidence_role":None},
    "competing-set":{"members":[],"exclusive":None,"exhaustive":None},
}


def now():
    return datetime.now(timezone.utc)


def read_human_form(kind: str, path: Path):
    raw=json.loads(path.read_text())
    def nonblank(value):
        if isinstance(value,str) and not value.strip():
            raise ValueError("Blank draft text cannot be recorded as a human judgment")
        if isinstance(value,dict):
            for item in value.values(): nonblank(item)
        if isinstance(value,list):
            for item in value: nonblank(item)
    nonblank(raw)
    return INPUT_TYPES[kind].model_validate(raw)


def local_id(value: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}",value):
        raise ValueError("Use a 1-64 character ID containing letters, numbers, hyphen or underscore")
    return value


class PilotWorkspace:
    def __init__(self,root:Path):
        self.root=root.expanduser().resolve()
        self.root.mkdir(parents=True,exist_ok=True)
        self.repo=Repository("sqlite:///"+str(self.root/"pilot.sqlite"))
        self._store=None

    @property
    def store(self):
        if self._store is None:
            self._store=MediaStore(self.root/"media")
        return self._store

    def close(self):
        self.repo.close()

    def latest(self,kind,id):
        return self.repo.latest(Ref(kind=kind,id=id))

    def init(self,dataset_id:str,owner:str):
        local_id(dataset_id)
        try: return self.latest("PilotDataset",dataset_id)
        except KeyError: pass
        dataset=PilotDataset(id=dataset_id,owner=owner)
        self.repo.put(dataset)
        return dataset

    def register(self,dataset_id,clip_id,path,author,label,selection_reason=None,provenance_note=None,rights_status="unknown"):
        local_id(clip_id)
        dataset=self.latest("PilotDataset",dataset_id)
        if dataset.state!="draft" or len(dataset.clips)>=20:
            raise ValueError("Register clips only in a draft dataset below 20 entries")
        if any(c.id==clip_id for c in dataset.clips):
            raise ValueError("Clip ID already registered")
        media,ingestion=self.store.ingest(path,rights_status=rights_status)
        if any(self.repo.get(self.repo.get(c).media).checksum==media.checksum for c in dataset.clips):
            raise ValueError("Duplicate bytes cannot count as another pilot clip")
        self.repo.put(media)
        self.repo.put(ingestion)
        clip=PilotClip(id=clip_id,media=media.ref,ingestion=ingestion.ref,selected_by=author,label=label,selection_reason=selection_reason,provenance_note=provenance_note)
        self.repo.put(clip)
        self.repo.put(dataset.model_copy(update={"revision":dataset.revision+1,"created_at":now(),"clips":dataset.clips+(clip.ref,)}))
        return clip

    def clip(self,id):
        return self.latest("PilotClip",id)

    def verify_clip(self,clip,derivative=None):
        return self.store.verify(self.repo.get(clip.ingestion),derivative)

    def frames(self,clip_id,timestamps):
        clip=self.clip(clip_id)
        manifest=self.store.extract(self.repo.get(clip.ingestion),tuple(timestamps))
        self.repo.put(manifest)
        return manifest

    def _ref(self,clip,kind,short):
        if kind=="IntentSpec":
            if short!="intent" or clip.intent is None:
                raise ValueError("Use 'intent' for this clip's declared intention")
            return clip.intent
        namespace={"Evidence":"observation","Hypothesis":"hypothesis","RelationClaim":"relation"}[kind]
        # Explicit @revision permits linking older evidence without silent replacement.
        name,marker,revision=short.partition("@")
        local_id(name)
        id=f"{clip.id}:{namespace}:{name}"
        return self.repo.get(Ref(kind=kind,id=id,revision=int(revision))).ref if marker else self.latest(kind,id).ref

    def _submission(self,clip,artifact,author,**extra):
        submission=PilotSubmission(id="submission-"+uuid.uuid4().hex,clip=clip.ref,author=author,artifact=artifact.ref,**extra)
        self.repo.put(submission)
        return submission

    def _session_ref(self,clip,author,session):
        if not session: return None
        record=self.latest("PilotSession",session)
        if record.clip.id!=clip.id or record.author!=author or record.state!="active":
            raise ValueError("Select an active session for this clip and author")
        return record.ref

    def intent(self,clip_id,author,form:IntentInput):
        clip=self.clip(clip_id)
        if clip.intent and not form.revision_reason:
            raise ValueError("Changing intent requires a human revision_reason")
        intent=IntentSpec(id=clip.id+":intent",revision=1 if clip.intent is None else clip.intent.revision+1,owner=author,approved_by=author,
            authority="human_declared",supersedes=clip.intent,**form.model_dump(exclude={"revision_reason"}))
        self.repo.put(intent)
        clip=clip.model_copy(update={"revision":clip.revision+1,"created_at":now(),"intent":intent.ref})
        self.repo.put(clip)
        for dataset in self.repo.all("PilotDataset"):
            if dataset!=self.latest("PilotDataset",dataset.id): continue
            if any(c.id==clip.id for c in dataset.clips):
                # A changed creative context returns a dataset to draft; historic snapshots stay pinned.
                revised=dataset.model_copy(update={"revision":dataset.revision+1,"created_at":now(),"state":"draft","clips":tuple(clip.ref if c.id==clip.id else c for c in dataset.clips)})
                self.repo.put(revised)
        self._submission(clip,intent,author,revision_reason=form.revision_reason)
        return intent

    def observe(self,clip_id,author,id,form:ObservationInput,session=None):
        clip=self.clip(clip_id)
        session_ref=self._session_ref(clip,author,session)
        self.verify_clip(clip)
        derivative=self.latest("DerivativeManifest",form.derivative_id) if form.derivative_id else None
        if derivative: self.verify_clip(clip,derivative)
        evidence=Evidence(id=f"{clip.id}:observation:{local_id(id)}",media=clip.media,observation=form.observation,
            timestamp_start=form.timestamp_start,timestamp_end=form.timestamp_end,source="human_observation",method="Human-authored local viewing observation; no automatic interpretation",
            coverage="interval",author=author,independence_group="human:"+author)
        # Validate attachment before committing the actual observation.
        if derivative and (derivative.media!=clip.media or set(form.frame_indices)-{f.frame_index for f in derivative.frames} or any(not form.timestamp_start<=f.actual_seconds<=form.timestamp_end for f in derivative.frames if f.frame_index in form.frame_indices)):
            raise ValueError("Frames must belong to this clip and observation interval")
        if form.frame_indices and not derivative:
            raise ValueError("Frame indices require a derivative manifest")
        self.repo.put(evidence)
        self._submission(clip,evidence,author,derivative=derivative.ref if derivative else None,frame_indices=form.frame_indices,
            observation_confidence=form.confidence,session=session_ref)
        return evidence

    def hypothesize(self,clip_id,author,id,form:HypothesisInput,session=None):
        clip=self.clip(clip_id)
        session_ref=self._session_ref(clip,author,session)
        if clip.intent is None: raise ValueError("Declare creative intent before hypotheses")
        support=tuple(self._ref(clip,"Evidence",e) for e in form.supporting_evidence)
        contradict=tuple(self._ref(clip,"Evidence",e) for e in form.contradicting_evidence)
        hypothesis=Hypothesis(id=f"{clip.id}:hypothesis:{local_id(id)}",intent=clip.intent,
            supporting_evidence=support,contradicting_evidence=contradict,**form.model_dump(exclude={"supporting_evidence","contradicting_evidence"}))
        self.repo.put(hypothesis)
        self._submission(clip,hypothesis,author,session=session_ref)
        return hypothesis

    def competing_set(self,clip_id,author,id,form:CompetingSetInput,session=None):
        clip=self.clip(clip_id)
        session_ref=self._session_ref(clip,author,session)
        if clip.intent is None: raise ValueError("Declare creative intent before competing sets")
        members=tuple(self._ref(clip,"Hypothesis",member) for member in form.members)
        identity=f"{clip.id}:competing-set:{local_id(id)}"
        try: prior=self.latest("CompetingSet",identity)
        except KeyError: prior=None
        item=CompetingSet(id=identity,intent=clip.intent,members=members,
            exclusive=form.exclusive,exhaustive=form.exhaustive,
            revision=prior.revision+1 if prior else 1,supersedes=prior.ref if prior else None)
        self.repo.put(item)
        self._submission(clip,item,author,session=session_ref)
        return item

    def relate(self,clip_id,author,id,form:RelationInput,session=None):
        clip=self.clip(clip_id)
        session_ref=self._session_ref(clip,author,session)
        if clip.intent is None: raise ValueError("Declare creative intent before relations")
        subject=self._ref(clip,form.subject_kind,form.subject)
        object=self._ref(clip,form.object_kind,form.object)
        evidence=tuple(self._ref(clip,"Evidence",e) for e in form.evidence)
        claim=RelationClaim(id=f"{clip.id}:relation:{local_id(id)}",subject=subject,object=object,predicate=form.predicate,intent=clip.intent,
            evidence=evidence,asserted_by=author,epistemic_status="asserted",purpose=form.purpose,scope=form.scope,confidence=form.confidence,valid_from=now())
        self.repo.put(claim)
        self._submission(clip,claim,author,session=session_ref)
        return claim

    def revise_confidence(self,clip_id,author,id,form:ConfidenceInput):
        clip=self.clip(clip_id)
        prior=self.repo.get(self._ref(clip,"Hypothesis",id))
        if prior.intent!=clip.intent:
            raise ValueError("Intent has changed; keep old hypothesis intact and author a new one under current intent")
        evidence=tuple(self._ref(clip,"Evidence",e) for e in form.new_evidence)
        old_evidence=set(prior.supporting_evidence+prior.contradicting_evidence)
        previous=[s for s in self.repo.all("PilotSubmission") if s.artifact.kind=="Hypothesis" and s.artifact.id==prior.id]
        old_evidence.update(e for s in previous for e in s.new_evidence)
        if not set(evidence)-old_evidence:
            raise ValueError("Confidence revision must identify newly supplied evidence")
        updates={"revision":prior.revision+1,"created_at":now(),"confidence":form.confidence}
        if form.evidence_role!="context_only":
            field=form.evidence_role+"_evidence"
            updates[field]=tuple(dict.fromkeys(getattr(prior,field)+evidence))
        revised=prior.model_copy(update=updates)
        self.repo.put(revised)
        self._submission(clip,revised,author,revision_reason=form.reason,new_evidence=evidence)
        return revised

    def session_start(self,clip_id,author):
        stamp=now()
        item=PilotSession(id="session-"+uuid.uuid4().hex,clip=self.clip(clip_id).ref,author=author,started_at=stamp,last_event_at=stamp)
        self.repo.put(item)
        return item

    def session_event(self,id,event):
        prior=self.latest("PilotSession",id)
        target={"pause":"paused","resume":"active","finish":"finished"}[event]
        if prior.state=="finished" or (event=="pause" and prior.state!="active") or (event=="resume" and prior.state!="paused"):
            raise ValueError("Invalid timer transition")
        stamp=now()
        elapsed=(stamp-prior.last_event_at).total_seconds()
        if elapsed<0: raise ValueError("Clock moved backwards; preserve session and review timing")
        item=prior.model_copy(update={"revision":prior.revision+1,"created_at":stamp,"last_event_at":stamp,"state":target,
            "active_seconds":prior.active_seconds+(elapsed if prior.state=="active" else 0)})
        self.repo.put(item)
        return item

    def ready(self,dataset_id):
        dataset=self.latest("PilotDataset",dataset_id)
        for ref in dataset.clips: self.verify_clip(self.repo.get(ref))
        updated=dataset.model_copy(update={"revision":dataset.revision+1,"created_at":now(),"state":"ready"})
        self.repo.put(updated)
        return updated

    def status(self,dataset_id):
        dataset=self.latest("PilotDataset",dataset_id)
        rows=[]
        for ref in dataset.clips:
            clip=self.repo.get(ref)
            try:
                self.verify_clip(clip)
                available="VERIFIED"
                reason=None
            except (MediaError,FileNotFoundError,OSError) as exc:
                available="UNKNOWN"
                reason=str(exc)
            submissions=[s for s in self.repo.all("PilotSubmission") if s.clip.id==clip.id]
            evidence_states=[]
            for submission in submissions:
                if submission.artifact.kind!="Evidence": continue
                state,problem=available,reason
                try:
                    if submission.derivative:
                        self.verify_clip(clip,self.repo.get(submission.derivative))
                except (MediaError,FileNotFoundError,OSError) as exc:
                    state,problem="UNKNOWN",str(exc)
                evidence_states.append({"ref":submission.artifact.model_dump(),"availability":state,"reason":problem})
            rows.append({"clip":clip.ref.model_dump(),"label":clip.label,"media_sha256":self.repo.get(clip.media).checksum,
                "media_availability":available,"reason":reason,"intent":clip.intent.model_dump() if clip.intent else None,
                "human_submissions":len(submissions),"evidence":evidence_states,"quality_verdict":"UNKNOWN","automated_judgments":0})
        return {"dataset":dataset.model_dump(mode="json"),"clips":rows,"comparison_conditions":"NOT_RUN","scope":"PILOT0_HUMAN_AUTHORING"}

    def snapshot(self,dataset_id,id):
        local_id(id)
        dataset=self.latest("PilotDataset",dataset_id)
        ids={r.id for r in dataset.clips}
        roots=[dataset.ref]
        for ref in dataset.clips: self.verify_clip(self.repo.get(ref))
        for kind in ("PilotSubmission","PilotSession","DerivativeManifest"):
            for artifact in self.repo.all(kind):
                if kind=="DerivativeManifest":
                    if artifact.ingestion not in {self.repo.get(c).ingestion for c in dataset.clips}: continue
                    self.store.verify(self.repo.get(artifact.ingestion),artifact)
                elif artifact.clip.id not in ids: continue
                roots.append(artifact.ref)
        seen={}
        while roots:
            ref=roots.pop()
            if ref in seen: continue
            item=self.repo.get(ref)
            seen[ref]=item
            roots.extend(refs_in(item))
        ordered=sorted(seen,key=lambda r:(r.kind,r.id,r.revision))
        snapshot=PilotSnapshot(id=id,dataset=dataset.ref,records=tuple(PinnedArtifact(ref=r,sha256=seen[r].digest) for r in ordered))
        self.repo.put(snapshot)
        return snapshot

    def export_snapshot(self,snapshot_id):
        snapshot=self.latest("PilotSnapshot",snapshot_id)
        records=[]
        for pinned in snapshot.records:
            artifact=self.repo.get(pinned.ref)
            if artifact.digest!=pinned.sha256: raise ValueError("Snapshot hash mismatch")
            records.append({"ref":pinned.ref.model_dump(),"sha256":pinned.sha256,"artifact":artifact.model_dump(mode="json")})
        return {"snapshot":snapshot.model_dump(mode="json"),"records":records,"visibility":"PRIVATE_LOCAL_NOT_PUBLISHED"}
