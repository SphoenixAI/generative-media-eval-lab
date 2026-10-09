"""Bounded local-file ingestion and frame addressing. No visual judgments."""
from bisect import bisect_left
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile

from .domain import MediaAsset
from .pilot_domain import ToolIdentity, FrameTime, VideoMetadata, MediaIngestion, DerivativeManifest, ExtractedFrame

MAX_BYTES = 2_000_000_000
MAX_SECONDS = 300
MAX_FRAMES = 90_000
CONTAINERS = "mov,matroska,webm,avi,mpegts,mpeg,ogg,asf"
EXTENSIONS = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".ts", ".mpeg", ".mpg", ".ogv", ".wmv"}


class MediaError(ValueError):
    """Unknown/unavailable media is an operational error, never a quality score."""


def hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_local(path: str | Path) -> Path:
    if "://" in str(path):
        raise MediaError("Only local video files are accepted; URLs are disabled")
    result = Path(path).expanduser().resolve(strict=True)
    if not result.is_file() or result.suffix.lower() not in EXTENSIONS:
        raise MediaError("Expected a local supported video container")
    if not 0 < result.stat().st_size <= MAX_BYTES:
        raise MediaError("Local video must be nonempty and at most 2 GB")
    return result


def within(root: Path, relative: str) -> Path:
    if Path(relative).is_absolute():
        raise MediaError("Manifest path must be relative to media store")
    result = (root / relative).resolve()
    if not result.is_relative_to(root.resolve()):
        raise MediaError("Manifest path escapes media store")
    return result


def run_tool(argv: list[str], timeout: float = 120, max_output: int = 64_000_000, reject_diagnostics: bool = False) -> bytes:
    """No shell/stdin/network. Disk-backed capture avoids unbounded in-memory stdout."""
    env = {**os.environ, "LC_ALL":"C", "TZ":"UTC"}
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        try:
            result = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=out, stderr=err, timeout=timeout, env=env, check=False)
        except (subprocess.TimeoutExpired, OSError) as exc:
            raise MediaError(f"Media tool failed or timed out: {type(exc).__name__}") from exc
        if out.tell() > max_output:
            raise MediaError("Media tool output exceeded limit")
        if result.returncode or (reject_diagnostics and err.tell()):
            err.seek(0)
            detail = err.read(1500).decode(errors="replace")
            raise MediaError(f"Media tool returned {result.returncode}: {detail}")
        out.seek(0)
        return out.read()


class MediaTools:
    def __init__(self, ffmpeg: str | Path | None = None, ffprobe: str | Path | None = None):
        root = Path(__file__).resolve().parents[2]
        self.paths, self.identities = {}, {}
        for name, provided in (("ffmpeg",ffmpeg),("ffprobe",ffprobe)):
            value = provided or os.environ.get("EVAL_LAB_"+name.upper())
            if not value:
                local = root/".tools"/name
                value = str(local) if local.is_file() else shutil.which(name)
            if not value or not Path(value).is_file():
                raise MediaError(f"{name} unavailable; install FFmpeg or set EVAL_LAB_{name.upper()}")
            path = Path(value).resolve()
            output = run_tool([str(path), "-version"],timeout=10).decode(errors="replace")
            self.paths[name] = path
            self.identities[name] = ToolIdentity(name=name,version=output.strip(),executable_sha256=hash_file(path))

    def invoke(self, name: str, args: list[str]) -> bytes:
        return run_tool([str(self.paths[name]),*args],reject_diagnostics=True)


