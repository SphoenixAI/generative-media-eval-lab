"""TEST-ONLY post-revert proof and bounded application-path regressions."""
import copy
import json
import unittest
from unittest.mock import patch, Mock
from pathlib import Path
import test_control as controls
import test_run as runners
import gates
c=controls.c
run=runners.run


class ProductInvariantTests(unittest.TestCase):
    def fixture(self, invariants=('I2',)):
        ev=controls.evaluation(4); ev['scores']['intention']['score']=0
        ev['blocking_findings']=[dict(dimension='intention',invariant=i) for i in invariants]
        return ev

    def test_only_explicit_product_invariants_qualify(self):
        for number in range(1,17):
            with self.subTest(invariant=number): self.assertEqual(c.product_zero(self.fixture((f'I{number}',))),number in (2,3,5,6,7,8,9,13))
        for labels in ((),('I2','I1'),('I2','I16'),('I2','I99'),(None,)):
            with self.subTest(labels=labels): self.assertFalse(c.product_zero(self.fixture(labels)))

    def test_each_zero_dimension_requires_its_own_allowed_finding(self):
        ev=self.fixture(); ev['scores']['scope']['score']=0
        self.assertFalse(c.product_zero(ev))
        ev['blocking_findings'].append(dict(dimension='scope',invariant='I13'))
        self.assertTrue(c.product_zero(ev))
        ev=controls.evaluation(4); self.assertFalse(c.product_zero(ev))

    def test_initial_decision_is_always_r0_until_post_revert(self):
        for labels in [('I2',),('I1',),('I2','I16')]:
            result=c.decision(self.fixture(labels),{'passed':True},[],{}, {},None,'exact')
            self.assertEqual(result,{'decision':'REVERT','rule':'R0','stop':True})


