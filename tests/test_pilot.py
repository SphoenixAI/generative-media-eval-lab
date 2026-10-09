"""Authorship tests contain explicit synthetic test text, not Sphoenix judgments."""
from datetime import timedelta
import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from test_media import media_tools,codec_videos

from eval_lab.domain import Criterion, Dimension, Ref
from eval_lab.media import MediaError, MediaStore
from eval_lab.pilot_domain import PilotDataset
from eval_lab.pilot import (PilotWorkspace, IntentInput, ObservationInput, HypothesisInput, RelationInput, ConfidenceInput, TEMPLATES, read_human_form)
from eval_lab.pilot_cli import main

AUTHOR="TEST_ONLY_OPERATOR"


def intent_form():
    return IntentInput(objective="Test-only intent text",audience="Test fixture",context="Codec workflow test; no real media judgment",criteria=(Criterion(dimension=Dimension.PROMPT,rationale="Test-only requirement",acceptance="Test-only anchor"),))


def hypothesis_form(**kw):
    return HypothesisInput(observed_problem="Test-only observation reference",proposed_cause="Test-only alternative",confidence=.2,
        evidence_required=("Test-only future data",),discriminating_test="Test-only proposed comparison, never executed",predicted_observation="Test-only prediction",falsifying_observation="Test-only falsifier",**kw)


@pytest.fixture
def pilot(tmp_path,media_tools,codec_videos):
    p=PilotWorkspace(tmp_path/"pilot")
    p._store=MediaStore(p.root/"media",media_tools)
    p.init("pilot0",AUTHOR)
    p.register("pilot0","clip01",codec_videos["cfr"],AUTHOR,"Test pattern only")
    yield p
    p.close()


def test_registration_does_not_invent_intent_run_or_judgment(pilot):
    status=pilot.status("pilot0")
    assert status["clips"][0]["media_availability"]=="VERIFIED"
    assert status["clips"][0]["quality_verdict"]=="UNKNOWN"
    assert pilot.clip("clip01").intent is None
    for kind in ("Evidence","Hypothesis","AgentAssessment","ModelRun","IntentSpec"):
        assert pilot.repo.all(kind)==()


def test_duplicate_bytes_and_ids_rejected(pilot,codec_videos):
    for id in ("clip01","different-name"):
        with pytest.raises(ValueError): pilot.register("pilot0",id,codec_videos["cfr"],AUTHOR,"Test only")
    assert len(pilot.latest("PilotDataset","pilot0").clips)==1


@pytest.mark.parametrize("count,state,valid",[(0,"draft",True),(11,"ready",False),(12,"ready",True),(20,"ready",True),(21,"draft",False)])
def test_dataset_size_contract(count,state,valid):
    kwargs=dict(id="pilot0",owner=AUTHOR,state=state,clips=tuple(Ref(kind="PilotClip",id=f"c{x}") for x in range(count)))
    if valid: assert len(PilotDataset(**kwargs).clips)==count
    else:
        with pytest.raises(ValidationError): PilotDataset(**kwargs)


def test_one_clip_cannot_claim_dataset_ready(pilot):
    with pytest.raises(ValueError): pilot.ready("pilot0")
    assert pilot.latest("PilotDataset","pilot0").state=="draft"


def test_human_intent_is_exact_and_versioned(pilot):
    first=pilot.intent("clip01",AUTHOR,intent_form())
    assert first.objective==intent_form().objective
    assert first.authority=="human_declared" and first.approved_by==AUTHOR
    second=pilot.intent("clip01",AUTHOR,intent_form().model_copy(update={"context":"New test-only context","revision_reason":"Test-only correction"}))
    assert second.supersedes==first.ref and second.revision==2
    assert pilot.repo.get(first.ref).context==intent_form().context
    assert pilot.repo.get(pilot.latest("PilotDataset","pilot0").clips[0]).intent==second.ref


def test_human_authoring_and_frame_attachments(pilot):
    pilot.intent("clip01",AUTHOR,intent_form())
    frames=pilot.frames("clip01",(.4,))
    session=pilot.session_start("clip01",AUTHOR)
    form=ObservationInput(observation="Exact TEST_ONLY text supplied by test",timestamp_start=.3,timestamp_end=.5,confidence=.65,derivative_id=frames.id,frame_indices=(4,))
    ev=pilot.observe("clip01",AUTHOR,"o1",form,session.id)
    assert ev.observation==form.observation and ev.author==AUTHOR
    note=pilot.repo.all("PilotSubmission")[-1]
    # IDs are random; find by artifact identity rather than insertion order.
    note=next(n for n in pilot.repo.all("PilotSubmission") if n.artifact==ev.ref)
    assert note.observation_confidence==.65 and note.derivative==frames.ref
    assert note.session==session.ref
    assert ev.timestamp_start==.3


