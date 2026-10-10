"""Pilot 0: register local clips and capture Sphoenix-authored evidence."""
import argparse
import json
import platform
from pathlib import Path
import subprocess
import sys

from .domain import Value
from .media import MediaError, MediaTools, within
from .pilot import PilotWorkspace, TEMPLATES, INPUT_TYPES, read_human_form
from .pilot_domain import PILOT_TYPES, PilotDataset
from .seals import seal_intent, verify_seal
from . import generation
from sqlalchemy.exc import SQLAlchemyError


def parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,default=Path("pilot-local"),help="Private local workspace; defaults to ./pilot-local")
    p.add_argument("--author",default="Sphoenix",help="Human authorship declaration; not authenticated identity")
    sub=p.add_subparsers(dest="command",required=True)
    seal=sub.add_parser("seal-intent", help="Append a private local intent seal", description="Seal a complete human-authored IntentSpecV2 FILE using RFC 8785 with integer literals only (safe integer range). Imports exact input; never edits it. Local time and declared Git metadata do not prove generation chronology.")
    seal.add_argument("file", type=Path, metavar="FILE")
    seal.add_argument("--git-commit", help="Declared full lowercase commit hash; requires --git-remote")
    seal.add_argument("--git-remote", help="Declared remote URL; requires --git-commit; no remote access")
    verify=sub.add_parser("verify-seal", help="Verify local seal integrity", description="Perform read-only verification by exact seal ID or original intent FILE path (all its seals against one captured source result). Missing evidence is UNKNOWN; corruption is INTEGRITY_FAILURE. Both exit nonzero; integrity is not a quality verdict.")
    verify.add_argument("target", metavar="ID|FILE")
    sub.add_parser("doctor")
    sc=sub.add_parser("schema"); sc.add_argument("--output",type=Path)
    dr=sub.add_parser("draft"); dr.add_argument("kind",choices=TEMPLATES); dr.add_argument("--output",type=Path,required=True)
    init=sub.add_parser("init"); init.add_argument("dataset",nargs="?",default="pilot0")
    reg=sub.add_parser("register"); reg.add_argument("dataset"); reg.add_argument("clip"); reg.add_argument("path",type=Path)
    reg.add_argument("--label",required=True); reg.add_argument("--selection-reason"); reg.add_argument("--provenance-note")
    reg.add_argument("--rights-status",choices=("unknown","owner_asserted","licensed"),default="unknown")
    reg.add_argument("--plan", help="Exact generation plan ID; PLANNED origin, otherwise FOUND")
    reg.add_argument("--intent", help="Existing intent ID@REV; required for a multi-intent plan")
    for cmd in ("plan", "selection"):
        sp=sub.add_parser(cmd, help="Append private human declarations; time and pins are application derived", description="See docs/generation-lifecycle.md for JSON fields and exact ID@REV references. Plans return a reference and digest; repeated selection IDs append corrections. No generation or sampling is performed.")
        if cmd=="selection": sp.add_argument("dataset")
        sp.add_argument("--file", type=Path, required=True)
    bi=sub.add_parser("bind-intent", help="Bind existing ID@REV; provenance is computed, quality remains UNKNOWN")
    bi.add_argument("clip"); bi.add_argument("--intent", required=True)
    bi.add_argument("--prompt-only", action="store_true", help="Explicit FOUND/v2 declaration; cannot promote a lineage")
    for cmd in ("status","ready","manifest"):
        sp=sub.add_parser(cmd); sp.add_argument("dataset",nargs="?",default="pilot0")
        if cmd=="manifest": sp.add_argument("--output",type=Path)
    fr=sub.add_parser("frames", help="Log first verified access attempt before extraction"); fr.add_argument("clip"); fr.add_argument("--at",type=float,nargs="+",required=True)
    op=sub.add_parser("open", help="Log first verified access attempt before launch; external viewing is undetectable"); op.add_argument("clip"); op.add_argument("--at",type=float)
    show=sub.add_parser("show"); show.add_argument("clip")
    descriptions={
        "competing-set":"Record a private hypothesis set with explicit exclusive/exhaustive flags. Members use IDs or ID@revision; repeating --id appends a pinned revision. Exhaustive sets add a structural RESIDUAL, without confidence arithmetic.",
        "relation":"Record a human relation. compatible_with and refines require distinct hypothesis endpoints; compatible_with cannot join pinned members of an exclusive set. refines records subject-to-object direction only.",
    }
    for kind,cmd in (("intent","intent"),("observation","observe"),("hypothesis","hypothesis"),("relation","relate"),("confidence","revise-confidence"),("competing-set","competing-set")):
        sp=sub.add_parser(cmd,description=descriptions.get(kind),help=descriptions.get(kind)); sp.add_argument("clip"); sp.add_argument("--file",type=Path,required=True)
        if kind in ("observation","hypothesis","relation","competing-set"): sp.add_argument("--id",required=True); sp.add_argument("--session")
        if kind=="confidence": sp.add_argument("--hypothesis",required=True)
    start=sub.add_parser("start"); start.add_argument("clip")
    for cmd in ("pause","resume","finish"):
        sp=sub.add_parser(cmd); sp.add_argument("session")
    snap=sub.add_parser("snapshot", description="Freeze private records, including checksum-linked intent binding history, plans, origins, selections, first-access events, contexts and pinned dependencies and seals for those exact intent revisions.", help="Freeze private records and intent binding history"); snap.add_argument("dataset"); snap.add_argument("--id",required=True); snap.add_argument("--output",type=Path)
    exp=sub.add_parser("export-snapshot", description="Export a frozen private snapshot with its pinned binding history, lifecycle records and retained seal events.", help="Export frozen private snapshot records"); exp.add_argument("id"); exp.add_argument("--output",type=Path)
    return p


