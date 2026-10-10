"""Negative gate tests use synthetic files; no operator workspace is opened."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gates


class GateChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.config = {'paths': {'forbidden': ['pilot-local/**', '.tools/**', '**/.env*', '**/*.mp4', 'AGENTS.md', 'loop/**'], 'generated': ['outputs/**', 'loop/reports/**']}, 'limits': {'max_changed_lines': 4}}
        self.node = 'tests/test_sample.py::test_case'
        self.baseline = {'passed': 1, 'collected': [self.node], 'outcomes': {self.node: 'passed'}}
        self.tests = {'passed': 1, 'collected': [self.node], 'outcomes': {self.node: 'passed'}, 'exit_code': 0, 'valid': True}
        self.report = '## Plan\nTEST-ONLY plan\n## Probes\n'
        self.step = {'number': 2, 'item': {}, 'plan_sha256': gates.digest(b'TEST-ONLY plan')}

    def check(self, changed=None, protected=None, research=None, last_count=0):
        return gates.static_checks(self.root, self.config, self.baseline, protected or {}, changed or {}, self.step, self.tests, self.report, research or {}, last_count)

    @staticmethod
    def delta(added=(), removed=(), symlink=False):
        return {'added': list(added), 'removed': list(removed), 'symlink': symlink, 'binary': False, 'untracked': False}

    def test_unchanged_passes(self):
        result, flags = self.check()
        self.assertTrue(all(g['passed'] for g in result.values()))
        self.assertEqual(flags, [])

    def test_exit_failure_and_invalid_junit_block(self):
        for key, value in [('exit_code', 1), ('valid', False)]:
            with self.subTest(key=key):
                previous = self.tests[key]
                self.tests[key] = value
                self.assertFalse(self.check()[0]['G1']['passed'])
                self.tests[key] = previous

    def test_last_integrated_count_cannot_drop(self):
        self.assertFalse(self.check(last_count=2)[0]['G2']['passed'])

    def test_missing_test_and_deselection_block(self):
        self.tests.update(collected=[], outcomes={})
        result, _ = self.check()
        self.assertFalse(result['G3']['passed'])
        self.assertFalse(result['G3b']['passed'])

    def test_skip_and_xfail_block(self):
        for outcome in ['skipped', 'xfailed']:
            self.tests['outcomes'][self.node] = outcome
            self.assertFalse(self.check()[0]['G3b']['passed'])

    def test_explicit_test_authorization_is_exact(self):
        self.tests.update(collected=[], outcomes={})
        self.step['item']['authorized_test_changes'] = ['tests/*']
        self.assertFalse(self.check()[0]['G3']['passed'])
        self.step['item']['authorized_test_changes'] = [self.node]
        result, _ = self.check()
        self.assertTrue(result['G3']['passed'])
        self.assertTrue(result['G3b']['passed'])

    def test_test_removal_flag(self):
        result, flags = self.check({'tests/test_sample.py': self.delta(removed=['assert value'])})
        self.assertIn('TEST_CHANGED', flags)
        self.assertFalse(result['G4']['blocking'])

    def test_protected_bytes_require_exact_authorization(self):
        (self.root / 'accepted.json').write_text('changed')
        protected = {'accepted.json': gates.digest(b'original')}
        self.assertFalse(self.check(protected=protected)[0]['G5']['passed'])
        self.step['item']['authorized_protected'] = ['accepted.json']
        self.assertTrue(self.check(protected=protected)[0]['G5']['passed'])
        (self.root / 'accepted.json').unlink()
        self.step['item']['authorized_protected'] = []
        self.assertFalse(self.check(protected=protected)[0]['G5']['passed'])

    def test_forbidden_current_report_exception_only(self):
        for path in ['loop/config.toml', 'loop/reports/STEP-0001-L00.md', 'loop/reports/STEP-0002-X/fake.md', 'loop/reports/STEP-0002-X.json', 'loop/proposals/STEP-0001.toml', 'AGENTS.md', '.env', 'clip.mp4', 'pilot-local/data.json']:
            with self.subTest(path=path):
                self.assertFalse(self.check({path: self.delta()})[0]['G6']['passed'])
        for path in ['loop/reports/STEP-0002-L00.md', 'loop/proposals/STEP-0002.toml', 'tests/fixture.mp4']:
            with self.subTest(path=path):
                self.assertTrue(self.check({path: self.delta()})[0]['G6']['passed'])

    def test_symlink_exception_is_blocked(self):
        self.assertFalse(self.check({'tests/link': self.delta(symlink=True)})[0]['G6']['passed'])

    def test_line_cap_excludes_generated_only(self):
        self.assertFalse(self.check({'src/app.py': self.delta(added=['a'] * 5)})[0]['G7']['passed'])
        self.assertTrue(self.check({'outputs/generated.json': self.delta(added=['a'] * 5)})[0]['G7']['passed'])

    def test_secret_scan_and_home_paths(self):
        result, flags = self.check({'README.md': self.delta(added=['key = "' + 'sk-' + 'X' * 30 + '"', '/Users/test/private/file'])})
        self.assertFalse(result['G8']['passed'])
        self.assertFalse(result['G9']['passed'])
        result, flags = self.check({'src/app.py': self.delta(added=['/home/test/file'])})
        self.assertTrue(result['G9']['passed'])
        self.assertIn('HOME_PATH', flags)

    def test_dependency_change_blocks_until_authorized(self):
        result, flags = self.check({'uv.lock': self.delta()})
        self.assertFalse(result['G10']['passed'])
        self.assertIn('DEPENDENCY_CHANGED', flags)
        self.step['item']['authorized_dependencies'] = True
        self.assertTrue(self.check({'uv.lock': self.delta()})[0]['G10']['passed'])

    def test_sealed_plan_cannot_be_edited(self):
        self.report = self.report.replace('TEST-ONLY plan', 'new plan')
        self.assertFalse(self.check()[0]['G11']['passed'])

    def test_plan_amendment_requires_affecting_contradiction(self):
        self.report += '## Plan amendments\n- C1: change a method\n'
        self.assertFalse(self.check()[0]['G11']['passed'])
        for verdict, affects, expected in [('CONFIRMED', True, False), ('OUTDATED', False, False), ('CONTRADICTED', True, True)]:
            research = {'claims': [{'id': 'C1', 'verdict': verdict, 'affects_this_step': affects}]}
            self.assertEqual(self.check(research=research)[0]['G11']['passed'], expected)
        self.report = self.report.replace('C1:', 'C10:')
        self.assertFalse(self.check(research=research)[0]['G11']['passed'])

    def test_public_prose_flags(self):
        result, flags = self.check({'docs/guide.md': self.delta()})
        self.assertIn('PUBLIC_PROSE', flags)
        self.assertFalse(result['G13']['blocking'])

    def test_plan_normalizes_trailing_spaces_and_crlf(self):
        self.assertEqual(gates.plan_body('## Plan\r\n\r\nA  \r\nB\r\n\r\n## Probes\r\n'), 'A\nB')


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def test_junit_maps_parameterized_ids_and_outcomes(self):
        path = self.root / 'junit.xml'
        path.write_text('<testsuites><testsuite tests="3"><testcase classname="tests.test_a.Check" name="test_x[a]"/><testcase classname="tests.test_a" name="test_y"><skipped type="pytest.xfail"/></testcase><testcase classname="tests.test_a" name="test_z"><failure/></testcase></testsuite></testsuites>')
        ids = ['tests/test_a.py::Check::test_x[a]', 'tests/test_a.py::test_y', 'tests/test_a.py::test_z']
        result = gates.junit(path, ids)
        self.assertEqual(result['passed'], 1)
        self.assertEqual(list(result['outcomes'].values()), ['passed', 'xfailed', 'failed'])

    def test_junit_rejects_fake_count_duplicate_and_unknown(self):
        path = self.root / 'junit.xml'
        case = '<testcase classname="tests.test_a" name="test_x"/>'
        for content in ['<testsuites/>', '<testsuite tests="2">' + case + '</testsuite>', '<testsuite tests="2">' + case * 2 + '</testsuite>', '<testsuite tests="1"><testcase classname="fake" name="fake"/></testsuite>']:
            path.write_text(content)
            with self.assertRaises(ValueError): gates.junit(path, ['tests/test_a.py::test_x'])

    def test_metadata_hash_never_reads_contents(self):
        private = self.root / 'pilot-local'
        private.mkdir()
        media = private / 'clip.txt'
        media.write_text('TEST-ONLY')
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('private content opened')), patch.object(Path, 'read_text', side_effect=AssertionError('private content opened')):
            before = gates.metadata_hash(private)
            os.utime(media, ns=(1, 2))
            self.assertNotEqual(before, gates.metadata_hash(private))

    def test_git_visible_copy_excludes_private_and_symlinks(self):
        (self.root / 'src').mkdir()
        (self.root / 'src/app.py').write_text('TEST-ONLY')
        (self.root / 'pilot-local').mkdir()
        (self.root / 'pilot-local/private').write_text('DO NOT COPY')
        destination = self.root / 'copy'
        with patch.object(gates, 'git', return_value='src/app.py\0pilot-local/private\0'):
            gates.safe_copy(self.root, destination)
        self.assertTrue((destination / 'src/app.py').exists())
        self.assertFalse((destination / 'pilot-local').exists())
        (self.root / 'src/link').symlink_to(self.root / 'pilot-local/private')
        with patch.object(gates, 'git', return_value='src/link\0'):
            with self.assertRaises(ValueError): gates.safe_copy(self.root, destination)

    def test_approval_writes_are_confined_to_copy(self):
        (self.root / 'outputs').mkdir()
        original = self.root / 'outputs/approval.json'
        original.write_text('accepted')
        def execute_copy(command, copied, config, baseline, advisory):
            self.assertNotEqual(copied, self.root)
            (copied / 'outputs/approval.json').write_text('new evidence')
            return {'exit_code': 0}
        config = {'paths': {'env_dir': 'env', 'main_checkout': 'main'}}
        with patch.object(gates, 'git', return_value='outputs/approval.json\0'), patch.object(gates, 'run_command', side_effect=execute_copy):
            result = gates.approval_check(self.root, config)
        self.assertEqual(result['changed_protected'], ['outputs/approval.json'])
        self.assertEqual(original.read_text(), 'accepted')

    def test_virtualenv_python_symlink_is_not_resolved(self):
        env = self.root / 'env'
        (env / 'bin').mkdir(parents=True)
        (env / 'bin/python').symlink_to(sys.executable)
        argv = gates.argv_for(['{python}', '-m', 'pytest'], self.root, {'paths': {'env_dir': 'env'}})
        self.assertEqual(argv[0], str(env / 'bin/python'))

    def test_gate_integrity_fails_closed_and_tests_use_frozen_snapshot(self):
        harness = self.root / 'frozen'
        harness.mkdir()
        (harness / 'config.toml').write_text('[paths]\nenv_dir="env"\nmain_checkout="main"\n')
        (harness / 'baseline.json').write_text(json.dumps({'sandbox': {'available': False}}))
        (harness / 'protected.sha256').write_text('')
        run_dir = self.root / 'runs'
        checks = {'G6': {'passed': True, 'blocking': True, 'details': {}}}
        with patch.object(gates, 'integrity', side_effect=[{'main': 'before'}, {'main': 'after'}]), patch.object(gates, 'product_tests', return_value={'passed': 1}), patch.object(gates, 'changes', return_value={}), patch.object(gates, 'static_checks', return_value=(checks, [])), patch.object(gates, 'approval_check', return_value={'exit_code': 0}), patch.object(gates, 'execute', return_value={'exit_code': 0, 'stdout': '', 'stderr': 'Ran 1 tests'}) as process:
            result = gates.gate(self.root, run_dir, harness, {'number': 1, 'item': {}, 'base_commit': 'TEST-ONLY'}, 1)
        self.assertFalse(result['passed'])
        self.assertIn('G14', result['invariant_violations'])
        self.assertEqual(process.call_args.args[1], harness)
        self.assertIn(str(harness / 'tests'), process.call_args.args[0])
        self.assertTrue((run_dir / 'gate_r1.json').exists())

    def test_advisory_does_not_write_gate_evidence_and_extra_failure_blocks(self):
        harness = self.root / 'frozen'
        harness.mkdir()
        (harness / 'config.toml').write_text('[paths]\nenv_dir="env"\nmain_checkout="main"\n')
        (harness / 'baseline.json').write_text(json.dumps({'sandbox': {'available': False}}))
        (harness / 'protected.sha256').write_text('')
        run_dir = self.root / 'runs'
        checks = {'G6': {'passed': True, 'blocking': True, 'details': {}}}
        with patch.object(gates, 'integrity', side_effect=AssertionError('advisory must skip integrity')), patch.object(gates, 'product_tests', return_value={'passed': 1}), patch.object(gates, 'changes', return_value={}), patch.object(gates, 'static_checks', return_value=(checks, [])), patch.object(gates, 'approval_check', return_value={'exit_code': 0}), patch.object(gates, 'execute', return_value={'exit_code': 1, 'stdout': '', 'stderr': 'failed'}):
            result = gates.gate(self.root, run_dir, harness, {'number': 1, 'item': {}, 'base_commit': 'TEST-ONLY'}, 1, advisory=True)
        self.assertFalse(result['passed'])
        self.assertFalse(result['gates']['G12']['passed'])
        self.assertFalse(run_dir.exists())

    def test_command_runner_never_uses_shell(self):
        with patch.object(gates.subprocess, 'run') as run:
            run.return_value.returncode = 0
            run.return_value.stdout = ''
            run.return_value.stderr = ''
            gates.execute(['echo', '$(not-a-command)'], self.root)
            self.assertIsInstance(run.call_args.args[0], list)
            self.assertNotIn('shell', run.call_args.kwargs)

    def test_failed_spawn_reports_evidence(self):
        with patch.object(gates.subprocess, 'run', side_effect=OSError('missing')):
            result = gates.execute(['missing'], self.root)
        self.assertEqual(result['exit_code'], -1)
        self.assertIn('missing', result['stderr'])


if __name__ == '__main__':
    unittest.main()
