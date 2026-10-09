"""Offline approval evidence for local software only; never empirical judge approval."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version as package_version
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from typing import Callable
import xml.etree.ElementTree as ET

from .demo import run_demo
from .domain import Criterion, Dimension, DimensionScore, IntentSpec, Ref
from .fixtures import STAMP, requests_for, seed
from .persistence import Repository
from .presentation import serialize_case, submit_pairwise
from .rubrics import initial_rubric
from .scoring import evaluate
from .swarm import BoundedSwarm

EVIDENCE_SCOPE = "LOCAL_SOFTWARE_CONTRACTS_AND_SYNTHETIC_FIXTURES_ONLY"
PYTEST_TIMEOUT_SECONDS = 120
MUTATION_NAMES = (
    "remove_catastrophic_veto", "drop_evidence_validation",
    "drop_rubric_hash_check", "ungate_pre_submission_reveal",
)


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def source_tree_digest(root: Path) -> dict:
    """Hash path/content pairs, excluding generated Python caches; no git required."""
    root = root.resolve()
    paths = []
    for directory in (root / "src", root / "tests"):
        if directory.exists():
            paths.extend(p for p in directory.rglob("*") if p.is_file()
                         and "__pycache__" not in p.parts and p.suffix != ".pyc"
                         and not any(part.endswith(".egg-info") for part in p.parts))
    paths.extend(p for p in (root / "pyproject.toml", root / "uv.lock") if p.is_file())
    manifest = [{"path": p.relative_to(root).as_posix(), "sha256": sha256(p.read_bytes()).hexdigest()}
                for p in sorted(paths)]
    return {"sha256": sha256(canonical_json(manifest).encode()).hexdigest(), "files": manifest}


def parse_junit(path: Path) -> dict:
    root = ET.parse(path).getroot()
    suites = [node for node in root.iter("testsuite") if not node.findall("testsuite")]
    if not suites:
        raise ValueError("JUnit contains no test suite")
    counts = {key: sum(int(s.get(key, "0")) for s in suites)
              for key in ("tests", "failures", "errors", "skipped")}
    if any(n < 0 for n in counts.values()):
        raise ValueError("negative JUnit count")
    cases = sum(len(s.findall("testcase")) for s in suites)
    if cases != counts["tests"]:
        raise ValueError("JUnit test counts do not match testcase records")
    counts["passed"] = counts["tests"] - counts["failures"] - counts["errors"] - counts["skipped"]
    if counts["passed"] < 0:
        raise ValueError("inconsistent JUnit counts")
    return counts


def run_pytest(root: Path) -> dict:
    """A real bounded subprocess; tests call the gates below, never this runner."""
    result = dict(exit_code=None, tests=0, passed=0, failures=0, errors=0, skipped=0,
                  timed_out=False, junit_valid=False, timeout_seconds=PYTEST_TIMEOUT_SECONDS)
    with tempfile.TemporaryDirectory(prefix="eval-lab-pytest-") as temporary:
        junit = Path(temporary) / "results.xml"
        env = dict(os.environ)
        env["PYTHONPATH"] = str(root / "src")
        # An inherited selection must not silently shrink the approval suite.
        env.pop("PYTEST_ADDOPTS", None)
        command = [sys.executable, "-m", "pytest", "tests", "-q", "--tb=short", f"--junitxml={junit}"]
        try:
            completed = subprocess.run(command, cwd=root, env=env, capture_output=True,
                                       text=True, timeout=PYTEST_TIMEOUT_SECONDS, check=False)
            result["exit_code"] = completed.returncode
            result["output_tail"] = (completed.stdout + completed.stderr)[-8000:]
        except subprocess.TimeoutExpired:
            result["timed_out"] = True
            result["output_tail"] = "Pytest exceeded the 120-second subprocess limit."
        except OSError as exc:
            result["output_tail"] = f"Pytest could not start ({type(exc).__name__})."
        try:
            result.update(parse_junit(junit))
            result["junit_valid"] = True
        except (OSError, ValueError, ET.ParseError) as exc:
            result["junit_error"] = type(exc).__name__
    return result


def pytest_passed(result: dict) -> bool:
    return (result.get("exit_code") == 0 and result.get("junit_valid") is True
            and result.get("timed_out") is False and result.get("tests", 0) > 0
            and result.get("passed") == result.get("tests")
            and all(result.get(key) == 0 for key in ("failures", "errors", "skipped")))


def _scoring_fixture():
    rubric = initial_rubric()
    dimensions = (Dimension.PROMPT, Dimension.AESTHETIC)
    intent = IntentSpec(id="harness-intent", created_at=STAMP, owner="test-author", objective="Required red dog",
                        audience="artist", context="independent software assertion", authority="human_declared",
                        approved_by="test-author", criteria=tuple(Criterion(dimension=d, rationale="Required",
                        acceptance="Correct request, compelling image") for d in dimensions))
    evidence = (Ref(kind="Evidence", id="harness-evidence"),)
    scores = tuple(DimensionScore(dimension=d, status="scored", score=n, confidence=0.5,
                                  evidence=evidence, rationale="Authored test category")
                   for d, n in ((Dimension.PROMPT, 0), (Dimension.AESTHETIC, 4)))
    return scores, rubric, intent


def check_hard_failure_veto(score_fn: Callable = evaluate) -> None:
    scores, rubric, intent = _scoring_fixture()
    verdict = score_fn(scores, rubric, intent)
    assert verdict.status == "FAILED", "catastrophic adherence must defeat polished aesthetics"
    assert Dimension.PROMPT in verdict.critical_dimensions, "critical dimension must remain visible"


def check_missing_evidence_unknown(score_fn: Callable = evaluate) -> None:
    scores, rubric, intent = _scoring_fixture()
    verdict = score_fn(scores[1:], rubric, intent)
    assert verdict.status == "UNKNOWN", "missing required judgment cannot pass"
    assert Dimension.PROMPT in verdict.missing_dimensions, "missing dimension must remain visible"


def check_evidence_contract(parse_fn: Callable = DimensionScore.model_validate) -> None:
    raw = {"dimension": Dimension.PROMPT, "status": "scored", "score": 4, "confidence": 0.9,
           "evidence": [], "rationale": "Approve with no inspectable evidence"}
    try:
        parse_fn(raw)
    except ValueError:
        return
    raise AssertionError("scored output without evidence was accepted")


def _run_swarm(provider, requests, run, version):
    return asyncio.run(BoundedSwarm(provider).run(requests, run, version, created_at=STAMP))


def check_rubric_pin(run_fn: Callable = _run_swarm) -> None:
    repo = Repository()
    try:
        data = seed(repo)
        requests = requests_for(repo, data, "beautiful_wrong")[:1]
        mismatched = requests[0].model_copy(update={"rubric_digest": "0" * 64})
        try:
            run_fn(data["provider"], (mismatched,), data["runs"]["beautiful_wrong"], data["version"])
        except ValueError:
            return
        raise AssertionError("mismatched rubric hash was accepted")
    finally:
        repo.close()


def check_delayed_reveal(serialize_fn: Callable = serialize_case) -> None:
    repo = Repository()
    try:
        data = seed(repo)
        args = (repo, data["case"].ref, data["round"].ref, data["raters"][0].ref)
        for mode in ("public", "embed"):
            before = serialize_fn(*args, mode=mode)
            assert before["stage"] == "blind", "pre-submission view must remain blind"
            assert not ({"results", "your_evaluation", "remaining_uncertainty"} & before.keys()), "premature result disclosure"
            assert "PRIVATE_SENTINEL" not in canonical_json(before), "private note leaked"
        submit_pairwise(repo, data["round"].ref, data["raters"][0].ref, "tie", "Harness submission", created_at=STAMP)
        after = serialize_fn(*args)
        assert after["stage"] == "revealed" and "results" in after, "valid submission must unlock review"
    finally:
        repo.close()


def run_behavioral_gates() -> list[dict]:
    checks = (
        ("catastrophic_veto", check_hard_failure_veto),
        ("missing_evidence_is_unknown", check_missing_evidence_unknown),
        ("evidence_required", check_evidence_contract),
        ("rubric_pin", check_rubric_pin),
        ("delayed_reveal", check_delayed_reveal),
    )
    results = []
    for name, check in checks:
        try:
            check()
            results.append({"name": name, "passed": True})
        except Exception as exc:
            results.append({"name": name, "passed": False, "error_type": type(exc).__name__, "detail": str(exc)[:500]})
    return results


# These deliberately defective local callables are never persisted or installed.
def _without_catastrophic_veto(scores, rubric, intent):
    altered = rubric.model_copy(update={"dimensions": tuple(d.model_copy(update={"hard_fail_at_or_below": None}) for d in rubric.dimensions)})
    return evaluate(scores, altered, intent)


def _without_evidence_validation(raw):
    return DimensionScore.model_construct(**raw)


def _without_rubric_pin(provider, requests, run, version):
    # Silently normalizing the incoming digest is equivalent to dropping its check.
    rewritten = tuple(r.model_copy(update={"rubric_digest": version.rubric_digest}) for r in requests)
    return _run_swarm(provider, rewritten, run, version)


def _without_reveal_gate(*args, **kwargs):
    payload = serialize_case(*args, **kwargs)
    payload.update(stage="revealed", results=[{"leaked_score": 4}])
    return payload


def run_mutation_probes() -> list[dict]:
    probes = (
        (MUTATION_NAMES[0], check_hard_failure_veto, _without_catastrophic_veto),
        (MUTATION_NAMES[1], check_evidence_contract, _without_evidence_validation),
        (MUTATION_NAMES[2], check_rubric_pin, _without_rubric_pin),
        (MUTATION_NAMES[3], check_delayed_reveal, _without_reveal_gate),
    )
    results = []
    for name, detector, mutant in probes:
        record = {"name": name, "scope": "LOCAL_SOFTWARE_MUTATION", "baseline_passed": False, "caught": False}
        try:
            detector()
            record["baseline_passed"] = True
        except Exception as exc:
            record["error_type"] = type(exc).__name__
            results.append(record)
            continue
        try:
            detector(mutant)
            record["detail"] = "Mutant survived the behavioral assertion."
        except AssertionError as exc:
            record["caught"] = True
            record["detail"] = str(exc)
        except Exception as exc:
            # Crashing a mutant is not evidence that our intended detector worked.
            record["error_type"] = type(exc).__name__
            record["detail"] = "Mutant execution failed outside the expected behavioral assertion."
        results.append(record)
    return results


def check_demo_reproducibility() -> dict:
    outputs = []
    for _ in range(2):
        repo = Repository()  # New SQLite engine/database, no shared state or cache.
        try:
            outputs.append(asyncio.run(run_demo(repo)))
        finally:
            repo.close()
    rendered = [canonical_json(output) for output in outputs]
    hashes = [sha256(output.encode()).hexdigest() for output in rendered]
    return {"name": "independent_demo_reproduction", "passed": rendered[0] == rendered[1],
            "independent_repositories": 2, "canonical_output_sha256": hashes,
            "paid_calls": [output.get("model_calls_paid") for output in outputs],
            "evidence_scope": "SYNTHETIC_SOFTWARE_FIXTURES_ONLY"}


def approval_status(pytest_result: dict, gates: list[dict], mutations: list[dict]) -> str:
    complete_gates = {g.get("name") for g in gates} >= {
        "catastrophic_veto", "missing_evidence_is_unknown", "evidence_required", "rubric_pin",
        "delayed_reveal", "independent_demo_reproduction", "source_unchanged",
    }
    complete_mutations = {m.get("name") for m in mutations} == set(MUTATION_NAMES)
    approved = (pytest_passed(pytest_result) and complete_gates and all(g.get("passed") is True for g in gates)
                and complete_mutations and len(mutations) == len(MUTATION_NAMES)
                and all(m.get("caught") is True and m.get("baseline_passed") is True for m in mutations))
    return "APPROVED_FOR_OFFLINE_TESTING" if approved else "BLOCKED"


def run_harness(root: Path) -> dict:
    root = root.resolve()
    before = source_tree_digest(root)
    pytest_result = run_pytest(root)
    gates = run_behavioral_gates()
    mutations = run_mutation_probes()
    try:
        reproduction = check_demo_reproducibility()
        reproduction["passed"] = reproduction["passed"] and reproduction["paid_calls"] == [0, 0]
        gates.append(reproduction)
    except Exception as exc:
        gates.append({"name": "independent_demo_reproduction", "passed": False, "error_type": type(exc).__name__})
    after = source_tree_digest(root)
    gates.append({"name": "source_unchanged", "passed": before == after})
    versions = {}
    for package in ("pydantic", "sqlalchemy", "fastapi", "pytest", "krippendorff"):
        try:
            versions[package] = package_version(package)
        except PackageNotFoundError:
            versions[package] = "not_installed"
    return {
        "schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
        "offline_readiness": approval_status(pytest_result, gates, mutations),
        "empirical_validation": "NEEDS_HUMAN_VALIDATION", "deployment_authorized": False,
        "evidence_scope": EVIDENCE_SCOPE, "paid_calls": 0,
        "source_tree": before, "source_tree_sha256_after": after["sha256"],
        "runtime": {"python": platform.python_version(), "packages": versions},
        "pytest": pytest_result, "gates": gates, "mutations": mutations,
        "mutations_caught": sum(m["caught"] for m in mutations),
        "limitations": [
            "Local software mutations and synthetic data do not validate a perceptual judge, human rubric or workflow benefit.",
            "Hash manifest covers src, tests, pyproject.toml and uv.lock when present; it is not an authenticated attestation.",
            "The pytest subprocess has a 120-second limit; fixture providers use cooperative asyncio cancellation, not a process sandbox.",
            "No live provider is configured; zero paid calls is fixture-mode evidence, not production billing reconciliation.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_harness(Path(__file__).resolve().parents[2])
    serialized = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized)
    print(serialized, end="")
    return 0 if result["offline_readiness"] == "APPROVED_FOR_OFFLINE_TESTING" else 1


if __name__ == "__main__":
    raise SystemExit(main())
