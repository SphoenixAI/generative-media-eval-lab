"""TEST-ONLY lifecycle contracts: declared fixtures and generated patterns only."""
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
import pytest
from pydantic import ValidationError
from eval_lab import __version__, generation as g
from eval_lab.domain import Ref
from eval_lab.persistence import Repository
from eval_lab.pilot import PilotWorkspace
from eval_lab.pilot_domain import PilotClip, PilotDataset
from eval_lab.media import MediaStore, MediaError
from eval_lab import pilot_cli
from eval_lab.seals import SealRecord
from eval_lab.canonical_json import canonicalize, file_digest
from test_intent_v2 import T, intent, anchors, pin, binding, ORDERS
from test_media import media_tools, codec_videos

JSON = {"TEST-ONLY": [[], {}, [None, True, False, 2, 0.5, "TEST-ONLY"]]}
CONTROLS = {"TEST-ONLY-controls": [{"lights": [3, None]}, []]}
PLAN = dict(family_id="TEST-ONLY-family", arm="TEST-ONLY-locked", varied_factor="TEST-ONLY-camera",
    controlled_factors=CONTROLS, prompt="TEST-ONLY-pan", model="TEST-ONLY-model", model_version_string="TEST-ONLY-v1",
    settings=JSON, seed=None, n_planned=2, intent_revision_ids=[], notes="TEST-ONLY-private")


def seal(repo, i, stamp, name="TEST-ONLY-seal"):
    raw = i.model_dump(mode="json")
    item = SealRecord(id=name, created_at=stamp, sealed_at=stamp, tool_version=__version__,
        source_path="/tmp/TEST-ONLY.json", canonical_source=canonicalize(raw).decode(),
        file_sha256=file_digest(json.dumps(raw)), intent=pin(i))
    repo.put(item)
    return item


def setup(repo, *, stamp=T, planned=None, name="TEST-ONLY", checksum="a"*64):
    m, r = anchors(repo, name, checksum, stamp)
    c = PilotClip(id=name, media=m.ref, ingestion=r.ref, selected_by="TEST-ONLY", label="TEST-ONLY")
    repo.put(c)
    origin = g.record_origin(repo, c, planned)
    return c, origin


@pytest.fixture
def env(tmp_path):
    repo = Repository("sqlite:///"+str(tmp_path/"pilot.sqlite"))
    i = intent(); repo.put(i)
    yield repo, i
    repo.close()


def test_plan_family_json_reopen_and_validation(env, tmp_path, monkeypatch):
    repo, i = env
    monkeypatch.setattr(g, "now", lambda: T)
    a = g.record_plan(repo, PLAN | {"intent_revision_ids": ["TEST-ONLY-intent@1"]})
    b = g.record_plan(repo, PLAN | {"arm": "TEST-ONLY-tracking"})
    assert a.planned_at == T and a.tool_version == __version__ and a.intent_revision_ids == (pin(i),)
    assert a.family_id == b.family_id and a.arm != b.arm and a.canonical() == repo.get(a.ref).canonical()
    reopened = Repository("sqlite:///"+str(tmp_path/"pilot.sqlite"))
    for field, expected in (("settings", JSON), ("controlled_factors", CONTROLS)):
        assert reopened.get(a.ref).model_dump(mode="json")[field] == expected
    assert reopened.put(reopened.get(a.ref)) == a.digest
    reopened.close()
    for index, (change, error_type, error) in enumerate([
        ({"n_planned": 0}, ValidationError, "greater than 0"), ({"n_planned": True}, ValidationError, "valid integer"),
        ({"seed": True}, ValidationError, "valid integer"), ({"planned_at": T}, ValueError, "unsupported fields"),
        ({"intent_revision_ids": ["TEST-ONLY-intent"]}, ValueError, "exact ID@REV"),
        ({"settings": {"x": float("inf")}}, ValidationError, "Out of range float"),
        ({"intent_revision_ids": ["TEST-ONLY-intent@1"]*2}, ValidationError, "intent pins must be unique")]):
        with pytest.raises(error_type, match=error): g.record_plan(repo, PLAN | {"id": f"TEST-ONLY-bad-plan-{index}"} | change)
    for index, (change, error_type, error) in enumerate([({"revision": 2}, ValidationError, "less than or equal to 1"),
        ({"settings": {"x": float("nan")}}, ValidationError, "Out of range float"),
        ({"intent_revision_ids": (pin(i).model_copy(update={"sha256": "0"*64}),)}, ValueError, "digest")]):
        with pytest.raises(error_type, match=error): repo.put(a.model_copy(update={"id": f"TEST-ONLY-bad-copy-{index}", **change}))
    assert len(repo.all("GenerationPlan")) == 2