@pytest.mark.parametrize("start,end,index",[(.6,.8,4),(.8,.2,4),(0,2,4),(.3,.5,100)])
def test_bad_timestamp_or_attachment_is_rejected(pilot,start,end,index):
    d=pilot.frames("clip01",(.4,))
    with pytest.raises(ValueError):
        pilot.observe("clip01",AUTHOR,"bad",ObservationInput(observation="TEST_ONLY",timestamp_start=start,timestamp_end=end,derivative_id=d.id,frame_indices=(index,)))
    assert not pilot.repo.all("Evidence")


def test_foreign_frame_rejected(pilot,codec_videos):
    pilot.register("pilot0","clip02",codec_videos["different"],AUTHOR,"Other technical test")
    d=pilot.frames("clip02",(0,))
    with pytest.raises(ValueError):
        pilot.observe("clip01",AUTHOR,"bad",ObservationInput(observation="TEST_ONLY",timestamp_start=0,timestamp_end=.2,derivative_id=d.id,frame_indices=(0,)))


def test_competing_hypotheses_and_intention_bearing_relation(pilot):
    pilot.intent("clip01",AUTHOR,intent_form())
    ev=pilot.observe("clip01",AUTHOR,"o1",ObservationInput(observation="TEST_ONLY",timestamp_start=0,timestamp_end=.2))
    h1=pilot.hypothesize("clip01",AUTHOR,"h1",hypothesis_form(supporting_evidence=("o1",)))
    h2=pilot.hypothesize("clip01",AUTHOR,"h2",hypothesis_form(contradicting_evidence=("o1",)))
    relation=pilot.relate("clip01",AUTHOR,"r1",RelationInput(subject="o1",subject_kind="Evidence",predicate="supports",object="h1",object_kind="Hypothesis",evidence=("o1",),purpose="TEST_ONLY purpose",scope="TEST_ONLY scope",confidence=.4))
    assert relation.subject==ev.ref and relation.object==h1.ref
    assert relation.intent==h1.intent==h2.intent
    assert relation.epistemic_status=="asserted"
    assert h1.discriminating_test==hypothesis_form().discriminating_test
    assert not pilot.repo.all("AgentAssessment")


def test_confidence_revision_preserves_old_judgment_and_records_new_evidence(pilot):
    pilot.intent("clip01",AUTHOR,intent_form())
    pilot.observe("clip01",AUTHOR,"o1",ObservationInput(observation="TEST_ONLY initial",timestamp_start=0,timestamp_end=.2))
    first=pilot.hypothesize("clip01",AUTHOR,"h1",hypothesis_form(supporting_evidence=("o1",)))
    before=pilot.snapshot("pilot0","before")
    export=pilot.export_snapshot(before.id)
    new=pilot.observe("clip01",AUTHOR,"o2",ObservationInput(observation="TEST_ONLY later",timestamp_start=.4,timestamp_end=.5))
    updated=pilot.revise_confidence("clip01",AUTHOR,"h1",ConfidenceInput(confidence=.7,reason="TEST_ONLY changed confidence",new_evidence=("o2",),evidence_role="contradicting"))
    assert updated.revision==2 and updated.confidence==.7
    assert pilot.repo.get(first.ref).confidence==.2
    assert new.ref in updated.contradicting_evidence
    note=next(n for n in pilot.repo.all("PilotSubmission") if n.artifact==updated.ref)
    assert note.revision_reason=="TEST_ONLY changed confidence" and note.new_evidence==(new.ref,)
    assert pilot.export_snapshot(before.id)==export
    after=pilot.snapshot("pilot0","after")
    assert after.records!=before.records


def test_confidence_revision_cannot_reuse_evidence_as_new(pilot):
    pilot.intent("clip01",AUTHOR,intent_form())
    pilot.observe("clip01",AUTHOR,"o1",ObservationInput(observation="TEST_ONLY",timestamp_start=0,timestamp_end=.2))
    h=pilot.hypothesize("clip01",AUTHOR,"h1",hypothesis_form(supporting_evidence=("o1",)))
    with pytest.raises(ValueError,match="newly supplied"):
        pilot.revise_confidence("clip01",AUTHOR,"h1",ConfidenceInput(confidence=.7,reason="TEST_ONLY",new_evidence=("o1",),evidence_role="supporting"))
    assert pilot.latest("Hypothesis",h.id).revision==1


