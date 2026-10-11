"""TEST-ONLY resolution oracles; no real clips or human judgments."""
from types import SimpleNamespace
import pytest
from pydantic import ValidationError
from eval_lab import domain as d, generation as g, test_plans as tp, evidence_roles as er
from eval_lab import resolutions as rs
from eval_lab.persistence import Repository
from eval_lab.pilot_domain import PilotClip
from test_competing_sets import seed, competing
from test_intent_v2 import anchors
from test_test_plans import form
from test_evidence_roles import at
from test_generation import PLAN


@pytest.fixture
def build(tmp_path, monkeypatch):
    repo = Repository('sqlite:///' + str(tmp_path / 'pilot.sqlite'))
    def make(counts=(2, 2), design='fixed', exhaustive=True, predictions=None, frozen=True, e=30, registered=25, h=(10, 12), generated=False):
        original = seed(repo)
        hs = tuple(h.model_copy(update=dict(id=name, created_at=at(t))) for h, name, t in
            zip(original, ('TEST-ONLY-alpha', 'TEST-ONLY-beta'), h))
        for h in hs: repo.put(h)
        group = competing(tuple(reversed(hs)), exhaustive=exhaustive); repo.put(group)
        arms = [dict(id=name, description='TEST-ONLY ' + name, generation_plan_ref=None)
            for name in ('TEST-ONLY-left', 'TEST-ONLY-right')]
        gp = g.record_plan(repo, PLAN | {'id': 'TEST-ONLY-generation'}) if generated else None
        if gp: arms[0]['generation_plan_ref'] = g.pin(gp)
        sample = None if design is None else dict(decision_rule='TEST-ONLY compare declared outcomes',
            **(dict(n_per_arm=2) if design == 'fixed' else dict(stopping_rule='TEST-ONLY stop after inspection')))
        draft = tp.TestPlan(**form(group, arms=arms, sample_design=sample,
            predictions=predictions or {'TEST-ONLY-alpha': ['TEST-ONLY-X'], 'TEST-ONLY-beta': ['TEST-ONLY-Y']}))
        repo.put(draft); monkeypatch.setattr(tp, 'now', lambda: at(20))
        plan = tp.freeze(repo, 'TEST-ONLY-plan@1') if frozen else draft
        samples, links, clips = [], [], []
        for arm, n in zip(arms, counts):
            for j in range(n):
                index = len(samples) + 1; name = f'TEST-ONLY-sample-{index}'
                media, registration = anchors(repo, name, f'{index:064x}', at(registered))
                clip = PilotClip(id=name, media=media.ref, ingestion=registration.ref,
                    selected_by='TEST-ONLY selector', label='TEST-ONLY source'); repo.put(clip)
                evidence = d.Evidence(id=name, created_at=at(e), media=media.ref, source='synthetic_fixture',
                    observation='TEST-ONLY result ' + str(index), method='TEST-ONLY frame', coverage='sampled_frames',
                    sampling_manifest=(.2,), author='TEST-ONLY viewer', independence_group=name); repo.put(evidence)
                link = er.EvidenceArm(id=name, author='TEST-ONLY linker', evidence=g.pin(evidence), plan=g.pin(plan),
                    arm=arm['id'], clip=g.pin(clip), origin=g.pin(g.record_origin(repo, clip, gp)) if gp and arm['generation_plan_ref'] else None); repo.put(link)
                samples.append(dict(arm=arm['id'], evidence=g.pin(evidence))); links.append(link); clips.append(clip)
        data = dict(id='TEST-ONLY-resolution', author='TEST-ONLY resolver', plan=g.pin(plan), outcome='TEST-ONLY-X',
            evidence=samples, decision_reason='TEST-ONLY outcome follows the declared comparison')
        if design == 'stopping':
            data['stopping'] = dict(author='TEST-ONLY resolver', plan=g.pin(plan), rule=sample['stopping_rule'],
                arms=['TEST-ONLY-left', 'TEST-ONLY-right'], samples=[v['evidence'] for v in samples],
                met=True, reason='TEST-ONLY inspected every submitted sample')
        return SimpleNamespace(repo=repo, hs=hs, p=plan, data=data, links=links, clips=clips)
    yield make
    repo.close()