@pytest.mark.parametrize("model,field,value,error", [
    (g.ClipOrigin, "origin", "PLANNED", "origin/plan mismatch"),
    (g.ClipOrigin, "plan", "plan", "origin/plan mismatch"),
    (g.ClipOrigin, "clip", "revised", "origin requires original clip"),
    (g.ClipOrigin, "clip", "intent", "pin must reference PilotClip"),
    (g.ClipOrigin, "plan", "intent", "pin must reference GenerationPlan"),
    (g.FirstView, "media", "intent", "pin must reference MediaAsset"),
    (g.FirstView, "registration", "intent", "pin must reference MediaIngestion"),
    (g.BindingContext, "binding", "intent", "pin must reference IntentBinding"),
    (g.BindingContext, "origin", "intent", "pin must reference ClipOrigin"),
    (g.BindingContext, "seal", "intent", "pin must reference SealRecord"),
    (g.BindingContext, "view", "intent", "pin must reference FirstView")])
@pytest.mark.parametrize("entrypoint", ["constructor", "admission"])
def test_lifecycle_contract_constructor_and_copied_admission(env, model, field, value, error, entrypoint):
    repo, i = env; m, r = anchors(repo)
    clip = PilotClip(id="TEST-ONLY-contract-clip", media=m.ref, ingestion=r.ref, selected_by="TEST-ONLY", label="TEST-ONLY")
    revised = clip.model_copy(update={"revision": 2}); repo.put(clip); repo.put(revised)
    plan = g.record_plan(repo, PLAN); bound = binding(i, m, r); repo.put(bound)
    controls = {g.ClipOrigin: dict(clip=pin(clip), origin="FOUND"),
        g.FirstView: dict(media=pin(m), registration=pin(r)), g.BindingContext: dict(binding=pin(bound))}
    control = model(id="TEST-ONLY-control", **controls[model])
    change = {field: {"intent": pin(i), "plan": pin(plan), "revised": pin(revised)}.get(value, value)}
    bad = control.model_copy(update={"id": "TEST-ONLY-invalid", **change})
    with pytest.raises(ValidationError, match=error):
        if entrypoint == "constructor": model(**bad.model_dump())
        else: repo.put(bad)
    assert repo.all(model.__name__) == ()
    repo.put(control)
    assert repo.get(control.ref) == control


@pytest.mark.parametrize("name", ["IntentSpecV2", "PilotClip"])
def test_exact_unprefixed_kind_name_ids(env, name):
    repo, _ = env
    item = intent(id=name) if name == "IntentSpecV2" else setup(repo, name=name)[0]
    repo.put(item)
    assert g.exact(repo, name + "@1", name).ref.model_dump() == {"kind": name, "id": name, "revision": 1}


