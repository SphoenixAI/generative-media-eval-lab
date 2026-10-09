"""Frozen, deterministic build-loop checks. All process calls use argument lists."""
from __future__ import annotations
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import tempfile
import time
import tomllib
import xml.etree.ElementTree as ET


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def execute(argv, root, timeout=300, env=None):
    try:
        result = subprocess.run(argv, cwd=root, env=env, text=True, capture_output=True, timeout=timeout)
        return {'argv': argv, 'exit_code': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'argv': argv, 'exit_code': -1, 'stdout': '', 'stderr': str(exc)}


def git(root, *args):
    result = execute(['git', *args], root)
    if result['exit_code']:
        raise RuntimeError(result['stderr'])
    return result['stdout']


def matches(path, pattern):
    return fnmatch.fnmatchcase(path, pattern) or (pattern.startswith('**/') and fnmatch.fnmatchcase(path, pattern[3:]))


def command_env(root, config):
    env = dict(os.environ)
    env.pop('PYTEST_ADDOPTS', None)
    env['PYTHONPATH'] = str(root / 'src')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['UV_PROJECT_ENVIRONMENT'] = str((root / config['paths']['env_dir']).resolve())
    main = (root / config['paths']['main_checkout']).resolve()
    for name in ('FFMPEG', 'FFPROBE'):
        if not env.get('EVAL_LAB_' + name):
            candidates = sorted((main / '.tools').glob('**/' + name.lower()))
            if candidates:
                env['EVAL_LAB_' + name] = str(candidates[0])
    return env


def argv_for(command, root, config):
    args = shlex.split(command) if isinstance(command, str) else list(command)
    python = str((root / config['paths']['env_dir']).resolve() / 'bin/python')
    return [arg.replace('{python}', python).replace('{root}', str(root)) for arg in args]


def run_command(command, root, config, baseline=None, advisory=False, timeout=300):
    argv = argv_for(command, root, config)
    prefix = (baseline or {}).get('sandbox', {}).get('prefix', [])
    if prefix and not advisory:
        argv = argv_for(prefix, root, config) + argv
    return execute(argv, root, timeout, command_env(root, config))


def junit(path, collected):
    """Map exact pytest node IDs to outcomes; malformed or duplicate evidence fails closed."""
    tree = ET.parse(path).getroot()
    lookup = {}
    for node in collected:
        parts = node.split('::')
        key = (parts[0].removesuffix('.py').replace('/', '.') + ''.join('.' + x for x in parts[1:-1]), parts[-1])
        if key in lookup:
            raise ValueError('ambiguous collected test id')
        lookup[key] = node
    outcomes = {}
    for case in tree.iter('testcase'):
        key = (case.get('classname', ''), case.get('name', ''))
        if key not in lookup:
            raise ValueError('JUnit test was not collected: ' + repr(key))
        node = lookup[key]
        if node in outcomes:
            raise ValueError('duplicate JUnit test: ' + node)
        state = 'passed'
        if case.find('failure') is not None: state = 'failed'
        if case.find('error') is not None: state = 'error'
        skip = case.find('skipped')
        if skip is not None:
            state = 'xfailed' if 'xfail' in (skip.get('type', '') + skip.get('message', '')).lower() else 'skipped'
        outcomes[node] = state
    if not outcomes:
        raise ValueError('empty JUnit evidence')
    leaves = [suite for suite in tree.iter('testsuite') if not suite.findall('testsuite')]
    if sum(int(s.get('tests', 0)) for s in leaves) != len(outcomes):
        raise ValueError('JUnit suite counts disagree with cases')
    return {'outcomes': outcomes, 'passed': sum(s == 'passed' for s in outcomes.values()), 'collected': collected}


