"""Real codec/file tests use generated technical patterns, never pilot study clips."""
import json
from pathlib import Path
import shutil
import sys
import pytest

from eval_lab.media import MediaTools, MediaStore, MediaError, hash_file, parse_probe, resolve_local, run_tool, within


@pytest.fixture(scope="session")
def media_tools():
    # Missing tools fail explicitly; a green suite must actually exercise decoding.
    return MediaTools()


@pytest.fixture(scope="session")
def codec_videos(tmp_path_factory,media_tools):
    root=tmp_path_factory.mktemp("codec-test-patterns")
    paths={}
    variants={
        "cfr":[],
        "vfr":["-vf","setpts=if(lt(N\\,5)\\,N\\,2*N-5)","-fps_mode","vfr"],
        "offset":["-output_ts_offset","3"],
        "different":["-vf","hflip"],
    }
    for name,options in variants.items():
        path=root/(name+".mp4")
        media_tools.invoke("ffmpeg",["-v","error","-f","lavfi","-i","testsrc2=size=160x96:rate=10:duration=1",*options,"-c:v","mpeg4","-y",str(path)])
        paths[name]=path
    return paths


@pytest.fixture
def store(tmp_path,media_tools):
    return MediaStore(tmp_path/"media",media_tools)


def test_hash_copy_probe_and_actual_frame_mapping(store,codec_videos):
    media,ing=store.ingest(codec_videos["cfr"])
    assert media.checksum==hash_file(codec_videos["cfr"])==hash_file(store.verify(ing))
    assert (media.width,media.height,media.fps)==(160,96,10)
    assert ing.metadata.frames[0].seconds==0
    assert len(ing.metadata.frames)==10
    manifest=store.extract(ing,(.55,0))
    assert [(f.requested_seconds,f.actual_seconds,f.frame_index) for f in manifest.frames]==[(0,0,0),(.55,.6,6)]
    assert manifest.tool.executable_sha256==store.tools.identities["ffmpeg"].executable_sha256
    assert store.verify(ing,manifest).is_file()


def test_repeated_ingestion_is_idempotent_and_copy_survives_source_removal(store,codec_videos,tmp_path):
    source=tmp_path/"operator copy.mp4"; shutil.copyfile(codec_videos["cfr"],source)
    first=store.ingest(source)
    assert store.ingest(source)==first
    source.unlink()
    assert store.verify(first[1]).exists()


def test_independent_decode_is_byte_deterministic(store,codec_videos,tmp_path,media_tools):
    a,i=store.ingest(codec_videos["cfr"])
    other=MediaStore(tmp_path/"other",media_tools)
    _,j=other.ingest(codec_videos["cfr"])
    one,two=store.extract(i,(0,.5)),other.extract(j,(0,.5))
    assert one.id==two.id
    assert [f.sha256 for f in one.frames]==[f.sha256 for f in two.frames]
    assert one.frames==two.frames
    assert store.extract(i,(0,.5))==one


def test_variable_frame_rate_uses_decoded_pts_not_average_fps(store,codec_videos):
    _,i=store.ingest(codec_videos["vfr"])
    assert i.metadata.variable_frame_rate
    frame=store.extract(i,(.55,)).frames[0]
    assert frame.actual_seconds==pytest.approx(.7)
    assert frame.frame_index==6


def test_nonzero_source_start_maps_to_clip_relative_zero(store,codec_videos):
    _,i=store.ingest(codec_videos["offset"])
    assert i.metadata.source_start_seconds==pytest.approx(3)
    assert i.metadata.frames[0].seconds==0
    assert store.extract(i,(0,)).frames[0].pts>0


@pytest.mark.parametrize("timestamps",[(),(-1,), (float("nan"),),(float("inf"),),(1,),(.99,),(.5,.5),(True,),tuple(x/1000 for x in range(257))])
def test_invalid_or_unaddressable_timestamps_are_unknown_errors(store,codec_videos,timestamps):
    _,i=store.ingest(codec_videos["cfr"])
    with pytest.raises(MediaError): store.extract(i,timestamps)


@pytest.mark.parametrize("target",["original","probe","frame"])
def test_missing_or_corrupt_files_rejected(store,codec_videos,target):
    _,i=store.ingest(codec_videos["cfr"]); d=store.extract(i,(0,))
    path={"original":i.original_relative_path,"probe":i.probe_relative_path,"frame":d.frames[0].relative_path}[target]
    (store.root/path).write_bytes(b"changed")
    with pytest.raises(MediaError,match="UNKNOWN"):
        store.verify(i,d)


@pytest.mark.parametrize("value",["https://example.com/a.mp4","file:///tmp/a.mp4","pipe://0"])
def test_urls_rejected(value):
    with pytest.raises(MediaError): resolve_local(value)


def test_empty_invalid_and_nonvideo_inputs_leave_no_committed_bundle(store,tmp_path):
    empty=tmp_path/"empty.mp4";empty.touch()
    junk=tmp_path/"junk.mp4";junk.write_text("not a container")
    wrong=tmp_path/"list.m3u8";wrong.write_text("not a file list")
    for path in (empty,junk,wrong,tmp_path):
        with pytest.raises((MediaError,OSError)): store.ingest(path)
    assert not list(store.root.glob("originals/*"))
    assert not list(store.root.glob(".ingest-*"))


