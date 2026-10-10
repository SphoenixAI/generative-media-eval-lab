"""Deterministic transport summaries; never used to decide a product outcome."""
import hashlib
import json
from collections import Counter
from pathlib import Path

ATTACHMENT_CAP = 16 * 1024
SECTION_CAP = 64 * 1024
FAILURE_LIMIT = 50


def render(value):
    return json.dumps(value, indent=2, ensure_ascii=True)


def size(value):
    return len(render(value).encode("utf-8"))


def test_summary(tests, source):
    # Preserve validity/errors: absent evidence must not become a passing count.
    out = {k: v for k, v in tests.items() if k not in ("outcomes", "collected")}
    outcomes = tests.get("outcomes", {})
    counts = Counter(outcomes.values())
    failed = sorted(node for node, status in outcomes.items() if status in ("failed", "error", "errored"))
    out.update(outcome_counts=dict(sorted(counts.items())), failed_or_errored_count=len(failed),
               failed_or_errored_node_ids=failed[:FAILURE_LIMIT], full_file_path=str(source))
    return out


def required(kind, data, source):
    if kind == "prior_attempts":
        if not isinstance(data, list) or any(not isinstance(a, dict) for a in data):
            raise ValueError("prior attempts must be an array of objects")
    elif not isinstance(data, dict):
        raise ValueError("evidence attachment must be an object")
    if kind == "gate":
        out = {k: data[k] for k in ("step", "round", "passed", "gates", "flags", "invariant_violations") if k in data}
        if "tests" in data: out["tests"] = test_summary(data["tests"], source)
        return out
    if kind == "prior_attempts":
        return [{k: attempt[k] for k in ("step", "decision", "rule", "blocking_findings", "prior_findings") if k in attempt}
                for attempt in data]
    if kind == "evaluation":
        out = {k: data[k] for k in ("step", "item", "role", "round", "diff_sha256", "blocking_findings", "prior_findings") if k in data}
        out["scores"] = {k: v if v["score"] <= 2 else {"score": v["score"]} for k, v in data.get("scores", {}).items()}
        return out
    if kind == "research":
        return {"claims": [c for c in data.get("claims", []) if c.get("action_required") is True],
                "total_claim_count": len(data.get("claims", []))}
    if kind == "finding_refs":
        return {"findings": data.get("findings", [])}
    raise ValueError("unsupported attachment kind: " + kind)


def attachment(kind, path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    data = json.loads(raw)
    mandatory = required(kind, data, path)
    normal = {**data, "tests": test_summary(data["tests"], path)} if kind == "gate" and "tests" in data else data
    envelope = {"source_path": str(path), "original_bytes": len(raw),
                "source_sha256": hashlib.sha256(raw).hexdigest(), "kind": kind,
                "compacted": kind == "gate", "content": normal}
    return envelope, mandatory


def compact(specs):
    """Soft caps: mandatory evidence wins; every overflow is measured, never hidden."""
    pairs = [attachment(kind, path) for kind, path in specs]
    envelopes = []
    for entry, mandatory in pairs:
        if size(entry) > ATTACHMENT_CAP:
            entry["content"] = mandatory
            entry["compacted"] = True
        envelopes.append(entry)
    # Combined pressure discards optional narrative only, in stable source order.
    if size(envelopes) > SECTION_CAP:
        for entry, mandatory in pairs:
            entry["content"] = mandatory
            entry["compacted"] = True
    report = {"attachment_cap_bytes": ATTACHMENT_CAP, "section_cap_bytes": SECTION_CAP,
              "section_bytes": size(envelopes), "section_over_cap": size(envelopes) > SECTION_CAP,
              "attachments": []}
    for entry, mandatory in pairs:
        n = size(entry)
        report["attachments"].append({"source_path": entry["source_path"],
            "original_bytes": entry["original_bytes"], "rendered_bytes": n,
            "mandatory_bytes": size({**entry, "content": mandatory}),
            "attachment_over_cap": n > ATTACHMENT_CAP})
    report["attachment_over_cap"] = any(x["attachment_over_cap"] for x in report["attachments"]) or report["section_over_cap"]
    return envelopes, report


def advisory_result(run_dir, round_number, result):
    """Keep advisory attempts separate and immutable; never replace authoritative gates."""
    folder = Path(run_dir) / "advisory"
    folder.mkdir(parents=True, exist_ok=True)
    attempt = 1
    while True:
        path = folder / f"gate_r{round_number}-attempt-{attempt:03d}.json"
        try:
            with path.open("x") as stream: stream.write(render(result) + "\n")
            break
        except FileExistsError: attempt += 1
    entries, report = compact([("gate", path)])
    summary = {**entries[0]["content"], "full_result_path": str(path.resolve()), "compaction": report}
    path.with_suffix(".summary.json").write_text(render(summary) + "\n")
    return summary
