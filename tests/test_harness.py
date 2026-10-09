"""Test gate logic directly: never invoke the recursive pytest subprocess runner."""
from copy import deepcopy
import json

import pytest

from eval_lab import harness


def successful_pytest():
    return dict(exit_code=0, junit_valid=True, timed_out=False, tests=12, passed=12,
                failures=0, errors=0, skipped=0)


def successful_gates():
    return [{"name": name, "passed": True} for name in (
        "catastrophic_veto", "missing_evidence_is_unknown", "evidence_required", "rubric_pin",
        "delayed_reveal", "independent_demo_reproduction", "source_unchanged",
    )]


def successful_mutations():
    return [{"name": name, "caught": True, "baseline_passed": True} for name in harness.MUTATION_NAMES]


def test_production_behavioral_gates_all_pass():
    results = harness.run_behavioral_gates()
    assert len(results) == 5
    assert all(result["passed"] for result in results), results


def test_callable_mutants_are_caught_by_same_behavioral_assertions():
    results = harness.run_mutation_probes()
    assert {r["name"] for r in results} == set(harness.MUTATION_NAMES)
    assert all(r["baseline_passed"] and r["caught"] for r in results), results
    assert all(r["scope"] == "LOCAL_SOFTWARE_MUTATION" for r in results)


def test_demo_reproduces_across_independent_repositories():
    result = harness.check_demo_reproducibility()
    assert result["passed"]
    assert result["independent_repositories"] == 2
    assert result["paid_calls"] == [0, 0]
    assert len(set(result["canonical_output_sha256"])) == 1


def test_complete_local_evidence_can_only_approve_offline_testing():
    assert harness.approval_status(successful_pytest(), successful_gates(), successful_mutations()) == "APPROVED_FOR_OFFLINE_TESTING"


@pytest.mark.parametrize("change", [
    {"exit_code": 1}, {"junit_valid": False}, {"timed_out": True},
    {"tests": 0, "passed": 0}, {"failures": 1, "passed": 11},
    {"errors": 1, "passed": 11}, {"skipped": 1, "passed": 11},
])
def test_incomplete_or_failing_pytest_blocks_approval(change):
    results = successful_pytest() | change
    assert harness.approval_status(results, successful_gates(), successful_mutations()) == "BLOCKED"


@pytest.mark.parametrize("name", ["catastrophic_veto", "delayed_reveal", "source_unchanged", "independent_demo_reproduction"])
def test_missing_required_gate_blocks_approval(name):
    gates = [g for g in successful_gates() if g["name"] != name]
    assert harness.approval_status(successful_pytest(), gates, successful_mutations()) == "BLOCKED"


def test_failure_cannot_be_outvoted_by_successful_gates():
    gates = successful_gates()
    gates[0]["passed"] = False
    assert harness.approval_status(successful_pytest(), gates, successful_mutations()) == "BLOCKED"


@pytest.mark.parametrize("mutation_change", [{"caught": False}, {"baseline_passed": False}])
def test_surviving_mutant_or_broken_baseline_blocks_approval(mutation_change):
    mutations = successful_mutations()
    mutations[0].update(mutation_change)
    assert harness.approval_status(successful_pytest(), successful_gates(), mutations) == "BLOCKED"


def test_missing_or_duplicate_mutation_cannot_meet_coverage_requirement():
    mutations = successful_mutations()
    mutations[-1] = deepcopy(mutations[0])
    assert harness.approval_status(successful_pytest(), successful_gates(), mutations) == "BLOCKED"
    assert harness.approval_status(successful_pytest(), successful_gates(), []) == "BLOCKED"


def test_junit_count_comes_from_executed_case_records(tmp_path):
    report = tmp_path / "report.xml"
    report.write_text('<testsuites><testsuite tests="3" failures="1" errors="0" skipped="1">'
                      '<testcase name="pass"/><testcase name="fail"><failure/></testcase>'
                      '<testcase name="skip"><skipped/></testcase></testsuite></testsuites>')
    result = harness.parse_junit(report)
    assert result == dict(tests=3, passed=1, failures=1, errors=0, skipped=1)


@pytest.mark.parametrize("xml", [
    '<testsuites/>',
    '<testsuites><testsuite tests="99"><testcase name="only-one"/></testsuite></testsuites>',
    '<testsuites><testsuite tests="1" failures="2"><testcase name="one"/></testsuite></testsuites>',
])
def test_invalid_junit_cannot_inflate_pass_count(tmp_path, xml):
    report = tmp_path / "report.xml"
    report.write_text(xml)
    with pytest.raises(ValueError):
        harness.parse_junit(report)


def test_source_digest_covers_code_tests_configuration_and_optional_lock(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "core.py").write_text("value = 1\n")
    (tmp_path / "tests" / "test_core.py").write_text("assert True\n")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "example"\n')
    before = harness.source_tree_digest(tmp_path)
    assert len(before["files"]) == 3
    (tmp_path / "src" / "core.py").write_text("value = 2\n")
    after_code = harness.source_tree_digest(tmp_path)
    assert before["sha256"] != after_code["sha256"]
    (tmp_path / "uv.lock").write_text("version = 1\n")
    after_lock = harness.source_tree_digest(tmp_path)
    assert after_code["sha256"] != after_lock["sha256"]
    assert "uv.lock" in {entry["path"] for entry in after_lock["files"]}
    (tmp_path / "src" / "__pycache__").mkdir()
    (tmp_path / "src" / "__pycache__" / "core.pyc").write_bytes(b"generated")
    assert harness.source_tree_digest(tmp_path) == after_lock


def test_canonical_comparison_ignores_map_insertion_order_but_not_values():
    assert harness.canonical_json({"a": 1, "b": [2]}) == harness.canonical_json({"b": [2], "a": 1})
    assert harness.canonical_json({"a": 1}) != harness.canonical_json({"a": 2})
    with pytest.raises(ValueError):
        harness.canonical_json({"confidence": float("nan")})
