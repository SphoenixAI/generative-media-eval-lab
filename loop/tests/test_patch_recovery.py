"""Hash-pinned recovery preserves historical bookkeeping and rejects drift."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_actionability import run, recovery


class PatchRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'repo'; self.root.mkdir()
        (self.root/'loop/reports').mkdir(parents=True); (self.root/'src').mkdir()
        (self.root/'loop/config.toml').write_text('[paths]\nruns_dir="runs"\nenv_dir="env"\n[git]\nmain="main"\nintegration="loop/integration"\nremote="origin"\n')
        (self.root/'.gitignore').write_text('runs/\n')
        self.git('init','-b','loop/integration'); self.git('config','user.name','TEST-ONLY'); self.git('config','user.email','test@example.invalid')
        self.product=self.root/'src/item.py'; self.product.write_text('# TEST-ONLY before\n')
        self.git('add','.'); self.git('commit','-m','TEST-ONLY base'); base=self.git('rev-parse','HEAD').strip()
        self.old_report=self.root/'loop/reports/STEP-0005-L02.md'
        self.old_report.write_text('# TEST-ONLY original report\n')
        self.product.write_text('# TEST-ONLY evaluated after\n'); self.git('add','.')
        patch=subprocess.check_output(['git','diff','--binary',base,'--'],cwd=self.root)
        self.expected=hashlib.sha256(patch).hexdigest()
        self.git('reset','--hard',base)
        self.old_report.parent.mkdir(parents=True,exist_ok=True)
        self.old_report.write_text('# TEST-ONLY historical REVERT / R4; never replace\n')
        self.git('add','.'); self.git('commit','-m','TEST-ONLY historical bookkeeping')
        self.runner=run.Runner(self.root); self.runner.step=6; self.runner.step_dir=self.root/'runs/0006'; self.runner.step_dir.mkdir(parents=True)
        self.runner.harness=recovery.HARNESS
        self.new_report=self.root/'loop/reports/STEP-0006-L02.md'; self.new_report.write_text('# TEST-ONLY new report\n\n## Plan\n\n## Probes\n')
        source=self.root/'runs/0005'; (source/'eval_view_r2').mkdir(parents=True)
        (source/'eval_view_r2/diff.patch').write_bytes(patch)
        run.write_json(source/'step.json',dict(base_commit=base,item={'id':'L02'},report=str(self.old_report.relative_to(self.root)),plan='TEST-ONLY sealed acceptance\n'))
        run.write_json(self.runner.step_dir/'step.json',dict(base_commit=self.git('rev-parse','HEAD').strip(),item={'id':'L02'},report=str(self.new_report.relative_to(self.root))))

    def git(self,*args):
        return subprocess.check_output(['git',*args],cwd=self.root,text=True,stderr=subprocess.DEVNULL)

    def test_exact_reconstruction_restores_only_product_and_new_plan(self):
        old=self.old_report.read_bytes()
        self.assertTrue(self.runner.recover_product(5,self.expected))
        self.assertEqual(self.product.read_text(),'# TEST-ONLY evaluated after\n')
        self.assertEqual(self.old_report.read_bytes(),old)
        self.assertIn('TEST-ONLY sealed acceptance',self.new_report.read_text())
        evidence=run.read_json(self.runner.step_dir/'recovery.json')
        self.assertEqual(evidence['restored_diff_sha256'],self.expected)
        self.assertTrue(evidence['matched']); self.assertEqual(evidence['product_paths'],['src/item.py'])
        self.assertFalse((self.runner.step_dir/'decision.json').exists())
        self.assertFalse((self.runner.step_dir/'eval_r1.json').exists())

    def test_hash_mismatch_does_not_restore_any_product_bytes(self):
        before=self.product.read_bytes(); old=self.old_report.read_bytes()
        self.assertFalse(self.runner.recover_product(5,'0'*64))
        self.assertEqual(self.product.read_bytes(),before); self.assertEqual(self.old_report.read_bytes(),old)

    def test_incompatible_product_base_falls_back_without_mutation(self):
        self.product.write_text('# TEST-ONLY incompatible content\n'); self.git('add','src/item.py'); self.git('commit','-m','TEST-ONLY changed base')
        before=self.product.read_bytes()
        self.assertFalse(self.runner.recover_product(5,self.expected))
        self.assertEqual(self.product.read_bytes(),before)
        self.assertIn('incompatible',run.read_json(self.runner.step_dir/'recovery.json')['reason'])

    def test_item_mismatch_cannot_restore_another_items_patch(self):
        meta=run.read_json(self.runner.step_dir/'step.json'); meta['item']['id']='L03'; run.write_json(self.runner.step_dir/'step.json',meta)
        self.assertFalse(self.runner.recover_product(5,self.expected))
        self.assertEqual(self.product.read_text(),'# TEST-ONLY before\n')

if __name__=='__main__': unittest.main()