def parse_probe(stream_document: dict, frame_document: dict) -> VideoMetadata:
    streams = [s for s in stream_document.get("streams",[]) if s.get("codec_type")=="video" and not s.get("disposition",{}).get("attached_pic")]
    if len(streams)!=1:
        raise MediaError("Pilot 0 requires exactly one video stream (attached pictures excluded)")
    stream=streams[0]
    try:
        base=Fraction(stream["time_base"])
        if base<=0:
            raise ValueError("time base")
        raw_frames=frame_document["frames"]
        if not 1 <= len(raw_frames) <= MAX_FRAMES:
            raise MediaError("Missing or excessive decoded frame index")
        points=[]
        for raw in raw_frames:
            if "best_effort_timestamp" not in raw:
                raise MediaError("Missing frame timestamp; temporal evidence remains unknown")
            pts=int(raw["best_effort_timestamp"])
            duration=raw.get("duration_time",raw.get("pkt_duration_time"))
            seconds=float(Decimal(str(duration))) if duration is not None else None
            points.append((pts,seconds if seconds and seconds>0 else None))
        start=points[0][0]
        times=[float((pts-start)*base) for pts,_ in points]
        reported=stream.get("avg_frame_rate","0/0")
        fps=float(Fraction(reported)) if reported not in ("0/0","N/A","0") else 0
        if not fps:
            fps=(len(times)-1)/times[-1] if len(times)>1 and times[-1]>0 else 0
        if not fps or not math.isfinite(fps):
            raise MediaError("Frame rate/duration unavailable")
        last_duration=points[-1][1] or (times[-1]-times[-2] if len(times)>1 else 1/fps)
        duration_basis="last_frame_duration" if points[-1][1] else ("last_interval_estimate" if len(times)>1 else "average_fps_estimate")
        duration=times[-1]+last_duration
        if duration>MAX_SECONDS:
            raise MediaError("Pilot clip exceeds 300 seconds")
        intervals=[b-a for a,b in zip(times,times[1:])]
        variable=bool(intervals and max(intervals)-min(intervals)>float(base)*1.1)
        rotation=next((float(s["rotation"]) for s in stream.get("side_data_list",[]) if "rotation" in s),float(stream.get("tags",{}).get("rotate",0)))
        return VideoMetadata(stream_index=stream["index"],codec=stream["codec_name"],container=stream_document["format"]["format_name"],
            width=stream["width"],height=stream["height"],duration_seconds=duration,duration_basis=duration_basis,average_fps=fps,time_base=stream["time_base"],source_start_seconds=float(start*base),
            variable_frame_rate=variable,pixel_format=stream["pix_fmt"],color_space=stream.get("color_space"),color_transfer=stream.get("color_transfer"),
            color_primaries=stream.get("color_primaries"),color_range=stream.get("color_range"),rotation_degrees=rotation,sample_aspect_ratio=stream.get("sample_aspect_ratio"),
            audio_present=any(s.get("codec_type")=="audio" for s in stream_document.get("streams",[])),
            frames=tuple(FrameTime(index=i,pts=pts,source_seconds=float(pts*base),seconds=times[i],duration_seconds=length) for i,(pts,length) in enumerate(points)))
    except (KeyError,ValueError,TypeError,ZeroDivisionError,InvalidOperation) as exc:
        raise MediaError(f"Cannot build a reliable decoded timeline: {exc}") from exc