def record(x, **changes):
    return rs.record(x.repo, x.data | changes, 'TEST-ONLY resolver')


def states(event):
    return [(s.member if isinstance(s.member, str) else s.member.ref.id, s.status) for s in event.states]


@pytest.mark.parametrize('predictions,outcome,expected', [
    (None, 'TEST-ONLY-X', [('TEST-ONLY-beta', 'ELIMINATED'), ('TEST-ONLY-alpha', 'RETAINED'), ('RESIDUAL', 'RETAINED')]),
    (None, 'TEST-ONLY-Z', [('TEST-ONLY-beta', 'ELIMINATED'), ('TEST-ONLY-alpha', 'ELIMINATED'), ('RESIDUAL', 'RETAINED')]),
    ({'TEST-ONLY-alpha': ['TEST-ONLY-X', 'TEST-ONLY-Y'], 'TEST-ONLY-beta': ['TEST-ONLY-Y']}, 'TEST-ONLY-Y',
        [('TEST-ONLY-beta', 'RETAINED'), ('TEST-ONLY-alpha', 'RETAINED'), ('RESIDUAL', 'RETAINED')]),
    ({'TEST-ONLY-alpha': ['TEST-ONLY-X'], 'TEST-ONLY-beta': ['TEST-ONLY-X']}, 'TEST-ONLY-X',
        [('TEST-ONLY-beta', 'RETAINED'), ('TEST-ONLY-alpha', 'RETAINED'), ('RESIDUAL', 'RETAINED')]),
])
def test_literal_elimination_overlap_identical_and_residual(build, predictions, outcome, expected):
    x = build(predictions=predictions); before = [h.canonical() for h in x.repo.all('Hypothesis')]
    event = record(x, outcome=outcome)
    assert states(event) == expected
    if predictions is None and outcome == 'TEST-ONLY-X':
        assert event.input_sha256 == '7c30d10f2136fb8790672be1ca822ec3205cc60e381f96329a5004416a2bb0d8'
    assert event.rule_version == 'resolution-v1' and event.tool_version == '0.1.0'
    assert [(c.arm, c.count) for c in event.counts] == [('TEST-ONLY-left', 2), ('TEST-ONLY-right', 2)]
    assert [s.unit for s in event.samples] == ['source:' + '0'*63 + n for n in ('1', '2', '3', '4')]
    assert [h.canonical() for h in x.repo.all('Hypothesis')] == before
    assert rs.replay(x.repo, event) == event.model_dump(mode='json', include=rs.DERIVED)


def test_nonexhaustive_and_indeterminate_are_explicit(build):
    x = build(exhaustive=False)
    event = record(x, outcome='TEST-ONLY-Z')
    assert states(event) == [('TEST-ONLY-beta', 'ELIMINATED'), ('TEST-ONLY-alpha', 'ELIMINATED')]
    assert event.unpredicted is True and event.residual_present is False
    next_event = record(x, revision=2, predecessor=g.pin(event), revision_reason='TEST-ONLY inconclusive correction',
        mode='INDETERMINATE', indeterminate_reason='TEST-ONLY cannot distinguish')
    assert states(next_event) == [('TEST-ONLY-beta', 'INDETERMINATE'), ('TEST-ONLY-alpha', 'INDETERMINATE')]
    assert [e.revision for e in x.repo.all('ResolutionEvent')] == [1, 2]
    assert x.repo.get(event.ref).canonical() == event.canonical()