@pytest.mark.parametrize("s,p,r,sealed", ORDERS)
@pytest.mark.parametrize("view", [None, -1, 0, 1])
def test_stored_ordering_degrades_and_replays(env, monkeypatch, s, p, r, sealed, view):
    repo, i = env
    stamp = lambda v: T+timedelta(seconds=v)
    event = seal(repo, i, stamp(s))
    monkeypatch.setattr(g, "now", lambda: stamp(p))
    plan = g.record_plan(repo, PLAN | {"intent_revision_ids": ["TEST-ONLY-intent@1"]})
    c, origin = setup(repo, stamp=stamp(r), planned=plan)
    if view is not None:
        repo.put(g.FirstView(media=pin(repo.get(c.media)), registration=pin(repo.get(c.ingestion)), created_at=stamp(s+view)))
    b = g.bind_intent(repo, c, pin(i))
    expected = "SEALED" if sealed else ("CONTEMPORANEOUS" if view == 1 else "RECONSTRUCTED")
    assert b.provenance == expected == repo.get(b.ref).provenance
    context = repo.all("BindingContext")[0]
    assert context.seal == pin(event) and context.origin == pin(origin)
    assert repo.put(context) == context.digest and repo.get(b.ref).canonical() == b.canonical()


@pytest.mark.parametrize("case,expected", [("none", "RECONSTRUCTED"), ("old-seal", "RECONSTRUCTED"),
    ("unlisted", "CONTEMPORANEOUS"), ("prompt", "PROMPT_ONLY"), ("legacy", "RECONSTRUCTED")])
def test_found_missing_and_exact_revision_evidence(env, monkeypatch, case, expected):
    repo, i = env
    monkeypatch.setattr(g, "now", lambda: T+timedelta(seconds=1))
    plan = None
    if case in ("old-seal", "unlisted"):
        seal(repo, i, T)
        old = i; i = intent(revision=2, predecessor=pin(old)); repo.put(i)
        if case == "unlisted":
            seal(repo, i, T, "TEST-ONLY-new-seal")
            plan = g.record_plan(repo, PLAN | {"intent_revision_ids": ["TEST-ONLY-intent@1"]})
    c, _ = setup(repo, stamp=T+timedelta(seconds=2), planned=plan)
    if case == "legacy":
        from eval_lab.fixtures import seed
        i = seed(repo)["intent"]
    repo.put(g.FirstView(media=pin(repo.get(c.media)), registration=pin(repo.get(c.ingestion)), created_at=T+timedelta(seconds=3)))
    b = g.bind_intent(repo, c, pin(i), prompt_only=case=="prompt")
    assert b.provenance == expected
    if case in ("none", "legacy"): assert b.seal is None and b.plan is None


@pytest.mark.parametrize("planned_first", [True, False])
def test_alias_lineage_and_no_promotion(env, monkeypatch, planned_first):
    repo, i = env
    monkeypatch.setattr(g, "now", lambda: T-timedelta(seconds=1))
    plan = g.record_plan(repo, PLAN | {"intent_revision_ids": ["TEST-ONLY-intent@1"]})
    c, origin = setup(repo, planned=plan if planned_first else None)
    first = g.bind_intent(repo, c, pin(i))
    alias, _ = setup(repo, name="TEST-ONLY-alias", planned=None if planned_first else plan, stamp=T+timedelta(seconds=2))
    second = g.bind_intent(repo, alias, pin(i))
    assert (second.id, second.revision, second.predecessor) == (first.id, 2, pin(first))
    assert (second.media, second.registration, second.origin) == (first.media, first.registration, first.origin)
    assert repo.all("BindingContext")[-1].origin == pin(origin)
    seal(repo, i, T-timedelta(seconds=2))
    repo.put(g.FirstView(media=pin(repo.get(c.media)), registration=pin(repo.get(c.ingestion)), created_at=T))
    with pytest.raises(ValueError, match="cannot raise provenance"):
        g.bind_intent(repo, alias, pin(i))
    with pytest.raises(ValueError, match="FOUND|cannot raise provenance"):
        g.bind_intent(repo, alias, pin(i), prompt_only=True)
    assert repo.get(first.ref).canonical() == first.canonical() and len(repo.all("IntentBinding")) == 2


