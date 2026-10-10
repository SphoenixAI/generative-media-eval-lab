#!/usr/bin/env python3
"""Bounded build-loop orchestrator. Only this process mutates Git or calls Codex."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import tomllib


class LoopError(RuntimeError):
    pass


class RoleError(LoopError):
    pass


def read_json(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, indent=2) + '\n')
    temporary.replace(path)


def command(args, cwd, *, check=True, env=None):
    result = subprocess.run([str(a) for a in args], cwd=cwd, env=env,
                            text=True, capture_output=True)
    if check and result.returncode:
        raise LoopError(f'{args[0]} failed ({result.returncode}): {result.stderr.strip()}')
    return result


def validate(value, schema, at='$'):
    """Validate the deliberately small strict-schema subset used by role outputs."""
    if 'anyOf' in schema:
        for option in schema['anyOf']:
            try:
                validate(value, option, at)
                return
            except ValueError:
                pass
        raise ValueError(f'{at}: does not match any allowed type')
    kinds = {'object': dict, 'array': list, 'string': str, 'integer': int,
             'number': (int, float), 'boolean': bool, 'null': type(None)}
    kind = schema.get('type')
    if kind and (not isinstance(value, kinds[kind]) or
                 (kind in ('integer', 'number') and isinstance(value, bool))):
        raise ValueError(f'{at}: expected {kind}')
    if 'enum' in schema and value not in schema['enum']:
        raise ValueError(f'{at}: outside enum')
    if kind == 'object':
        props = schema.get('properties', {})
        if set(schema.get('required', [])) - value.keys():
            raise ValueError(f'{at}: missing required fields')
        if schema.get('additionalProperties') is False and value.keys() - props.keys():
            raise ValueError(f'{at}: unexpected fields')
        for key, child in value.items():
            if key in props:
                validate(child, props[key], f'{at}.{key}')
    if kind == 'array':
        for index, child in enumerate(value):
            validate(child, schema.get('items', {}), f'{at}[{index}]')


def needs_enhancement(evaluation, research, gate):
    return (not gate.get('passed', False) or bool(evaluation['blocking_findings']) or
            any(s['score'] <= 2 for s in evaluation['scores'].values()) or
            any(c['action_required'] for c in research['claims']))


def sanitize_paths(text, roots):
    """Known sibling roots precede their shorter prefixes; never match partial segments."""
    for prefix,label in roots:
        text=re.sub(re.escape(str(prefix))+r"(?=/|$|[\"'\n\r\t:;,\)])",lambda _:label,text)
    return text


def trailing_counts(state):
    after=max((e['after_step'] for e in state.get('events',[]) if e.get('event')=='RESUME'),default=-1)
    history=[s for s in state.get('steps',[]) if s['step']>after]
    non_integrated=failures=0
    for row in reversed(history):
        if row['decision']=='INTEGRATE': break
        non_integrated+=1
    for row in reversed(history):
        if row.get('rule')!='RF': break
        failures+=1
    return non_integrated,failures


def observed_model(log):
    """Read only the CLI header, never infer a model from defaults or role prose."""
    header = '\n'.join(log.splitlines()[:30]).split('\nuser\n', 1)[0]
    match = re.search(r'^model:\s*(\S+)\s*$', header, re.M)
    return match.group(1) if match else 'unknown'


def cutoff(clock, now=None):
    """The next local occurrence allows the documented overnight --until 07:30."""
    now = now or dt.datetime.now()
    target = dt.datetime.combine(now.date(), dt.datetime.strptime(clock, '%H:%M').time())
    return target if target > now else target + dt.timedelta(days=1)


def alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except (PermissionError, ValueError):
        return True


def role_argv(role, cwd, output, schema=None):
    writable = role in ('builder_plan', 'builder_build', 'enhancer')
    args = ['codex', 'exec', '-C', str(cwd), '-s',
            'workspace-write' if writable else 'read-only',
            '-c', 'approval_policy=never', '-c', 'sandbox_workspace_write.network_access=false']
    if not writable:
        args += ['--skip-git-repo-check']
    if role == 'evaluator':
        args += ['-c', 'model_reasoning_effort=high']
        if os.environ.get('LOOP_EVAL_MODEL'):
            args += ['-m', os.environ['LOOP_EVAL_MODEL']]
    if role == 'researcher':
        args += ['-c', 'web_search=live']
    if schema:
        args += ['--output-schema', str(schema)]
    return args + ['-o', str(output), '-']


class Runner:
    def __init__(self, root, *, fixtures=False, recovery=None):
        self.root = Path(root).resolve()
        self.config = tomllib.loads((self.root / 'loop/config.toml').read_text())
        self.runs = (self.root / self.config['paths']['runs_dir']).resolve()
        self.environment = (self.root / self.config['paths']['env_dir']).resolve()
        self.fixture_mode = fixtures
        self.recovery = recovery
        self.recovered = False
        self.env = dict(os.environ, UV_PROJECT_ENVIRONMENT=str(self.environment),
                        LOOP_RUNNER_PID=str(os.getpid()))
        self.step = None
        self.step_dir = None
        self.harness = self.root / 'loop'
        self.codex_failures = 0
        self.main = self.config['git']['main']
        self.integration = self.config['git']['integration']
        self.remote = self.config['git']['remote']
        if self.main == self.integration:
            raise LoopError('main and integration must be different branches')
        self.git_ready = False
        self.remote_url = None
        self.deadline = None

    def configured_command(self, value):
        args = shlex.split(value) if isinstance(value, str) else list(value)
        return [a.replace('{python}', str(self.environment / 'bin/python')).replace('{root}', str(self.root)) for a in args]

    def git(self, *args, check=True):
        return command(['git', *args], self.root, check=check, env=self.env)

    def ctl(self, name, *args, check=True, live=False):
        script = self.root / 'loop/loopctl.py' if live else self.harness / 'loopctl.py'
        result = command([sys.executable, script, '--root', self.root, '--runs',
                          self.runs, name, *args], self.root, check=check, env=self.env)
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return result.stdout.strip()

    def ensure_branch(self):
        if self.git('branch', '--show-current').stdout.strip() != self.integration:
            self.git_ready = False
            raise LoopError('Refusing mutation: worktree is not on integration')
        if self.remote_url and self.git('remote', 'get-url', self.remote).stdout.strip() != self.remote_url:
            self.git_ready = False
            raise LoopError('Remote URL changed during loop')

    def commit(self, message):
        main=(self.root/self.config['paths'].get('main_checkout','../Content Evaluator')).resolve()
        message=sanitize_paths(message,[(self.runs,'<RUNS>'),(self.environment,'<ENV>'),(self.root,'<WT>'),(main,'<MAIN>'),(Path.home(),'~')])
        self.ensure_branch()
        self.git('add', '-A')
        if self.git('diff', '--cached', '--quiet', check=False).returncode:
            self.git('commit', '-m', message)

    def push(self):
        if self.git('branch', '--show-current').stdout.strip() != self.integration:
            raise LoopError('Refusing push: worktree is not on integration')
        self.ensure_branch()
        self.git('push', self.remote, f'HEAD:refs/heads/{self.integration}')

    def sync(self):
        self.git('fetch', self.remote)
        upstream = f'{self.remote}/{self.main}'
        if self.git('merge-base', '--is-ancestor', upstream, 'HEAD', check=False).returncode:
            merged = self.git('merge', '--no-edit', upstream, check=False)
            if merged.returncode:
                self.git('merge', '--abort', check=False)
                raise LoopError('Merge conflict; merge aborted')
            self.ctl('bootstrap', '--rebaseline', live=True)
            self.commit('loop: rebaseline after merging main')

    def preflight(self):
        if self.git('branch', '--show-current').stdout.strip() != self.integration:
            raise LoopError(f'Expected branch {self.integration}')
        self.git_ready = True
        lock = read_json(self.runs / 'lock.json')
        if lock:
            if alive(lock['pid']):
                self.git_ready = False  # Do not race a live owner's packet or push.
                raise LoopError('Live lock owner; no work performed')
            self.step = int(lock['step'])
            self.step_dir = self.runs / f'{self.step:04d}'
            self.harness = self.step_dir / 'harness'
            result = self.ctl('abort-step')
            self.git('reset', '--hard', result['base_commit'])
            self.git('clean', '-fd')
            self.ctl('finish', '--step', str(self.step))
            self.commit(f'loop(step-{self.step:04d}): recovered ABANDONED step')
            self.step = None
            self.harness = self.root / 'loop'
        if self.git('status', '--porcelain').stdout.strip():
            self.git_ready = False
            raise LoopError('Worktree must be clean before starting')
        if (self.root / 'loop/STOP').exists():
            raise LoopError('STOP file exists')
        self.remote_url = self.git('remote', 'get-url', self.remote).stdout.strip()
        self.sync()
        if not self.fixture_mode:
            help_text = command(['codex', 'exec', '--help'], self.root).stdout
            for flag in ('--sandbox', '--output-schema', '-o', '--skip-git-repo-check'):
                if flag not in help_text:
                    raise LoopError(f'Installed codex exec lacks required flag {flag}')
            version = command(['codex', '--version'], self.root).stdout.strip()
        else:
            version = 'SYNTHETIC DRY-RUN; no Codex process'
        self.runs.mkdir(parents=True, exist_ok=True)
        write_json(self.runs / 'preflight.json', {'codex': version, 'python': sys.version,
                   'time': dt.datetime.now(dt.timezone.utc).isoformat()})
        doctor = self.config['commands'].get('doctor')
        if doctor:
            command(self.configured_command(doctor), self.root, env=self.env)

    def heartbeat(self):
        path = self.runs / 'lock.json'
        lock = read_json(path)
        if lock and int(lock['pid']) == os.getpid():
            lock['heartbeat'] = dt.datetime.now(dt.timezone.utc).isoformat()
            write_json(path, lock)

    def fixture(self, role, output, cwd, round_number):
        folder = self.harness / 'tests/fixtures'
        if role == 'builder_plan':
            body = (folder / 'builder_plan.md').read_text()
            duplicate=read_json(folder / 'duplicate_research.json')
            if duplicate: body+='\nCLAIM C1: '+duplicate['claims'][0]['claim']+'\n'
            report = self.root / read_json(self.step_dir / 'step.json')['report']
            text = report.read_text()
            report.write_text(re.sub(r'(## Plan[^\n]*\n).*?(?=\n## |\Z)',
                                    lambda m: m[1] + body.rstrip() + '\n', text,
                                    count=1, flags=re.S))
            output.write_text('SYNTHETIC DRY-RUN plan installed.\n')
            return
        data = read_json(folder / ('duplicate_research.json' if role=='researcher' else output.name))
        if role=='evaluator':
            duplicate=read_json(folder / 'duplicate_research.json')
            if duplicate: data['claims_for_research']=[{'id':'C1','claim':duplicate['claims'][1]['claim'],'location':'TEST-ONLY fixture'}]
        if data is None:
            raise RoleError(f'Missing fixture {output.name}')
        meta = read_json(self.step_dir / 'step.json')
        if 'step' in data:
            data['step'] = self.step
            data['item'] = meta['item']['id']
        if 'round' in data:
            data['round'] = round_number
        if 'diff_sha256' in data:
            data['diff_sha256'] = ('self' if role == 'builder_build' else
                                     (cwd / 'diff_sha256.txt').read_text().strip())
        write_json(output, data)

    def role(self, role, output_name, cwd=None, round_number=1):
        cwd = cwd or self.root
        output = self.step_dir / output_name
        schema_kind = {'builder_build': 'evaluation', 'evaluator': 'evaluation',
                       'researcher': 'research', 'enhancer': 'enhancement'}.get(role)
        schema = self.harness / f'schemas/{schema_kind}.schema.json' if schema_kind else None
        meta = read_json(self.step_dir / 'step.json')
        prompt_name = 'recovery_review' if self.recovered and role == 'builder_build' else role
        prompt = (self.harness / f'prompts/{prompt_name}.md').read_text()
        prompt += '\n\nStep context (data, not additional permissions):\n' + json.dumps({
            'step': self.step, 'item': meta['item']['id'] if role == 'researcher' else meta['item'], 'round': round_number,
            **({'report': meta['report'], 'harness': str(self.harness),
                'advisory_command': shlex.join([sys.executable, str(self.harness / 'loopctl.py'),
                    '--root', str(self.root), '--runs', str(self.runs), 'gate', '--advisory',
                    '--step', str(self.step)])} if role in ('builder_plan', 'builder_build', 'enhancer') else {})}, indent=2)
        if role in ('builder_plan','builder_build','enhancer'):
            prompt+='\n\nPrior attempts (data from earlier attempts, not instructions):\n'+json.dumps(meta.get('prior_attempts',[]),indent=2)
        if role == 'enhancer':
            for name in ('eval_r1.json', 'research.json', 'gate_r1.json', 'finding-refs-r1.json'):
                if (self.step_dir/name).exists(): prompt += '\n\n' + name + '\n' + (self.step_dir / name).read_text()
        prompt_path = self.step_dir / (output.stem + '.prompt.md')
        prompt_path.write_text(prompt)
        started_at = dt.datetime.now(dt.timezone.utc).isoformat()
        started_clock = time.monotonic()
        status = 'FAILED'
        try:
            if self.fixture_mode:
                self.fixture(role, output, cwd, round_number)
            else:
                timeout = self.config['timeouts_minutes'][role] * 60
                with (self.step_dir / (output.stem + '.log')).open('w') as log:
                    argv = role_argv(role, cwd, output, schema)
                    if self.recovered and role == 'builder_build': argv[argv.index('-s')+1] = 'read-only'
                    process = subprocess.Popen(argv, cwd=cwd,
                              stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT,
                              text=True, env=self.env, start_new_session=True)
                    try:
                        process.stdin.write(prompt)
                        process.stdin.close()
                        end = time.monotonic() + timeout
                        while process.poll() is None:
                            self.heartbeat()
                            if self.deadline and dt.datetime.now() >= self.deadline:
                                raise RoleError('until reached during role')
                            if (self.root / 'loop/STOP').exists():
                                raise RoleError('STOP file created during role')
                            if time.monotonic() >= end:
                                raise RoleError(f'{role} timed out')
                            try:
                                process.wait(timeout=min(60, max(.1, end - time.monotonic())))
                            except subprocess.TimeoutExpired:
                                pass
                        if process.returncode:
                            raise RoleError(f'{role} failed with exit {process.returncode}')
                    finally:
                        if process.poll() is None:
                            os.killpg(process.pid, signal.SIGTERM)
                            try:
                                process.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                os.killpg(process.pid, signal.SIGKILL)
                                process.wait()
            if schema:
                data = read_json(output)
                validate(data, read_json(schema))
                if schema_kind != 'enhancement' and (data['step'] != self.step or
                                                    data['item'] != meta['item']['id']):
                    raise ValueError('role returned wrong step or item')
                if schema_kind == 'evaluation':
                    expected_role = 'builder' if role == 'builder_build' else 'evaluator'
                    if data['role'] != expected_role or data['round'] != round_number:
                        raise ValueError('role returned wrong role or round')
                    if role == 'builder_build' and data['diff_sha256'] != 'self':
                        raise ValueError('builder self-evaluation hash must be self')
                status = 'COMPLETED'
                return data
            if not output.exists():
                raise ValueError('role output is missing')
            status = 'COMPLETED'
        except (OSError, ValueError, RoleError) as error:
            raise RoleError(f'{role}: {error}') from error
        finally:
            log_path = self.step_dir / (output.stem + '.log')
            model = 'SYNTHETIC_FIXTURE' if self.fixture_mode else observed_model(
                log_path.read_text(errors='replace') if log_path.exists() else '')
            metadata_path = self.step_dir / 'role_metadata.json'
            metadata = read_json(metadata_path, {'calls': []})
            metadata['calls'].append({'role': role, 'round': round_number,
                'output': output.name, 'model': model, 'started_at': started_at,
                'finished_at': dt.datetime.now(dt.timezone.utc).isoformat(),
                'elapsed_seconds': round(time.monotonic() - started_clock, 3),
                'status': status})
            write_json(metadata_path, metadata)

    def evaluate(self, round_number):
        self.ensure_branch()
        self.git('add', '-A')
        # Gate first: export must contain authoritative results, never a placeholder.
        self.ctl('gate', '--step', str(self.step), '--round', str(round_number), check=False)
        self.ctl('export', '--step', str(self.step), '--round', str(round_number))
        view = self.step_dir / f'eval_view_r{round_number}'
        expected = (view / 'diff_sha256.txt').read_text().strip()
        for attempt in range(2):
            result = self.role('evaluator', f'eval_r{round_number}.json', view, round_number)
            result = self.ctl('canonicalize-evaluation','--step',str(self.step),'--round',str(round_number))
            if result['diff_sha256'] == expected:
                return result
            if attempt == 0:
                shutil.copy2(self.step_dir / f'eval_r{round_number}.json',
                             self.step_dir / f'eval_r{round_number}_hash_mismatch.json')
        return result  # Deterministic R5 handles the mismatch after its one rerun.

    def recover_product(self, source_number, expected_hash):
        """Verify the historical full diff in isolation; never restore old bookkeeping."""
        source = self.runs / f'{source_number:04d}'
        original = read_json(source / 'step.json')
        current = read_json(self.step_dir / 'step.json')
        evidence = {'source_step': source_number, 'new_step': self.step,
                    'expected_diff_sha256': expected_hash, 'matched': False}
        def record(reason):
            evidence['reason'] = reason
            write_json(self.step_dir / 'recovery.json', evidence)
            return False
        if original['item']['id'] != current['item']['id']:
            return record('item mismatch; use fresh build')
        patch = source / 'eval_view_r2/diff.patch'
        raw = patch.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected_hash:
            return record('source diff hash mismatch; use fresh build')
        with tempfile.TemporaryDirectory(prefix='eval-loop-recover-') as temporary:
            replica = Path(temporary) / 'replica'
            command(['git','clone','--shared','--no-checkout',str(self.root),str(replica)], self.root)
            command(['git','checkout','--detach',original['base_commit']], replica)
            command(['git','apply','--index',str(patch)], replica)
            restored = subprocess.check_output(['git','diff','--binary',original['base_commit'],'--'],cwd=replica)
            evidence['restored_diff_sha256'] = hashlib.sha256(restored).hexdigest()
            if evidence['restored_diff_sha256'] != expected_hash:
                return record('reconstructed diff hash mismatch; use fresh build')
            paths = command(['git','diff','--name-only',original['base_commit'],'--'],replica).stdout.splitlines()
            product = [name for name in paths if name != original['report']]
            if not product or any(not name.startswith(('src/','tests/','docs/')) for name in product):
                return record('unexpected recovery path; use fresh build')
            delta = subprocess.check_output(['git','diff','--binary',original['base_commit'],'--',*product],cwd=replica)
            product_patch = self.step_dir / 'recovered-product.patch'
            product_patch.write_bytes(delta)
            if self.git('apply','--check','--index',str(product_patch),check=False).returncode:
                return record('current product base incompatible; use fresh build')
            self.git('apply','--index',str(product_patch))
            actual = subprocess.check_output(['git','diff','--binary',current['base_commit'],'--',*product],cwd=self.root)
            if actual != delta:
                # Roll back only the exact patch just applied; retain the new step skeleton.
                self.git('apply','--reverse','--index',str(product_patch))
                return record('restored product bytes mismatch; use fresh build')
            evidence.update(matched=True,product_diff_sha256=hashlib.sha256(actual).hexdigest(),
                            product_paths=product,original_base=original['base_commit'],
                            excluded_historical_report=original['report'])
        # Only the sealed plan is carried forward; all assessments are freshly produced.
        import importlib.util
        spec=importlib.util.spec_from_file_location('recovery_control',self.harness/'loopctl.py')
        control=importlib.util.module_from_spec(spec); spec.loader.exec_module(control)
        report=self.root/current['report']
        report.write_text(control.replace_section(report.read_text(),'Plan',original['plan']))
        evidence['reason']='exact historical full diff reconstructed; matching product patch restored; fresh validation required'
        write_json(self.step_dir/'recovery.json',evidence)
        return True

    def one_step(self):
        prefer = read_json(self.runs/f'{self.recovery[0]:04d}/step.json')['item']['id'] if self.recovery else None
        preference = ['--prefer',prefer] if prefer else []
        item = self.ctl('next', *preference, live=True)
        if item == 'NONE' or item is None:
            return None
        item_id = item['id'] if isinstance(item, dict) else item
        started = self.ctl('start', '--item', item_id, *preference, live=True)
        self.step = int(started['step'])
        self.step_dir = self.runs / f'{self.step:04d}'
        self.harness = self.step_dir / 'harness'
        self.config = tomllib.loads((self.harness / 'config.toml').read_text())
        role_failed = False
        try:
            self.recovered = False
            if self.recovery is not None:
                source_number, expected_hash = self.recovery
                self.recovery = None  # Never apply an old patch to a subsequent queue item.
                self.recovered = self.recover_product(source_number, expected_hash)
            if not self.recovered:
                self.role('builder_plan', 'builder_plan.md')
            split_path = self.root / f'loop/reports/STEP-{self.step:04d}-split.toml'
            if split_path.exists():
                self.ctl('split', '--step', str(self.step))
            else:
                self.ctl('seal-plan', '--step', str(self.step))
                self.role('builder_build', 'self_eval.json')
                evaluation = self.evaluate(1)
                self.ctl('research-view', '--step', str(self.step))
                self.role('researcher', 'research.json', self.step_dir / 'research_view')
                research = self.ctl('canonicalize-research', '--step', str(self.step))
                self.ctl('report', '--step', str(self.step), '--round', '1')
                if needs_enhancement(evaluation, research, read_json(self.step_dir / 'gate_r1.json')):
                    self.role('enhancer', 'enhancement.json')
                    self.evaluate(2)
                    self.ctl('report', '--step', str(self.step), '--round', '2')
                self.ctl('decide', '--step', str(self.step))
        except RoleError as error:
            role_failed = True
            write_json(self.step_dir / 'failure.json', {'rule': 'RF', 'error': str(error)})
            self.ctl('decide', '--step', str(self.step))
        decision = read_json(self.step_dir / 'decision.json')
        self.ensure_branch()
        if decision['decision'] != 'INTEGRATE':
            self.git('reset', '--hard', started['base_commit'])
            self.git('clean', '-fd')
        self.ctl('finish', '--step', str(self.step))
        title = read_json(self.step_dir / 'step.json')['item']['title']
        self.commit(f"loop(step-{self.step:04d}): {item_id} {title} [{decision['decision']}]")
        self.push()
        self.update_pr()
        self.step = None
        self.harness = self.root / 'loop'
        self.codex_failures = self.codex_failures + 1 if role_failed else 0
        return decision

    def update_pr(self):
        if self.fixture_mode or not shutil.which('gh'):
            return
        result = command(['gh', 'pr', 'list', '--head', self.integration, '--base', self.main,
                          '--json', 'number'], self.root, check=False, env=self.env)
        if result.returncode:
            return
        prs = json.loads(result.stdout)
        body = self.root / 'loop/reports/PACKET-latest.md'
        args = (['gh', 'pr', 'edit', str(prs[0]['number'])] if prs else
                ['gh', 'pr', 'create', '--head', self.integration, '--base', self.main,
                 '--title', 'Evaluated build loop: Pilot 0.1'])
        result = command(args + ['--body-file', str(body)], self.root, check=False, env=self.env)
        if not prs and result.returncode == 0:
            print('ROLLING_PR=' + result.stdout.strip(), flush=True)

    def stop(self, reason):
        if self.git_ready and self.step is not None:
            self.ensure_branch()
            step = read_json(self.step_dir / 'step.json')
            report = self.root / step['report']
            if report.exists():
                shutil.copy2(report, self.step_dir / 'report.md')
            write_json(self.step_dir / 'decision.json', {'decision': 'ABANDONED',
                       'rule': 'ABANDONED', 'stop': True, 'reason': reason})
            self.git('reset', '--hard', step['base_commit'])
            self.git('clean', '-fd')
            self.ctl('finish', '--step', str(self.step))
            self.commit(f'loop(step-{self.step:04d}): {step["item"]["id"]} [ABANDONED]')
            self.step = None
            self.harness = self.root / 'loop'
        if self.git_ready and self.step is None:
            self.ctl('packet', live=True)
            packet = self.root / 'loop/reports/PACKET-latest.md'
            self.ctl('packet','--reason',reason,live=True)
            self.commit('loop: checkpoint (' + reason + ')')
            self.push()
        print(json.dumps({'stopped': reason, 'runs': str(self.runs)}), flush=True)

    def run(self, *, once=False, max_steps=None, until=None):
        completed = non_integrated = 0
        self.deadline = cutoff(until) if until else None
        non_integrated,self.codex_failures = trailing_counts(read_json(self.root/'loop/state.json',{}))
        reason = 'complete'
        try:
            self.preflight()
            while True:
                if (self.root / 'loop/STOP').exists():
                    reason = 'STOP file exists'
                    break
                if (self.root/'loop/STOP_AFTER_STEP').exists():
                    reason='STOP_AFTER_STEP file exists'
                    break
                if non_integrated >= self.config['limits']['max_consecutive_non_integrate']:
                    reason = 'consecutive non-integrations'
                    break
                if self.codex_failures >= self.config['limits']['max_codex_failures']:
                    reason = 'three consecutive Codex failures'
                    break
                if max_steps is not None and completed >= max_steps:
                    reason = 'max-steps reached'
                    break
                if self.deadline and dt.datetime.now() >= self.deadline:
                    reason = 'until reached'
                    break
                self.ensure_branch()
                if self.git('status', '--porcelain').stdout.strip():
                    raise LoopError('Worktree became dirty between steps')
                self.sync()
                result = self.one_step()
                if result is None:
                    reason = 'no eligible item'
                    break
                completed += 1
                non_integrated = 0 if result['decision'] == 'INTEGRATE' else non_integrated + 1
                print(json.dumps({'step_result': result}), flush=True)
                if result['rule'] == 'R0':
                    reason = 'R0 invariant failure'
                    break
                if self.codex_failures:
                    # Back off even on the third failure, as specified; STOP interrupts waits.
                    self.pause((120, 300, 600)[min(self.codex_failures, 3) - 1])
                if self.codex_failures >= self.config['limits']['max_codex_failures']:
                    reason = 'three consecutive Codex failures'
                    break
                if once:
                    reason = 'once complete'
                    break
                if non_integrated >= self.config['limits']['max_consecutive_non_integrate']:
                    reason = 'consecutive non-integrations'
                    break
                self.pause(30)
        except (LoopError, KeyboardInterrupt) as error:
            reason = str(error) or 'interrupted; recover abandoned step on restart'
            self.stop(reason)
            return 1
        self.stop(reason)
        return 0

    def pause(self, seconds):
        if self.fixture_mode:
            return
        end = time.monotonic() + seconds
        while time.monotonic() < end and not (self.root / 'loop/STOP').exists() and not (self.root/'loop/STOP_AFTER_STEP').exists():
            time.sleep(min(1, end - time.monotonic()))


def dry_run(root, args):
    """Run actual gates and Git operations against disposable local-only repositories."""
    with tempfile.TemporaryDirectory(prefix='eval-loop-dry-') as temporary:
        base = Path(temporary).resolve()
        bare, wt, main = base / 'remote.git', base / 'Content Evaluator - loop', base / 'Content Evaluator'
        command(['git', 'clone', '--bare', '--no-local', str(root), str(bare)], base)
        command(['git', 'clone', str(bare), str(wt)], base)
        command(['git', 'clone', '--branch', 'main', str(bare), str(main)], base)
        command(['git', 'checkout', 'loop/integration'], wt)
        command(['git', 'config', 'user.name', 'TEST-ONLY dry run'], wt)
        command(['git', 'config', 'user.email', 'dry-run@example.invalid'], wt)
        runner = Runner(wt, fixtures=True)
        # Relative layout keeps the dry run away from real worktree, RUNS and ENV.
        for name, expected in [('runs_dir', base / 'Content Evaluator - loop-runs'),
                               ('env_dir', base / 'Content Evaluator - loop-env'),
                               ('main_checkout', main)]:
            actual = (wt / runner.config['paths'][name]).resolve()
            if actual != expected:
                raise LoopError(f'Dry-run configuration must use standard sibling layout: {name}')
        state=read_json(wt / 'loop/state.json')
        state['items']['L00']={'status':'PENDING','retries':0}
        after=max((s['step'] for s in state.get('steps',[])),default=0)
        state.setdefault('events',[]).append({'event':'RESUME','authorized_by':'TEST-ONLY dry run','reason':'TEST-ONLY isolated validation','after_step':after,'decision':'RESUME','product_retry_charged':False,'step':after})
        write_json(wt / 'loop/state.json',state)
        runner.commit('TEST-ONLY: reopen L00 in disposable dry-run clone')
        command(runner.configured_command(runner.config['commands']['setup']), wt, env=runner.env)
        result = runner.run(once=args.once, max_steps=args.max_steps or 1, until=args.until)
        decisions = [read_json(p) for p in sorted(runner.runs.glob('*/decision.json'))]
        gates = [read_json(p) for p in runner.runs.glob('*/gate_r*.json')]
        clean = (result == 0 and len(decisions) == 1 and
                 decisions[0]['decision'] == 'INTEGRATE' and decisions[0]['rule'] == 'R6' and
                 bool(gates) and all(g['passed'] for g in gates) and
                 not list(runner.runs.glob('*/failure.json')))
        print(json.dumps({'dry_run': 'PASS' if clean else 'FAIL',
                          'isolated_local_remote': True, 'model_calls': 0,
                          'decisions': decisions}))
        return 0 if clean else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--max-steps', type=int)
    parser.add_argument('--until')
    parser.add_argument('--recover-step', type=int)
    parser.add_argument('--recover-sha256')
    args = parser.parse_args()
    if (args.recover_step is None) != (args.recover_sha256 is None):
        parser.error('recovery requires both --recover-step and --recover-sha256')
    if args.recover_sha256 and not re.fullmatch(r'[a-f0-9]{64}',args.recover_sha256):
        parser.error('recovery requires a SHA-256 hex digest')
    if args.dry_run and args.recover_step is not None:
        parser.error('historical recovery is separate from synthetic dry-run')
    if args.max_steps is not None and args.max_steps < 1:
        parser.error('--max-steps must be positive')
    if args.until:
        try:
            args.until = dt.datetime.strptime(args.until, '%H:%M').strftime('%H:%M')
        except ValueError:
            parser.error('--until must be HH:MM')
    root = Path(__file__).resolve().parent.parent
    return dry_run(root, args) if args.dry_run else Runner(root,recovery=(args.recover_step,args.recover_sha256) if args.recover_step is not None else None).run(
        once=args.once, max_steps=args.max_steps, until=args.until)


if __name__ == '__main__':
    raise SystemExit(main())