def product_tests(root, evidence, config, baseline=None, advisory=False):
    command = (baseline or {}).get('commands', {}).get('tests', ['{python}', '-m', 'pytest', 'tests', '-q'])
    collect = run_command(list(shlex.split(command) if isinstance(command, str) else command) + ['--collect-only'], root, config, baseline, advisory)
    ids = [line.strip() for line in collect['stdout'].splitlines() if re.match(r'^tests/.*\.py::', line.strip())]
    with tempfile.TemporaryDirectory(prefix='loop-junit-') as directory:
        xml = Path(directory) / 'tests.xml'
        run = run_command(list(shlex.split(command) if isinstance(command, str) else command) + ['-p', 'no:cacheprovider', '--junitxml=' + str(xml)], root, config, baseline, advisory)
        data = {'passed': 0, 'outcomes': {}, 'collected': ids, 'valid': False, 'exit_code': run['exit_code']}
        try:
            data.update(junit(xml, ids))
            data['valid'] = collect['exit_code'] == 0 and bool(ids)
        except (OSError, ValueError, ET.ParseError) as exc:
            data['error'] = str(exc)
        if evidence is not None:
            evidence.mkdir(parents=True, exist_ok=True)
            write_json(evidence / 'product-tests-command.json', run)
            write_json(evidence / 'collection-command.json', collect)
            if xml.exists(): shutil.copyfile(xml, evidence / 'product-tests.xml')
    return data


def protected_paths(root):
    patterns = ['schemas/**/*.json', 'schemas/*.json', 'outputs/*.json', 'outputs/pilot0/**/*', 'pilot0/*.json', 'tests/**/*snapshot*', 'tests/**/*canonical*']
    return sorted({p.relative_to(root).as_posix() for pattern in patterns for p in root.glob(pattern) if p.is_file()})


def hashes(root, paths):
    return {p: digest((root / p).read_bytes()) if (root / p).is_file() and not (root / p).is_symlink() else None for p in paths}


def safe_copy(root, destination):
    """Only Git-visible files; never enumerate or copy ignored operator data."""
    paths = git(root, 'ls-files', '-z').split('\0') + git(root, 'ls-files', '--others', '--exclude-standard', '-z').split('\0')
    for name in set(paths) - {''}:
        source = root / name
        if name.startswith(('pilot-local/', '.tools/')):
            continue
        if source.is_symlink():
            raise ValueError('cannot execute a copy with a symlink: ' + name)
        if source.is_file():
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)


def approval_check(root, config, baseline=None, advisory=False):
    """Run even discovery in a throwaway copy, never overwrite accepted approval."""
    with tempfile.TemporaryDirectory(prefix='loop-approval-') as directory:
        copied = Path(directory)
        safe_copy(root, copied)
        paths = protected_paths(copied)
        before = hashes(copied, paths)
        local_config = json.loads(json.dumps(config))
        for key in ('env_dir', 'main_checkout'):
            local_config['paths'][key] = str((root / config['paths'][key]).resolve())
        command = (baseline or {}).get('commands', {}).get('approval', ['{python}', '-m', 'eval_lab.harness', '--output', 'outputs/approval.json'])
        result = run_command(command, copied, local_config, baseline, advisory)
        result['changed_protected'] = [p for p, old in before.items() if hashes(copied, [p])[p] != old]
        result['isolated_copy'] = True
        return result


def discover_sandbox(root):
    help_result = execute(['codex', 'sandbox', '--help'], root)
    prefix = ['codex', 'sandbox', '-P', 'workspace-write', '-C', '{root}', '-c', 'sandbox_workspace_write.network_access=false', '--']
    probe = execute([part.replace('{root}', str(root)) for part in prefix] + ['/usr/bin/true'], root)
    probe['argv'] = prefix + ['/usr/bin/true']
    # A named profile must be independently confirmed to limit writes; a successful
    # profile invocation alone is not proof. This CLI currently lacks that profile.
    return {'prefix': [], 'available': False, 'help': help_result['stdout'], 'probe': probe,
            'reason': 'No verified workspace-write permission profile; using documented direct execution fallback with G14.'}