def test_missing_evidence_file_yields_unknown_and_blocks_new_observation(pilot):
    source=pilot.verify_clip(pilot.clip("clip01"));source.unlink()
    assert pilot.status("pilot0")["clips"][0]["media_availability"]=="UNKNOWN"
    with pytest.raises(MediaError): pilot.observe("clip01",AUTHOR,"o1",ObservationInput(observation="TEST_ONLY",timestamp_start=0,timestamp_end=.1))
    assert pilot.repo.all("Evidence")==()
    with pytest.raises(MediaError): pilot.snapshot("pilot0","unavailable")


def test_missing_attached_frame_is_unknown_not_retracted_human_history(pilot):
    d=pilot.frames("clip01",(0,))
    ev=pilot.observe("clip01",AUTHOR,"o1",ObservationInput(observation="TEST_ONLY",timestamp_start=0,timestamp_end=.1,derivative_id=d.id,frame_indices=(0,)))
    (pilot.store.root/d.frames[0].relative_path).unlink()
    status=pilot.status("pilot0")["clips"][0]
    assert status["media_availability"]=="VERIFIED"
    assert status["evidence"][0]["availability"]=="UNKNOWN"
    assert pilot.repo.get(ev.ref)==ev


def test_timer_pause_resume_and_finish_preserve_intervals(pilot,monkeypatch):
    import eval_lab.pilot as module
    session=pilot.session_start("clip01",AUTHOR)
    monkeypatch.setattr(module,"now",lambda:session.started_at+timedelta(seconds=10))
    paused=pilot.session_event(session.id,"pause")
    assert paused.active_seconds==10
    monkeypatch.setattr(module,"now",lambda:session.started_at+timedelta(seconds=110))
    assert pilot.session_event(session.id,"resume").active_seconds==10
    monkeypatch.setattr(module,"now",lambda:session.started_at+timedelta(seconds=120))
    done=pilot.session_event(session.id,"finish")
    assert done.active_seconds==20 and done.condition=="PILOT0_AUTHORING"
    with pytest.raises(ValueError): pilot.session_event(session.id,"resume")


def test_invalid_session_rejects_before_authoring_record(pilot):
    session=pilot.session_start("clip01",AUTHOR)
    pilot.session_event(session.id,"pause")
    with pytest.raises(ValueError): pilot.observe("clip01",AUTHOR,"bad",ObservationInput(observation="TEST_ONLY",timestamp_start=0,timestamp_end=.1),session.id)
    assert not pilot.repo.all("Evidence")


@pytest.mark.parametrize("kind",list(TEMPLATES))
def test_unfilled_templates_cannot_become_judgments(tmp_path,kind):
    path=tmp_path/(kind+".json");path.write_text(json.dumps(TEMPLATES[kind]))
    with pytest.raises(ValueError): read_human_form(kind,path)


def test_cli_draft_never_overwrites_human_work(tmp_path,capsys):
    path=tmp_path/"hypothesis.json"
    assert main(["draft","hypothesis","--output",str(path)])==0
    path.write_text("human work")
    assert main(["draft","hypothesis","--output",str(path)])==2
    assert path.read_text()=="human work"


def test_cli_open_uses_verified_file_and_correct_frame(pilot,monkeypatch,capsys):
    import eval_lab.pilot_cli as cli
    paths=[]
    monkeypatch.setattr(cli,"launch_file",lambda path:paths.append(path))
    assert main(["--root",str(pilot.root),"open","clip01"])==0
    assert hash_file_for_test(paths[0])==pilot.repo.get(pilot.clip("clip01").media).checksum
    assert main(["--root",str(pilot.root),"open","clip01","--at","0.55"])==0
    assert paths[1].suffix==".png"
    assert '"actual_seconds": 0.6' in capsys.readouterr().out


def hash_file_for_test(path):
    from hashlib import sha256
    return sha256(path.read_bytes()).hexdigest()


def test_cli_rejects_nonexistent_and_remote_input_as_unknown(tmp_path,capsys):
    root=tmp_path/"root"
    assert main(["--root",str(root),"init"])==0
    assert main(["--root",str(root),"register","pilot0","clip01",str(tmp_path/"missing.mp4"),"--label","Test only"])==2
    assert '"quality_verdict": "UNKNOWN"' in capsys.readouterr().err