@pytest.mark.parametrize('options,updates,error,message', [
    ({'frozen': False}, {}, ValueError, 'frozen plan required'),
    ({}, {'outcome': 'TEST-ONLY-undeclared'}, ValueError, 'outcome absent'),
    ({}, {'evidence': []}, ValidationError, 'at least 1 item'),
    ({'e': 5}, {}, ValueError, 'TEST_RESULT required: DISCOVERY'),
    ({'h': (31, 12)}, {}, ValueError, 'TEST_RESULT required: DISCOVERY'),
    ({'counts': (1, 2), 'generated': True}, {}, rs.ResolutionUnavailable, 'insufficient samples'),
    ({'registered': 2}, {}, ValueError, 'TEST_RESULT required: SUPPORTING'),
    ({'e': 12}, {}, rs.ResolutionUnavailable, 'UNKNOWN'),
    ({'counts': (2, 1)}, {}, rs.ResolutionUnavailable, 'insufficient samples'),
    ({'counts': (3, 0)}, {}, rs.ResolutionUnavailable, 'insufficient samples'),
    ({'counts': (3, 1)}, {}, rs.ResolutionUnavailable, 'insufficient samples'),
    ({'counts': (1, 0), 'design': None}, {}, rs.ResolutionUnavailable, 'insufficient samples'),
    ({}, {'mode': 'INDETERMINATE'}, ValidationError, 'indeterminate reason required'),
    ({}, {'mode': 'INDETERMINATE', 'indeterminate_reason': ' '}, ValidationError, 'String should match pattern'),
    ({}, {'decision_reason': None}, ValueError, 'decision reason required'),
])
def test_prerequisite_rejections_do_not_append(build, options, updates, error, message):
    x = build(**options)
    with pytest.raises(error, match=message): record(x, **updates)
    assert x.repo.all('ResolutionEvent') == ()


@pytest.mark.parametrize('count', [2, 3])
def test_exact_and_above_sample_threshold(build, count):
    x = build(counts=(count, count)); event = record(x)
    assert [c.count for c in event.counts] == ([2, 2] if count == 2 else [3, 3])


@pytest.mark.parametrize('field', ['created_at', 'states', 'counts', 'dependencies', 'samples', 'input_sha256', 'tool_version', 'rule_version'])
def test_human_cannot_supply_computed_fields(build, field):
    x = build()
    with pytest.raises(ValidationError, match='Extra inputs are not permitted'): record(x, **{field: 'TEST-ONLY injected'})
    assert x.repo.all('ResolutionEvent') == ()


@pytest.mark.parametrize('case,message,error', [('pin', 'pinned artifact digest mismatch', ValueError),
    ('missing', 'UNKNOWN.*missing artifact', rs.ResolutionUnavailable), ('arm', 'unknown arm', ValueError),
    ('author', 'author declaration mismatch', ValueError), ('kind', 'pin must reference TestPlan', ValidationError),
    ('revision', 'pins require an explicit revision', ValidationError)])
def test_exact_inputs(build, case, message, error):
    x = build(); data = dict(x.data)
    if case == 'pin': data['plan'] = g.pin(x.p).model_copy(update={'sha256': 'f'*64})
    if case == 'missing': data['plan'] = g.pin(x.p).model_copy(update={'ref': d.Ref(kind='TestPlan', id='TEST-ONLY-absent')})
    if case == 'arm': data['evidence'] = [dict(arm='TEST-ONLY-absent-arm', evidence=x.data['evidence'][0]['evidence'])]
    if case == 'author': data['author'] = 'TEST-ONLY different author'
    if case == 'kind': data['plan'] = g.pin(x.hs[0])
    if case == 'revision':
        data['plan'] = g.pin(x.p).model_dump(); del data['plan']['ref']['revision']
    with pytest.raises(error, match=message): rs.record(x.repo, data, 'TEST-ONLY resolver')
    assert x.repo.all('ResolutionEvent') == ()