def bootstrap(root, runs, config):
    root, runs = Path(root).resolve(), Path(runs).resolve()
    evidence = runs / 'bootstrap' / str(time.time_ns())
    commands = {'tests': ['{python}', '-m', 'pytest', 'tests', '-q'], 'doctor': ['{python}', '-m', 'eval_lab.pilot_cli', 'doctor'],
                'approval': ['{python}', '-m', 'eval_lab.harness', '--output', 'outputs/approval.json']}
    baseline = {'version': 1, 'commands': commands, 'sandbox': discover_sandbox(root)}
    tests = product_tests(root, evidence, config, baseline)
    if tests['exit_code'] or not tests['valid'] or tests['passed'] != len(tests['collected']):
        raise RuntimeError('bootstrap product tests failed: ' + json.dumps(tests))
    doctor = run_command(commands['doctor'], root, config, baseline)
    if doctor['exit_code']: raise RuntimeError('doctor failed: ' + doctor['stderr'])
    approval = approval_check(root, config, baseline)
    write_json(evidence / 'approval-discovery.json', approval)
    if approval['exit_code']: raise RuntimeError('bootstrap approval failed: ' + approval['stderr'])
    python = run_command(['{python}', '--version'], root, config)
    codex = execute(['codex', '--version'], root)
    try: doctor_data = json.loads(doctor['stdout'])
    except ValueError: raise RuntimeError('doctor must report JSON')
    baseline.update(passed=tests['passed'], outcomes=tests['outcomes'], collected=tests['collected'],
                    tools={'python': python['stdout'].strip(), 'codex': codex['stdout'].strip(), 'doctor': doctor_data},
                    approval={'isolated_copy': True, 'changed_protected': approval['changed_protected']})
    config_path = root / 'loop/config.toml'
    config_text = config_path.read_text()
    for key, value in {**commands, 'sandbox': baseline['sandbox']['prefix']}.items():
        config_text = re.sub(r'^' + key + r' = .*$', key + ' = ' + json.dumps(value), config_text, flags=re.M)
    config_path.write_text(config_text)
    manifest = hashes(root, protected_paths(root))
    baseline['protected_count'] = len(manifest)
    write_json(root / 'loop/baseline.json', baseline)
    (root / 'loop/baseline_tests.txt').write_text(''.join(f'{node}\t{outcome}\n' for node, outcome in sorted(tests['outcomes'].items())))
    (root / 'loop/protected.sha256').write_text(''.join(f'{sha}  {name}\n' for name, sha in sorted(manifest.items())))
    return baseline


def metadata_hash(directory):
    """Hash names and lstat metadata only: never open operator-authored files."""
    listing = []
    if directory.exists():
        for current, dirs, files in os.walk(directory, followlinks=False):
            for name in sorted(dirs + files):
                path = Path(current) / name
                stat = path.lstat()
                listing.append((path.relative_to(directory).as_posix(), stat.st_size, stat.st_mtime_ns))
    return digest(json.dumps(sorted(listing), separators=(',', ':')).encode())


def integrity(root, config):
    main = (root / config['paths']['main_checkout']).resolve()
    remote = config.get('git', {}).get('remote', 'origin')
    branch = config.get('git', {}).get('main', 'main')
    remote_main = git(root, 'ls-remote', remote, 'refs/heads/' + branch).strip()
    if not re.fullmatch(r'[0-9a-f]{40,64}\s+refs/heads/' + re.escape(branch), remote_main):
        raise RuntimeError('remote main could not be verified')
    return {'pilot_listing_sha256': metadata_hash(main / 'pilot-local'), 'remote_main': remote_main}


def changes(root, base):
    names = set(git(root, 'diff', '--name-only', '-z', base).split('\0')) - {''}
    untracked = set(git(root, 'ls-files', '--others', '--exclude-standard', '-z').split('\0')) - {''}
    records = {}
    for name in sorted(names | untracked):
        patch = git(root, 'diff', '--no-ext-diff', '--no-renames', '--unified=0', base, '--', name) if name in names else ''
        added = [line[1:] for line in patch.splitlines() if line.startswith('+') and not line.startswith('+++')]
        removed = [line[1:] for line in patch.splitlines() if line.startswith('-') and not line.startswith('---')]
        path = root / name
        binary = 'Binary files ' in patch
        if name in untracked and path.is_file():
            try: added = path.read_text().splitlines()
            except UnicodeError: binary = True
        records[name] = {'added': added, 'removed': removed, 'binary': binary, 'untracked': name in untracked, 'symlink': path.is_symlink()}
    return records


def plan_body(text):
    text = text.replace('\r\n', '\n')
    match = re.search(r'^## Plan(?:[ \t]+\(sealed[^\n]*\))?[ \t]*\n(.*?)(?=^## |\Z)', text, re.M | re.S)
    return '\n'.join(line.rstrip() for line in match.group(1).replace('\r\n', '\n').strip('\n').split('\n')) if match else ''


