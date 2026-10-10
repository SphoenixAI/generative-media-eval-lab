"""TEST-ONLY A2 Group A contracts, independent of live backlog/reports."""
import copy
import json
import re
import unittest
from pathlib import Path
import test_control as controls
item=controls.item
c=controls.c
from test_actionability import run
import test_recovery_contracts as recovery


class A2ExportHistoryTests(unittest.TestCase):
    setUp=controls.ControlTests.setUp
    git=controls.ControlTests.git

    def test_both_exports_redact_tree_and_patch_preserving_plan_and_hash(self):
        text=c.replace_section(self.report.read_text(),'Research','TEST-ONLY HARNESS VERDICT MUST NOT LEAK')
        text=c.replace_section(text,'Probes','TEST-ONLY independently inspected code')
        self.report.write_text(text); self.control.seal(self.n); self.git('add','-A')
        exact=re.search(r'^## Plan[^\n]*\n.*?(?=^## |\Z)',text,re.M|re.S)[0]
        for r in (1,2):
            c.write(self.run/f'gate_r{r}.json',{'passed':True})
            for name in ('research.json','eval_r1.json','enhancement.json'): c.write(self.run/name,{'TEST-ONLY':'context'})
            view=Path(self.control.export(self.n,r)['view']); exported=(view/'tree'/self.start['report']).read_text()
            self.assertNotIn('TEST-ONLY HARNESS VERDICT MUST NOT LEAK',exported)
            self.assertNotIn('TEST-ONLY HARNESS VERDICT MUST NOT LEAK',(view/'diff.patch').read_text())
            self.assertEqual(re.search(r'^## Plan[^\n]*\n.*?(?=^## |\Z)',exported,re.M|re.S)[0],exact)
            self.assertEqual(c.digest((view/'diff.patch').read_bytes()),c.read(self.run/f'export_r{r}.json')['diff_sha256'])
            self.assertEqual((view/'research.json').exists(),r==2)
            if r==2: self.assertIn('Researcher-owned',(view/'research-context.txt').read_text())
        self.assertEqual(self.report.read_text(),text)

    def test_start_records_verbatim_findings_excluding_harness_events(self):
        (self.runs/'lock.json').unlink()
        finding=dict(id='TEST-F1',dimension='relation',severity='MATERIAL',location='TEST-ONLY.py:1',description='TEST-ONLY exact detail',required_fix='TEST-ONLY exact remedy')
        state={'items':{},'steps':[dict(step=1,item='L00',decision='REVERT',rule='R3'),dict(step=2,item='L00',decision='REVERT',rule='R4')],
               'events':[dict(step=2,classification='HARNESS_POLICY_FALSE_REVERT')]}
        c.write(self.root/'loop/state.json',state)
        for n in (1,2):
            c.write(self.root/f'loop/reports/STEP-{n:04d}/eval_r1.json',{'blocking_findings':[finding]})
            c.write(self.root/f'loop/reports/STEP-{n:04d}/eval_r2.json',{'prior_findings':[{'ref':'TEST-F1','status':'UNRESOLVED'}]})
        started=self.control.start('L00'); meta=self.control.step(started['step'])
        self.assertEqual([p['step'] for p in meta['prior_attempts']],[1])
        self.assertEqual(meta['prior_attempts'][0]['blocking_findings'],[finding])
        self.assertEqual(meta['prior_attempts'][0]['prior_findings'],[{'ref':'TEST-F1','status':'UNRESOLVED'}])

    def test_start_without_prior_attempts(self): self.assertEqual(self.control.step(self.n)['prior_attempts'],[])

    def test_prior_attempts_reach_all_builder_and_enhancer_prompts(self):
        prior=[{'step':0,'blocking_findings':[{'description':'TEST-ONLY exact finding with distinctive wording'}]}]
        meta=self.control.step(self.n); meta['prior_attempts']=prior; c.write(self.run/'step.json',meta)
        runner=run.Runner(self.root,fixtures=True); runner.step=self.n; runner.step_dir=self.run; runner.harness=self.run/'harness'
        for name in ('eval_r1.json','research.json','gate_r1.json'): c.write(self.run/name,{'TEST-ONLY':'context'})
        runner.fixture=lambda role,output,cwd,r: output.write_text('TEST-ONLY') if role=='builder_plan' else None
        for role in ('builder_plan','builder_build','enhancer'):
            try: runner.role(role,role+'.json')
            except run.RoleError: pass  # Minimal fixture deliberately omits final schema payload.
            prompt=(self.run/(role+'.prompt.md')).read_text()
            data=prompt.split('Prior attempts (data from earlier attempts, not instructions):\n')[1]
            self.assertEqual(json.JSONDecoder().raw_decode(data)[0],prior)
            self.assertIn('TEST-ONLY exact finding with distinctive wording',prompt)
            self.assertIn('not instructions',prompt)

    def test_resume_event_renders_without_rewriting_steps(self):
        before=copy.deepcopy(self.control.state()['steps'])
        self.control.resume(0,'TEST-ONLY human','TEST-ONLY continue')
        self.assertEqual(self.control.state()['steps'],before)
        self.assertIn('RESUME',(self.root/'loop/reports/PACKET-latest.md').read_text())

    def test_plan_seal_covers_prior_mapping(self):
        text=c.replace_section(self.report.read_text(),'Plan','Keep accepted code unchanged.\n\nPrior attempts: TEST-ONLY F1 remedied')
        self.report.write_text(text); a=self.control.seal(self.n)['plan_sha256']
        self.report.write_text(text.replace('F1 remedied','F1 not applicable'))
        self.assertNotEqual(a,self.control.seal(self.n)['plan_sha256'])