class RollbackProofTests(unittest.TestCase):
    git=controls.ControlTests.git
    def setUp(self):
        controls.ControlTests.setUp(self)
        self.integrity={'remote_main':'TEST-ONLY-main','local_main':'TEST-ONLY-local','branch_main':'TEST-ONLY-branch','pilot_listing_sha256':'TEST-ONLY-list'}
        self.patcher=patch.object(gates,'repository_integrity',return_value=self.integrity)
        self.patcher.start(); self.addCleanup(self.patcher.stop)
        (self.root/'protected.txt').write_text('TEST-ONLY fixed artifact')
        (self.root/'loop/protected.sha256').write_text(c.digest((self.root/'protected.txt').read_bytes())+'  protected.txt\n')
        self.git('add','protected.txt','loop/protected.sha256'); self.git('commit','-m','TEST-ONLY protected base')
        meta=self.control.step(self.n); meta.update(base_commit=self.git('rev-parse','HEAD').strip(),integrity_before=self.integrity)
        c.write(self.run/'step.json',meta); self.base=meta['base_commit']
        ev=c.read(controls.ROOT/'tests/fixtures/r0p_eval.json'); ev.update(step=self.n,item='L00',round=1)
        c.write(self.run/'eval_r1.json',ev)
        c.write(self.run/'gate_r1.json',{'gates':{k:{'passed':True,'blocking':True,'details':{}} for k in ('G5','G6','G14')}})
        self.original={'decision':'REVERT','rule':'R0','stop':True,'rounds':1}; c.write(self.run/'decision.json',self.original)

    def revert(self):
        self.git('reset','--hard',self.base); self.git('clean','-fd')

    def check(self):
        self.control.prepare_revert(self.n); self.revert(); return self.control.post_revert(self.n)

    def test_r0p_requires_actual_clean_rollback_and_preserves_initial_decision(self):
        (self.root/'src').mkdir(); (self.root/'src/candidate.py').write_text('TEST-ONLY broken candidate')
        self.assertEqual(self.check(),{'decision':'REVERT','rule':'R0P','stop':False,'rounds':1})
        self.assertFalse((self.root/'src/candidate.py').exists())
        self.assertEqual(c.read(self.run/'decision.pre-revert.json'),self.original)
        proof=c.read(self.run/'rollback-verification.json')
        self.assertTrue(proof['verified']); self.assertIn('outside the checked paths',proof['limitation'])
        self.control.finish(self.n)
        self.assertEqual(self.control.state()['items']['L00']['retries'],1)
        self.assertEqual(run.trailing_counts(self.control.state()),(1,0))

    def test_protected_candidate_change_stays_r0_even_after_restore(self):
        (self.root/'protected.txt').write_text('TEST-ONLY altered')
        self.assertEqual(self.check()['rule'],'R0')

    def test_forbidden_candidate_change_stays_r0_even_after_restore(self):
        (self.root/'loop/unauthorized.py').write_text('TEST-ONLY forbidden')
        self.assertEqual(self.check()['rule'],'R0')

    def test_dirty_rollback_stays_r0(self):
        self.control.prepare_revert(self.n); self.revert(); (self.root/'dirty.txt').write_text('TEST-ONLY dirty')
        self.assertEqual(self.control.post_revert(self.n)['rule'],'R0')

    def test_wrong_base_stays_r0(self):
        self.control.prepare_revert(self.n); self.revert(); self.git('commit','--allow-empty','-m','TEST-ONLY wrong head')
        self.assertEqual(self.control.post_revert(self.n)['rule'],'R0')

    def test_each_main_or_pilot_integrity_mismatch_stays_r0(self):
        self.control.prepare_revert(self.n); self.revert()
        for key in self.integrity:
            with self.subTest(field=key), patch.object(gates,'repository_integrity',return_value={**self.integrity,key:'TEST-ONLY changed'}):
                self.assertEqual(self.control.post_revert(self.n)['rule'],'R0')

    def test_unverifiable_integrity_stays_r0(self):
        self.control.prepare_revert(self.n); self.revert()
        with patch.object(gates,'repository_integrity',side_effect=RuntimeError('TEST-ONLY unavailable')):
            self.assertEqual(self.control.post_revert(self.n)['rule'],'R0')
            self.assertFalse(c.read(self.run/'rollback-verification.json')['verified'])

    def test_missing_null_and_failed_gate_evidence_stays_r0(self):
        self.control.prepare_revert(self.n); self.revert()
        original=c.read(self.run/'gate_r1.json')
        for gate in ('G5','G6','G14'):
            for bad in ('missing',None,False,'true'):
                with self.subTest(gate=gate,bad=bad):
                    data=copy.deepcopy(original)
                    if bad=='missing': del data['gates'][gate]
                    else: data['gates'][gate]['passed']=bad
                    c.write(self.run/'gate_r1.json',data)
                    self.assertEqual(self.control.post_revert(self.n)['rule'],'R0')
        (self.run/'gate_r1.json').unlink()
        self.assertEqual(self.control.post_revert(self.n)['rule'],'R0')

    def test_any_earlier_gate_breach_stays_r0(self):
        ev=c.read(self.run/'eval_r1.json'); ev.update(round=2); c.write(self.run/'eval_r2.json',ev)
        good=c.read(self.run/'gate_r1.json'); c.write(self.run/'gate_r2.json',good)
        good['gates']['G6']['passed']=False; c.write(self.run/'gate_r1.json',good)
        c.write(self.run/'decision.json',{**self.original,'rounds':2})
        self.assertEqual(self.check()['rule'],'R0')

    def test_missing_start_snapshot_stays_r0(self):
        meta=self.control.step(self.n); meta.pop('integrity_before'); c.write(self.run/'step.json',meta)
        self.assertEqual(self.check()['rule'],'R0')

    def test_nonproduct_invariant_stays_r0(self):
        ev=c.read(self.run/'eval_r1.json'); ev['blocking_findings'][0]['invariant']='I1'; c.write(self.run/'eval_r1.json',ev)
        self.assertEqual(self.check()['rule'],'R0')

    def test_historical_step_cannot_be_reclassified(self):
        c.write(self.root/'loop/state.json',{'items':{},'steps':[{'step':self.n,'decision':'REVERT','rule':'R0'}]})
        for method in (self.control.prepare_revert,self.control.post_revert):
            with self.assertRaisesRegex(ValueError,'historical decisions are immutable'): method(self.n)
        self.assertEqual(c.read(self.run/'decision.json'),self.original)