def static_checks(root, config, baseline, protected, changed, step, tests, report, research, last_count=0):
    item = step['item']
    result, flags = {}, []
    def add(key, ok, details, blocking=True):
        result[key] = {'passed': bool(ok), 'blocking': blocking, 'details': details}
    add('G1', tests['exit_code'] == 0 and tests['valid'], {'exit_code': tests['exit_code'], 'valid_junit': tests['valid']})
    minimum = max(baseline['passed'], last_count)
    add('G2', tests['passed'] >= minimum, {'passed': tests['passed'], 'minimum': minimum})
    authorized = set(item.get('authorized_test_changes', []))
    missing = sorted(set(baseline['collected']) - set(tests['collected']) - authorized)
    add('G3', not missing, {'missing': missing})
    worse = [node for node, old in baseline['outcomes'].items() if old == 'passed' and tests['outcomes'].get(node) in (None, 'skipped', 'xfailed') and node not in authorized]
    add('G3b', not worse, {'newly_not_executed': worse})
    weakened = [name for name, delta in changed.items() if name.startswith('tests/') and delta['removed']]
    add('G4', True, {'removed_lines_in_existing_tests': weakened}, False)
    if weakened: flags.append('TEST_CHANGED')
    modified = [name for name, sha in protected.items() if hashes(root, [name])[name] != sha]
    allowed = set(item.get('authorized_protected', []))
    add('G5', not (set(modified) - allowed), {'changed': modified, 'unauthorized': sorted(set(modified) - allowed)})
    if modified: flags.append('PROTECTED_CHANGED')
    number = int(step.get('number', step.get('step', 0)))
    forbidden = config['paths'].get('forbidden', [])
    violations = []
    for name, delta in changed.items():
        exception = name.startswith('tests/') or bool(re.fullmatch(r'loop/reports/STEP-' + f'{number:04d}' + r'-[^/]+\.md', name)) or name == f'loop/proposals/STEP-{number:04d}.toml'
        # A test exception allows media fixtures; it never permits symlinks.
        if delta['symlink'] or (any(matches(name, p) for p in forbidden) and not exception): violations.append(name)
    add('G6', not violations, {'forbidden_changes': violations})
    generated = config['paths'].get('generated', [])
    line_count = sum((config['limits']['max_changed_lines'] + 1 if d['binary'] else len(d['added']) + len(d['removed'])) for name, d in changed.items() if not any(matches(name, p) for p in generated))
    add('G7', line_count <= config['limits']['max_changed_lines'], {'changed_lines': line_count, 'maximum': config['limits']['max_changed_lines']})
    secret = re.compile(r'(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|(?:api[_-]?key|password|secret|token)\s*[=:]\s*[\"\x27][A-Za-z0-9_/-]{20,})', re.I)
    secrets, homes, public_homes = [], [], []
    for name, delta in changed.items():
        for line in delta['added']:
            if secret.search(line): secrets.append(name)
            if re.search(r'/Users/[^/\s]+/|/home/[^/\s]+/|[A-Za-z]:\\Users\\', line):
                homes.append(name)
                if name == 'README.md' or name.startswith('docs/'): public_homes.append(name)
    add('G8', not secrets, {'paths': sorted(set(secrets))})
    add('G9', not public_homes, {'paths': sorted(set(homes)), 'blocking_paths': sorted(set(public_homes))})
    if homes: flags.append('HOME_PATH')
    dependencies = [p for p in changed if p in ('pyproject.toml', 'uv.lock', 'requirements.txt', 'requirements.lock', 'setup.py', 'setup.cfg')]
    add('G10', not dependencies or item.get('authorized_dependencies') is True, {'changed': dependencies})
    if dependencies: flags.append('DEPENDENCY_CHANGED')
    body = plan_body(report)
    sealed = step.get('plan_sha256', step.get('sealed_plan_sha256'))
    plan_ok = bool(body) and digest(body.encode()) == sealed
    amendment = re.search(r'^## Plan amendments[^\n]*\n(.*?)(?=^## |\Z)', report, re.M | re.S)
    entries = [line.strip() for line in (amendment.group(1) if amendment else '').splitlines() if line.strip() and line.strip().lower() not in ('none', 'none.', '_none_', 'pending')]
    claim_ids = [claim['id'] for claim in research.get('claims', []) if claim.get('verdict') in ('CONTRADICTED', 'OUTDATED') and claim.get('affects_this_step')]
    invalid = [line for line in entries if not any(re.search(r'(?<![\w-])' + re.escape(cid) + r'(?![\w-])', line) for cid in claim_ids)]
    add('G11', plan_ok and not invalid, {'sealed_plan_matches': plan_ok, 'invalid_amendments': invalid})
    prose = [p for p in changed if p == 'README.md' or p.startswith('docs/')]
    add('G13', True, {'public_prose': prose}, False)
    if prose: flags.append('PUBLIC_PROSE')
    return result, flags