def test_audio_only_and_multivideo_are_rejected(store,tmp_path,media_tools):
    audio=tmp_path/"audio.mp4"
    media_tools.invoke("ffmpeg",["-v","error","-f","lavfi","-i","sine=duration=0.2","-c:a","aac","-y",str(audio)])
    multi=tmp_path/"multi.mkv"
    media_tools.invoke("ffmpeg",["-v","error","-f","lavfi","-i","testsrc2=size=32x32:rate=2:duration=1","-map","0:v","-map","0:v","-c:v","ffv1","-y",str(multi)])
    for path in (audio,multi):
        with pytest.raises(MediaError,match="one video stream"): store.ingest(path)


def test_rotation_and_audio_metadata_are_recorded(store,codec_videos,tmp_path,media_tools):
    path=tmp_path/"rotated.mp4"
    media_tools.invoke("ffmpeg",["-v","error","-display_rotation","90","-i",str(codec_videos["cfr"]),"-f","lavfi","-i","sine=duration=1","-c:v","copy","-c:a","aac","-y",str(path)])
    _,i=store.ingest(path)
    assert abs(i.metadata.rotation_degrees)==90
    assert i.metadata.audio_present
    frame=store.extract(i,(0,)).frames[0]
    assert (frame.width,frame.height)==(160,96)  # coded orientation, explicitly recorded


def test_local_paths_are_argv_not_shell(store,codec_videos,tmp_path):
    source=tmp_path/"a $(touch SHOULD_NOT_EXIST) ' clip.mp4"
    shutil.copyfile(codec_videos["cfr"],source)
    _,i=store.ingest(source)
    assert store.extract(i,(0,)).frames
    assert not (Path.cwd()/"SHOULD_NOT_EXIST").exists()


def test_path_traversal_rejected(tmp_path):
    for path in ("../escape",str(tmp_path/"absolute")):
        with pytest.raises(MediaError): within(tmp_path,path)


def test_source_changed_during_copy_is_rejected(store,codec_videos,tmp_path,monkeypatch):
    source=tmp_path/"source.mp4";shutil.copyfile(codec_videos["cfr"],source)
    original=shutil.copyfile
    def mutate(src,dest):
        result=original(src,dest)
        Path(src).write_bytes(Path(src).read_bytes()+b"modified")
        return result
    monkeypatch.setattr(shutil,"copyfile",mutate)
    with pytest.raises(MediaError,match="Source changed"): store.ingest(source)


def test_tool_timeout_and_output_limit():
    with pytest.raises(MediaError,match="timed out"):
        run_tool([sys.executable,"-c","import time;time.sleep(1)"],timeout=.01)
    with pytest.raises(MediaError,match="output exceeded"):
        run_tool([sys.executable,"-c","print('x'*1000)"],max_output=100)


def test_decode_error_on_stderr_cannot_be_hidden_by_exit_zero():
    with pytest.raises(MediaError):
        run_tool([sys.executable,"-c","import sys;sys.stderr.write('decode error');print('{}')"],reject_diagnostics=True)


def test_decoder_output_is_an_actual_selected_frame(store,codec_videos,tmp_path,media_tools):
    _,i=store.ingest(codec_videos["cfr"])
    selected=store.extract(i,(.55,)).frames[0]
    # Independently decode all frames, then compare the indexed image.
    media_tools.invoke("ffmpeg",["-v","error","-i",str(codec_videos["cfr"]),"-map","0:v:0","-fps_mode","passthrough","-threads:v","1","-c:v","png","-pix_fmt","rgb24","-map_metadata","-1","-fflags","+bitexact","-flags:v","+bitexact","-start_number","0",str(tmp_path/"all-%02d.png")])
    assert selected.sha256==hash_file(tmp_path/"all-06.png")


def test_failed_extraction_leaves_no_manifest(store,codec_videos,monkeypatch):
    _,i=store.ingest(codec_videos["cfr"])
    def fail(*args): raise MediaError("decode failed")
    monkeypatch.setattr(store.tools,"invoke",fail)
    with pytest.raises(MediaError): store.extract(i,(0,))
    assert not list(store.root.glob("derivatives/*"))
    assert not list(store.root.glob(".frames-*"))


@pytest.mark.parametrize("mutation",["missing_pts","duplicate_pts","negative_order","no_frames","zero_time_base"])
def test_unreliable_timeline_never_invents_timestamps(store,codec_videos,mutation):
    _,i=store.ingest(codec_videos["cfr"])
    raw=json.loads((store.root/i.probe_relative_path).read_text())
    frames=raw["frames"]
    if mutation=="missing_pts": frames["frames"][0].pop("best_effort_timestamp")
    if mutation=="duplicate_pts": frames["frames"][1]["best_effort_timestamp"]=frames["frames"][0]["best_effort_timestamp"]
    if mutation=="negative_order": frames["frames"][1]["best_effort_timestamp"]=-1
    if mutation=="no_frames": frames["frames"]=[]
    if mutation=="zero_time_base": raw["streams_and_format"]["streams"][0]["time_base"]="0/1"
    with pytest.raises(MediaError): parse_probe(raw["streams_and_format"],frames)


def test_duration_budget_blocks_before_full_decode(store,codec_videos,monkeypatch):
    import eval_lab.media as module
    monkeypatch.setattr(module,"MAX_SECONDS",.1)
    with pytest.raises(MediaError,match="300 seconds"): store.ingest(codec_videos["cfr"])


def test_file_size_budget_blocks(store,codec_videos,monkeypatch):
    import eval_lab.media as module
    monkeypatch.setattr(module,"MAX_BYTES",10)
    with pytest.raises(MediaError,match="2 GB"): store.ingest(codec_videos["cfr"])
