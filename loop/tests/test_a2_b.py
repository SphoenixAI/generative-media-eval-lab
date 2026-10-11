"""TEST-ONLY canonical finding identity and graceful boundary contracts."""
import copy
import unittest
from unittest.mock import Mock, patch
import test_recovery_contracts as recovery
import test_run as orchestrator
c=recovery.ctl_module


class FindingIdentityTests(unittest.TestCase):
    setUp=recovery.RecoveryContracts.setUp
    write=recovery.RecoveryContracts.write
    read=recovery.RecoveryContracts.read
    def duplicated(self):
        ev=self.read('eval_r1.json')
        first=dict(id='F1',dimension='production_quality',severity='MATERIAL',invariant=None,location='TEST-ONLY.py:1',description='TEST-ONLY first distinct finding',required_fix='TEST-ONLY repair first')
        ev['blocking_findings']=[first,{**first,'description':'TEST-ONLY second distinct finding','location':'TEST-ONLY.py:2'}]
        self.write('eval_r1.json',ev); return ev

    def test_duplicate_model_ids_preserve_distinct_findings_and_raw_evidence(self):
        raw=self.duplicated(); ev=self.ctl.canonicalize_evaluation(1,1)
        self.assertEqual([f['id'] for f in ev['blocking_findings']],['F0001-R1-001','F0001-R1-002'])
        self.assertEqual([f['description'] for f in ev['blocking_findings']],[f['description'] for f in raw['blocking_findings']])
        self.assertEqual(self.read('eval_r1.raw-01.json'),raw)
        self.assertEqual(self.ctl.canonicalize_evaluation(1,1),ev)

    def test_round_two_and_enhancer_refer_to_canonical_findings(self):
        self.duplicated(); self.ctl.canonicalize_evaluation(1,1)
        second=self.read('eval_r1.json'); second.update(round=2,blocking_findings=[],prior_findings=[dict(ref='F0001-R1-001',status='RESOLVED'),dict(ref='F0001-R1-002',status='RESOLVED')])
        self.write('eval_r2.json',second); self.ctl.canonicalize_evaluation(1,2)
        enhancement=dict(resolutions=[dict(ref=f'F0001-R1-{i:03d}',action='FIXED',evidence=f'TEST-ONLY proof {i}') for i in (1,2)],amendments=[])
        self.write('enhancement.json',enhancement)
        self.assertEqual(self.ctl.role(1,'enhancement.json','enhancement'),enhancement)
        self.write('gate_r2.json',self.read('gate_r1.json')); self.write('export_r2.json',self.read('export_r1.json'))
        self.assertEqual(self.ctl.decide(1)['rule'],'R6')
        enhancement['resolutions'].pop(); self.write('enhancement.json',enhancement)
        self.assertEqual(self.ctl.decide(1)['rule'],'R4')

    def test_unknown_and_duplicate_enhancer_references_are_errors(self):
        self.duplicated(); self.ctl.canonicalize_evaluation(1,1)
        for refs in (['eval_r1.json:production_quality'],['F0001-R1-001']*2):
            with self.subTest(refs=refs):
                self.write('enhancement.json',dict(resolutions=[dict(ref=ref,action='FIXED',evidence='TEST-ONLY') for ref in refs],amendments=[]))
                with self.assertRaises(ValueError): self.ctl.role(1,'enhancement.json','enhancement')

    def test_unknown_and_duplicate_prior_statuses_are_errors(self):
        self.duplicated(); self.ctl.canonicalize_evaluation(1,1)
        for refs in (['eval_r1.json:production_quality'],['F0001-R1-001']*2):
            ev=self.read('eval_r1.json'); ev.update(round=2,blocking_findings=[],prior_findings=[dict(ref=ref,status='RESOLVED') for ref in refs]); self.write('eval_r2.json',ev)
            with self.assertRaises(ValueError): self.ctl.canonicalize_evaluation(1,2)

    def test_nonblocking_score_note_has_explicit_harness_reference(self):
        self.ctl.canonicalize_evaluation(1,1)
        self.write('enhancement.json',dict(resolutions=[dict(ref='F0001-R1-D-production_quality',action='FIXED',evidence='TEST-ONLY score-note correction')],amendments=[]))
        self.ctl.role(1,'enhancement.json','enhancement')
        ids={r['id'] for r in self.read('finding-refs-r1.json')['score_notes']}
        self.assertIn('F0001-R1-D-production_quality',ids)

    def test_round_specific_ids_are_disjoint(self):
        self.duplicated(); a=self.ctl.canonicalize_evaluation(1,1)
        b=copy.deepcopy(a); b['round']=2; self.write('eval_r2.json',b); b=self.ctl.canonicalize_evaluation(1,2)
        self.assertTrue({f['id'] for f in a['blocking_findings']}.isdisjoint(f['id'] for f in b['blocking_findings']))


class GracefulStopTests(unittest.TestCase):
    setUp=orchestrator.RunnerTests.setUp
    tearDown=orchestrator.RunnerTests.tearDown
    def test_stop_after_step_prevents_next_step_at_boundary(self):
        (self.root/'loop/STOP_AFTER_STEP').touch(); self.runner.preflight=Mock(); self.runner.stop=Mock(); self.runner.one_step=Mock()
        self.assertEqual(self.runner.run(),0); self.runner.one_step.assert_not_called()
        self.runner.stop.assert_called_once_with('STOP_AFTER_STEP file exists')

    def test_pause_returns_on_graceful_stop(self):
        (self.root/'loop/STOP_AFTER_STEP').touch()
        with patch.object(orchestrator.run.time,'sleep') as sleep:
            self.runner.pause(30); sleep.assert_not_called()

if __name__=='__main__': unittest.main()
