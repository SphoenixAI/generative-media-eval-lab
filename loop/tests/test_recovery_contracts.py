"""Failure/recovery contracts using disposable workspaces and actual schemas."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import tomllib
import unittest

HARNESS = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('recovery_loopctl', HARNESS / 'loopctl.py')
ctl_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ctl_module)


class RecoveryContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='loop-recovery-contract-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'worktree'
        self.runs = Path(self.temp.name) / 'runs'
        self.run = self.runs / '0001'
        self.run.mkdir(parents=True)
        (self.root / 'loop/reports').mkdir(parents=True)
        self.ctl = ctl_module.Control(self.root, self.runs)
        shutil.copytree(HARNESS / 'schemas', self.run / 'harness/schemas')
        self.item = dict(id='L00', title='Verify bootstrap', priority='P0', approval='APPROVED',
                         size='S', risk='LOW', category='tooling', depends_on=[], human_review=False,
                         authorized_protected=[], authorized_test_changes=[], authorized_dependencies=False,
                         probes=[], acceptance=['TEST-ONLY acceptance'])
        self.state = dict(items={'L01': {'status': 'DONE', 'retries': 0}}, steps=[], last_integrated_test_count=209)
        self.backlog = ctl_module.toml_item(self.item)
        (self.root / 'loop/backlog.toml').write_text(self.backlog)
        self.report_name = 'loop/reports/STEP-0001-L00.md'
        self.report = '# TEST-ONLY report\n\nDecision: pending\n\n' + ''.join('## ' + s + '\n\n' for s in ctl_module.SECTIONS)
        (self.root / self.report_name).write_text(self.report)
        (self.run / 'report.md').write_text(self.report)
        self.write('step.json', dict(step=1, number=1, item=self.item, base_commit='TEST-ONLY-base',
             started_at='2026-10-08T00:00:00+00:00', report=self.report_name, plan='TEST-ONLY acceptance\n',
             state_before=self.state, backlog_before=self.backlog))
        self.write('gate_r1.json', dict(passed=True, gates={}, flags=[], tests={'passed': 209}))
        self.write('export_r1.json', {'diff_sha256': 'TEST-ONLY-digest'})
        for name in ('self_eval', 'eval_r1', 'research'):
            value = json.loads((HARNESS / 'tests/fixtures' / (name + '.json')).read_text())
            value.update(step=1, item='L00')
            if name == 'eval_r1':
                value['diff_sha256'] = 'TEST-ONLY-digest'
            self.write(name + '.json', value)
        self.write('research_view/claims.json', {'claims': []})

    def write(self, name, value):
        ctl_module.write(self.run / name, value)

    def read(self, name):
        return json.loads((self.run / name).read_text())

    def test_evaluator_wrong_role_round_or_identity_is_rejected(self):
        original = self.read('eval_r1.json')
        for field, wrong in [('role', 'builder'), ('round', 2), ('step', 9), ('item', 'OTHER')]:
            with self.subTest(field=field):
                value = copy.deepcopy(original)
                value[field] = wrong
                self.write('eval_r1.json', value)
                with self.assertRaises(ValueError):
                    self.ctl.role(1, 'eval_r1.json', 'evaluation')
        self.write('eval_r1.json', original)
        self.assertEqual(self.ctl.role(1, 'eval_r1.json', 'evaluation')['role'], 'evaluator')

    def test_self_evaluation_requires_builder_role_and_self_hash(self):
        original = self.read('self_eval.json')
        for field, wrong in [('role', 'evaluator'), ('round', 2), ('diff_sha256', 'pretend-external')]:
            with self.subTest(field=field):
                value = copy.deepcopy(original)
                value[field] = wrong
                self.write('self_eval.json', value)
                with self.assertRaises(ValueError):
                    self.ctl.role(1, 'self_eval.json', 'evaluation')

    def test_malformed_and_structurally_invalid_outputs_finish_as_rf(self):
        for raw in ('{not valid JSON', '{"scores": {"accuracy": null}}'):
            with self.subTest(raw=raw):
                (self.run / 'self_eval.json').write_text(raw)
                result = self.ctl.decide(1)
                self.assertEqual((result['decision'], result['rule']), ('REVERT', 'RF'))
                summary = self.ctl.finish(1)
                self.assertEqual(summary['calibration'], {})
                state = json.loads((self.root / 'loop/state.json').read_text())
                self.assertEqual(state['items']['L00']['retries'], 0)
                self.assertEqual(len(state['steps']), 1)
                self.assertEqual((self.root / 'loop/reports/STEP-0001/self_eval.json').read_text(), raw)
                (self.run / 'failure.json').unlink()

    def test_missing_primary_evidence_is_rf_and_never_becomes_ledger_evidence(self):
        self.write('research_view/claims.json', {'claims': [{'id': 'C1', 'claim': 'TEST-ONLY assertion'}]})
        research = self.read('research.json')
        research['claims'] = [dict(id='C1', claim='TEST-ONLY assertion', origin='plan', verdict='CONTRADICTED',
             sources=[], newer_practice=None, affects_this_step=True, recommended_action='TEST-ONLY correction')]
        research['proposals'] = [dict(title='Clarify wording', rationale='TEST-ONLY wording correction',
             size='S', risk='LOW', category='docs', relevance=4, claim_id='C1')]
        self.write('research.json', research)
        decision = self.ctl.decide(1)
        self.assertEqual(decision['rule'], 'RF')
        summary = self.ctl.finish(1)
        self.assertEqual(summary['auto_approved'], [])
        self.assertEqual((self.root / 'loop/research/ledger.jsonl').read_text(), '')

    def test_enhancer_proposal_survives_reset_and_finish_is_idempotent(self):
        proposal = self.root / 'loop/proposals/STEP-0001.toml'
        proposal.parent.mkdir()
        proposal.write_text('''[[proposal]]
 title = "TEST-ONLY follow-up"
 rationale = "TEST-ONLY work outside this step"
 size = "S"
 risk = "LOW"
 category = "test"
 acceptance = ["TEST-ONLY follow-up acceptance"]
''')
        evaluation = self.read('eval_r1.json')
        evaluation['scores']['accuracy']['score'] = 2
        self.write('eval_r1.json', evaluation)
        decision = self.ctl.decide(1)
        self.assertEqual(decision['rule'], 'R3')
        self.assertEqual((self.run / 'proposals.toml').read_text(), proposal.read_text())
        proposal.unlink()  # Simulate reset/clean removing an untracked proposal.
        (self.root / self.report_name).unlink()
        self.ctl.finish(1)
        first_state = (self.root / 'loop/state.json').read_bytes()
        first_backlog = (self.root / 'loop/backlog.toml').read_bytes()
        appended = tomllib.loads(first_backlog.decode())['item'][-1]
        self.assertEqual(appended['approval'], 'PROPOSED')
        self.assertEqual(appended['acceptance'], ['TEST-ONLY follow-up acceptance'])
        self.ctl.finish(1)
        self.assertEqual((self.root / 'loop/state.json').read_bytes(), first_state)
        self.assertEqual((self.root / 'loop/backlog.toml').read_bytes(), first_backlog)
        self.assertEqual(json.loads(first_state)['items']['L00']['retries'], 1)


if __name__ == '__main__':
    unittest.main()
