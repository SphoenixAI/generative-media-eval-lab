"""Explicit research actionability; historical false-R4 and accounting regressions."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_recovery_contracts as recovery
from test_control import evaluation
c=recovery.ctl_module
spec=importlib.util.spec_from_file_location('actionability_runner',recovery.HARNESS/'run.py')
run=importlib.util.module_from_spec(spec); spec.loader.exec_module(run)


def claim(verdict='CONFIRMED', newer=False, required=False):
    return dict(id='R0001-C001',claim='TEST-ONLY assertion',origin='plan',verdict=verdict,
        sources=[] if verdict=='UNVERIFIABLE' else [dict(url='https://example.invalid/test',title='TEST-ONLY source',accessed='2026-10-09',quote='TEST-ONLY assertion')],
        affects_this_step=True,action_required=required,
        newer_practice=dict(summary='TEST-ONLY contextual practice',date='2026-10-09',url='https://example.invalid/test') if newer else None,
        recommended_action='TEST-ONLY correct the shipped assertion' if required else 'TEST-ONLY no change; context reinforces the design')


class ActionabilityTests(unittest.TestCase):
    def check(self, claims, refs=(), ev=None, prior=None):
        return c.decision(ev or evaluation(),{'passed':True},[],{'claims':claims},
            {'resolutions':[{'ref':ref,'action':'FIXED','evidence':'TEST-ONLY correction'} for ref in refs]},None,'exact',prior)['rule']

    def assert_required(self, verdict, newer=False):
        value=claim(verdict,newer,True)
        self.assertTrue(run.needs_enhancement(evaluation(),{'claims':[value]},{'passed':True}))
        self.assertEqual(self.check([value]),'R4')
        self.assertEqual(self.check([value],[value['id']]),'R6')

    def test_confirmed_without_newer_practice_needs_no_resolution(self):
        value=claim(); self.assertEqual(self.check([value]),'R6')
        self.assertFalse(run.needs_enhancement(evaluation(),{'claims':[value]},{'passed':True}))

    def test_confirmed_contextual_newer_practice_needs_no_resolution(self):
        value=claim(newer=True); self.assertEqual(self.check([value]),'R6')
        self.assertFalse(run.needs_enhancement(evaluation(),{'claims':[value]},{'passed':True}))

    def test_confirmed_material_newer_practice_requires_resolution(self): self.assert_required('CONFIRMED',True)
    def test_contradicted_relied_upon_claim_requires_resolution(self): self.assert_required('CONTRADICTED')
    def test_outdated_relied_upon_claim_requires_resolution(self): self.assert_required('OUTDATED')
    def test_unverifiable_shipped_fact_requires_resolution(self): self.assert_required('UNVERIFIABLE')

    def test_missing_one_required_resolution_still_fires_R4(self):
        a=claim(required=True); b={**claim(required=True),'id':'R0001-C002'}
        self.assertEqual(self.check([a,b],[a['id']]),'R4')
        self.assertEqual(self.check([a,b],[a['id'],b['id']]),'R6')

    def test_nonconfirmed_assumption_can_be_nonactionable(self):
        value=claim('UNVERIFIABLE'); value['recommended_action']='TEST-ONLY already marked as an assumption; no factual assertion ships'
        self.assertEqual(self.check([value]),'R6')
        self.assertFalse(run.needs_enhancement(evaluation(),{'claims':[value]},{'passed':True}))

    def test_evaluator_gate_and_prior_finding_requirements_unchanged(self):
        ev=evaluation(); ev['blocking_findings']=[{'id':'F1'}]
        self.assertTrue(run.needs_enhancement(ev,{'claims':[claim(newer=True)]},{'passed':True}))
        self.assertEqual(self.check([],ev=ev),'R4')
        self.assertEqual(self.check([],['F1'],ev),'R6')
        self.assertTrue(run.needs_enhancement(evaluation(),{'claims':[]},{'passed':False}))
        self.assertTrue(run.needs_enhancement(evaluation(2),{'claims':[]},{'passed':True}))
        self.assertEqual(self.check([],['F1'],evaluation(),ev),'R4')

    def test_historical_step0005_shape_old_R4_corrected_R6(self):
        fixture=json.loads((recovery.HARNESS/'tests/fixtures/step0005_actionability.json').read_text())
        claims=fixture['claims']; refs=fixture['resolution_refs']
        old_required={x['id'] for x in claims if x['affects_this_step'] and (x['verdict']!='CONFIRMED' or x['newer_practice'])}
        self.assertEqual(len(old_required-set(refs)),8)  # Exact historical false-R4 trigger.
        corrected=[dict(x,action_required=False) for x in claims]
        ev=evaluation(); ev['prior_findings']=[{'ref':'L02-R1-01','status':'RESOLVED'}]
        prior={'blocking_findings':[{'id':'L02-R1-01'}]}
        self.assertEqual(self.check(corrected,refs,ev,prior),'R6')
        self.assertFalse(run.needs_enhancement(ev,{'claims':corrected},{'passed':True}))
        self.assertEqual(fixture['diff_sha256'],'a7db0d4ac8839ecfc117dbeeef15e49cdc197330233ce8d402c0ecd2fbf20bad')


class ActionabilityContractTests(unittest.TestCase):
    setUp=recovery.RecoveryContracts.setUp
    write=recovery.RecoveryContracts.write
    read=recovery.RecoveryContracts.read

    def install(self,value):
        raw=self.read('research.json'); raw['claims']=[value]; self.write('research.json',raw)
        step=self.read('step.json'); step['plan']='CLAIM C1: '+value['claim']; self.write('step.json',step)
        self.ctl.research_view(1)

    def test_required_boolean_has_no_legacy_or_newer_practice_default(self):
        value=claim(newer=True); del value['action_required']; self.install(value)
        with self.assertRaisesRegex(ValueError,'required'): self.ctl.canonicalize_research(1)
        value['action_required']='false'; self.install(value)
        with self.assertRaises(ValueError): self.ctl.canonicalize_research(1)

    def test_required_action_must_be_relevant(self):
        value=claim(required=True); value['affects_this_step']=False; self.install(value)
        with self.assertRaisesRegex(ValueError,'affect this step'): self.ctl.canonicalize_research(1)

    def test_blank_action_or_no_action_rationale_is_rejected(self):
        value=claim(); value['recommended_action']=' '; self.install(value)
        with self.assertRaisesRegex(ValueError,'rationale'): self.ctl.canonicalize_research(1)

    def test_contextual_claim_persists_in_ledger_and_report(self):
        self.install(claim(newer=True)); self.ctl.canonicalize_research(1)
        self.assertEqual(self.ctl.decide(1)['rule'],'R6'); self.ctl.finish(1)
        stored=json.loads((self.root/'loop/research/ledger.jsonl').read_text())
        self.assertFalse(stored['action_required']); self.assertIsNotNone(stored['newer_practice'])
        report=(self.root/self.report_name).read_text()
        self.assertIn('Action required',report); self.assertIn('TEST-ONLY no change',report)

    def test_retry_credit_is_append_only_idempotent_and_restores_eligibility(self):
        self.write('decision.json',dict(decision='REVERT',rule='R4')); self.ctl.finish(1)
        state=self.ctl.state(); state['items']['L00'].update(retries=2,status='BLOCKED'); c.write(self.root/'loop/state.json',state)
        files=list((self.root/'loop/reports/STEP-0001').glob('*.json'))+[self.root/self.report_name]
        before={p:p.read_bytes() for p in files}; old_steps=copy.deepcopy(state['steps'])
        event=self.ctl.classify_policy_false_revert(1)
        self.assertEqual(event['classification'],'HARNESS_POLICY_FALSE_REVERT')
        self.assertEqual(self.ctl.state()['items']['L00'],dict(retries=1,status='PENDING'))
        self.assertEqual(self.ctl.state()['steps'],old_steps)
        self.assertEqual(c.next_item(c.items(self.root),self.ctl.state())['id'],'L00')
        self.assertEqual({p:p.read_bytes() for p in files},before)
        self.assertEqual(self.ctl.classify_policy_false_revert(1),event)
        self.assertEqual(self.ctl.state()['items']['L00']['retries'],1)

if __name__=='__main__': unittest.main()