def gate(root, run_dir, harness, step, round, advisory=False):
    root, run_dir, harness = Path(root).resolve(), Path(run_dir).resolve(), Path(harness).resolve()
    config = tomllib.loads((harness / 'config.toml').read_text())
    baseline = json.loads((harness / 'baseline.json').read_text())
    protected = {line.split('  ', 1)[1]: line.split('  ', 1)[0] for line in (harness / 'protected.sha256').read_text().splitlines() if line}
    before = None
    integrity_error = None
    if not advisory:
        try: before = integrity(root, config)
        except Exception as exc: integrity_error = str(exc)
    evidence = None if advisory else run_dir / f'gate_r{round}_logs'
    tests = product_tests(root, evidence, config, baseline, advisory)
    number = int(step.get('number', step.get('step', 0)))
    reports = list((root / 'loop/reports').glob(f'STEP-{number:04d}-*.md'))
    report = reports[0].read_text() if len(reports) == 1 else ''
    research_path = run_dir / 'research.json'
    research = json.loads(research_path.read_text()) if research_path.exists() else {}
    state_path = harness / 'state.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    changed = changes(root, step.get('base_commit', step.get('base')))
    checks, flags = static_checks(root, config, baseline, protected, changed, step, tests, report, research, state.get('last_integrated_test_count', 0))
    extras = []
    # Execute frozen tests, import frozen loopctl: builder changes cannot replace the judge.
    env = command_env(root, config)
    env['PYTHONPATH'] = str(harness)
    unittest_argv = argv_for(['{python}', '-m', 'unittest', 'discover', '-s', str(harness / 'tests'), '-p', 'test_*.py'], root, config)
    extra = execute(unittest_argv, harness, env=env)
    if re.search(r'Ran 0 tests\b', extra['stderr'] + extra['stdout']):
        extra['exit_code'] = 1
    extras.append({'name': 'frozen_loop_tests', **extra})
    extras.append({'name': 'approval', **approval_check(root, config, baseline, advisory)})
    for index, command in enumerate(config.get('commands', {}).get('linters', [])):
        extras.append({'name': f'linter_{index}', **run_command(command, root, config, baseline, advisory)})
    checks['G12'] = {'passed': all(x['exit_code'] == 0 for x in extras), 'blocking': True, 'details': [{'name': x['name'], 'exit_code': x['exit_code']} for x in extras]}
    if advisory:
        checks['G14'] = {'passed': True, 'blocking': False, 'details': {'skipped': 'advisory'}}
    else:
        after = None
        try: after = integrity(root, config)
        except Exception as exc: integrity_error = str(exc)
        checks['G14'] = {'passed': before is not None and before == after and not integrity_error, 'blocking': True, 'details': {'before': before, 'after': after, 'error': integrity_error}}
    result = {'step': number, 'round': round, 'passed': all(v['passed'] for v in checks.values() if v['blocking']), 'gates': checks,
              'flags': flags, 'tests': tests, 'changed_files': sorted(changed), 'sandbox': {'available': baseline['sandbox']['available'], 'reason': baseline['sandbox'].get('reason')},
              'invariant_violations': [key for key in ('G6', 'G14') if not checks[key]['passed']]}
    if not advisory:
        for index, extra in enumerate(extras): write_json(evidence / f'extra-{index}.json', extra)
        write_json(run_dir / f'gate_r{round}.json', result)
    return result