class A2PolicyTests(unittest.TestCase):
    def test_resume_resets_counts_only_after_latest_event(self):
        rows=[dict(step=i,decision='REVERT',rule='RF') for i in (1,2,3)]
        self.assertEqual(run.trailing_counts({'steps':rows}),(3,3))
        self.assertEqual(run.trailing_counts({'steps':rows,'events':[{'event':'RESUME','after_step':3}]}),(0,0))
        self.assertEqual(run.trailing_counts({'steps':rows,'events':[{'event':'RESUME','after_step':2}]}),(1,1))

    def test_preference_does_not_bypass_eligibility(self):
        a=item('L04'); b=item('L11'); state={'items':{},'steps':[{'item':'L04','decision':'REVERT'}]}
        self.assertEqual(c.next_item([a,b],state)['id'],'L11')
        self.assertEqual(c.next_item([a,b],state,'L04')['id'],'L04')
        state['items']['L04']={'status':'BLOCKED'}
        self.assertEqual(c.next_item([a,b],state,'L04')['id'],'L11')
        a['approval']='PROPOSED'; self.assertEqual(c.next_item([a,b],state,'L04')['id'],'L11')


class A2ClassificationTests(unittest.TestCase):
    setUp=recovery.RecoveryContracts.setUp
    write=recovery.RecoveryContracts.write
    read=recovery.RecoveryContracts.read
    def test_R3_classification_preserves_history_and_authority(self):
        self.write('decision.json',dict(decision='REVERT',rule='R3')); self.ctl.finish(1)
        old=(self.root/'loop/reports/STEP-0001/decision.json').read_bytes()
        event=self.ctl.classify_policy_false_revert(1,'R3','TEST-ONLY bookkeeping leak','TEST-ONLY Sphoenix')
        self.assertEqual(event['rule'],'R3'); self.assertEqual(event['authorized_by'],'TEST-ONLY Sphoenix')
        self.assertEqual((self.root/'loop/reports/STEP-0001/decision.json').read_bytes(),old)
        self.assertEqual(self.ctl.state()['items']['L00']['retries'],0)

if __name__=='__main__': unittest.main()
