#!/usr/bin/env python3
"""Deterministic build-loop control. Git queries/export only; run.py owns history."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tomllib

DIMS = ('relevance', 'intention', 'relation', 'production_quality', 'accuracy', 'scope')
SECTIONS = ('Plan', 'Probes', 'Changes', 'Deterministic gate', 'Independent evaluation, round 1',
            'Research', 'Plan amendments', 'Enhancements', 'Independent evaluation, round 2',
            'Self-evaluation', 'Calibration', 'Flags for Sphoenix', 'Proposals filed', 'Next')


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path, default=None):
    return json.loads(Path(path).read_text()) if Path(path).exists() else default


def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')
    tmp.replace(path)


def digest(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode()).hexdigest()


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def validate(value, schema, at='$'):
    """Validate the small, closed JSON Schema subset used by the role contracts."""
    if 'anyOf' in schema:
        for option in schema['anyOf']:
            try:
                validate(value, option, at); return
            except ValueError:
                pass
        raise ValueError(f'{at}: no allowed type')
    kind = schema.get('type')
    checks = {'object': lambda: isinstance(value, dict), 'array': lambda: isinstance(value, list),
              'string': lambda: isinstance(value, str), 'integer': lambda: type(value) is int,
              'boolean': lambda: type(value) is bool, 'null': lambda: value is None,
              'number': lambda: type(value) in (int, float)}
    if kind in checks and not checks[kind]():
        raise ValueError(f'{at}: expected {kind}')
    if 'enum' in schema and value not in schema['enum']:
        raise ValueError(f'{at}: invalid enum')
    if kind == 'object':
        missing = set(schema.get('required', [])) - value.keys()
        extra = value.keys() - schema.get('properties', {}).keys()
        if missing or (schema.get('additionalProperties') is False and extra):
            raise ValueError(f'{at}: missing {sorted(missing)} / extra {sorted(extra)}')
        for k, v in value.items():
            if k in schema.get('properties', {}): validate(v, schema['properties'][k], f'{at}.{k}')
    if kind == 'array':
        for i, v in enumerate(value): validate(v, schema['items'], f'{at}[{i}]')


def body(text, heading):
    match = re.search(r'^## ' + re.escape(heading) + r'(?:[ \t]+\([^\n]*\))?[ \t]*\n(.*?)(?=^## |\Z)', text, re.M | re.S)
    return '\n'.join(line.rstrip() for line in match.group(1).replace('\r\n', '\n').splitlines()).strip('\n') + '\n' if match else ''


def replace_section(text, heading, content):
    pattern = r'(^## ' + re.escape(heading) + r'(?:[ \t]+\([^\n]*\))?[ \t]*\n).*?(?=^## |\Z)'
    return re.sub(pattern, lambda m: m.group(1) + '\n' + content.rstrip() + '\n\n', text, flags=re.M | re.S)


def items(root):
    return tomllib.loads((root / 'loop/backlog.toml').read_text()).get('item', [])


def next_item(backlog, state):
    statuses = state.get('items', {})
    def done(key, seen=()):
        if key in seen: return False
        row = statuses.get(key, {})
        if isinstance(row, str): row = {'status': row}
        if row.get('status') == 'DONE': return True
        return row.get('status') == 'SPLIT' and bool(row.get('children')) and all(done(c, (*seen,key)) for c in row['children'])
    eligible = []
    for order, item in enumerate(backlog):
        row = statuses.get(item['id'], {})
        if isinstance(row, str): row = {'status': row}
        if item['approval'] in ('APPROVED', 'AUTO_APPROVED') and row.get('status') not in ('DONE','BLOCKED','SPLIT') and all(done(d) for d in item.get('depends_on', [])):
            eligible.append((item['priority'], order, item))
    eligible.sort(key=lambda row: row[:2])
    previous = state.get('steps', [])[-1:]
    if len(eligible) > 1 and previous and previous[0]['decision'] == 'REVERT':
        others = [r for r in eligible if r[2]['id'] != previous[0]['item']]
        if others: eligible = others
    return eligible[0][2] if eligible else None


def auto_approval(proposal, source, step, state, claims, terms):
    recent = any(s.get('auto_approved') for s in state.get('steps', []) if step - 3 <= s['step'] < step)
    docs_ok = proposal.get('category') != 'docs' or any(c['id'] == proposal.get('claim_id') and c['verdict'] == 'CONTRADICTED' for c in claims)
    text = (proposal.get('title','') + ' ' + proposal.get('rationale','')).lower()
    return source == 'researcher' and proposal.get('size') == 'S' and proposal.get('risk') == 'LOW' and proposal.get('category') in ('test','validation','bugfix','docs') and proposal.get('relevance',0) >= 3 and docs_ok and not recent and not any(t.lower() in text for t in terms)


def decision(evaluation, gate, all_gates, research, enhancement, failure, expected_hash, prior=None):
    findings = evaluation.get('blocking_findings', [])
    scores = [v['score'] for v in evaluation.get('scores', {}).values()]
    invariant_zero = 0 in scores and any(re.fullmatch(r'I(?:[1-9]|1[0-6])', f.get('invariant') or '') for f in findings)
    breach = any(any(not g.get('gates',{}).get(k, {'passed':True})['passed'] for k in ('G6','G14')) for g in all_gates)
    if invariant_zero or breach: rule = 'R0'
    elif failure: rule = 'RF'
    elif not gate.get('passed', False): rule = 'R1'
    elif not scores or any(s <= 1 for s in scores): rule = 'R2'
    elif 2 in scores: rule = 'R3'
    else:
        resolutions = {r['ref']: r for r in enhancement.get('resolutions', [])}
        required = {f['id'] for f in findings}
        required |= {c['id'] for c in research.get('claims', []) if c['affects_this_step'] and (c['verdict'] != 'CONFIRMED' or c.get('newer_practice'))}
        prior_status = {p['ref']: p['status'] for p in evaluation.get('prior_findings', [])}
        unresolved = any(s == 'UNRESOLVED' for s in prior_status.values())
        if prior is not None:
            required |= {f['id'] for f in prior.get('blocking_findings', [])}
            unresolved |= any(f['id'] not in prior_status for f in prior.get('blocking_findings', []))
        if unresolved or required - resolutions.keys(): rule = 'R4'
        elif evaluation.get('diff_sha256') != expected_hash: rule = 'R5'
        else: rule = 'R6'
    return {'decision': 'INTEGRATE' if rule == 'R6' else 'REVERT', 'rule': rule, 'stop': rule == 'R0'}


class Control:
    def __init__(self, root, runs=None):
        self.root = Path(root).resolve()
        self.harness = Path(__file__).resolve().parent
        self.config = tomllib.loads((self.harness / 'config.toml').read_text())
        self.runs = Path(runs).resolve() if runs else (self.root / self.config['paths']['runs_dir']).resolve()

    def state(self):
        return read(self.root / 'loop/state.json', {'items': {}, 'steps': []})

    def path(self, n):
        return self.runs / f'{int(n):04d}'

    def step(self, n):
        return read(self.path(n) / 'step.json')

    def status(self):
        state = self.state(); candidate = next_item(items(self.root), state)
        return {'current': read(self.runs / 'current.json'), 'lock': read(self.runs / 'lock.json'),
                'next': candidate['id'] if candidate else 'NONE', 'counts': dict(Counter(v.get('status','PENDING') if isinstance(v,dict) else v for v in state['items'].values()))}

    def start(self, item_id):
        self.runs.mkdir(parents=True, exist_ok=True)
        n = max([int(p.name) for p in self.runs.iterdir() if p.is_dir() and p.name.isdigit()] + [0]) + 1
        state = self.state(); backlog = items(self.root)
        eligible = next_item(backlog, state)
        if eligible is None or eligible['id'] != item_id: raise ValueError('item is not the next eligible item')
        lock = {'step': n, 'pid': int(os.environ.get('LOOP_RUNNER_PID', os.getppid())), 'host': socket.gethostname(), 'start': now(), 'heartbeat': now()}
        # Exclusive creation prevents two orchestrators from owning one step.
        with (self.runs / 'lock.json').open('x') as stream: json.dump(lock, stream)
        run = self.path(n); run.mkdir()
        base = git(self.root, 'rev-parse', 'HEAD')
        report = f'loop/reports/STEP-{n:04d}-{item_id}.md'
        step = {'step': n, 'number': n, 'item': eligible, 'base_commit': base, 'started_at': now(), 'report': report,
                'state_before': state, 'backlog_before': (self.root/'loop/backlog.toml').read_text()}
        write(run/'step.json',step); write(self.runs/'current.json',{'step': n,'item':item_id})
        for name in git(self.root,'ls-tree','-r','--name-only',base,'loop').splitlines():
            relative = name.removeprefix('loop/')
            if relative in ('loopctl.py','run.py','gates.py','config.toml','RUBRIC.md','INVARIANTS.md','NORTH_STAR.md','baseline.json','baseline_tests.txt','protected.sha256','state.json') or relative.startswith(('schemas/','prompts/','tests/')):
                target=run/'harness'/relative; target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(subprocess.check_output(['git','-C',str(self.root),'show',f'{base}:{name}']))
        content = f'# Step {n:04d} · {item_id} · {eligible["title"]}\n\nDecision: pending\n\n' + ''.join(f'## {s}\n\n' for s in SECTIONS)
        target=self.root/report; target.parent.mkdir(parents=True,exist_ok=True); target.write_text(content)
        (run/'report.md').write_text(content)
        return {'step':n,'item':item_id,'base_commit':base,'report':report}

    def seal(self,n):
        step=self.step(n); text=(self.root/step['report']).read_text(); plan=body(text,'Plan')
        if not plan.strip(): raise ValueError('Plan is empty')
        if any(c not in plan for c in step['item']['acceptance']): raise ValueError('Plan omitted a verbatim acceptance criterion')
        from gates import plan_body
        plan=plan_body(text)
        step['plan_sha256']=digest(plan); step['plan']=plan
        write(self.path(n)/'step.json',step); (self.path(n)/'report.md').write_text(text)
        return {'plan_sha256':step['plan_sha256']}

    def split(self,n):
        step=self.step(n); path=self.root/f'loop/reports/STEP-{n:04d}-split.toml'
        data=tomllib.loads(path.read_text()); children=data.get('item',data.get('subitems',[]))
        if not children or any(not c.get('acceptance') for c in children): raise ValueError('split requires nonempty criteria per child')
        if Counter(c for item in children for c in item['acceptance']) != Counter(step['item']['acceptance']): raise ValueError('split must exactly partition criteria')
        ids=[c['id'] for c in children]
        if len(set(ids))!=len(ids) or any(k in {i['id'] for i in items(self.root)} for k in ids): raise ValueError('split ids must be new and unique')
        for c in children:
            if not re.fullmatch(r'[A-Za-z0-9_-]+',c['id']): raise ValueError('invalid split id')
        normalized=[]
        for c in children:
            child=dict(step['item']); child.update({k:c[k] for k in ('id','title','acceptance')}); child['size']=c.get('size','S'); child['parent']=step['item']['id']; normalized.append(child)
        write(self.path(n)/'split.json',normalized)
        write(self.path(n)/'decision.json',{'decision':'SPLIT','rule':'SPLIT','stop':False})
        (self.path(n)/'report.md').write_text((self.root/step['report']).read_text())
        return {'decision':'SPLIT','children':ids}

    def export(self,n,r):
        run=self.path(n); step=self.step(n); target=run/f'eval_view_r{r}'
        if target.exists(): shutil.rmtree(target)
        (target/'tree').mkdir(parents=True)
        subprocess.run(['git','-C',str(self.root),'checkout-index','-a',f'--prefix={target / "tree"}/'],check=True)
        diff=subprocess.check_output(['git','-C',str(self.root),'diff','--binary',step['base_commit'],'--'])
        (target/'diff.patch').write_bytes(diff); (target/'diff_sha256.txt').write_text(digest(diff)+'\n')
        (target/'plan.md').write_text(step['plan']); write(target/'item.json',step['item'])
        shutil.copy2(run/f'gate_r{r}.json',target/'gate.json')
        for name in ('RUBRIC.md','INVARIANTS.md'): shutil.copy2(run/'harness'/name,target/name)
        if r==2:
            for name in ('eval_r1.json','enhancement.json'): shutil.copy2(run/name,target/name)
        write(run/f'export_r{r}.json',{'diff_sha256':digest(diff)})
        return {'view':str(target),'diff_sha256':digest(diff)}

    def research_view(self,n):
        run=self.path(n); step=self.step(n); ev=self.role(n,'eval_r1.json','evaluation')
        claims=[{'id':m[0],'claim':m[1],'location':'sealed plan','origin':'plan'} for m in re.findall(r'^CLAIM ([\w.-]+):\s*(.+)$',step['plan'],re.M)]
        for c in ev['claims_for_research']: claims.append({**c,'origin':'evaluator'})
        if len({c['id'] for c in claims})!=len(claims): raise ValueError('research claim ids must be unique')
        view=run/'research_view'; view.mkdir(exist_ok=True)
        write(view/'claims.json',{'step':n,'item':step['item']['id'],'claims':claims,'landscape_required':n%5==0})
        ledger=self.root/'loop/research/ledger.jsonl'
        relevant=[]
        if ledger.exists():
            for line in ledger.read_text().splitlines():
                row=json.loads(line)
                if any(c['claim']==row.get('claim') for c in claims): relevant.append(row)
        (view/'ledger.jsonl').write_text(''.join(json.dumps(c)+'\n' for c in relevant))
        return {'view':str(view),'claims':len(claims),'landscape_required':n%5==0}

    def role(self,n,name,kind):
        value=read(self.path(n)/name)
        validate(value,read(self.path(n)/'harness/schemas'/f'{kind}.schema.json'))
        if kind!='enhancement':
            if value['step']!=n or value['item']!=self.step(n)['item']['id']: raise ValueError('role output identity mismatch')
        if kind=='research':
            if len({c['id'] for c in value['claims']}) != len(value['claims']): raise ValueError('duplicate research claim')
            requested=read(self.path(n)/'research_view/claims.json',{}).get('claims',[])
            if {c['id'] for c in requested}!={c['id'] for c in value['claims']}: raise ValueError('research coverage mismatch')
            for claim in value['claims']:
                if claim['verdict']!='UNVERIFIABLE' and not claim['sources']: raise ValueError('research verdict lacks primary-source evidence')
                for source in claim['sources']:
                    if not all(source.values()) or not source['url'].startswith('https://'): raise ValueError('research source attribution is incomplete')
        if kind=='evaluation':
            expected_role='builder' if name=='self_eval.json' else 'evaluator'
            expected_round=2 if name=='eval_r2.json' else 1
            if value['role']!=expected_role or value['round']!=expected_round: raise ValueError('role or round mismatch')
            if expected_role=='builder' and value['diff_sha256']!='self': raise ValueError('self evaluation identity mismatch')
        return value

    def optional_role(self,n,name,kind):
        try: return self.role(n,name,kind)
        except (ValueError,TypeError,KeyError,OSError): return {}

    def report(self,n,r,final=False):
        run=self.path(n); step=self.step(n); path=self.root/step['report']
        text=path.read_text() if path.exists() else (run/'report.md').read_text()
        def table(headers, rows):
            def cell(v): return str(v).replace('|','\\|').replace('\n','<br>')
            return ' | '.join(headers)+'\n'+' | '.join('---' for _ in headers)+'\n'+'\n'.join(' | '.join(cell(v) for v in row) for row in rows)
        gate=read(run/f'gate_r{r}.json',{})
        if gate:
            text=replace_section(text,'Deterministic gate',table(['Check','Passed','Blocking','Evidence'],[(k,v['passed'],v['blocking'],json.dumps(v['details'],sort_keys=True)) for k,v in gate['gates'].items()]))
            base=read(run/'harness/baseline.json',{})
            changed=gate.get('changed_files',[])
            count=gate.get('gates',{}).get('G7',{}).get('details',{}).get('changed_lines','unknown')
            text=replace_section(text,'Changes',f'Files: {", ".join(changed) or "none"}. Changed lines outside generated paths: {count}. Product tests passed: {gate.get("tests",{}).get("passed","unknown")}; baseline: {base.get("passed","unknown")}.')
        for number in (1,2):
            ev=self.optional_role(n,f'eval_r{number}.json','evaluation')
            if ev:
                content=table(['Dimension','Score','Evidence'],[(d,ev['scores'][d]['score'],'; '.join(ev['scores'][d]['evidence'])) for d in DIMS])
                content+='\n\nBlocking findings:\n'+('\n'.join('- '+f['id']+': '+f['description']+' ('+f['location']+'); required: '+f['required_fix'] for f in ev['blocking_findings']) or 'None.')
                content+='\n\nLoophole audit:\n'+table(['Criterion','Lazy pass','Present','Evidence'],[(a['criterion'],a['lazy_pass'],a['present_in_diff'],a['evidence']) for a in ev['loophole_audit']])
                if number==2: content+='\n\n'+table(['Prior finding','Status'],[(f['ref'],f['status']) for f in ev['prior_findings']])
                text=replace_section(text,f'Independent evaluation, round {number}',content)
        research=self.optional_role(n,'research.json','research')
        if research:
            content=research['summary']+'\n\n'+table(['ID','Claim','Verdict','Sources (accessed)','Newer practice','Affects step'],[(c['id'],c['claim'],c['verdict'],'; '.join(f"[{x['title']}]({x['url']}) ({x['accessed']})" for x in c['sources']),json.dumps(c['newer_practice']),c['affects_this_step']) for c in research['claims']])
            text=replace_section(text,'Research',content)
        enhancement=self.optional_role(n,'enhancement.json','enhancement')
        if enhancement:
            text=replace_section(text,'Enhancements',table(['Reference','Action','Evidence'],[(e['ref'],e['action'],e['evidence']) for e in enhancement['resolutions']]))
        if final:
            own=self.optional_role(n,'self_eval.json','evaluation'); independent=self.optional_role(n,'eval_r1.json','evaluation')
            content=table(['Dimension','Score','Evidence'],[(d,own['scores'][d]['score'],'; '.join(own['scores'][d]['evidence'])) for d in DIMS]) if own else 'Unavailable; no score inferred. Raw role output remains in the external evidence directory.'
            text=replace_section(text,'Self-evaluation',content)
            calibration=read(run/'calibration.json',{})
            text=replace_section(text,'Calibration',table(['Dimension','Self','Independent round 1','Gap'],[(d,own['scores'][d]['score'],independent['scores'][d]['score'],calibration[d]) for d in calibration]) if calibration else 'Unavailable; no gap inferred.')
            dec=read(run/'decision.json'); minutes=(datetime.now(timezone.utc)-datetime.fromisoformat(step['started_at'])).total_seconds()/60
            text=re.sub(r'^Decision:.*$',f'Decision: {dec["decision"]} (rule {dec["rule"]}) · rounds {r} · base {step["base_commit"]} → enclosing step commit · {minutes:.2f} min',text,flags=re.M)
            baseline=read(run/'harness/baseline.json',{}); tools=baseline.get('tools',{}); ff=tools.get('doctor',{}).get('tools',{}).get('ffmpeg',{}).get('executable_sha256','unknown')
            models='; '.join(f"{m['role']} r{m['round']}: {m['model']}" for m in read(run/'role_metadata.json',{}).get('calls',[])) or 'unknown'
            tool_line=f'Tools: python {tools.get("python","unknown")} · ffmpeg {ff} · codex {tools.get("codex","unknown")} · models: {models}'
            if re.search(r'^Tools:',text,re.M): text=re.sub(r'^Tools:.*$',tool_line,text,flags=re.M)
            else: text=text.replace('\n## Plan', '\n'+tool_line+'\n\n## Plan',1)
            flags=read(run/'summary.json',{}).get('flags',[])
            text=replace_section(text,'Flags for Sphoenix','\n'.join('- '+f for f in flags) or 'None.')
            text=replace_section(text,'Proposals filed','; '.join(i['id']+': '+i['title'] for i in items(self.root) if i['id'].startswith(f'P{n:04d}-')) or 'None.')
            candidate=next_item(items(self.root),self.state())
            text=replace_section(text,'Next',candidate['id']+': '+candidate['title'] if candidate else 'No eligible item.')
        path.parent.mkdir(parents=True,exist_ok=True); path.write_text(text); (run/'report.md').write_text(text)
        return {'report':step['report']}

    def decide(self,n):
        run=self.path(n); r=2 if (run/'eval_r2.json').exists() else 1
        proposal=self.root/f'loop/proposals/STEP-{n:04d}.toml'
        if proposal.exists(): shutil.copy2(proposal,run/'proposals.toml')
        failure=read(run/'failure.json'); evaluation={}; research={}; enhancement={}; prior=None
        try:
            if not failure:
                evaluation=self.role(n,f'eval_r{r}.json','evaluation'); self.role(n,'self_eval.json','evaluation')
                research=self.role(n,'research.json','research')
                if (run/'enhancement.json').exists(): enhancement=self.role(n,'enhancement.json','enhancement')
                if r==2: prior=self.role(n,'eval_r1.json','evaluation')
                input_claims=read(run/'research_view/claims.json',{}).get('claims',[])
                if {c['id'] for c in input_claims} != {c['id'] for c in research['claims']}: raise ValueError('research did not cover all and only requested claims')
                if len({c['id'] for c in research['claims']}) != len(research['claims']): raise ValueError('duplicate research claim')
                for claim in research['claims']:
                    if claim['verdict']!='UNVERIFIABLE' and not claim['sources']: raise ValueError('research verdict lacks primary-source evidence')
                    for source in claim['sources']:
                        if not all(source.values()) or not source['url'].startswith('https://'): raise ValueError('research source attribution is incomplete')
        except (ValueError,TypeError,KeyError) as exc:
            failure={'rule':'RF','role':'contract','error':str(exc)}; write(run/'failure.json',failure)
        gates=[read(p) for p in sorted(run.glob('gate_r*.json'))]
        result=decision(evaluation,read(run/f'gate_r{r}.json',{}),gates,research,enhancement,failure,read(run/f'export_r{r}.json',{}).get('diff_sha256'),prior)
        result['rounds']=r; write(run/'decision.json',result)
        path=self.root/self.step(n)['report']
        if path.exists(): (run/'report.md').write_text(path.read_text())
        return result

    def finish(self,n):
        run=self.path(n); step=self.step(n); dec=read(run/'decision.json')
        if not dec: raise ValueError('finish requires a decision')
        state=step['state_before']; item=step['item']; row=state.setdefault('items',{}).setdefault(item['id'],{'status':'PENDING','retries':0})
        if isinstance(row,str): row=state['items'][item['id']]={'status':row,'retries':0}
        if dec['decision']=='INTEGRATE': row['status']='DONE'
        elif dec['decision']=='SPLIT': row.update(status='SPLIT',children=[c['id'] for c in read(run/'split.json')])
        elif dec['decision']=='REVERT' and dec['rule']!='RF':
            row['retries']=row.get('retries',0)+1; row['status']='BLOCKED' if row['retries']>=self.config['limits']['max_retries_per_item'] else 'PENDING'
        rounds=dec.get('rounds',2 if (run/'eval_r2.json').exists() else 1)
        gate=read(run/f'gate_r{rounds}.json',{}); ev=self.optional_role(n,f'eval_r{rounds}.json','evaluation'); ev1=self.optional_role(n,'eval_r1.json','evaluation'); own=self.optional_role(n,'self_eval.json','evaluation')
        calibration={d:own['scores'][d]['score']-ev1['scores'][d]['score'] for d in DIMS} if own.get('scores') and ev1.get('scores') else {}
        write(run/'calibration.json',calibration)
        research=self.optional_role(n,'research.json','research')
        flags=sorted(set(gate.get('flags',[])+ev.get('flags',[])))
        summary={'step':n,'item':item['id'],'decision':dec['decision'],'rule':dec['rule'],'rounds':rounds,'scores':{d:v['score'] for d,v in ev.get('scores',{}).items()},'passed':gate.get('tests',{}).get('passed',0),'gate':gate.get('passed',False),'flags':flags,'calibration':calibration,'research':dict(Counter(c['verdict'] for c in research.get('claims',[]))),'auto_approved':[]}
        if dec['decision']=='INTEGRATE': state['last_integrated_test_count']=summary['passed']
        backlog_text=step['backlog_before']
        for child in read(run/'split.json',[]): backlog_text+='\n'+toml_item(child)
        proposals=[(p,'researcher') for p in research.get('proposals',[])]
        proposal_path=self.root/f'loop/proposals/STEP-{n:04d}.toml'
        saved=run/'proposals.toml'
        if proposal_path.exists(): shutil.copy2(proposal_path,saved)
        if saved.exists(): proposals += [(p,'enhancer') for p in tomllib.loads(saved.read_text()).get('proposal',[])]
        terms=self.config['paths'].get('deferred_terms',[])
        for i,(p,source) in enumerate(proposals):
            approved=auto_approval(p,source,n,state,research.get('claims',[]),terms)
            if summary['auto_approved']: approved=False
            pid=f'P{n:04d}-{i+1}'
            candidate={'id':pid,'title':p['title'],'rationale':p['rationale'],'priority':'P2','approval':'AUTO_APPROVED' if approved else 'PROPOSED','size':p['size'],'risk':p['risk'],'category':p['category'],'depends_on':[],'human_review':True,'authorized_protected':[],'authorized_test_changes':[],'authorized_dependencies':False,'probes':[],'acceptance':p.get('acceptance',[p['rationale']])}
            backlog_text+='\n'+toml_item(candidate)
            if approved: summary['auto_approved'].append(pid)
        (self.root/'loop/backlog.toml').write_text(backlog_text)
        state.setdefault('steps',[]).append(summary); write(self.root/'loop/state.json',state); write(run/'summary.json',summary)
        # Restore the external report after a reset before filling final sections.
        report=self.root/step['report']; report.parent.mkdir(parents=True,exist_ok=True); report.write_text((run/'report.md').read_text())
        self.report(n,rounds,final=True)
        evidence=self.root/f'loop/reports/STEP-{n:04d}'; evidence.mkdir(exist_ok=True)
        for p in run.glob('*.json'):
            if p.name not in ('step.json',): shutil.copy2(p,evidence/p.name)
        ledger=self.root/'loop/research/ledger.jsonl'; ledger.parent.mkdir(parents=True,exist_ok=True)
        existing=[json.loads(l) for l in ledger.read_text().splitlines()] if ledger.exists() else []
        existing=[c for c in existing if c.get('loop_step')!=n]
        existing.extend({**c,'loop_step':n} for c in research.get('claims',[]))
        ledger.write_text(''.join(json.dumps(c,sort_keys=True)+'\n' for c in existing))
        if n%5==0:
            (self.root/'loop/research/landscape.md').write_text(f'# Landscape scan · step {n}\n\n'+research.get('summary','No research result available.')+'\n')
        self.packet()
        lock=read(self.runs/'lock.json',{})
        if lock.get('step')==n: (self.runs/'lock.json').unlink()
        write(self.runs/'current.json',{'step':n,'item':item['id'],'finished':True,'decision':dec['decision']})
        return summary

    def abort(self):
        lock=read(self.runs/'lock.json')
        if not lock: return {'reset_required':False}
        if lock.get('host')!=socket.gethostname(): raise ValueError('lock belongs to another host; cannot prove dead')
        try: os.kill(lock['pid'],0)
        except ProcessLookupError: pass
        except PermissionError: raise ValueError('lock pid exists but is not accessible')
        else: raise ValueError('lock owner is still running')
        step=self.step(lock['step']); path=self.root/step['report']
        if path.exists(): (self.path(lock['step'])/'report.md').write_text(path.read_text())
        write(self.path(lock['step'])/'decision.json',{'decision':'ABANDONED','rule':'ABANDONED','stop':False})
        return {'reset_required':True,'base_commit':step['base_commit'],'step':lock['step']}

    def packet(self, reason=None):
        state=self.state(); rows=[]
        for s in state.get('steps',[]):
            scores=' '.join(str(s.get('scores',{}).get(d,'?')) for d in DIMS)
            research='/'.join(str(s.get('research',{}).get(k,0)) for k in ('CONFIRMED','CONTRADICTED','OUTDATED','UNVERIFIABLE'))
            rows.append(f'{s["step"]:04d} | {s["item"]} | {s["decision"]} | {scores} | {s.get("passed",0)} | {s.get("gate",False)} | {research} | {", ".join(s.get("flags",[]))}')
        header='step | item | decision | Rv In Rl PQ Ac Sc | passed tests | gate | research C/X/O/U | flags\n--- | --- | --- | --- | --- | --- | --- | ---\n'
        reports=self.root/'loop/reports'; reports.mkdir(parents=True,exist_ok=True)
        (reports/'INDEX.md').write_text('# Step index\n\n'+header+'\n'.join(rows)+'\n')
        steps=state.get('steps',[]); flags=sorted({f for s in steps for f in s.get('flags',[])})
        proposals=[i['id']+': '+i['title'] for i in items(self.root) if i['approval']=='PROPOSED']
        recent=[v for s in steps[-5:] for v in s.get('calibration',{}).values()]
        over=sum(recent)/len(recent) if recent else None
        text='# Review packet\n\n'+header+'\n'.join(rows[-5:])+'\n\n'
        text+='Open flags: '+(', '.join(flags) or 'none')+'\n\nProposals awaiting approval: '+('; '.join(proposals) or 'none')+'\n\n'
        ledger=self.root/'loop/research/ledger.jsonl'
        unresolved=[c['id'] for c in (json.loads(l) for l in ledger.read_text().splitlines()) if c['verdict']=='CONTRADICTED'] if ledger.exists() else []
        text+='Contradictions for review: '+(', '.join(unresolved) or 'none')+'\n\n'
        text+=f'Calibration gaps: {json.dumps([s.get("calibration",{}) for s in steps[-5:]])}. Mean self-minus-independent: {over}.\n\n'
        if over is not None and over>1: text+='Flag: builder mean overconfidence exceeds 1.0.\n\n'
        text+=f'Revert rate: {sum(s["decision"]=="REVERT" for s in steps)}/{len(steps)} steps.\n\n'
        if reason: text+='Stop reason: '+reason+'\n\n'
        text+='- Which integrated change most likely violates an invariant?\n- Which research verdict is weakest?\n- What should be deferred?\n'
        (reports/'PACKET-latest.md').write_text(text)
        return {'packet':'loop/reports/PACKET-latest.md','steps':len(steps),'stop_reason':reason}


def toml_item(item):
    return '[[item]]\n'+'\n'.join(k+' = '+json.dumps(v,ensure_ascii=False) for k,v in item.items() if v is not None)+'\n'


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',default=str(Path.cwd())); parser.add_argument('--runs')
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('bootstrap','status','next','start','split','seal-plan','gate','export','research-view','report','decide','finish','abort-step','packet'):
        p=sub.add_parser(name)
        if name=='bootstrap': p.add_argument('--rebaseline',action='store_true')
        if name=='start': p.add_argument('--item',required=True)
        if name in ('split','seal-plan','gate','export','research-view','report','decide','finish'): p.add_argument('--step',type=int,required=name!='gate')
        if name in ('gate','export','report'): p.add_argument('--round',type=int,default=1)
        if name=='gate': p.add_argument('--advisory',action='store_true')
        if name=='packet': p.add_argument('--reason')
    args=parser.parse_args(argv)
    try:
        ctl=Control(args.root,args.runs); cmd=args.command; failed=False
        if cmd=='bootstrap':
            import gates
            if (ctl.root/'loop/baseline.json').exists() and not args.rebaseline: raise ValueError('baseline exists; use --rebaseline')
            result=gates.bootstrap(ctl.root,ctl.runs,ctl.config)
        elif cmd=='status': result=ctl.status()
        elif cmd=='next':
            item=next_item(items(ctl.root),ctl.state()); result=item if item else 'NONE'
        elif cmd=='start': result=ctl.start(args.item)
        elif cmd=='seal-plan': result=ctl.seal(args.step)
        elif cmd=='split': result=ctl.split(args.step)
        elif cmd=='gate':
            import gates
            n=args.step or read(ctl.runs/'current.json',{}).get('step')
            if n is None: raise ValueError('gate needs --step')
            result=gates.gate(ctl.root,ctl.path(n),ctl.harness,ctl.step(n),args.round,args.advisory); failed=not result['passed']
        elif cmd=='export': result=ctl.export(args.step,args.round)
        elif cmd=='research-view': result=ctl.research_view(args.step)
        elif cmd=='report': result=ctl.report(args.step,args.round)
        elif cmd=='decide': result=ctl.decide(args.step)
        elif cmd=='finish': result=ctl.finish(args.step)
        elif cmd=='abort-step': result=ctl.abort()
        else: result=ctl.packet(args.reason)
        print(json.dumps(result,indent=2)); return int(failed)
    except (ValueError,OSError,KeyError,TypeError,subprocess.CalledProcessError) as exc:
        print(json.dumps({'error':str(exc),'command':args.command}),file=sys.stderr); return 1

if __name__=='__main__': raise SystemExit(main())