def test_earliest_seal_and_forged_context_are_independently_checked(env, monkeypatch):
    repo, i = env
    for name, delta in (("z", 0), ("a", 0), ("earlier", -1)):
        seal(repo, i, T+timedelta(seconds=delta), "TEST-ONLY-"+name)
    c, _ = setup(repo)
    b = g.bind_intent(repo, c, pin(i))
    context = repo.all("BindingContext")[0]
    assert context.seal.ref.id == "TEST-ONLY-earlier"
    forged = b.model_copy(update={"revision": 2, "predecessor": pin(b), "seal": None})
    repo.put(forged)  # A valid lower-level L02 binding, but not this context's evidence.
    bad = context.model_copy(update={"id": "TEST-ONLY-forged-context", "binding": pin(forged)})
    with pytest.raises(ValueError, match="stored chronology"):
        repo.put(bad)
    assert len(repo.all("BindingContext")) == 1
    valid = context.model_copy(update={"id": "TEST-ONLY-valid-context", "binding": pin(forged), "seal": None})
    repo.put(valid)
    assert repo.get(valid.ref).binding == pin(forged)
    other = intent(id="TEST-ONLY-tie"); repo.put(other)
    for name in ("z-tie", "a-tie"): seal(repo, other, T, "TEST-ONLY-"+name)
    d, _ = setup(repo, name="TEST-ONLY-other", checksum="b"*64)
    g.bind_intent(repo, d, pin(other))
    assert next(x for x in repo.all("BindingContext") if repo.get(x.binding.ref).intent == pin(other)).seal.ref.id == "TEST-ONLY-a-tie"


def selection_fixture(repo):
    a, _ = setup(repo); b, _ = setup(repo, name="TEST-ONLY-other", checksum="b"*64)
    dataset = PilotDataset(id="TEST-ONLY", owner="TEST-ONLY", clips=(a.ref, b.ref)); repo.put(dataset)
    return dataset, dict(id="TEST-ONLY-selection", candidates_considered=["TEST-ONLY-other@1", "TEST-ONLY@1"],
        rejected=[dict(ref="TEST-ONLY-other@1", reason="TEST-ONLY-reason")], kept=["TEST-ONLY@1"], random_draw=JSON)


@pytest.mark.parametrize("case,error", [("partition", "partition"), ("overlap", "partition"),
    ("blank", "pattern"), ("duplicate", "unique"), ("foreign", "dataset"), ("dangling", "missing")])
def test_selection_negative_cases_are_not_masked(env, case, error):
    repo, _ = env; dataset, data = selection_fixture(repo)
    control = g.record_selection(repo, dataset, data)
    bad = dict(data, id="TEST-ONLY-invalid")
    if case == "partition": bad["rejected"] = []
    if case == "overlap": bad["kept"] = data["candidates_considered"]
    if case == "blank": bad["rejected"] = [dict(ref="TEST-ONLY-other@1", reason="  ")]
    if case == "duplicate": bad["candidates_considered"] = data["candidates_considered"]*2
    if case in ("foreign", "dangling"):
        if case == "foreign": setup(repo, name="TEST-ONLY-foreign", checksum="c"*64)
        bad.update(candidates_considered=["TEST-ONLY-foreign@1"], kept=["TEST-ONLY-foreign@1"], rejected=[])
    with pytest.raises(ValueError if case in ("foreign", "dangling") else ValidationError, match=error): g.record_selection(repo, dataset, bad)
    assert repo.all("SelectionLog") == (control,)


