"""TEST-ONLY malformed lifecycle declarations must never become stored evidence."""
import json
import pytest
from eval_lab.pilot import PilotWorkspace
from eval_lab import pilot_cli
from test_generation import PLAN, selection_fixture
from test_intent_v2 import intent


CASES = [(field, bad) for field in ("intent_revision_ids", "candidates_considered", "rejected", "kept")
         for bad in (None, {}, "", "TEST-ONLY@1", 0, 1.5, True, "keyed-object")]
CASES += [("rejection", bad) for bad in (None, {}, [], "", 0, True,
    {"ref": "TEST-ONLY-other@1"}, {"reason": "TEST-ONLY"},
    {"ref": "TEST-ONLY-other@1", "reason": "TEST-ONLY", "extra": "TEST-ONLY"})]


@pytest.mark.parametrize("field,bad", CASES)
def test_lifecycle_cli_rejects_raw_shapes_without_admission(tmp_path, capsys, field, bad):
    root = tmp_path/"TEST-ONLY-workspace"
    source = tmp_path/"TEST-ONLY-input.json"
    p = PilotWorkspace(root)
    try:
        if field == "intent_revision_ids":
            p.repo.put(intent())
            data = PLAN | {"id": "TEST-ONLY-control", field: ["TEST-ONLY-intent@1"]}
            command, kind = ["plan"], "GenerationPlan"
        else:
            dataset, data = selection_fixture(p.repo)
            if field == "rejected": data = data | {"kept": data["candidates_considered"], "rejected": []}
            command, kind = ["selection", dataset.id], "SelectionLog"
        argv = ["--root", str(root), *command, "--file", str(source)]
        source.write_text(json.dumps(data))
        assert pilot_cli.main(argv) == 0
        assert capsys.readouterr().err == ""
        control = p.repo.all(kind)
        assert len(control) == 1
        if bad == "keyed-object": bad = dict.fromkeys(data[field], "TEST-ONLY-discarded-value")
        change = {"rejected": [bad]} if field == "rejection" else {field: bad}
        source.write_text(json.dumps(data | {"id": "TEST-ONLY-invalid"} | change))
        assert pilot_cli.main(argv) == 2
        output = capsys.readouterr()
        assert output.out == ""
        error = json.loads(output.err)
        assert ("rejected entries" if field == "rejection" else field + " must be a JSON array") in error["error"]
        assert error["quality_verdict"] == "UNKNOWN" and error["no_automatic_judgment"] is True
        assert p.repo.all(kind) == control
    finally:
        p.close()