@pytest.mark.parametrize('case', ['submission', 'frame', 'revision', 'registration', 'cross-arm'])
def test_duplicate_sample_units_cannot_inflate_counts(build, case):
    x = build(); first = x.links[0]; ev = x.repo.get(first.evidence.ref); clip = x.clips[0]
    if case == 'submission': extra = x.data['evidence'][0]
    else:
        if case == 'registration':
            media, reg = anchors(x.repo, 'TEST-ONLY-reregistered', '0'*63 + '1', at(26))
            clip = clip.model_copy(update=dict(id='TEST-ONLY-reregistered', media=media.ref, ingestion=reg.ref)); x.repo.put(clip)
        ev = ev.model_copy(update=dict(id=ev.id if case == 'revision' else 'TEST-ONLY-alias',
            revision=2 if case == 'revision' else 1, media=clip.media, sampling_manifest=(.7,))); x.repo.put(ev)
        arm = 'TEST-ONLY-right' if case == 'cross-arm' else first.arm
        x.repo.put(first.model_copy(update=dict(id='TEST-ONLY-alias-link', evidence=g.pin(ev), clip=g.pin(clip), arm=arm)))
        extra = dict(arm=arm, evidence=g.pin(ev))
    with pytest.raises(ValueError, match='duplicate sample unit'): record(x, evidence=x.data['evidence'] + [extra])
    assert x.repo.all('ResolutionEvent') == ()


@pytest.mark.parametrize('case,message', [('missing', 'stopping declaration required'), ('false', 'stopping declaration mismatch'),
    ('author', 'stopping declaration mismatch'), ('plan', 'stopping declaration mismatch'), ('rule', 'stopping declaration mismatch'),
    ('arms', 'stopping declaration mismatch'), ('samples', 'stopping declaration mismatch'), ('reason', 'String should match pattern')])
def test_stopping_declarations_are_attributed_and_exact(build, case, message):
    x = build(counts=(1, 1), design='stopping'); stop = dict(x.data['stopping'])
    if case == 'missing': stop = None
    elif case == 'false': stop['met'] = False
    elif case == 'plan': stop['plan'] = g.pin(x.p).model_copy(update={'sha256': 'e'*64})
    elif case == 'arms': stop['arms'] = ['TEST-ONLY-left']
    elif case == 'samples': stop['samples'] = stop['samples'][:1]
    else: stop[case] = ' ' if case == 'reason' else 'TEST-ONLY mismatch'
    with pytest.raises(ValidationError if case == 'reason' else ValueError, match=message): record(x, stopping=stop)
    assert x.repo.all('ResolutionEvent') == ()


def test_stopping_success_and_fixed_design_cannot_be_bypassed(build):
    x = build(counts=(1, 1), design='stopping'); event = record(x)
    assert [c.count for c in event.counts] == [1, 1]
    assert states(event) == [('TEST-ONLY-beta', 'ELIMINATED'), ('TEST-ONLY-alpha', 'RETAINED'), ('RESIDUAL', 'RETAINED')]


def test_fixed_design_rejects_stopping_declaration(build):
    x = build(); stop = dict(author='TEST-ONLY resolver', plan=g.pin(x.p), rule='TEST-ONLY invented rule',
        arms=['TEST-ONLY-left', 'TEST-ONLY-right'], samples=[s['evidence'] for s in x.data['evidence']], met=True, reason='TEST-ONLY attempted override')
    with pytest.raises(ValueError, match='no stopping rule'): record(x, stopping=stop)


@pytest.mark.parametrize('field,value,message', [('revision_reason', None, 'revision reason required'),
    ('predecessor', None, 'immediate same-kind'), ('predecessor', 'bad-digest', 'pinned artifact digest mismatch')])
def test_correction_guards_have_no_revision_collision(build, field, value, message):
    x = build(); first = record(x)
    update = dict(revision=2, predecessor=g.pin(first), revision_reason='TEST-ONLY revised outcome')
    update[field] = g.pin(first).model_copy(update={'sha256': 'b'*64}) if value == 'bad-digest' else value
    with pytest.raises(ValueError if value == 'bad-digest' else ValidationError, match=message):
        rs.prepare(x.repo, x.data | update, 'TEST-ONLY resolver')
    with pytest.raises(ValueError if value == 'bad-digest' else ValidationError, match=message): record(x, **update)
    assert [e.revision for e in x.repo.all('ResolutionEvent')] == [1]


def test_initial_predecessor_guard_is_not_collision(build):
    x = build(); first = record(x)
    with pytest.raises(ValidationError, match='initial revision cannot have a predecessor'):
        record(x, id='TEST-ONLY-fresh-initial', predecessor=g.pin(first))