def test_selection_history_reopen_sql_and_bad_pins(env, tmp_path):
    repo, _ = env; dataset, data = selection_fixture(repo)
    a = g.record_selection(repo, dataset, data)
    b = g.record_selection(repo, dataset, data | {"random_draw": []})
    assert b.predecessor == pin(a) and b.revision == 2 and a.model_dump(mode="json")["random_draw"] == JSON
    for change, error_type, error in (({"random_draw": None}, ValueError, "immutable"), ({"revision": 4}, ValidationError, "predecessor"),
        ({"revision": 3, "predecessor": pin(b).model_copy(update={"sha256": "0"*64})}, ValueError, "digest"),
        ({"predecessor": None}, ValidationError, "predecessor"), ({"dataset": pin(repo.get(dataset.clips[0]))}, ValidationError, "PilotDataset")):
        candidate = b.model_copy(update=change)
        with pytest.raises(error_type, match=error): repo.put(candidate)
    gap = b.model_copy(update={"id": "TEST-ONLY-gap", "revision": 2,
        "predecessor": pin(a).model_copy(update={"ref": a.ref.model_copy(update={"id": "TEST-ONLY-gap"})})})
    with pytest.raises(KeyError, match="TEST-ONLY-gap"): repo.put(gap)
    with sqlite3.connect(tmp_path/"pilot.sqlite") as db:
        for sql in ("UPDATE artifacts SET payload='{}' WHERE kind='SelectionLog'", "DELETE FROM artifacts WHERE kind='SelectionLog'"):
            with pytest.raises(sqlite3.IntegrityError, match="append-only"): db.execute(sql)
    reopened = Repository("sqlite:///"+str(tmp_path/"pilot.sqlite"))
    assert reopened.get(a.ref).canonical() == a.canonical() and reopened.get(b.ref).random_draw == []
    assert [p.ref.id for p in reopened.get(a.ref).candidates_considered] == ["TEST-ONLY-other", "TEST-ONLY"]
    assert [p.ref.id for p in reopened.get(b.ref).candidates_considered] == ["TEST-ONLY-other", "TEST-ONLY"]
    reopened.close()


@pytest.fixture
def workspace(tmp_path, media_tools, codec_videos):
    p = PilotWorkspace(tmp_path/"TEST-ONLY-workspace"); p._store = MediaStore(p.root/"media", media_tools)
    p.init("TEST-ONLY", "TEST-ONLY")
    yield p, codec_videos
    p.close()


def register(p, paths, name="TEST-ONLY", **kw):
    return p.register("TEST-ONLY", name, paths["cfr"], "TEST-ONLY", "TEST-ONLY", **kw)


def call(p, capsys, *args):
    code = pilot_cli.main(["--root", str(p.root), *map(str, args)])
    out = capsys.readouterr()
    return code, json.loads(out.out or out.err)


def test_found_cli_private_export_and_public_exclusion(workspace, tmp_path, monkeypatch, capsys):
    p, paths = workspace
    from eval_lab.fixtures import seed
    from eval_lab.presentation import serialize_case
    fixtures = seed(p.repo)
    args = (p.repo, fixtures["case"].ref, fixtures["round"].ref, fixtures["raters"][0].ref)
    public = {mode: serialize_case(*args, mode=mode) for mode in ("public", "embed")}
    assert call(p, capsys, "register", "TEST-ONLY", "TEST-ONLY", paths["cfr"], "--label", "TEST-ONLY")[0] == 0
    show = call(p, capsys, "show", "TEST-ONLY")[1]
    assert show["origin"] == "FOUND" and show["provenance"] == show["quality_verdict"] == "UNKNOWN"
    i = intent(); p.repo.put(i); seal(p.repo, i, T)
    monkeypatch.setattr(pilot_cli, "launch_file", lambda path: None)
    for command in (("open", "TEST-ONLY"), ("open", "TEST-ONLY", "--at", "0"), ("frames", "TEST-ONLY", "--at", "0")):
        assert call(p, capsys, *command)[0] == 0
    assert len(p.repo.all("FirstView")) == 1
    assert call(p, capsys, "bind-intent", "TEST-ONLY", "--intent", "TEST-ONLY-intent@1")[1]["provenance"] == "CONTEMPORANEOUS"
    source = tmp_path/"TEST-ONLY-selection.json"
    source.write_text(json.dumps(dict(id="TEST-ONLY-selection", candidates_considered=["TEST-ONLY@1"], rejected=[], kept=["TEST-ONLY@1"], random_draw=JSON)))
    assert call(p, capsys, "selection", "TEST-ONLY", "--file", source)[0] == 0
    p.snapshot("TEST-ONLY", "TEST-ONLY-frozen"); frozen = p.export_snapshot("TEST-ONLY-frozen")
    kinds = {x["ref"]["kind"] for x in frozen["records"]}
    assert {"ClipOrigin", "FirstView", "BindingContext", "SelectionLog", "SealRecord"} <= kinds
    for row in frozen["records"]: assert p.repo.get(Ref(**row["ref"])).digest == row["sha256"]
    assert call(p, capsys, "selection", "TEST-ONLY", "--file", source)[0] == 0
    assert call(p, capsys, "export-snapshot", "TEST-ONLY-frozen")[1] == frozen
    show = call(p, capsys, "show", "TEST-ONLY")[1]
    assert {x["ref"]["kind"] for x in show["lifecycle_records"]} >= kinds - {"PilotDataset"}
    for mode in public: assert serialize_case(*args, mode=mode) == public[mode]


