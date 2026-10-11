"""TEST-ONLY operator registration contracts in disposable local repositories."""
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import loopctl as c

PARENT = 'L12-A2d1'
CHILDREN = ['L12-A2d1a', 'L12-A2d1b']
PROPOSAL = 'loop/proposals/APPROVED-L12-A2d1-split.toml'
AUTHORITY = 'Sphoenix, 2026-10-10'
REASON = 'TEST-ONLY authorized structural registration'
LINEAGE = ['L12', 'L12-A', 'L12-A2', 'L12-A2d', PARENT]


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='TEST-ONLY-registration-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / 'checkout'
        self.root.mkdir()
        self.control = c.Control(self.root)
        self.state_path = self.root / 'loop/state.json'
        self.backlog_path = self.root / 'loop/backlog.toml'
        self.record_path = self.root / f'loop/operator/registrations/{PARENT}.json'
        self.backlog = []
        for index, key in enumerate(LINEAGE):
            item = dict(id=key, title='TEST-ONLY parent', approval='APPROVED', priority='P0',
                        size='S', depends_on=['L11'], acceptance=['TEST-ONLY original conjunction'],
                        authorized_protected=['TEST-ONLY-protected.txt'], authorized_test_changes=[],
                        authorized_dependencies=False, human_review=True,
                        notes='TEST-ONLY sealed constraints must be inherited', probes=[])
            if index:
                item['parent'] = LINEAGE[index-1]
            self.backlog.append(item)
        self.backlog[-1]['acceptance'] += ['TEST-ONLY media foundation', 'TEST-ONLY role foundation']
        self.before = {'items': {'L11': {'status':'DONE', 'retries':1}},
                       'last_integrated_test_count':5100,
                       'steps':[{'step':32, 'item':PARENT, 'decision':'REVERT', 'rule':'R1'},
                                {'step':33, 'item':PARENT, 'decision':'REVERT', 'rule':'R2'}],
                       'events':[{'event':'RESUME', 'step':32, 'after_step':32, 'reason':'TEST-ONLY historical authorization', 'decision':'RESUME', 'product_retry_charged':False}]}
        for index, key in enumerate(LINEAGE):
            self.before['items'][key] = {'status':'SPLIT', 'retries':1, 'children':[LINEAGE[index+1]]} if index < 4 else {'status':'BLOCKED', 'retries':2}
        self.proposal = {'authorization':{'parent':PARENT, 'approval':'APPROVED', 'authorized_by':AUTHORITY,
                                         'activation':'TEST-ONLY historical registration blocker', 'execution_authorized':False},
                         'item':[{'id':CHILDREN[0], 'title':'TEST-ONLY media', 'size':'S', 'acceptance':['TEST-ONLY media foundation']},
                                 {'id':CHILDREN[1], 'title':'TEST-ONLY role', 'size':'S', 'acceptance':['TEST-ONLY role foundation', 'TEST-ONLY original conjunction']}]}
        c.write(self.state_path, self.before)
        self.save_backlog()
        self.save_proposal()
        c.write(self.root/'loop/reports/STEP-0033/decision.json', {'decision':'REVERT', 'rule':'R2', 'rounds':2, 'stop':False})
        for name in ('loop/reports/STEP-0033/eval_r2.json', 'loop/reports/STEP-0033-L12-A2d1.md',
                     'loop/research/ledger.jsonl', 'src/product.py', 'tests/test_product.py', 'TEST-ONLY-protected.txt'):
            path = self.root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'TEST-ONLY historical bytes\r\nretain whitespace  \n')
        c.write(self.control.runs/'current.json', {'step':33, 'finished':True, 'item':PARENT, 'decision':'REVERT'})
        c.write(self.root/'loop/reports/STEP-0033/eval_r2.json', {'blocking_findings':[]})
        self.control.packet()
        self.git('init', '-q')
        self.git('config', 'user.name', 'TEST-ONLY operator')
        self.git('config', 'user.email', 'test-only@example.invalid')
        self.commit()
        self.initial_head = self.git('rev-parse', 'HEAD')
        # Model an idle process inventory. The sandbox can deny ps; a separate
        # refusal test covers that failure. Git and all file operations are real.
        self.processes = '999 /usr/bin/TEST-ONLY-idle\n'
        actual_check_output = subprocess.check_output
        def output(args, **kwargs):
            if args == ['ps', '-axww', '-o', 'pid=,command=']:
                return self.processes
            return actual_check_output(args, **kwargs)
        process_patch = patch.object(c.subprocess, 'check_output', side_effect=output)
        process_patch.start()
        self.addCleanup(process_patch.stop)
        environment_patch = patch.dict(os.environ)
        environment_patch.start()
        self.addCleanup(environment_patch.stop)
        os.environ.pop('LOOP_RUNNER_PID', None)

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), '-c', 'core.hooksPath=/dev/null',
                                        '-c', 'commit.gpgsign=false', *args], text=True).strip()

    def commit(self):
        self.git('add', '-A')
        self.git('commit', '--allow-empty', '-qm', 'TEST-ONLY fixture')

    def save_backlog(self):
        self.backlog_path.parent.mkdir(parents=True, exist_ok=True)
        self.backlog_path.write_text('# TEST-ONLY immutable prefix\n' + '\n'.join(c.toml_item(item) for item in self.backlog))

    def save_proposal(self):
        path = self.root/PROPOSAL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('[authorization]\n' + ''.join(f'{key} = {json.dumps(value)}\n' for key, value in self.proposal['authorization'].items()) +
                        '\n' + '\n'.join(c.toml_item(item) for item in self.proposal['item']))

    def register(self, **overrides):
        arguments = dict(parent=PARENT, proposal=PROPOSAL, authorized_by=AUTHORITY, reason=REASON)
        arguments.update(overrides)
        return self.control.register_approved_split(**arguments)

    def snapshot(self):
        return {str(path.relative_to(self.base)): (os.readlink(path) if path.is_symlink() else path.read_bytes())
                for path in self.base.rglob('*') if '.git' not in path.parts and (path.is_file() or path.is_symlink())}

    def reject(self, message, **arguments):
        before, head = self.snapshot(), self.git('rev-parse', 'HEAD')
        with self.assertRaisesRegex((ValueError, OSError, subprocess.CalledProcessError), message):
            self.register(**arguments)
        self.assertEqual(self.snapshot(), before, 'rejection must not write any file')
        self.assertEqual(self.git('rev-parse', 'HEAD'), head)

    def test_happy_path_preserves_history_permissions_retries_and_source_bytes(self):
        files, backlog_bytes = self.snapshot(), self.backlog_path.read_bytes()
        record = self.register()
        state = self.control.state()
        self.assertEqual(state['steps'], self.before['steps'])
        self.assertEqual(state['events'], self.before['events'])
        for key, row in self.before['items'].items():
            self.assertEqual(state['items'][key], {**row, 'status':'SPLIT', 'children':CHILDREN} if key == PARENT else row)
        self.assertEqual(state['items'][PARENT]['retries'], 2)
        for key in CHILDREN:
            self.assertEqual(state['items'][key], {'status':'PENDING', 'retries':0})
        children = c.items(self.root)[-2:]
        for index, child in enumerate(children):
            expected = {**self.backlog[-1], **self.proposal['item'][index], 'parent':PARENT}
            self.assertEqual(child, expected)
        self.assertTrue(self.backlog_path.read_bytes().startswith(backlog_bytes))
        for name, data in files.items():
            if name not in ('checkout/loop/state.json', 'checkout/loop/backlog.toml', 'checkout/loop/reports/PACKET-latest.md'):
                self.assertEqual(self.snapshot()[name], data)
        self.assertEqual(set(self.snapshot()) - files.keys(), {f'checkout/loop/operator/registrations/{PARENT}.json'})
        self.assertEqual(c.read(self.record_path), record)
        self.assertEqual(record['proposal'], {'path':PROPOSAL, 'sha256':c.digest((self.root/PROPOSAL).read_bytes())})
        self.assertEqual(record['authorization'], {'authorized_by':AUTHORITY, 'reason':REASON})
        self.assertEqual(record['before_state'], self.before)
        self.assertEqual(record['after_state'], state)
        self.assertEqual(record['child_order'], CHILDREN)
        self.assertFalse(record['retry_preservation']['product_retry_charged'])
        self.assertIn('REVERT / R2', record['historical_preservation'])
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.initial_head)

    def test_critical_path_order_selects_d1a_then_d1b_without_dependency(self):
        self.register()
        backlog, state = c.items(self.root), self.control.state()
        self.assertEqual(c.critical_item(backlog, state, ['L12','L16','L15'])['id'], CHILDREN[0])
        self.assertEqual(backlog[-1]['depends_on'], self.backlog[-1]['depends_on'])
        self.assertNotIn(CHILDREN[0], backlog[-1]['depends_on'])
        for path in ([], ['L12','L16','L15'], ['L12-A2d1']):
            with self.assertRaisesRegex(ValueError, 'require --critical-path L12'):
                self.control.start(CHILDREN[1], critical_path=path)
        state['items'][CHILDREN[0]]['status'] = 'BLOCKED'
        with self.assertRaisesRegex(ValueError, 'critical item blocked'):
            c.critical_item(backlog, state, ['L12','L16','L15'])
        state['items'][CHILDREN[0]]['status'] = 'DONE'
        self.assertEqual(c.critical_item(backlog, state, ['L12','L16','L15'])['id'], CHILDREN[1])

    def test_clean_exact_replay_returns_same_record_without_writes_or_events(self):
        record = self.register()
        self.reject('clean tree')  # A successful uncommitted registration is still dirty.
        self.commit()
        before = self.snapshot()
        times = {path: path.stat().st_mtime_ns for path in (self.state_path, self.backlog_path, self.record_path)}
        with patch.object(Path, 'write_bytes', side_effect=AssertionError('replay wrote bytes')):
            self.assertEqual(self.register(), record)
            self.assertEqual(self.register(), record)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual({path: path.stat().st_mtime_ns for path in times}, times)
        self.assertEqual(len(list(self.record_path.parent.iterdir())), 1)

    def test_wrong_parent_authority_or_empty_reason(self):
        for arguments in ({'parent':'L12'}, {'authorized_by':'TEST-ONLY forged'}, {'reason':'  '}):
            with self.subTest(arguments=arguments):
                self.reject('exact d1 parent, authorization and reason', **arguments)

    def test_unapproved_wrong_parent_or_wrong_proposal_authority(self):
        for key, value in [('approval','PROPOSED'), ('approval','AUTO_APPROVED'), ('parent','L12-A2d2'), ('authorized_by','TEST-ONLY wrong')]:
            with self.subTest(key=key, value=value):
                original = self.proposal['authorization'][key]
                self.proposal['authorization'][key] = value
                self.save_proposal(); self.commit()
                self.reject('proposal approval/parent/authorization mismatch')
                self.proposal['authorization'][key] = original

    def test_wrong_parent_state_or_retry_count(self):
        for row in [{'status':status, 'retries':2} for status in ('PENDING','DONE','SPLIT','RUNNING')] + [
                {'status':'BLOCKED', 'retries':1}, {'status':'BLOCKED', 'retries':True},
                {'status':'BLOCKED', 'retries':2, 'children':[]}]:
            with self.subTest(row=row):
                state = copy.deepcopy(self.before)
                state['items'][PARENT] = row
                c.write(self.state_path, state); self.commit()
                self.reject('exactly BLOCKED')

    def test_missing_parent_and_existing_child_ids_in_either_store(self):
        original = copy.deepcopy(self.backlog)
        self.backlog = self.backlog[:-1]
        self.save_backlog(); self.commit()
        self.reject('parent missing')
        self.backlog = original + [{**original[-1], 'id':CHILDREN[0]}]
        self.save_backlog(); self.commit()
        self.reject('must be new')
        self.backlog = original
        self.save_backlog()
        state = copy.deepcopy(self.before)
        state['items'][CHILDREN[1]] = {'status':'DONE', 'retries':1}
        c.write(self.state_path, state); self.commit()
        self.reject('must be new')

    def test_duplicate_invalid_wrong_and_reordered_child_ids(self):
        original = copy.deepcopy(self.proposal['item'])
        for ids in ([CHILDREN[0],CHILDREN[0]], ['../bad',CHILDREN[1]], ['',CHILDREN[1]],
                    ['L12-A2d1z',CHILDREN[1]], list(reversed(CHILDREN))):
            with self.subTest(ids=ids):
                self.proposal['item'] = copy.deepcopy(original)
                for child, key in zip(self.proposal['item'], ids):
                    child['id'] = key
                self.save_proposal(); self.commit()
                self.reject('IDs must be valid and unique|approved child order')

    def test_empty_missing_changed_extra_or_duplicated_acceptance(self):
        original = copy.deepcopy(self.proposal['item'])
        variants = [[], [''], ['TEST-ONLY changed'], ['TEST-ONLY role foundation'],
                    ['TEST-ONLY media foundation', 'TEST-ONLY original conjunction'],
                    ['TEST-ONLY media foundation', 'TEST-ONLY extra'], 'TEST-ONLY string']
        for acceptance in variants:
            with self.subTest(acceptance=acceptance):
                self.proposal['item'] = copy.deepcopy(original)
                self.proposal['item'][0]['acceptance'] = acceptance
                self.save_proposal(); self.commit()
                self.reject('acceptance|criteria')
        self.proposal['item'] = copy.deepcopy(original)
        self.proposal['item'][1]['acceptance'] = ['TEST-ONLY role foundation']
        self.save_proposal(); self.commit()
        self.reject('exactly partition')

    def test_permission_override_cannot_be_smuggled_in_child(self):
        self.proposal['item'][0]['authorized_dependencies'] = True
        self.save_proposal(); self.commit()
        self.reject('invalid approved child structure')

    def test_parent_approval_missing_child_acceptance_and_duplicate_parent_criteria(self):
        self.backlog[-1]['approval'] = 'PROPOSED'
        self.save_backlog(); self.commit()
        self.reject('critical-path approval')
        self.backlog[-1]['approval'] = 'APPROVED'
        self.save_backlog()
        acceptance = self.proposal['item'][0].pop('acceptance')
        self.save_proposal(); self.commit()
        self.reject('invalid approved child structure')
        self.proposal['item'][0]['acceptance'] = acceptance * 2
        self.backlog[-1]['acceptance'].append(acceptance[0])
        self.save_backlog(); self.save_proposal(); self.commit()
        self.reject('exactly partition')

    def test_dirty_tracked_staged_and_untracked_files(self):
        for staged in (False, True):
            (self.root/'src/product.py').write_text(f'TEST-ONLY dirty staged={staged}')
            if staged:
                self.git('add', 'src/product.py')
            self.reject('clean tree')
            self.commit()
        (self.root/'untracked.txt').write_text('TEST-ONLY untracked')
        self.reject('clean tree')

    def test_uncommitted_proposal_even_when_hidden_from_git_status(self):
        self.git('update-index', '--assume-unchanged', PROPOSAL)
        with (self.root/PROPOSAL).open('a') as stream:
            stream.write('\n# TEST-ONLY uncommitted\n')
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.reject('proposal differs from committed HEAD')

    def test_outside_proposal_and_symlink_escapes(self):
        outside = self.base/'outside.toml'
        outside.write_bytes((self.root/PROPOSAL).read_bytes())
        self.reject('inside loop/proposals', proposal=str(outside))
        path = self.root/PROPOSAL
        path.unlink(); path.symlink_to(outside); self.commit()
        self.reject('inside loop/proposals|symlinks')
        path.unlink(); path.write_bytes(outside.read_bytes())
        directory = self.root/'loop/proposals'
        directory.rename(self.base/'outside-proposals')
        directory.symlink_to(self.base/'outside-proposals', target_is_directory=True)
        self.commit()
        self.reject('inside loop/proposals|symlinks')

    def test_operator_output_symlink_escape(self):
        target = self.base/'outside-operator'
        target.mkdir()
        (self.root/'loop/operator').symlink_to(target, target_is_directory=True)
        self.commit()
        self.reject('symlinks')

    def test_autonomous_roles_are_denied_even_between_steps(self):
        os.environ['LOOP_RUNNER_PID'] = str(os.getpid())
        self.reject('operator-only')
        os.environ['LOOP_RUNNER_PID'] = ''
        self.reject('operator-only')

    def test_live_dead_foreign_or_malformed_lock_all_deny_registration(self):
        for value in ({'pid':os.getpid(), 'host':'TEST-ONLY local', 'step':34},
                      {'pid':99999999, 'host':'TEST-ONLY stale', 'step':34}, {}):
            with self.subTest(value=value):
                c.write(self.control.runs/'lock.json', value)
                self.reject('owned step lock')

    def test_required_current_absent_malformed_unfinished_or_wrong_step(self):
        path = self.control.runs/'current.json'
        path.unlink(); self.reject('current.json is required')
        path.write_text('{broken'); self.reject('current.json is required')
        for current in ({'step':33}, {'step':33,'finished':False}, {'step':33,'finished':'true'},
                        {'finished':True}, {'step':32,'finished':True}, {'step':True,'finished':True},
                        {'step':33,'finished':True,'item':None}, {'step':33,'finished':True,'decision':None},
                        {'step':33,'finished':True,'unexpected':True}, [], None):
            with self.subTest(current=current):
                c.write(path,current); self.reject('latest finished step')

    def test_valid_finished_current_for_latest_step_passes(self):
        c.write(self.control.runs/'current.json', {'step':33,'finished':True})
        self.register()

    def test_alternate_runs_cannot_hide_configured_owned_step(self):
        c.write(self.control.runs/'lock.json', {'pid':os.getpid(), 'step':34})
        self.control.runs = self.base/'alternate-runs'
        self.reject('owned step lock')

    def test_relative_runner_without_lock_rejects(self):
        self.processes = '123 python loop/run.py --once\n'
        self.assertFalse((self.control.runs/'lock.json').exists())
        self.reject(r'PID\(s\): 123')

    def test_multiple_matching_pids_anywhere_are_reported(self):
        self.processes = '987 python /elsewhere/loop/run.py --once\n123 python loop/run.py\n'
        self.reject(r'PID\(s\): 123, 987')

    def test_process_table_failure_and_unreliable_data_reject(self):
        for table in ('', 'garbled\n', '123\n', '0 invalid\n', '123 good\n123 duplicate\n'):
            self.processes = table; self.reject('cannot reliably read process table')
        actual = c.subprocess.check_output
        def failed(args, **kwargs):
            if args == ['ps','-axww','-o','pid=,command=']:
                raise PermissionError('TEST-ONLY ps unavailable')
            return actual(args, **kwargs)
        with patch.object(c.subprocess, 'check_output', side_effect=failed):
            self.reject('cannot reliably read process table')

    def test_critical_path_mismatch_and_unfinished_prior_sibling_or_dependency(self):
        for change in ('wrong lineage', 'earlier sibling', 'blocked dependency', 'done root'):
            with self.subTest(change=change):
                state = copy.deepcopy(self.before)
                if change == 'wrong lineage':
                    state['items']['L12-A2d']['children'] = ['TEST-ONLY wrong']
                elif change == 'earlier sibling':
                    state['items']['L12-A2d']['children'].insert(0, 'TEST-ONLY unavailable')
                elif change == 'blocked dependency':
                    state['items']['L11']['status'] = 'BLOCKED'
                else:
                    state['items']['L12']['status'] = 'DONE'
                c.write(self.state_path, state); self.commit()
                self.reject('critical')

    def test_step_0033_cannot_be_reclassified_or_followed_by_another_step(self):
        c.write(self.root/'loop/reports/STEP-0033/decision.json', {'decision':'INTEGRATE', 'rule':'R6'})
        self.commit(); self.reject('Step 0033')
        c.write(self.root/'loop/reports/STEP-0033/decision.json', {'decision':'REVERT', 'rule':'R2'})
        state = copy.deepcopy(self.before)
        state['steps'].append({'step':34, 'item':PARENT, 'decision':'REVERT', 'rule':'R2'})
        c.write(self.state_path, state); self.commit()
        c.write(self.control.runs/'current.json', {'step':34, 'finished':True, 'item':PARENT, 'decision':'REVERT'})
        self.reject('Step 0033')

    def test_replay_rejects_any_changed_registered_structure_or_evidence(self):
        self.register(); self.commit()
        baseline = self.snapshot()
        changes = ('reason', 'record', 'record bytes', 'order', 'dependency', 'acceptance', 'retries', 'history', 'product', 'missing record')
        for change in changes:
            with self.subTest(change=change):
                for relative, data in baseline.items():
                    (self.base/relative).write_bytes(data)
                if change == 'record':
                    record = c.read(self.record_path); record['historical_preservation'] = 'TEST-ONLY forged'; c.write(self.record_path, record)
                elif change == 'record bytes':
                    self.record_path.write_text(json.dumps(c.read(self.record_path)))
                elif change in ('order', 'retries'):
                    state = c.read(self.state_path)
                    if change == 'order': state['items'][PARENT]['children'].reverse()
                    else: state['items'][PARENT]['retries'] = 0
                    c.write(self.state_path, state)
                elif change in ('dependency', 'acceptance'):
                    backlog = c.items(self.root)
                    backlog[-1]['depends_on' if change == 'dependency' else 'acceptance'] = []
                    self.backlog_path.write_text('\n'.join(c.toml_item(item) for item in backlog))
                elif change in ('history', 'product'):
                    path = 'loop/reports/STEP-0033/eval_r2.json' if change == 'history' else 'src/product.py'
                    (self.root/path).write_text('TEST-ONLY changed bytes')
                elif change == 'missing record':
                    self.record_path.unlink()
                self.commit()
                self.reject('exact replay|exactly BLOCKED', **({'reason':'TEST-ONLY different reason'} if change == 'reason' else {}))

    def test_each_replace_boundary_rolls_back_exact_bytes(self):
        actual = c.os.replace
        for fail_at in (1,2,3):
            with self.subTest(boundary=fail_at):
                calls = 0
                def replace(source, target):
                    nonlocal calls
                    calls += 1
                    if calls == fail_at:
                        raise OSError('TEST-ONLY injected replace failure')
                    return actual(source,target)
                with patch.object(c.os, 'replace', side_effect=replace), patch.object(self.control,'packet') as packet:
                    self.reject('injected replace failure')
                    packet.assert_not_called()

    def test_replace_then_raise_at_each_boundary_rolls_back(self):
        actual = c.os.replace
        for fail_at in (1,2,3):
            with self.subTest(boundary=fail_at):
                calls = 0
                def replace(source,target):
                    nonlocal calls
                    calls += 1
                    result = actual(source,target)
                    if calls == fail_at:
                        raise OSError('TEST-ONLY post-replace failure')
                    return result
                with patch.object(c.os,'replace',side_effect=replace):
                    self.reject('post-replace failure')

    def test_partial_and_persistent_staging_failure_cannot_touch_canonical_files(self):
        actual = c.os.fdopen
        class Partial:
            def __init__(self,stream): self.stream=stream
            def __enter__(self): return self
            def __exit__(self,*args): self.stream.close()
            def write(self,data):
                self.stream.write(data[:max(1,len(data)//2)])
                raise OSError('TEST-ONLY persistent partial staging failure')
        with patch.object(c.os,'fdopen',side_effect=lambda *a,**kw:Partial(actual(*a,**kw))):
            self.reject('persistent partial staging failure')

    def test_lock_serialization_failure_releases_owned_lock(self):
        actual = Path.open
        lock = self.control.runs/'lock.json'
        class Partial:
            def __init__(self,stream): self.stream=stream
            def __enter__(self): return self
            def __exit__(self,*args): self.stream.close()
            def write(self,data):
                self.stream.write(data[:1])
                raise OSError('TEST-ONLY partial lock failure')
        def opening(path,*args,**kwargs):
            stream=actual(path,*args,**kwargs)
            return Partial(stream) if path==lock and args==('xb',) else stream
        with patch.object(Path,'open',opening):
            self.reject('partial lock failure')

    def test_packet_regeneration_occurs_only_after_three_file_commit(self):
        actual = self.control.packet
        def packet():
            self.assertEqual(self.control.state()['items'][PARENT]['status'],'SPLIT')
            self.assertEqual([i['id'] for i in c.items(self.root)[-2:]],CHILDREN)
            self.assertTrue(self.record_path.is_file())
            return actual()
        with patch.object(self.control,'packet',side_effect=packet) as called:
            self.register();called.assert_called_once()

    def test_packet_failure_reports_committed_transaction_without_rollback(self):
        with patch.object(self.control,'packet',side_effect=OSError('TEST-ONLY packet failed')):
            with self.assertRaisesRegex(RuntimeError,'registration committed; PACKET regeneration failed'):
                self.register()
        self.assertEqual(self.control.state()['items'][PARENT]['status'],'SPLIT')
        self.assertEqual([i['id'] for i in c.items(self.root)[-2:]],CHILDREN)
        self.assertTrue(self.record_path.is_file())
        self.assertFalse((self.control.runs/'lock.json').exists())

    def test_authorization_exact_keys_types_and_execution_false(self):
        original=copy.deepcopy(self.proposal['authorization'])
        for key,value in [('execution_authorized',True),('execution_authorized',0),
                          ('execution_authorized','false'),('activation',False),('extra','unexpected')]:
            with self.subTest(key=key,value=value):
                self.proposal['authorization']=copy.deepcopy(original)
                self.proposal['authorization'][key]=value
                self.save_proposal();self.commit();self.reject('approval keys/types')
        for key in original:
            self.proposal['authorization']=copy.deepcopy(original)
            self.proposal['authorization'].pop(key)
            self.save_proposal();self.commit();self.reject('approval keys/types')

    def test_malformed_or_symlink_lock_always_rejects(self):
        lock=self.control.runs/'lock.json'
        lock.write_text('{malformed');self.reject('owned step lock')
        lock.unlink();lock.symlink_to(self.base/'absent-lock-target')
        self.reject('owned step lock')

    def test_rollback_failure_retains_ownership_and_recovery_bytes(self):
        actual=c.os.replace
        def failing(source,target):
            if str(target)==str(self.backlog_path) or str(source).endswith('.old'):
                raise OSError('TEST-ONLY filesystem replacement unavailable')
            return actual(source,target)
        with patch.object(c.os,'replace',side_effect=failing), patch.object(self.control,'packet') as packet:
            with self.assertRaisesRegex(RuntimeError,'rollback failed; ownership and recovery files retained'):
                self.register()
            packet.assert_not_called()
        self.assertTrue((self.control.runs/'lock.json').exists())
        originals=list(self.state_path.parent.glob('.state.json.*.old'))
        self.assertEqual(len(originals),1)
        self.assertEqual(json.loads(originals[0].read_bytes()),self.before)
        self.assertFalse(self.record_path.exists())

    def test_child_execution_requires_exact_l12_path_and_integrated_prior_child(self):
        self.register();self.commit()
        with self.assertRaisesRegex(ValueError,'not the next eligible item'):
            self.control.start(CHILDREN[1],critical_path=['L12'])
        self.assertFalse((self.control.runs/'lock.json').exists())
        started=self.control.start(CHILDREN[0],critical_path=['L12'])
        self.assertEqual(started['item'],CHILDREN[0])

    def test_late_dirty_refusal_releases_ownership_without_registration(self):
        actual_git = c.git
        checks = 0
        def git(root, *args):
            nonlocal checks
            if args[0] == 'status':
                checks += 1
                if checks == 2:
                    return 'TEST-ONLY concurrent dirty tree'
            return actual_git(root, *args)
        with patch.object(c, 'git', side_effect=git):
            self.reject('repository changed during registration')
        self.assertFalse((self.control.runs/'lock.json').exists())

    def test_cli_contract(self):
        with patch('sys.stdout', new_callable=io.StringIO) as stdout:
            result = c.main(['--root', str(self.root), 'register-approved-split', '--parent', PARENT,
                             '--proposal', PROPOSAL, '--authorized-by', AUTHORITY, '--reason', REASON])
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(stdout.getvalue())['child_order'], CHILDREN)


if __name__ == '__main__':
    unittest.main()