class CriticalPathTests(unittest.TestCase):
    def setUp(self):
        self.path=['L12','L16','L15']
        self.items=[controls.item(k) for k in ('L12','L15','L16','WP01','WP02')]
        self.items[1]['depends_on']=['L12']; self.items[2]['depends_on']=['L12']
        self.state={'items':{},'steps':[dict(step=19,item='L12',decision='REVERT',rule='R0')]}

    def test_order_and_completion_never_select_witness_work(self):
        for key in self.path:
            self.assertEqual(c.critical_item(self.items,self.state,self.path)['id'],key)
            self.state['items'][key]={'status':'DONE'}
        self.assertIsNone(c.critical_item(self.items,self.state,self.path))
        self.assertEqual(c.next_item(self.items,self.state)['id'],'WP01')

    def test_normal_queue_prefers_l16_without_new_dependency(self):
        original=copy.deepcopy(self.items); self.state['items']['L12']={'status':'DONE'}
        self.assertEqual(c.next_item(self.items,self.state)['id'],'L16')
        self.assertEqual(self.items,original)

    def test_blocked_or_unapproved_path_stops_without_fallthrough(self):
        self.state['items']['L12']={'status':'BLOCKED'}
        with self.assertRaisesRegex(ValueError,'critical item blocked'): c.critical_item(self.items,self.state,self.path)
        self.state['items']={}; self.items[0]['approval']='PROPOSED'
        with self.assertRaisesRegex(ValueError,'critical item blocked'): c.critical_item(self.items,self.state,self.path)

    def test_split_children_finish_before_next_root(self):
        self.state['items']['L12']={'status':'SPLIT','children':['L12a','L12b']}
        self.items.extend([controls.item('L12a'),controls.item('L12b')])
        for key in ('L12a','L12b','L16'):
            self.assertEqual(c.critical_item(self.items,self.state,self.path)['id'],key)
            self.state['items'][key]={'status':'DONE'}
        self.assertEqual(c.critical_item(self.items,self.state,self.path)['id'],'L15')

    def test_cycle_or_empty_split_fails_closed(self):
        for children in ([],['L12']):
            self.state['items']['L12']={'status':'SPLIT','children':children}
            with self.assertRaisesRegex(ValueError,'critical split'): c.critical_item(self.items,self.state,self.path)


class RunnerBoundaryTests(unittest.TestCase):
    setUp=runners.RunnerTests.setUp
    tearDown=runners.RunnerTests.tearDown
    def test_r0p_fixture_preserves_requested_research_coverage(self):
        self.runner.r0p_fixture=True; self.runner.step=20; self.runner.step_dir=self.root
        self.runner.harness=controls.ROOT
        run.write_json(self.root/'step.json',{'item':{'id':'L00'}})
        (self.root/'diff_sha256.txt').write_text('TEST-ONLY exact')
        self.runner.fixture('evaluator',self.root/'eval_r1.json',self.root,1)
        self.runner.fixture('researcher',self.root/'research.json',self.root,1)
        ev=run.read_json(self.root/'eval_r1.json'); research=run.read_json(self.root/'research.json')
        self.assertEqual(ev['scores']['intention']['score'],0)
        self.assertEqual([v['claim'] for v in ev['claims_for_research']],[v['claim'] for v in research['claims'] if v['origin']=='evaluator'])

    def test_r0p_continues_and_r0_stops(self):
        for rule,expected in [('R0P',2),('R0',1)]:
            self.runner.preflight=Mock(); self.runner.ensure_branch=Mock(); self.runner.sync=Mock(); self.runner.stop=Mock(); self.runner.pause=Mock()
            self.runner.one_step=Mock(side_effect=[{'decision':'REVERT','rule':rule},None])
            self.runner.run(critical_path=['L12','L16','L15'])
            self.assertEqual(self.runner.one_step.call_count,expected)

    def test_r0p_respects_consecutive_limit(self):
        self.runner.preflight=Mock(); self.runner.ensure_branch=Mock(); self.runner.sync=Mock(); self.runner.stop=Mock(); self.runner.pause=Mock()
        self.runner.one_step=Mock(return_value={'decision':'REVERT','rule':'R0P'})
        self.runner.run(critical_path=['L12','L16','L15'])
        self.assertEqual(self.runner.one_step.call_count,3)
        self.runner.stop.assert_called_once_with('consecutive non-integrations')

if __name__=='__main__': unittest.main()