def test_plan_cli_and_registration_prevalidation(workspace, tmp_path, monkeypatch, capsys):
    p, paths = workspace; i = intent(); p.repo.put(i)
    source = tmp_path/"TEST-ONLY-plan.json"
    for intents in ([], ["TEST-ONLY-intent@1"], ["TEST-ONLY-intent@1", "TEST-ONLY-intent@2"]):
        if len(intents) == 2: p.repo.put(intent(revision=2, predecessor=pin(i)))
        source.write_text(json.dumps(PLAN | {"intent_revision_ids": intents}))
        code, output = call(p, capsys, "plan", "--file", source)
        assert code == 0 and output["sha256"] == p.repo.get(Ref(**output["ref"])).digest
    plan_id = output["ref"]["id"]
    for options, error_type, error in (({"plan": "absent"}, KeyError, "absent"),
        ({"plan": plan_id}, ValueError, "multiple intents"), ({"plan": plan_id, "intent": "TEST-ONLY-intent@3"}, ValueError, "missing exact reference"),
        ({"plan": ""}, ValidationError, "at least 1 character"), ({"intent": ""}, ValueError, "exact ID@REV")):
        with pytest.raises(error_type, match=error): register(p, paths, name="TEST-ONLY-invalid-"+error, **options)
    assert p.repo.all("PilotClip") == () and p.repo.all("MediaIngestion") == ()
    assert call(p, capsys, "register", "TEST-ONLY", "TEST-ONLY", paths["cfr"], "--label", "TEST-ONLY", "--plan", plan_id, "--intent", "TEST-ONLY-intent@2")[0] == 0
    show = call(p, capsys, "show", "TEST-ONLY")[1]
    assert show["origin"] == "PLANNED" and show["provenance"] == "RECONSTRUCTED"
    assert next(x for x in show["lifecycle_records"] if x["ref"]["kind"] == "GenerationPlan")["artifact"]["settings"] == JSON
    assert next(x for x in show["lifecycle_records"] if x["ref"]["kind"] == "GenerationPlan")["artifact"]["controlled_factors"] == CONTROLS


@pytest.mark.parametrize("failure", ["missing", "corrupt", "extract", "launch"])
def test_view_failure_boundaries(workspace, monkeypatch, capsys, failure):
    p, paths = workspace; c = register(p, paths); path = p.verify_clip(c)
    if failure == "missing": path.unlink()
    if failure == "corrupt": path.write_bytes(b"TEST-ONLY corrupt")
    def fail(*args): raise MediaError("TEST-ONLY failure")
    if failure == "extract": monkeypatch.setattr(MediaStore, "extract", fail)
    monkeypatch.setattr(pilot_cli, "launch_file", fail)
    args = ("frames", c.id, "--at", "0") if failure == "extract" else ("open", c.id)
    assert call(p, capsys, *args)[0] == 2
    assert len(p.repo.all("FirstView")) == (1 if failure in ("extract", "launch") else 0)


