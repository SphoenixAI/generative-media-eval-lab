"""Control contracts tested with disposable repositories and authored role fixtures."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import loopctl as c
import gates

ROOT=Path(__file__).resolve().parents[1]


def item(key='L00', **extra):
    return dict(id=key,title='TEST-ONLY bootstrap',approval='APPROVED',priority='P0',size='S',risk='LOW',category='tooling',depends_on=[],acceptance=['Keep accepted code unchanged.'],**extra)


def evaluation(score=4):
    return dict(scores={d:{'score':score,'evidence':['TEST-ONLY check']} for d in c.DIMS},blocking_findings=[],prior_findings=[],diff_sha256='exact')


class DecisionTests(unittest.TestCase):
    def test_all_rules_and_precedence(self):
        ev=evaluation(); gate={'passed':True}; g=[{'gates':{}}]
        def decide(**kw):
            args=dict(evaluation=ev,gate=gate,all_gates=g,research={'claims':[]},enhancement={},failure=None,expected_hash='exact'); args.update(kw); return c.decision(**args)['rule']
        self.assertEqual(decide(),'R6')
        self.assertEqual(decide(expected_hash='wrong'),'R5')
        self.assertEqual(decide(failure={'timeout':True}),'RF')
        self.assertEqual(decide(gate={'passed':False}),'R1')
        self.assertEqual(decide(evaluation=evaluation(1)),'R2')
        self.assertEqual(decide(evaluation=evaluation(2)),'R3')
        self.assertEqual(decide(research={'claims':[{'id':'C1','affects_this_step':True,'verdict':'UNVERIFIABLE'}]}),'R4')
        zero=evaluation(0); zero['blocking_findings']=[{'id':'F1','invariant':'I11'}]
        self.assertEqual(decide(evaluation=zero,failure={'error':True}),'R0')
        self.assertEqual(decide(all_gates=[{'gates':{'G6':{'passed':False}}}],failure={'error':True}),'R0')
        self.assertEqual(decide(evaluation=evaluation(0)),'R2')

    def test_prior_findings_cannot_disappear(self):
        result=c.decision(evaluation(),{'passed':True},[],{'claims':[]},{},None,'exact',{'blocking_findings':[{'id':'F1'}]})
        self.assertEqual(result['rule'],'R4')

    def test_selection_dependencies_priority_split_and_revert_rotation(self):
        backlog=[item('L00'),item('L02'),item('L03')]; backlog[2]['depends_on']=['L00']
        state={'items':{},'steps':[]}; self.assertEqual(c.next_item(backlog,state)['id'],'L00')
        state['steps']=[{'item':'L00','decision':'REVERT'}]; self.assertEqual(c.next_item(backlog,state)['id'],'L02')
        state['items']={'L00':{'status':'SPLIT','children':['C1']},'C1':{'status':'DONE'},'L02':{'status':'BLOCKED'}}
        self.assertEqual(c.next_item(backlog,state)['id'],'L03')
        backlog[2]['approval']='DEFERRED'; self.assertIsNone(c.next_item(backlog,state))

    def test_autoapproval_exact_requirements(self):
        proposal=dict(title='TEST-ONLY clarify wording',rationale='Small fix',size='S',risk='LOW',category='docs',relevance=3,claim_id='C1')
        def auto(**kw):
            args=dict(proposal=proposal,source='researcher',step=4,state={'steps':[]},claims=[{'id':'C1','verdict':'CONTRADICTED'}],terms=['gold']); args.update(kw); return c.auto_approval(**args)
        self.assertTrue(auto()); self.assertFalse(auto(source='enhancer')); self.assertFalse(auto(claims=[]))
        self.assertFalse(auto(state={'steps':[{'step':1,'auto_approved':['P1']}]}))
        self.assertFalse(auto(proposal={**proposal,'title':'Gold output'}))

    def test_strict_schema(self):
        schema={'type':'object','properties':{'score':{'type':'integer','enum':[0,1,2,3,4]}},'required':['score'],'additionalProperties':False}
        c.validate({'score':4},schema)
        for value in ({'score':True},{'score':5},{'score':4,'extra':1},{}):
            with self.assertRaises(ValueError): c.validate(value,schema)


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        base=Path(self.temp.name); self.root=base/'work tree'; self.root.mkdir(); self.runs=base/'runs'
        shutil.copytree(ROOT,self.root/'loop',ignore=shutil.ignore_patterns('__pycache__','reports','research','baseline.json','baseline_tests.txt','protected.sha256'))
        (self.root/'loop/research').mkdir(); (self.root/'loop/research/ledger.jsonl').write_text('')
        (self.root/'loop/backlog.toml').write_text(c.toml_item(item()))
        c.write(self.root/'loop/state.json',{'items':{},'steps':[]})
        for name,value in [('baseline.json','{}'),('baseline_tests.txt',''),('protected.sha256','')]: (self.root/'loop'/name).write_text(value)
        self.git('init','-b','loop/integration'); self.git('config','user.name','TEST-ONLY'); self.git('config','user.email','test@example.invalid'); self.git('add','.'); self.git('commit','-m','TEST-ONLY baseline')
        self.control=c.Control(self.root,self.runs); self.control.harness=self.root/'loop'
        self.start=self.control.start('L00'); self.n=self.start['step']; self.run=self.control.path(self.n)
        self.report=self.root/self.start['report']
        self.report.write_text(c.replace_section(self.report.read_text(),'Plan','Keep accepted code unchanged.\n\nMethod claims: none'))

    def git(self,*args):
        return subprocess.check_output(['git','-C',str(self.root),*args],stderr=subprocess.DEVNULL,text=True)

    def test_start_snapshot_and_lock_exclusivity(self):
        self.assertTrue((self.run/'harness/state.json').exists())
        self.assertTrue((self.run/'harness/gates.py').exists())
        with self.assertRaises(FileExistsError): self.control.start('L00')
        self.assertEqual(self.control.status()['current']['step'],1)

    def test_seal_uses_gate_normalization(self):
        result=self.control.seal(self.n)
        self.assertEqual(result['plan_sha256'],c.digest(gates.plan_body(self.report.read_text())))
        before=result['plan_sha256']; self.report.write_text(self.report.read_text().replace('unchanged.','different.'))
        self.assertNotEqual(before,c.digest(gates.plan_body(self.report.read_text())))

    def test_split_exact_partition_and_parent_approval(self):
        split=self.root/f'loop/reports/STEP-{self.n:04d}-split.toml'
        split.write_text('[[item]]\nid="C1"\ntitle="TEST-ONLY child"\nacceptance=["wrong"]\n')
        with self.assertRaises(ValueError): self.control.split(self.n)
        split.write_text('[[item]]\nid="C1"\ntitle="TEST-ONLY child"\napproval="DEFERRED"\nacceptance=["Keep accepted code unchanged."]\n')
        self.control.split(self.n); children=c.read(self.run/'split.json'); self.assertEqual(children[0]['approval'],'APPROVED')
        self.control.finish(self.n); state=self.control.state(); self.assertEqual(state['items']['L00']['status'],'SPLIT')

    def test_finish_after_reset_is_idempotent_and_retries_bound(self):
        c.write(self.run/'decision.json',{'decision':'REVERT','rule':'R3'})
        self.report.unlink(); a=self.control.finish(self.n); once=(self.root/'loop/state.json').read_bytes()
        self.control.finish(self.n); self.assertEqual((self.root/'loop/state.json').read_bytes(),once)
        self.assertTrue(self.report.exists()); self.assertEqual(self.control.state()['items']['L00']['retries'],1)
        self.assertEqual(a['decision'],'REVERT'); self.assertFalse((self.runs/'lock.json').exists())

    def test_abort_refuses_live_owner(self):
        c.write(self.runs/'lock.json',{'pid':os.getpid(),'host':c.socket.gethostname(),'step':self.n})
        with self.assertRaisesRegex(ValueError,'still running'): self.control.abort()
        with patch('loopctl.os.kill',side_effect=ProcessLookupError):
            result=self.control.abort()
        self.assertTrue(result['reset_required']); self.assertEqual(c.read(self.run/'decision.json')['decision'],'ABANDONED')

    def test_export_and_research_view_do_not_expose_self_evaluation(self):
        self.control.seal(self.n); self.git('add','-A'); c.write(self.run/'gate_r1.json',{'passed':True})
        output=self.control.export(self.n,1); view=Path(output['view'])
        self.assertEqual(c.digest((view/'diff.patch').read_bytes()),(view/'diff_sha256.txt').read_text().strip())
        ev=c.read(ROOT/'tests/fixtures/eval_r1.json'); ev.update(step=self.n,item='L00')
        c.write(self.run/'eval_r1.json',ev); self.control.research_view(self.n)
        self.assertEqual({p.name for p in (self.run/'research_view').iterdir()},{'claims.json','ledger.jsonl'})
        self.assertFalse((view/'self_eval.json').exists())

    def test_report_withholds_self_assessment_until_finish(self):
        c.write(self.run/'self_eval.json',{'TEST-ONLY':'secret self-rating'})
        self.control.report(self.n,1)
        self.assertNotIn('secret self-rating',self.report.read_text())

    def test_cli_status_next_packet(self):
        for name in ('status','next','packet'):
            result=subprocess.run([sys.executable,str(self.root/'loop/loopctl.py'),'--root',str(self.root),'--runs',str(self.runs),name],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr); json.loads(result.stdout)

if __name__=='__main__': unittest.main()