class MediaStore:
    def __init__(self, root: Path, tools: MediaTools | None = None):
        self.root=root.resolve()
        self.root.mkdir(parents=True,exist_ok=True)
        self.tools=tools or MediaTools()

    def ingest(self, source: str | Path, *, rights_status="unknown") -> tuple[MediaAsset,MediaIngestion]:
        source=resolve_local(source)
        with tempfile.TemporaryDirectory(prefix=".ingest-",dir=self.root) as temp:
            staging=Path(temp)
            copied=staging/("source"+source.suffix.lower())
            before=source.stat()
            shutil.copyfile(source,copied)
            digest=hash_file(copied)
            after=source.stat()
            if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino) or digest!=hash_file(source):
                raise MediaError("Source changed during copy; no ingestion committed")
            args=["-v","error","-protocol_whitelist","file","-format_whitelist",CONTAINERS]
            info=json.loads(self.tools.invoke("ffprobe",args+["-show_streams","-show_format","-of","json",str(copied)]))
            video_streams=[s for s in info.get("streams",[]) if s.get("codec_type")=="video" and not s.get("disposition",{}).get("attached_pic")]
            if len(video_streams)!=1:
                raise MediaError("Pilot 0 requires exactly one video stream")
            duration=video_streams[0].get("duration",info.get("format",{}).get("duration"))
            if duration is not None and (not math.isfinite(float(duration)) or float(duration)>MAX_SECONDS):
                raise MediaError("Pilot clip exceeds 300 seconds or has invalid duration")
            frames=json.loads(self.tools.invoke("ffprobe",args+["-select_streams","V:0","-show_frames","-show_entries","frame=best_effort_timestamp,duration_time,pkt_duration_time","-of","json",str(copied)]))
            metadata=parse_probe(info,frames)
            if hash_file(copied)!=digest:
                raise MediaError("Copied media changed during probing")
            # Exclude only transient path; retain raw probe metadata for independent inspection.
            info.get("format",{}).pop("filename",None)
            probe_bytes=json.dumps({"streams_and_format":info,"frames":frames},sort_keys=True,separators=(",",":"),allow_nan=False).encode()
            (staging/"probe.json").write_bytes(probe_bytes)
            bundle_key=sha256((digest+self.tools.identities["ffprobe"].model_dump_json()+"pilot-local-video-v1").encode()).hexdigest()
            bundle=self.root/"originals"/bundle_key
            relative=str((bundle/copied.name).relative_to(self.root))
            asset=MediaAsset(id="media-"+bundle_key,type="video",storage_reference=str(bundle/copied.name),checksum=digest,
                duration=metadata.duration_seconds,fps=metadata.average_fps,width=metadata.width,height=metadata.height,provenance="uploaded",rights_status=rights_status)
            ingestion=MediaIngestion(id="ingest-"+bundle_key,media=asset.ref,original_name=source.name,source_sha256=digest,source_size_bytes=copied.stat().st_size,
                original_relative_path=relative,probe_relative_path=str((bundle/"probe.json").relative_to(self.root)),probe_sha256=sha256(probe_bytes).hexdigest(),
                metadata=metadata,probe_tool=self.tools.identities["ffprobe"])
            if bundle.exists():
                old_asset=MediaAsset.model_validate_json((bundle/"asset.json").read_text())
                old=MediaIngestion.model_validate_json((bundle/"ingestion.json").read_text())
                self.verify(old)
                if old.source_sha256!=digest or old.probe_sha256!=ingestion.probe_sha256 or old.metadata!=metadata or old.probe_tool!=ingestion.probe_tool or old.media!=old_asset.ref:
                    raise MediaError("Existing ingestion differs from current probe")
                return old_asset,old
            (staging/"asset.json").write_text(asset.canonical())
            (staging/"ingestion.json").write_text(ingestion.canonical())
            bundle.parent.mkdir(exist_ok=True)
            staging.rename(bundle)
            return asset,ingestion

    def verify(self, ingestion: MediaIngestion, derivative: DerivativeManifest | None = None) -> Path:
        source=within(self.root,ingestion.original_relative_path)
        if not source.is_file() or source.stat().st_size!=ingestion.source_size_bytes or hash_file(source)!=ingestion.source_sha256:
            raise MediaError("Original missing or checksum mismatch: evidence availability UNKNOWN")
        probe=within(self.root,ingestion.probe_relative_path)
        if not probe.is_file() or hash_file(probe)!=ingestion.probe_sha256:
            raise MediaError("Probe missing or checksum mismatch: evidence availability UNKNOWN")
        if derivative:
            if derivative.ingestion!=ingestion.ref or derivative.source_sha256!=ingestion.source_sha256:
                raise MediaError("Derivative source mismatch")
            for frame in derivative.frames:
                path=within(self.root,frame.relative_path)
                if not path.is_file() or hash_file(path)!=frame.sha256:
                    raise MediaError("Frame missing or checksum mismatch: evidence availability UNKNOWN")
        return source

    def extract(self, ingestion: MediaIngestion, timestamps: tuple[float,...]) -> DerivativeManifest:
        source=self.verify(ingestion)
        targets=tuple(sorted(timestamps))
        if not 1<=len(targets)<=256 or len(set(targets))!=len(targets) or any(isinstance(t,bool) or not math.isfinite(t) or t<0 or t>=ingestion.metadata.duration_seconds for t in targets):
            raise MediaError("Provide 1-256 unique finite timestamps in [0, duration)")
        times=[f.seconds for f in ingestion.metadata.frames]
        selected=[]
        for target in targets:
            index=bisect_left(times,target)
            if index==len(times):
                raise MediaError("No frame begins at or after requested timestamp; choose an earlier timestamp")
            selected.append(ingestion.metadata.frames[index])
        policy={"source":ingestion.source_sha256,"probe":ingestion.probe_sha256,"targets":targets,"tool":self.tools.identities["ffmpeg"].model_dump(),"policy":"first-frame-at-or-after-v1"}
        key=sha256(json.dumps(policy,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        bundle=self.root/"derivatives"/key
        if bundle.exists():
            old=DerivativeManifest.model_validate_json((bundle/"manifest.json").read_text())
            self.verify(ingestion,old)
            if old.id!="derivative-"+key:
                raise MediaError("Derivative manifest identity mismatch")
            return old
        template=("-v","error","-nostdin","-xerror","-threads","1","-filter_threads","1","-protocol_whitelist","file","-format_whitelist",CONTAINERS,
            "-noautorotate","-i","{source}","-map",f"0:{ingestion.metadata.stream_index}","-an","-sn","-dn","-vf","select=eq(n\\,{frame_index})",
            "-frames:v","1","-fps_mode","passthrough","-threads:v","1","-c:v","png","-pix_fmt","rgb24","-map_metadata","-1","-fflags","+bitexact","-flags:v","+bitexact","-y","{output}")
        with tempfile.TemporaryDirectory(prefix=".frames-",dir=self.root) as temp:
            staging=Path(temp)
            extracted={}
            for frame in selected:
                if frame.index in extracted:
                    continue
                path=staging/f"frame-{frame.index:08d}.png"
                args=[arg.replace("{source}",str(source)).replace("{frame_index}",str(frame.index)).replace("{output}",str(path)) for arg in template]
                self.tools.invoke("ffmpeg",args)
                if not path.is_file() or path.stat().st_size<24:
                    raise MediaError("Decoder produced no usable frame")
                header=path.read_bytes()[:24]
                if header[:8]!=b"\x89PNG\r\n\x1a\n":
                    raise MediaError("Invalid PNG derivative")
                width,height=struct.unpack(">II",header[16:24])
                extracted[frame.index]=(path,hash_file(path),width,height)
            # Check that extraction used the same immutable source.
            self.verify(ingestion)
            manifest=DerivativeManifest(id="derivative-"+key,ingestion=ingestion.ref,media=ingestion.media,source_sha256=ingestion.source_sha256,
                tool=self.tools.identities["ffmpeg"],command_template=template,
                frames=tuple(ExtractedFrame(requested_seconds=t,frame_index=f.index,pts=f.pts,actual_seconds=f.seconds,
                    relative_path=str((bundle/extracted[f.index][0].name).relative_to(self.root)),sha256=extracted[f.index][1],width=extracted[f.index][2],height=extracted[f.index][3]) for t,f in zip(targets,selected)))
            (staging/"manifest.json").write_text(manifest.canonical())
            bundle.parent.mkdir(exist_ok=True)
            staging.rename(bundle)
            return manifest
