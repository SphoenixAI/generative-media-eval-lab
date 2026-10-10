"""TEST-ONLY packet and path disclosure contracts."""
import unittest
from pathlib import Path
import test_control as controls
import test_recovery_contracts as recovery
from test_actionability import run
c=recovery.ctl_module


class PathLabelTests(unittest.TestCase):
    def test_exact_sibling_names_and_segment_boundaries(self):
        base='/Users/sphoenix/Desktop/Content Evaluator'
        roots=[(base+' - loop-runs','<RUNS>'),(base+' - loop-env','<ENV>'),(base+' - loop','<WT>'),(base,'<MAIN>'),('/Users/sphoenix','~')]
        for suffix,label in [(' - loop-runs','<RUNS>'),(' - loop-env','<ENV>'),(' - loop','<WT>'),('','<MAIN>')]:
            self.assertEqual(run.sanitize_paths(base+suffix+'/file.json',roots),label+'/file.json')
            self.assertEqual(run.sanitize_paths('"'+base+suffix+'"',roots),'"'+label+'"')
        self.assertEqual(run.sanitize_paths(base+' - loop-other/file',roots),'~/Desktop/Content Evaluator - loop-other/file')
        self.assertEqual(run.sanitize_paths('/Users/sphoenix2/file',roots),'/Users/sphoenix2/file')


class ReportPacketTests(unittest.TestCase):
    setUp=controls.ControlTests.setUp
    git=controls.ControlTests.git
    def test_report_preserves_plan_and_probes_bytes(self):
        path=str(self.control.root)+'/private-file'
        text='# report '+path+'\n## Plan\n'+path+'\n\n## Probes\n'+path+'\n\n## Research\n'+path+'\n'
        clean=self.control.clean_report(text)
        self.assertEqual(c.body(clean,'Plan'),c.body(text,'Plan'))
        self.assertEqual(c.body(clean,'Probes'),c.body(text,'Probes'))
        self.assertEqual(c.body(clean,'Research'),'<WT>/private-file\n')

    def test_json_summaries_are_cleaned_recursively(self):
        value={'flags':[str(self.control.runs)+'/0001/error'],'nested':{'path':str(self.control.root)+'/file'}}
        self.assertEqual(self.control.clean_summary(value),{'flags':['<RUNS>/0001/error'],'nested':{'path':'<WT>/file'}})
        self.assertTrue(value['flags'][0].startswith('/'))

    def test_packet_health_sections_dedup_and_standing_limitations(self):
        state={'items':{'L00':{'status':'BLOCKED','retries':2},'L02':{'status':'PENDING','retries':1}},
          'steps':[dict(step=1,item='L00',decision='REVERT',rule='R3',rounds=1,flags=['PUBLIC_PROSE','Independent tests unavailable']),dict(step=2,item='L02',decision='REVERT',rule='R3',rounds=1,flags=['PUBLIC_PROSE','HOME_PATH '+str(self.control.root)+'/file'])],
          'events':[dict(event='RESUME',after_step=1,step=1,decision='RESUME',authorized_by='TEST-ONLY',reason='TEST-ONLY resume',product_retry_charged=False)]}
        c.write(self.root/'loop/state.json',state)
        finding=dict(id='TEST-F1',location='tests/test_example.py:2',description='TEST-ONLY same issue')
        for n in (1,2): c.write(self.root/f'loop/reports/STEP-{n:04d}/eval_r1.json',{'blocking_findings':[finding]})
        self.control.packet('TEST-ONLY stop '+str(self.control.runs)+'/0002')
        text=(self.root/'loop/reports/PACKET-latest.md').read_text()
        for heading in ('Loop health','New this step','Open issues','Standing limitations'): self.assertIn('## '+heading,text)
        self.assertIn('since RESUME: 1',text); self.assertIn('L00: 2',text); self.assertIn('BLOCKED: L00',text)
        self.assertEqual(text.count('tests/test_example.py:2'),1); self.assertIn('steps 0001,0002',text)
        self.assertIn('PUBLIC_PROSE: 2',text); self.assertIn('VALIDATION_LIMITATION: 1',text)
        table=text.split('## Loop health')[0]
        self.assertNotIn('PUBLIC_PROSE',table); self.assertNotIn('Independent tests unavailable',table)
        self.assertTrue(all(len(line.split(' | '))==8 for line in table.splitlines() if line.startswith('000')))
        state['events'].append(dict(step=2,decision='REVERT',classification='HARNESS_POLICY_FALSE_REVERT',reason='TEST-ONLY policy',product_retry_charged=False))
        c.write(self.root/'loop/state.json',state)
        self.control.packet()
        self.assertIn('steps 0001,0002',(self.root/'loop/reports/PACKET-latest.md').read_text())
        self.assertNotIn(str(self.control.root),text); self.assertNotIn(str(self.control.runs),text)
        self.control.packet(); self.assertIn('TEST-ONLY stop <RUNS>/0002',(self.root/'loop/reports/PACKET-latest.md').read_text())
        self.assertIn('Independent tests unavailable',(self.root/'loop/reports/INDEX.md').read_text())

if __name__=='__main__': unittest.main()