@pytest.mark.parametrize('field,value', [('states', ()), ('counts', ()), ('dependencies', ()), ('samples', ()),
    ('input_sha256', 'a'*64), ('tool_version', 'TEST-ONLY forged'), ('unpredicted', True), ('residual_present', False)])
def test_direct_repository_rederives_computed_fields(build, field, value):
    x = build(); event = rs.prepare(x.repo, x.data, 'TEST-ONLY resolver')
    with pytest.raises(ValueError, match='computed resolution mismatch'): x.repo.put(event.model_copy(update={field: value}))
    assert x.repo.all('ResolutionEvent') == ()


@pytest.mark.parametrize('revision', [1, 2])
def test_direct_admission_rejects_altered_application_timestamp(build, monkeypatch, revision):
    x = build(); monkeypatch.setattr(rs, 'now', lambda: at(40))
    data = x.data | {'id': 'TEST-ONLY-timestamp-admission'}
    if revision == 2:
        first = rs.record(x.repo, data, 'TEST-ONLY resolver')
        data |= dict(revision=2, predecessor=g.pin(first), revision_reason='TEST-ONLY timestamp correction')
    event = rs.prepare(x.repo, data, 'TEST-ONLY resolver')
    assert event.created_at == at(40)
    forged = event.model_copy(update={'created_at': at(41)})
    assert forged.model_dump(exclude={'created_at'}) == event.model_dump(exclude={'created_at'})
    before_rows = resolution_rows(x.repo)
    before = tuple(e.canonical() for e in x.repo.all('ResolutionEvent'))
    with pytest.raises(ValueError, match='created_at is application recorded'):
        x.repo.put(forged)
    assert tuple(e.canonical() for e in x.repo.all('ResolutionEvent')) == before
    assert resolution_rows(x.repo) == before_rows
    # A delayed, unchanged prepared copy still carries the application's timestamp.
    monkeypatch.setattr(rs, 'now', lambda: at(50))
    x.repo.put(event.model_copy())
    assert x.repo.get(event.ref).created_at == at(40)


def test_direct_admission_requires_timestamp_preparation_receipt(build):
    x = build(); event = rs.prepare(x.repo, x.data | {'id': 'TEST-ONLY-unprepared'}, 'TEST-ONLY resolver')
    imported = rs.ResolutionEvent.model_validate_json(event.model_dump_json())
    with pytest.raises(ValueError, match='created_at is application recorded'):
        x.repo.put(imported)
    assert x.repo.all('ResolutionEvent') == ()


@pytest.mark.parametrize('case,message,error', [('kind', 'pin must reference Evidence', ValidationError),
    ('digest', 'INTEGRITY_FAILURE.*pinned artifact digest mismatch', ValueError)])
def test_evidence_pin_guards(build, case, message, error):
    x = build(); evidence = list(x.data['evidence'])
    evidence[0] = dict(arm='TEST-ONLY-left', evidence=g.pin(x.hs[0]) if case == 'kind' else
        evidence[0]['evidence'].model_copy(update={'sha256': 'a'*64}))
    with pytest.raises(error, match=message): record(x, evidence=evidence)
    assert x.repo.all('ResolutionEvent') == ()


def test_direct_nested_copy_extras_are_revalidated(build):
    x = build(); event = rs.prepare(x.repo, x.data, 'TEST-ONLY resolver')
    sample = event.evidence[0].model_copy(update={'evidence': event.evidence[0].evidence.model_copy(update={'forged': 'TEST-ONLY'})})
    with pytest.raises(ValidationError, match='Extra inputs are not permitted'):
        x.repo.put(event.model_copy(update={'evidence': (sample,) + event.evidence[1:]}))
    assert x.repo.all('ResolutionEvent') == ()