def test_competing_first_access_alias_reopen_and_backward_clock(workspace, monkeypatch):
    p, paths = workspace; c = register(p, paths)
    p.init("TEST-ONLY-aliases", "TEST-ONLY")
    alias = p.register("TEST-ONLY-aliases", "TEST-ONLY-alias", paths["cfr"], "TEST-ONLY", "TEST-ONLY")
    barrier = Barrier(2); original = Repository.put
    def competing(repo, item):
        if isinstance(item, g.FirstView): barrier.wait(timeout=10)
        return original(repo, item)
    monkeypatch.setattr(Repository, "put", competing)
    def access(name):
        other = PilotWorkspace(p.root)
        try: return g.first_access(other, other.clip(name))
        finally: other.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = list(pool.map(access, [c.id, alias.id]))
    assert a == b and len(p.repo.all("FirstView")) == 1 and a.tool_version == __version__
    monkeypatch.setattr(g, "now", lambda: T-timedelta(days=100))
    assert g.first_access(p, alias) == a
    i = intent(); p.repo.put(i); binding = g.bind_intent(p.repo, c, pin(i))
    snap = p.snapshot("TEST-ONLY-aliases", "TEST-ONLY-alias-snapshot")
    assert {binding.ref, a.ref} <= {x.ref for x in snap.records}


@pytest.mark.parametrize("planned_first", [True, False])
def test_real_alias_prompt_eligibility_follows_established_origin(workspace, planned_first):
    p, paths = workspace; i = intent(); p.repo.put(i)
    plan = g.record_plan(p.repo, PLAN)
    c = register(p, paths, plan=plan.id if planned_first else None)
    first = g.bind_intent(p.repo, c, pin(i), prompt_only=not planned_first)
    p.init("TEST-ONLY-aliases", "TEST-ONLY")
    alias = p.register("TEST-ONLY-aliases", "TEST-ONLY-alias", paths["cfr"], "TEST-ONLY", "TEST-ONLY", plan=None if planned_first else plan.id)
    if planned_first:
        with pytest.raises(ValueError, match="FOUND"): g.bind_intent(p.repo, alias, pin(i), prompt_only=True)
    else:
        second = g.bind_intent(p.repo, alias, pin(i), prompt_only=True)
        assert second.origin == "FOUND" and second.provenance == "PROMPT_ONLY" and second.predecessor == pin(first)
    frozen = p.snapshot("TEST-ONLY-aliases", "TEST-ONLY-alias-frozen")
    assert plan.ref in {x.ref for x in frozen.records}


@pytest.mark.parametrize("first", ["open", "frame", "frames"])
def test_each_access_entrypoint_logs_before_exposure(workspace, monkeypatch, capsys, first):
    p, paths = workspace; c = register(p, paths)
    original = MediaStore.extract
    def extract(store, *args):
        assert len(p.repo.all("FirstView")) == 1
        return original(store, *args)
    def launch(path): assert len(p.repo.all("FirstView")) == 1
    monkeypatch.setattr(MediaStore, "extract", extract); monkeypatch.setattr(pilot_cli, "launch_file", launch)
    command = ("open", c.id) if first == "open" else (("open" if first == "frame" else "frames"), c.id, "--at", "0")
    assert call(p, capsys, *command)[0] == 0
    assert len(p.repo.all("FirstView")) == 1


