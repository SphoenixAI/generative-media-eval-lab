"""TEST-ONLY orchestrator tests: process boundaries, isolation and failure paths."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

SPEC = importlib.util.spec_from_file_location('loop_runner', Path(__file__).parents[1] / 'run.py')
run = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(run)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / 'loop').mkdir()
        (self.root / 'loop/config.toml').write_text('''
[paths]
runs_dir = "runs"
env_dir = "env"
[git]
main = "main"
integration = "loop/integration"
remote = "origin"
[commands]
doctor = ""
[limits]
max_codex_failures = 3
max_consecutive_non_integrate = 3
''')
        self.runner = run.Runner(self.root)
        self.runner.git = Mock(return_value=subprocess.CompletedProcess([], 0, '', ''))

    def tearDown(self):
        self.temporary.cleanup()

    def test_evaluator_separate_read_only_process_and_hash_schema(self):
        with patch.dict(os.environ, {'LOOP_EVAL_MODEL': 'TEST-ONLY alternate'}):
            argv = run.role_argv('evaluator', self.root / 'view', self.root / 'out.json', 'schema.json')
        self.assertEqual(argv[0:2], ['codex', 'exec'])
        self.assertEqual(argv[argv.index('-s') + 1], 'read-only')
        self.assertIn('--skip-git-repo-check', argv)
        self.assertIn('--output-schema', argv)
        self.assertEqual(argv[argv.index('-m') + 1], 'TEST-ONLY alternate')
        self.assertNotIn('--full-auto', argv)

    def test_builder_and_researcher_have_distinct_capabilities(self):
        builder = run.role_argv('builder_build', self.root, 'out', 'schema')
        researcher = run.role_argv('researcher', self.root / 'research_view', 'out', 'schema')
        self.assertIn('workspace-write', builder)
        self.assertNotIn('web_search=live', builder)
        self.assertIn('read-only', researcher)
        self.assertIn('web_search=live', researcher)

    def test_strict_schema_rejects_missing_extra_wrong_and_bool_scores(self):
        schema = {'type': 'object', 'required': ['score'], 'additionalProperties': False,
                  'properties': {'score': {'type': 'integer', 'enum': [0, 1, 2, 3, 4]}}}
        for data in ({}, {'score': 4, 'extra': 1}, {'score': '4'}, {'score': True}, {'score': 5}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                run.validate(data, schema)
        run.validate({'score': 4}, schema)

    def test_schema_nullable_invariant(self):
        schema = {'anyOf': [{'type': 'null'}, {'type': 'string', 'enum': ['I1']}]}
        run.validate(None, schema)
        run.validate('I1', schema)
        with self.assertRaises(ValueError):
            run.validate('invented', schema)

    def test_enhancement_conditions_are_not_averaged(self):
        evaluation = {'scores': {'one': {'score': 4}, 'two': {'score': 2}}, 'blocking_findings': []}
        research = {'claims': []}
        self.assertTrue(run.needs_enhancement(evaluation, research, {'passed': True}))
        evaluation['scores']['two']['score'] = 4
        self.assertFalse(run.needs_enhancement(evaluation, research, {'passed': True}))
        self.assertTrue(run.needs_enhancement(evaluation, research, {'passed': False}))
        research['claims'] = [{'affects_this_step': True, 'verdict': 'CONFIRMED',
                               'newer_practice': {'summary': 'TEST-ONLY newer practice'}}]
        self.assertTrue(run.needs_enhancement(evaluation, research, {'passed': True}))

    def test_refuses_main_push_even_if_called_directly(self):
        self.runner.git.return_value.stdout = 'main\n'
        with self.assertRaisesRegex(run.LoopError, 'Refusing push'):
            self.runner.push()
        self.assertEqual(self.runner.git.call_count, 1)

    def test_push_is_explicit_integration_ref_no_force(self):
        self.runner.git.return_value.stdout = 'loop/integration\n'
        self.runner.push()
        self.runner.git.assert_called_with('push', 'origin', 'HEAD:refs/heads/loop/integration')

    def test_merge_conflict_aborts_never_rebases(self):
        def git(*args, **kwargs):
            code = 1 if args[0] in ('merge-base', 'merge') and args[-1] != '--abort' else 0
            return subprocess.CompletedProcess(args, code, '', '')
        self.runner.git.side_effect = git
        with self.assertRaisesRegex(run.LoopError, 'Merge conflict'):
            self.runner.sync()
        self.assertIn(unittest.mock.call('merge', '--abort', check=False), self.runner.git.call_args_list)
        self.assertFalse(any(call.args[0] == 'rebase' for call in self.runner.git.call_args_list))

    def test_live_lock_does_not_modify_or_race_owner(self):
        self.runner.git.return_value.stdout = 'loop/integration\n'
        run.write_json(self.runner.runs / 'lock.json', {'pid': os.getpid()})
        self.runner.ctl = Mock()
        with self.assertRaisesRegex(run.LoopError, 'Live lock owner'):
            self.runner.preflight()
        self.assertFalse(self.runner.git_ready)
        self.runner.ctl.assert_not_called()

    def test_heartbeat_updates_only_own_lock(self):
        path = self.runner.runs / 'lock.json'
        run.write_json(path, {'pid': os.getpid(), 'heartbeat': 'old'})
        self.runner.heartbeat()
        self.assertNotEqual(run.read_json(path)['heartbeat'], 'old')
        run.write_json(path, {'pid': os.getpid() + 100, 'heartbeat': 'other'})
        self.runner.heartbeat()
        self.assertEqual(run.read_json(path)['heartbeat'], 'other')

    def test_gate_precedes_export_and_hash_mismatch_gets_exactly_one_retry(self):
        self.runner.step = 1
        self.runner.step_dir = self.root / 'runs/0001'
        view = self.runner.step_dir / 'eval_view_r1'
        view.mkdir(parents=True)
        (view / 'diff_sha256.txt').write_text('actual')
        events = []
        self.runner.ensure_branch = Mock()
        self.runner.ctl = lambda name, *a, **k: events.append(name)
        def role(*args):
            run.write_json(self.runner.step_dir / 'eval_r1.json', {'diff_sha256': 'wrong'})
            return {'diff_sha256': 'wrong'}
        self.runner.role = Mock(side_effect=role)
        result = self.runner.evaluate(1)
        self.assertEqual(events, ['gate', 'export'])
        self.assertEqual(self.runner.role.call_count, 2)
        self.assertEqual(result['diff_sha256'], 'wrong')
        self.assertTrue((self.runner.step_dir / 'eval_r1_hash_mismatch.json').exists())

    def test_matching_hash_needs_no_rerun(self):
        self.runner.step = 1
        self.runner.step_dir = self.root / 'runs/0001'
        view = self.runner.step_dir / 'eval_view_r1'
        view.mkdir(parents=True)
        (view / 'diff_sha256.txt').write_text('actual')
        self.runner.ensure_branch = Mock()
        self.runner.ctl = Mock()
        self.runner.role = Mock(return_value={'diff_sha256': 'actual'})
        self.runner.evaluate(1)
        self.assertEqual(self.runner.role.call_count, 1)

    def test_role_failure_records_rf_reverts_and_preserves_external_evidence(self):
        step_dir = self.root / 'runs/0001'
        step_dir.mkdir(parents=True)
        run.write_json(step_dir / 'step.json', {'item': {'id': 'L00', 'title': 'TEST-ONLY'}})
        (step_dir / 'harness').mkdir()
        (step_dir / 'harness/config.toml').write_text((self.root / 'loop/config.toml').read_text())
        def ctl(name, *args, **kwargs):
            if name == 'next':
                return {'id': 'L00'}
            if name == 'start':
                return {'step': 1, 'base_commit': 'base'}
            if name == 'decide':
                run.write_json(step_dir / 'decision.json', {'decision': 'REVERT', 'rule': 'RF'})
        self.runner.ensure_branch = Mock()
        self.runner.ctl = Mock(side_effect=ctl)
        self.runner.role = Mock(side_effect=run.RoleError('TEST-ONLY timeout'))
        self.runner.commit = Mock()
        self.runner.push = Mock()
        self.runner.update_pr = Mock()
        result = self.runner.one_step()
        self.assertEqual(result['rule'], 'RF')
        self.assertEqual(run.read_json(step_dir / 'failure.json')['rule'], 'RF')
        self.assertIn(unittest.mock.call('reset', '--hard', 'base'), self.runner.git.call_args_list)
        self.assertIn(unittest.mock.call('clean', '-fd'), self.runner.git.call_args_list)
        self.assertEqual(self.runner.codex_failures, 1)
        self.runner.commit.assert_called_once()

    def test_dry_run_requires_sibling_layout_before_setup(self):
        # A malicious absolute RUNS path must never be used by dry-run setup.
        runner = Mock(config={'paths': {'runs_dir': '/unsafe-real-runs'}})
        with patch.object(run, 'command'), patch.object(run, 'Runner', return_value=runner):
            with self.assertRaisesRegex(run.LoopError, 'standard sibling layout'):
                run.dry_run(self.root, Mock(once=True, max_steps=1, until=None))

    def test_model_metadata_uses_observed_header_or_unknown(self):
        self.assertEqual(run.observed_model('OpenAI Codex\nmodel: TEST-ONLY-model\nuser\nhello'), 'TEST-ONLY-model')
        self.assertEqual(run.observed_model('no model header'), 'unknown')
        self.assertEqual(run.observed_model('header\nuser\nmodel: invented-by-role'), 'unknown')

    def test_fixture_role_records_timing_and_synthetic_model(self):
        self.runner.fixture_mode = True
        self.runner.step = 1
        self.runner.step_dir = self.root / 'runs/0001'
        self.runner.harness = self.root / 'loop'
        (self.runner.harness / 'prompts').mkdir()
        (self.runner.harness / 'prompts/builder_plan.md').write_text('TEST-ONLY prompt')
        run.write_json(self.runner.step_dir / 'step.json', {
            'item': {'id': 'L00'}, 'report': 'loop/reports/STEP-0001-L00.md'})
        self.runner.fixture = lambda role, output, cwd, round_number: output.write_text('TEST-ONLY')
        self.runner.role('builder_plan', 'builder_plan.md')
        call = run.read_json(self.runner.step_dir / 'role_metadata.json')['calls'][0]
        self.assertEqual(call['model'], 'SYNTHETIC_FIXTURE')
        self.assertEqual(call['status'], 'COMPLETED')
        self.assertGreaterEqual(call['elapsed_seconds'], 0)
        self.assertLessEqual(call['started_at'], call['finished_at'])

    def test_overnight_cutoff_and_same_day_cutoff(self):
        now = run.dt.datetime(2026, 10, 8, 19, 30)
        self.assertEqual(run.cutoff('07:30', now), run.dt.datetime(2026, 10, 9, 7, 30))
        self.assertEqual(run.cutoff('23:30', now), run.dt.datetime(2026, 10, 8, 23, 30))

    def test_configured_command_arrays_preserve_spaces(self):
        self.assertEqual(self.runner.configured_command(['{python}', '-m', 'pytest', '{root}/a file']),
                         [str(self.runner.environment / 'bin/python'), '-m', 'pytest', str(self.root.resolve() / 'a file')])

    def test_command_uses_argument_array_not_shell(self):
        with patch.object(run.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')) as process:
            run.command(['echo', 'a path with spaces; still one arg'], self.root)
        self.assertEqual(process.call_args.args[0][1], 'a path with spaces; still one arg')
        self.assertNotIn('shell', process.call_args.kwargs)


if __name__ == '__main__':
    unittest.main()