def test_replay_rejects_changed_dependency_digest_and_computed_states(build):
    x = build(); event = record(x)
    corrupted = event.model_copy(update={'dependencies': (event.dependencies[0].model_copy(update={'sha256': 'e'*64}),) + event.dependencies[1:]})
    with pytest.raises(ValueError, match='pinned artifact digest mismatch'): rs.replay(x.repo, corrupted)
    with pytest.raises(ValueError, match='computed resolution mismatch'): rs.replay(x.repo, event.model_copy(update={'states': ()}))


@pytest.mark.parametrize('damage,message,error', [('missing', 'UNKNOWN.*missing artifact', rs.ResolutionUnavailable),
    ('freeze', 'frozen digest mismatch', ValueError), ('hash', 'snapshot integrity failure', ValueError)])
def test_retained_plan_integrity_and_missing_dependencies(build, damage, message, error):
    import sqlite3
    x = build()
    with sqlite3.connect(x.repo.engine.url.database) as db:
        if damage == 'missing':
            db.execute('DROP TRIGGER no_delete_artifacts'); db.execute("DELETE FROM artifacts WHERE kind='CompetingSet'")
        else:
            db.execute('DROP TRIGGER no_update_artifacts')
            if damage == 'hash': db.execute("UPDATE artifacts SET sha256=? WHERE kind='TestPlan' AND revision=2", ('f'*64,))
            else:
                data = x.p.model_dump(mode='json'); data['outcome_categories'].append('TEST-ONLY-tampered')
                import json
                db.execute("UPDATE artifacts SET payload=? WHERE kind='TestPlan' AND revision=2", (json.dumps(data),))
    with pytest.raises(error, match=message): record(x)
    assert x.repo.all('ResolutionEvent') == ()


def resolution_rows(repo):
    from sqlalchemy import select, func
    from eval_lab.persistence import artifacts, references
    with repo.engine.connect() as conn:
        return tuple(conn.execute(select(func.count()).select_from(table).where(table.c.kind == 'ResolutionEvent')).scalar_one()
            for table in (artifacts, references))


@pytest.mark.parametrize('field', ['tool_version', 'schema_version', 'canonicalization', 'number_profile', 'sample_design', 'nonobject'])
@pytest.mark.parametrize('boundary', ['prepare', 'transaction'])
def test_raw_frozen_defaults_rejected_at_each_read_boundary(build, monkeypatch, field, boundary):
    import json, sqlite3
    x = build(counts=(1, 1), design=None)
    data = x.data | {'id': 'TEST-ONLY-raw-' + boundary + '-' + field}
    event = rs.prepare(x.repo, data, 'TEST-ONLY resolver')
    def corrupt():
        payload = x.p.model_dump(mode='json')
        if field == 'nonobject': payload = []
        else: del payload[field]
        with sqlite3.connect(x.repo.engine.url.database) as db:
            db.execute('DROP TRIGGER no_update_artifacts')
            db.execute("UPDATE artifacts SET payload=? WHERE kind='TestPlan' AND revision=2", (json.dumps(payload),))
    if boundary == 'prepare': corrupt()
    else:
        original = x.repo._validate_links
        def after_preflight(item):
            original(item)
            corrupt()  # The transaction is the first reader of the damaged retained row.
        monkeypatch.setattr(x.repo, '_validate_links', after_preflight)
    message = 'retained TestPlan payload must be a JSON object' if field == 'nonobject' else 'frozen digest mismatch in retained payload'
    with pytest.raises(ValueError, match=message):
        if boundary == 'prepare': rs.prepare(x.repo, data, 'TEST-ONLY resolver')
        else: x.repo.put(event)
    assert resolution_rows(x.repo) == (0, 0)


def test_timestamp_receipt_is_bound_to_prepared_content(build):
    x = build(); event = rs.prepare(x.repo, x.data, 'TEST-ONLY resolver')
    changed = rs.ResolutionInput(**(x.data | {'outcome': 'TEST-ONLY-Z'}))
    forged = event.model_copy(update={'outcome': 'TEST-ONLY-Z', **rs.derive(x.repo, changed)})
    with pytest.raises(ValueError, match='created_at is application recorded'): x.repo.put(forged)
    assert resolution_rows(x.repo) == (0, 0)