def write_new(path:Path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x") as stream:
        stream.write(json.dumps(data,indent=2,sort_keys=True)+"\n")


def launch_file(path:Path):
    if platform.system()=="Darwin": command=["/usr/bin/open",str(path)]
    elif platform.system()=="Linux": command=["xdg-open",str(path)]
    else: raise MediaError(f"Open this verified local path manually: {path}")
    subprocess.run(command,check=True,timeout=15,stdin=subprocess.DEVNULL)


def main(argv=None):
    args=parser().parse_args(argv)
    workspace=None
    try:
        if args.command=="verify-seal":
            result=verify_seal(args.root,args.target)
            print(json.dumps(result,indent=2,sort_keys=True))
            return 0 if result["status"]=="VERIFIED" else 2
        elif args.command=="seal-intent":
            result=seal_intent(args.root,args.file,git_commit=args.git_commit,git_remote=args.git_remote)
        elif args.command=="doctor":
            tools=MediaTools()
            result={"tools":{name:identity.model_dump() for name,identity in tools.identities.items()},"local_video_only":True,"automated_media_judging":False}
        elif args.command=="schema":
            result={"dataset_manifest_schema":PilotDataset.model_json_schema(),"record_schemas":{cls.__name__:cls.model_json_schema() for cls in PILOT_TYPES},"human_form_schemas":{name:cls.model_json_schema() for name,cls in INPUT_TYPES.items()}}
        elif args.command=="draft":
            result=TEMPLATES[args.kind]
        else:
            workspace=PilotWorkspace(args.root)
            p=workspace
            if args.command=="init": result=p.init(args.dataset,args.author)
            elif args.command=="register":
                clip=p.register(args.dataset,args.clip,args.path,args.author,args.label,args.selection_reason,args.provenance_note,args.rights_status,plan=args.plan,intent=args.intent)
                result={**clip.model_dump(mode="json"), **generation.audit(p.repo, clip)}
            elif args.command=="plan": result=generation.pin(generation.record_plan(p.repo,json.loads(args.file.read_text())))
            elif args.command=="selection": result=generation.record_selection(p.repo,p.latest("PilotDataset",args.dataset),json.loads(args.file.read_text()))
            elif args.command=="bind-intent":
                binding=generation.bind_intent(p.repo,p.clip(args.clip),generation.exact(p.repo,args.intent),args.prompt_only)
                result={"binding":binding.model_dump(mode="json"), **generation.audit(p.repo,p.clip(args.clip))}
            elif args.command=="status": result=p.status(args.dataset)
            elif args.command=="ready": result=p.ready(args.dataset)
            elif args.command=="manifest": result=p.latest("PilotDataset",args.dataset)
            elif args.command=="frames": result=p.frames(args.clip,args.at)
            elif args.command=="open":
                clip=p.clip(args.clip)
                if args.at is None:
                    generation.first_access(p, clip)
                    path=p.verify_clip(clip)
                    result={"path":str(path),"view":"original_clip","time_origin":"first decoded video frame; source stream offset is in ingestion metadata"}
                else:
                    manifest=p.frames(args.clip,(args.at,)); frame=manifest.frames[0]
                    path=within(p.store.root,frame.relative_path)
                    result={"path":str(path),"view":"extracted_frame","derivative_id":manifest.id,"frame":frame.model_dump(),"transforms":manifest.transforms}
                launch_file(path)
            elif args.command=="show":
                clip=p.clip(args.clip)
                submissions=[s for s in p.repo.all("PilotSubmission") if s.clip.id==clip.id]
                result={"clip":clip.model_dump(mode="json"),"ingestion":p.repo.get(clip.ingestion).model_dump(mode="json"),
                    "submissions":[{"submission":s.model_dump(mode="json"),"artifact":p.repo.get(s.artifact).model_dump(mode="json")} for s in submissions], **generation.audit(p.repo, clip)}
            elif args.command=="intent": result=p.intent(args.clip,args.author,read_human_form("intent",args.file))
            elif args.command=="observe": result=p.observe(args.clip,args.author,args.id,read_human_form("observation",args.file),args.session)
            elif args.command=="hypothesis": result=p.hypothesize(args.clip,args.author,args.id,read_human_form("hypothesis",args.file),args.session)
            elif args.command=="competing-set": result=p.competing_set(args.clip,args.author,args.id,read_human_form("competing-set",args.file),args.session)
            elif args.command=="relate": result=p.relate(args.clip,args.author,args.id,read_human_form("relation",args.file),args.session)
            elif args.command=="revise-confidence": result=p.revise_confidence(args.clip,args.author,args.hypothesis,read_human_form("confidence",args.file))
            elif args.command=="start": result=p.session_start(args.clip,args.author)
            elif args.command in ("pause","resume","finish"): result=p.session_event(args.session,args.command)
            elif args.command=="snapshot":
                snapshot=p.snapshot(args.dataset,args.id)
                result=p.export_snapshot(snapshot.id)
            elif args.command=="export-snapshot": result=p.export_snapshot(args.id)
            else: raise ValueError("Unknown command")
        if isinstance(result,Value): result=result.model_dump(mode="json")
        if getattr(args,"output",None):
            write_new(args.output,result)
            print(json.dumps({"written":str(args.output.resolve()),"command":args.command}))
        else: print(json.dumps(result,indent=2,sort_keys=True,allow_nan=False))
        return 0
    except (ValueError,KeyError,OSError,subprocess.SubprocessError,SQLAlchemyError) as exc:
        print(json.dumps({"error":str(exc),"quality_verdict":"UNKNOWN","no_automatic_judgment":True}),file=sys.stderr)
        return 2
    finally:
        if workspace is not None: workspace.close()


if __name__=="__main__":
    raise SystemExit(main())