def test_late_seal_does_not_refresh_and_partial_binding_is_reported(workspace, monkeypatch):
    p, paths = workspace; c = register(p, paths); i = intent(); p.repo.put(i)
    monkeypatch.setattr(g, "now", lambda: T)
    view = g.first_access(p, c); seal(p.repo, i, T+timedelta(seconds=1))
    first = g.bind_intent(p.repo, c, pin(i))
    assert first.provenance == "RECONSTRUCTED" and first.first_view_at == view.created_at
    seal(p.repo, i, T-timedelta(seconds=1), "TEST-ONLY-earlier-clock")
    assert g.audit(p.repo, c)["provenance"] == "RECONSTRUCTED"
    with pytest.raises(ValueError, match="cannot raise provenance"): g.bind_intent(p.repo, c, pin(i))
    original = Repository.put
    def fail(repo, item):
        if isinstance(item, g.BindingContext): raise ValueError("TEST-ONLY storage failure")
        return original(repo, item)
    monkeypatch.setattr(Repository, "put", fail)
    other = intent(id="TEST-ONLY-unsealed"); p.repo.put(other)
    with pytest.raises(ValueError, match="binding.*retained; context not stored"):
        g.bind_intent(p.repo, c, pin(other))
    assert len(p.repo.all("IntentBinding")) == 2 and len(p.repo.all("BindingContext")) == 1


@pytest.mark.parametrize("count", [0, 1])
def test_planned_empty_or_sole_intent_and_forbidden_controls(workspace, tmp_path, capsys, count):
    p, paths = workspace; i = intent(); p.repo.put(i)
    plan = g.record_plan(p.repo, PLAN | {"intent_revision_ids": ["TEST-ONLY-intent@1"]*count})
    clip = register(p, paths, plan=plan.id)
    assert len(p.repo.all("IntentBinding")) == count and g.audit(p.repo, clip)["origin"] == "PLANNED"
    assert g.audit(p.repo, clip)["provenance"] == ("RECONSTRUCTED" if count else "UNKNOWN")
    bad = tmp_path/"TEST-ONLY-bad-plan.json"
    for field in ("planned_at", "created_at", "provenance"):
        bad.write_text(json.dumps(PLAN | {field: "TEST-ONLY"}))
        assert call(p, capsys, "plan", "--file", bad)[0] == 2
    for event in (plan, *p.repo.all("ClipOrigin"), *p.repo.all("BindingContext")):
        with pytest.raises(ValidationError, match="less than or equal to 1"): p.repo.put(event.model_copy(update={"id": "TEST-ONLY-revision", "revision": 2}))
    with pytest.raises(ValueError, match="origin"):
        g.record_origin(p.repo, clip, plan)


def test_registration_partial_records_are_reported(workspace, monkeypatch):
    p, paths = workspace; original = Repository.put
    def fail(repo, item):
        if isinstance(item, PilotClip): raise ValueError("TEST-ONLY registration failure")
        return original(repo, item)
    monkeypatch.setattr(Repository, "put", fail)
    with pytest.raises(ValueError, match="incomplete.*MediaAsset.*MediaIngestion"):
        register(p, paths)
    assert len(p.repo.all("MediaIngestion")) == 1 and p.repo.all("PilotClip") == ()


def test_old_binding_without_context_does_not_borrow_alias_origin(env):
    from test_intent_v2 import binding
    repo, i = env; m, r = anchors(repo)
    original = binding(i, m, r); repo.put(original)
    plan = g.record_plan(repo, PLAN)
    alias = PilotClip(id="TEST-ONLY-alias", media=m.ref, ingestion=r.ref, selected_by="TEST-ONLY", label="TEST-ONLY")
    repo.put(alias); g.record_origin(repo, alias, plan)
    successor = g.bind_intent(repo, alias, pin(i))
    assert successor.origin == "FOUND" and successor.predecessor == pin(original)
    assert successor.plan is None and successor.provenance == "RECONSTRUCTED"
    assert repo.all("BindingContext")[0].origin is None
    assert g.bind_intent(repo, alias, pin(i)).plan is None
    assert all(x.origin is None for x in repo.all("BindingContext"))
