"""TEST-ONLY scalable evidence transport; mandatory evidence never disappears."""
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch
import test_control as controls
import prompt_evidence as pe
from test_actionability import run


def gate(count=5000, outcome="passed"):
    outcomes = {f"tests/test_fixture.py::test_case[{i:05d}]": outcome for i in reversed(range(count))}
    return {"passed": outcome == "passed", "step": 1, "round": 1,
            "gates": {f"G{i}": {"passed": i != 1 or outcome == "passed", "blocking": True,
                                "details": {"TEST-ONLY": f"literal-{i}"}} for i in range(1, 15)},
            "flags": [], "invariant_violations": [],
            "tests": {"passed": count if outcome == "passed" else 0, "valid": True,
                      "exit_code": 0 if outcome == "passed" else 1,
                      "outcomes": outcomes, "collected": list(outcomes)}}


class CompactTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)

    def source(self, name, value):
        p = self.folder / name; p.write_text(pe.render(value) + "\n"); return p

    def test_large_passing_gate_preserves_checks_without_passed_node_ids(self):
        value = gate(); path = self.source("gate.json", value); before = path.read_bytes()
        entries, report = pe.compact([("gate", path)])
        result = entries[0]
        self.assertEqual(result["content"]["gates"], value["gates"])
        self.assertEqual(result["content"]["tests"]["passed"], 5000)
        self.assertNotIn("test_case", pe.render(entries))
        self.assertLess(pe.size(entries), pe.ATTACHMENT_CAP)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(result["original_bytes"], len(before))
        self.assertEqual(result["source_sha256"], hashlib.sha256(before).hexdigest())
        self.assertFalse(report["attachment_over_cap"])

    def test_mass_failure_5000_sorted_first_50_total_and_full_path(self):
        value = gate(outcome="failed"); path = self.source("fail.json", value)
        entries, report = pe.compact([("gate", path)]); tests = entries[0]["content"]["tests"]
        self.assertEqual(tests["failed_or_errored_count"], 5000)
        self.assertEqual(tests["failed_or_errored_node_ids"], sorted(value["tests"]["outcomes"])[:50])
        self.assertEqual(tests["full_file_path"], str(path.resolve()))
        self.assertEqual(entries[0]["content"]["gates"], value["gates"])
        self.assertFalse(entries[0]["content"]["passed"])
        self.assertLess(pe.size(entries), pe.ATTACHMENT_CAP)
        self.assertFalse(report["attachment_over_cap"])

    def test_errors_and_failures_share_limit_without_passed_ids(self):
        value = gate(100, "error"); value["tests"]["outcomes"]["TEST-ONLY failed"] = "failed"
        value["tests"]["outcomes"]["TEST-ONLY pass"] = "passed"
        path = self.source("mixed.json", value)
        tests = pe.compact([("gate", path)])[0][0]["content"]["tests"]
        self.assertEqual(tests["failed_or_errored_count"], 101)
        self.assertEqual(len(tests["failed_or_errored_node_ids"]), 50)
        self.assertNotIn("TEST-ONLY pass", tests["failed_or_errored_node_ids"])

    def test_gate_details_over_cap_are_verbatim_and_flagged(self):
        value = gate(1); value["gates"]["G5"]["details"] = {"critical": "TEST-ONLY λ" * 4000}
        path = self.source("oversize.json", value)
        entries, report = pe.compact([("gate", path)])
        self.assertEqual(entries[0]["content"]["gates"], value["gates"])
        self.assertTrue(report["attachment_over_cap"])
        self.assertTrue(report["attachments"][0]["attachment_over_cap"])
        self.assertEqual(report["section_bytes"], len(pe.render(entries).encode()))

    def test_prior_attempts_drop_narrative_not_any_blocking_finding(self):
        prior = [{"step": i, "decision": "REVERT", "rule": "R3", "narrative": "old " * 10000,
                  "blocking_findings": [{"id": f"F{i}", "description": f"TEST-ONLY exact {i}",
                     "required_fix": "Never paraphrase this remedy."}],
                  "prior_findings": [{"ref": f"F{i}", "status": "UNRESOLVED"}]} for i in range(20)]
        path = self.source("prior.json", prior); entries, _ = pe.compact([("prior_attempts", path)])
        for actual, original in zip(entries[0]["content"], prior):
            self.assertEqual(actual["blocking_findings"], original["blocking_findings"])
            self.assertEqual(actual["prior_findings"], original["prior_findings"])
            self.assertNotIn("narrative", actual)
        self.assertEqual(len(entries[0]["content"]), 20)
        self.assertEqual(entries[0]["original_bytes"], path.stat().st_size)

    def test_required_evaluator_research_and_reference_content_survives_caps(self):
        finding = {"id": "F1", "description": "TEST-ONLY " * 3000, "required_fix": "exact remedy"}
        claim = {"id": "R0001-C001", "action_required": True, "claim": "TEST-ONLY " * 3000}
        sources = [("evaluation", self.source("eval.json", {"blocking_findings": [finding], "prior_findings": [{"ref": "F0", "status": "UNRESOLVED"}], "summary": "optional " * 10000})),
                   ("research", self.source("research.json", {"claims": [claim, {"id": "context", "action_required": False, "claim": "optional " * 10000}]})),
                   ("finding_refs", self.source("refs.json", {"findings": [finding], "score_notes": ["optional " * 10000]}))]
        entries, report = pe.compact(sources)
        self.assertEqual(entries[0]["content"]["blocking_findings"], [finding])
        self.assertEqual(entries[0]["content"]["prior_findings"], [{"ref": "F0", "status": "UNRESOLVED"}])
        self.assertEqual(entries[1]["content"]["claims"], [claim])
        self.assertEqual(entries[2]["content"]["findings"], [finding])
        self.assertTrue(report["section_over_cap"])
        self.assertTrue(report["attachment_over_cap"])

    def test_blocking_score_evidence_also_remains_verbatim(self):
        score = {"score": 2, "evidence": ["TEST-ONLY blocking score detail " * 1000]}
        path = self.source("score.json", {"scores": {"intention": score}})
        entries, report = pe.compact([("evaluation", path)])
        self.assertEqual(entries[0]["content"]["scores"]["intention"], score)
        self.assertTrue(report["attachment_over_cap"])

    def test_combined_cap_removes_only_optional_narrative(self):
        specs = [("evaluation", self.source(f"e{i}.json", {"blocking_findings": [{"id": f"F{i}"}], "summary": "x" * 14000})) for i in range(5)]
        entries, report = pe.compact(specs)
        self.assertLess(report["section_bytes"], pe.SECTION_CAP)
        for i, entry in enumerate(entries):
            self.assertEqual(entry["content"]["blocking_findings"], [{"id": f"F{i}"}])
            self.assertNotIn("summary", entry["content"])

    def test_determinism_and_input_nonmutation(self):
        value = gate(3); before = copy.deepcopy(value); p = self.source("gate.json", value)
        self.assertEqual(pe.compact([("gate", p)]), pe.compact([("gate", p)]))
        self.assertEqual(value, before)

    def test_unavailable_or_malformed_tests_never_become_clean(self):
        for tests in ({}, {"valid": False, "error": "unavailable"}, {"passed": None}):
            with self.subTest(tests=tests):
                p = self.source("missing.json", {"passed": False, "tests": tests})
                result = pe.compact([("gate", p)])[0][0]["content"]
                self.assertFalse(result["passed"])
                self.assertEqual(result["tests"].get("passed"), tests.get("passed"))
        for tests in (None, [], {"outcomes": None}):
            with self.subTest(tests=tests), self.assertRaises((TypeError, AttributeError)):
                pe.test_summary(tests, "TEST-ONLY")

    def test_advisory_is_append_only_with_same_summary_and_no_authoritative_file(self):
        value = gate(outcome="failed")
        a = pe.advisory_result(self.folder, 1, value); b = pe.advisory_result(self.folder, 1, value)
        self.assertNotEqual(a["full_result_path"], b["full_result_path"])
        for summary in (a, b):
            p = Path(summary["full_result_path"])
            self.assertEqual(json.loads(p.read_text()), value)
            expected = pe.compact([("gate", p)])[0][0]["content"]
            self.assertEqual({k: summary[k] for k in expected}, expected)
            self.assertLess(pe.size(summary), pe.ATTACHMENT_CAP)
        self.assertFalse((self.folder / "gate_r1.json").exists())


