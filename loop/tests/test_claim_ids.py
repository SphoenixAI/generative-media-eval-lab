"""Research IDs belong to the harness, never the role's suggested labels."""
import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_recovery_contracts as recovery
c=recovery.ctl_module
HARNESS=recovery.HARNESS


class CanonicalClaimTests(unittest.TestCase):
    setUp=recovery.RecoveryContracts.setUp
    write=recovery.RecoveryContracts.write
    read=recovery.RecoveryContracts.read
    def install_duplicates(self):
        raw=json.loads((HARNESS/'tests/fixtures/duplicate_research.json').read_text())
        raw.update(step=1,item='L00')
        self.write('research.json',raw)
        step=self.read('step.json'); step['plan']='CLAIM C1: '+raw['claims'][0]['claim']; self.write('step.json',step)
        ev=self.read('eval_r1.json'); ev['claims_for_research']=[{'id':'C1','claim':raw['claims'][1]['claim'],'location':'TEST-ONLY'}]; self.write('eval_r1.json',ev)
        return raw

    def test_duplicate_fixture_is_schema_valid_and_both_claims_preserved(self):
        raw=self.install_duplicates(); c.validate(raw,json.loads((HARNESS/'schemas/research.schema.json').read_text()))
        self.ctl.research_view(1); result=self.ctl.canonicalize_research(1)
        self.assertEqual(len(result['claims']),2)
        self.assertEqual([x['id'] for x in result['claims']],['R0001-C001','R0001-C002'])
        self.assertEqual([{k:v for k,v in x.items() if k!='id'} for x in result['claims']], [{k:v for k,v in x.items() if k!='id'} for x in raw['claims']])
        self.assertEqual(self.read('research.raw.json'),raw)

    def test_format_stability_and_separate_step_uniqueness(self):
        raw=self.install_duplicates()
        a=c.canonical_claims(2,raw['claims']); b=c.canonical_claims(2,raw['claims']); other=c.canonical_claims(3,raw['claims'])
        self.assertEqual(a,b); self.assertEqual([x['id'] for x in a],['R0002-C001','R0002-C002'])
        self.assertTrue({x['id'] for x in a}.isdisjoint(x['id'] for x in other))
        self.assertEqual([x['id'] for x in raw['claims']],['C1','C1'])

    def test_research_view_accepts_colliding_sources_and_canonical_output(self):
        self.install_duplicates(); self.ctl.research_view(1)
        before=self.read('research_view/claims.json')['claims']; self.assertEqual(len(before),2)
        self.assertEqual([x['id'] for x in before],['R0001-C001','R0001-C002'])
        self.ctl.canonicalize_research(1); self.ctl.research_view(1)
        self.assertEqual(self.read('research_view/claims.json')['claims'],before)

    def test_repeated_parsing_is_byte_stable(self):
        self.install_duplicates(); self.ctl.research_view(1); self.ctl.canonicalize_research(1)
        before={name:(self.run/name).read_bytes() for name in ('research.json','research.raw.json','research-normalization.json')}
        self.ctl.canonicalize_research(1)
        self.assertEqual(before,{name:(self.run/name).read_bytes() for name in before})

    def test_reordering_output_rekeys_view_by_content_and_occurrence(self):
        raw=self.install_duplicates(); self.ctl.research_view(1)
        raw['claims'].reverse(); self.write('research.json',raw)
        result=self.ctl.canonicalize_research(1)
        self.assertEqual([x['claim'] for x in result['claims']],[x['claim'] for x in raw['claims']])
        self.assertEqual([x['claim'] for x in self.read('research_view/claims.json')['claims']],[x['claim'] for x in raw['claims']])

    def test_identical_content_is_not_deduplicated(self):
        raw=self.install_duplicates(); raw['claims'][1]=copy.deepcopy(raw['claims'][0]); self.write('research.json',raw)
        step=self.read('step.json'); step['plan']+='\n'+step['plan']; self.write('step.json',step)
        ev=self.read('eval_r1.json'); ev['claims_for_research']=[]; self.write('eval_r1.json',ev)
        self.ctl.research_view(1); result=self.ctl.canonicalize_research(1)
        self.assertEqual(len(result['claims']),2); self.assertEqual(len({x['id'] for x in result['claims']}),2)

    def test_claim_loss_or_addition_is_rejected_not_hidden_by_id_sets(self):
        raw=self.install_duplicates(); self.ctl.research_view(1); raw['claims'].pop(); self.write('research.json',raw)
        with self.assertRaisesRegex(ValueError,'coverage'): self.ctl.canonicalize_research(1)

    def test_ledger_and_report_preserve_both_canonical_claims(self):
        self.install_duplicates(); self.ctl.research_view(1); self.ctl.canonicalize_research(1)
        self.assertEqual(self.ctl.decide(1)['rule'],'R6'); self.ctl.finish(1)
        rows=[json.loads(line) for line in (self.root/'loop/research/ledger.jsonl').read_text().splitlines()]
        self.assertEqual([x['id'] for x in rows],['R0001-C001','R0001-C002'])
        report=(self.root/self.report_name).read_text()
        self.assertIn('R0001-C001',report); self.assertIn('R0001-C002',report)
        self.ctl.finish(1)
        self.assertEqual(len((self.root/'loop/research/ledger.jsonl').read_text().splitlines()),2)

    def test_existing_ledger_identifier_collision_remains_an_error(self):
        self.install_duplicates(); self.ctl.research_view(1)
        p=self.root/'loop/research/ledger.jsonl'; p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps({'id':'R0001-C001','loop_step':9,'claim':'different'})+'\n')
        with self.assertRaisesRegex(ValueError,'ledger'): self.ctl.canonicalize_research(1)

    def test_enhancer_and_amendments_resolve_only_canonical_claim_ids(self):
        self.install_duplicates(); self.ctl.research_view(1); self.ctl.canonicalize_research(1)
        data={'resolutions':[{'ref':'R0001-C001','action':'FIXED','evidence':'TEST-ONLY proof'}], 'amendments':[{'claim_id':'R0001-C002','change':'TEST-ONLY change'}]}
        self.write('enhancement.json',data); self.assertEqual(self.ctl.role(1,'enhancement.json','enhancement'),data)
        data['amendments'][0]['claim_id']='C1'; self.write('enhancement.json',data)
        with self.assertRaises(ValueError): self.ctl.role(1,'enhancement.json','enhancement')

    def test_plan_amendment_gate_accepts_canonical_identifier(self):
        sys.path.insert(0,str(HARNESS)); import gates
        report='## Plan\nTEST-ONLY acceptance\n\n## Plan amendments\n- R0001-C002: TEST-ONLY correction\n'
        step={'item':self.item,'step':1,'plan_sha256':c.digest(gates.plan_body(report))}
        tests={'exit_code':0,'valid':True,'passed':1,'collected':['tests/t.py::t'],'outcomes':{'tests/t.py::t':'passed'}}
        baseline={'passed':1,'collected':tests['collected'],'outcomes':tests['outcomes']}
        result,_=gates.static_checks(self.root,self.ctl.config,baseline,{}, {},step,tests,report,{'claims':[{'id':'R0001-C002','verdict':'CONTRADICTED','affects_this_step':True}]})
        self.assertTrue(result['G11']['passed'])

    def test_ambiguous_proposal_reference_is_not_guessed_or_autoapproved(self):
        raw=self.install_duplicates(); raw['proposals']=[dict(title='TEST-ONLY follow-up',rationale='TEST-ONLY rationale',size='S',risk='LOW',category='test',relevance=4,claim_id='C1')]
        self.write('research.json',raw); self.ctl.research_view(1); result=self.ctl.canonicalize_research(1)
        self.assertIsNone(result['proposals'][0]['claim_id'])
        self.assertEqual(self.read('research-normalization.json')['unresolved_proposals'],[0])
        self.ctl.decide(1); summary=self.ctl.finish(1); self.assertEqual(summary['auto_approved'],[])

    def test_infrastructure_abandonment_has_no_product_retry(self):
        self.install_duplicates(); self.ctl.research_view(1); self.ctl.canonicalize_research(1)
        self.write('decision.json',{'decision':'ABANDONED','rule':'ABANDONED','reason':'HARNESS_INFRASTRUCTURE_FAILURE: duplicate model-authored research claim ids'})
        self.ctl.finish(1)
        self.assertEqual(self.ctl.state()['items']['L00']['retries'],0)
        self.assertEqual(self.ctl.state()['steps'][0]['decision'],'ABANDONED')

    def test_classification_is_append_only_and_packet_exposes_reason(self):
        decision={'decision':'ABANDONED','rule':'ABANDONED','reason':'original duplicate claim error'}
        self.write('decision.json',decision); self.ctl.finish(1)
        old=(self.root/'loop/reports/STEP-0001/decision.json').read_bytes()
        result=self.ctl.classify_infrastructure(1,'HARNESS_INFRASTRUCTURE_FAILURE: duplicate model-authored research claim ids')
        self.assertEqual(result['decision'],'ABANDONED')
        self.assertEqual((self.root/'loop/reports/STEP-0001/decision.json').read_bytes(),old)
        self.assertEqual(self.ctl.state()['items']['L00']['retries'],0)
        self.assertIn('HARNESS_INFRASTRUCTURE_FAILURE',(self.root/'loop/reports/PACKET-latest.md').read_text())

    def test_proposal_request_reference_follows_reordered_output(self):
        raw=self.install_duplicates(); self.ctl.research_view(1)
        raw['claims'].reverse()
        raw['proposals']=[dict(title='TEST-ONLY follow-up',rationale='TEST-ONLY rationale',size='S',risk='LOW',category='test',relevance=4,claim_id='R0001-C001')]
        self.write('research.json',raw); result=self.ctl.canonicalize_research(1)
        self.assertEqual(result['proposals'][0]['claim_id'],'R0001-C002')
        self.assertEqual(result['claims'][1]['origin'],'plan')
        self.assertEqual(self.read('research-normalization.json')['unresolved_proposals'],[])

    def test_decision_requires_resolution_of_both_duplicate_labeled_claims(self):
        raw=self.install_duplicates()
        for claim in raw['claims']: claim.update(affects_this_step=True,action_required=True)
        self.write('research.json',raw); self.ctl.research_view(1); self.ctl.canonicalize_research(1)
        data={'resolutions':[{'ref':'R0001-C001','action':'FIXED','evidence':'TEST-ONLY proof'}], 'amendments':[]}
        self.write('enhancement.json',data)
        self.assertEqual(self.ctl.decide(1)['rule'],'R4')
        data['resolutions'].append({'ref':'R0001-C002','action':'FIXED','evidence':'TEST-ONLY second proof'})
        self.write('enhancement.json',data)
        self.assertEqual(self.ctl.decide(1)['rule'],'R6')

if __name__=='__main__': unittest.main()