class TransportIntegrationTests(unittest.TestCase):
    setUp = controls.ControlTests.setUp
    git = controls.ControlTests.git

    def test_new_helper_is_frozen_from_base(self):
        self.assertEqual((self.run/'harness/prompt_evidence.py').read_bytes(), (self.root/'loop/prompt_evidence.py').read_bytes())

    def test_advisory_cli_compact_stdout_preserves_failure_exit_and_full_file(self):
        value = gate(outcome="failed")
        with patch('gates.gate', return_value=value), redirect_stdout(io.StringIO()) as output:
            code = controls.c.main(['--root', str(self.root), '--runs', str(self.runs), 'gate', '--advisory', '--step', str(self.n)])
        result = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(result['gates'], value['gates'])
        self.assertEqual(json.loads(Path(result['full_result_path']).read_text()), value)
        self.assertLess(len(output.getvalue().encode()), pe.ATTACHMENT_CAP)
        self.assertFalse((self.run/'gate_r1.json').exists())

    def test_role_prompt_and_metadata_preserve_over_cap_prior_findings(self):
        prior = [{'step': 0, 'blocking_findings': [{'id': 'F0', 'description': 'TEST-ONLY exact ' * 6000}]}]
        meta = controls.c.read(self.run/'step.json'); meta['prior_attempts'] = prior; controls.c.write(self.run/'step.json', meta)
        runner = run.Runner(self.root, fixtures=True); runner.step=self.n; runner.step_dir=self.run; runner.harness=self.run/'harness'
        runner.fixture=lambda role,output,cwd,r: output.write_text('TEST-ONLY')
        for role in ('builder_plan','builder_build','enhancer'):
            try: runner.role(role, role+'.json')
            except run.RoleError: pass
            prompt = (self.run/(role+'.prompt.md')).read_text()
            entries = json.loads(prompt.split('full sources remain authoritative):\n')[1])
            self.assertEqual(entries[0]['content'], prior)
            metadata = controls.c.read(self.run/'step.json')['attachment_compaction'][-1]
            self.assertTrue(metadata['attachment_over_cap'])
            self.assertTrue(metadata['section_over_cap'])
            self.assertEqual(metadata['section_bytes'], pe.size(entries))

    def test_advisory_overflow_is_captured_in_step_metadata(self):
        value=gate(1); value['gates']['G1']['details']={'critical': 'TEST-ONLY '*4000}
        pe.advisory_result(self.run, 1, value)
        runner=run.Runner(self.root,fixtures=True);runner.step=self.n;runner.step_dir=self.run;runner.harness=self.run/'harness'
        runner.fixture=lambda role,output,cwd,r: output.write_text('TEST-ONLY')
        runner.role('builder_plan','builder_plan.md')
        self.assertTrue(controls.c.read(self.run/'step.json')['advisory_compaction'][0]['attachment_over_cap'])

    def test_only_build_and_enhancer_gain_only_advisory_subfolder_access(self):
        runner=run.Runner(self.root); runner.step=self.n;runner.step_dir=self.run;runner.harness=self.run/'harness'
        for role in ('builder_plan','builder_build','enhancer','evaluator','researcher'):
            process=Mock();process.poll.return_value=1;process.returncode=1;process.stdin=io.StringIO()
            with patch.object(run.subprocess,'Popen',return_value=process) as spawn:
                with self.assertRaisesRegex(run.RoleError,'failed with exit 1'):
                    runner.role(role,role+'.json')
                argv=spawn.call_args.args[0]
            if role in ('builder_build','enhancer'):
                self.assertEqual(argv[argv.index('--add-dir')+1],str(self.run/'advisory'))
                self.assertEqual(argv.count('--add-dir'),1)
            else: self.assertNotIn('--add-dir',argv)

    def test_malformed_attachment_fails_closed_before_any_role_process(self):
        runner=run.Runner(self.root);runner.step=self.n;runner.step_dir=self.run;runner.harness=self.run/'harness'
        for raw in ('null','[]','not JSON'):
            (self.run/'gate_r1.json').write_text(raw)
            with patch.object(run.subprocess,'Popen') as spawn:
                with self.assertRaisesRegex(run.RoleError,'unusable evidence attachment'):
                    runner.role('enhancer','enhancement.json')
                spawn.assert_not_called()
            self.assertEqual((self.run/'gate_r1.json').read_text(),raw)
