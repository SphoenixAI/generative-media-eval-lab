"""TEST-ONLY private workflow and pinned replay, using synthetic metadata."""
import json
from types import SimpleNamespace
import pytest
from eval_lab import resolutions as rs, evidence_roles as er, test_plans as tp, generation as g, domain as d, pilot_cli
from eval_lab.persistence import Repository
from eval_lab.pilot import PilotWorkspace
from eval_lab.pilot_domain import PilotDataset
from eval_lab.presentation import serialize_case, submit_pairwise
from test_domain_review import seed_review
from test_resolutions import build, record, states, resolution_rows
from test_evidence_roles import at
from test_intent_v2 import anchors

def test_scoped_plan_links_and_context_corrections_do_not_rewrite_replay(build):
    x = build(); draft = x.repo.get(d.Ref(kind='TestPlan', id=x.p.id, revision=1))
    other = draft.model_copy(update={'id': 'TEST-ONLY-other-plan'}); x.repo.put(other)
    other = tp.freeze(x.repo, 'TEST-ONLY-other-plan@1')
    for link in x.links:
        x.repo.put(link.model_copy(update=dict(id='TEST-ONLY-aaa-' + link.id, plan=g.pin(other))))
    first = record(x)
    assert {r.link.ref.id for s in first.samples for r in s.roles} == {
        'TEST-ONLY-sample-1', 'TEST-ONLY-sample-2', 'TEST-ONLY-sample-3', 'TEST-ONLY-sample-4'}
    before = rs.replay(x.repo, first)
    for link in x.links:
        x.repo.put(link.model_copy(update=dict(revision=2, predecessor=g.pin(link), plan=g.pin(other),
            revision_reason='TEST-ONLY reassociate with another plan')))
    assert rs.replay(x.repo, first) == before
    with pytest.raises(ValueError, match='TEST_RESULT required: SUPPORTING'):
        record(x, id='TEST-ONLY-new-after-correction')
    assert [e.id for e in x.repo.all('ResolutionEvent')] == ['TEST-ONLY-resolution']

def test_transaction_checks_live_context_after_preparation(build, monkeypatch):
    x = build(); event = rs.prepare(x.repo, x.data, 'TEST-ONLY resolver')
    old_validate = x.repo._validate_links
    def change(item):
        old_validate(item)
        if isinstance(item, rs.ResolutionEvent):
            link = x.links[0]
            x.repo.put(link.model_copy(update=dict(revision=2, predecessor=g.pin(link),
                revision_reason='TEST-ONLY concurrent correction')))
    monkeypatch.setattr(x.repo, '_validate_links', change)
    with pytest.raises(ValueError, match='computed resolution mismatch'): x.repo.put(event)
    assert x.repo.all('ResolutionEvent') == ()
    from test_resolutions import resolution_rows
    assert resolution_rows(x.repo) == (0, 0)

def test_cli_show_schema_reopen_snapshots_and_public_boundaries(build, tmp_path, monkeypatch, capsys):
    x = build(); p = PilotWorkspace(tmp_path)
    monkeypatch.setattr(p, 'verify_clip', lambda clip: None)  # Metadata closure only; no media-byte claim.
    media, reg = anchors(p.repo, 'TEST-ONLY-original-case', 'f'*64, at(1))
    original = x.clips[0].model_copy(update=dict(id='TEST-ONLY-original-case', media=media.ref, ingestion=reg.ref, intent=x.hs[0].intent)); p.repo.put(original)
    p.repo.put(PilotDataset(id='TEST-ONLY-dataset', owner='TEST-ONLY curator', clips=(original.ref,)))
    p.snapshot('TEST-ONLY-dataset', 'TEST-ONLY-before'); before = p.export_snapshot('TEST-ONLY-before')
    args = ['--root', str(tmp_path), '--author', 'TEST-ONLY resolver']
    source = tmp_path / 'TEST-ONLY-human.json'; source.write_text(rs.ResolutionInput(**x.data).model_dump_json())
    assert pilot_cli.main(args + ['resolve', '--file', str(source)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert [s['status'] for s in output['states']] == ['ELIMINATED', 'RETAINED', 'RETAINED']
    event = x.repo.all('ResolutionEvent')[0]
    assert pilot_cli.main(args + ['show', original.id]) == 0
    assert json.loads(capsys.readouterr().out)['resolutions'] == [event.model_dump(mode='json')]
    assert pilot_cli.main(args + ['schema']) == 0
    schema = json.loads(capsys.readouterr().out)
    assert 'ResolutionEvent' in schema['record_schemas'] and 'resolve' in schema['human_form_schemas']
    correction = record(x, revision=2, predecessor=g.pin(event), revision_reason='TEST-ONLY revise outcome', outcome='TEST-ONLY-Z')
    p.snapshot('TEST-ONLY-dataset', 'TEST-ONLY-after'); exported = p.export_snapshot('TEST-ONLY-after')
    assert p.export_snapshot('TEST-ONLY-before') == before
    rows = exported['records']
    assert [(r['ref']['id'], r['ref']['revision']) for r in rows if r['ref']['kind'] == 'ResolutionEvent'] == [
        ('TEST-ONLY-resolution', 1), ('TEST-ONLY-resolution', 2)]
    assert {r['ref']['id'] for r in rows if r['ref']['kind'] == 'Evidence'} == {
        'TEST-ONLY-sample-1', 'TEST-ONLY-sample-2', 'TEST-ONLY-sample-3', 'TEST-ONLY-sample-4'}
    records = {d.Ref(**r['ref']): d.ARTIFACT_TYPES[r['ref']['kind']].model_validate(r['artifact']) for r in rows}
    snapshot = SimpleNamespace(get=records.__getitem__, all=lambda name: tuple(v for v in records.values() if v.ref.kind == name))
    reopened = Repository(str(x.repo.engine.url))
    for repo in (snapshot, reopened):
        assert rs.replay(repo, event) == event.model_dump(mode='json', include=rs.DERIVED)
        assert rs.replay(repo, correction)['unpredicted'] is True
    assert rs.roots(x.repo, (x.clips[3],)) == [event.ref, correction.ref]
    lab = seed_review(x.repo)
    for mode in ('public', 'embed'):
        public = json.dumps(serialize_case(x.repo, lab.case.ref, lab.round.ref, lab.rater.ref, mode=mode))
        for marker in ('TEST-ONLY-resolution', 'TEST-ONLY revise outcome', 'resolution-v1', 'TEST-ONLY-sample-1'):
            assert marker not in public
    reopened.close(); p.close()
    with pytest.raises(SystemExit, match='0') as error: pilot_cli.parser().parse_args(['resolve', '--help'])
    assert error.value.code == 0
    help_text = capsys.readouterr().out
    assert 'TEST_RESULT' in help_text and 'docs/hypothesis-testing.md' in help_text

def test_cli_rejects_unfrozen_and_keeps_unknown(build, tmp_path, capsys):
    x = build(frozen=False); source = tmp_path / 'TEST-ONLY-draft.json'
    source.write_text(rs.ResolutionInput(**x.data).model_dump_json())
    assert pilot_cli.main(['--root', str(tmp_path), '--author', 'TEST-ONLY resolver', 'resolve', '--file', str(source)]) == 2
    result = json.loads(capsys.readouterr().err)
    assert 'frozen plan required' in result['error'] and result['quality_verdict'] == 'UNKNOWN'
    assert x.repo.all('ResolutionEvent') == ()

@pytest.mark.parametrize('mode', ['public', 'embed'])
@pytest.mark.parametrize('stage', ['blind', 'revealed'])
def test_associated_resolutions_are_private_in_each_presentation_state(build, mode, stage):
    x = build(); lab = seed_review(x.repo)
    prompt = lab.prompt.model_copy(update=dict(id='TEST-ONLY-associated-prompt', intent=x.hs[0].intent,
        original_prompt='TEST-ONLY public prompt', normalized_prompt='TEST-ONLY public normalized prompt'))
    x.repo.put(prompt)
    runs = tuple(run.model_copy(update=dict(id=f'TEST-ONLY-associated-run-{i}', prompt=prompt.ref))
        for i, run in enumerate(lab.runs))
    for run in runs: x.repo.put(run)
    rnd = lab.round.model_copy(update=dict(id='TEST-ONLY-associated-round', candidate_model_runs=tuple(r.ref for r in runs)))
    case = lab.case.model_copy(update=dict(id='TEST-ONLY-associated-case', intent=x.hs[0].intent,
        model_runs=rnd.candidate_model_runs, title='TEST-ONLY public title', description='TEST-ONLY public description'))
    x.repo.put(rnd); x.repo.put(case)
    event = record(x, id='TEST-ONLY-private-event', decision_reason='TEST-ONLY-private-decision-input',
        mode='INDETERMINATE', indeterminate_reason='TEST-ONLY-private-indeterminate-reason')
    correction = record(x, id=event.id, revision=2, predecessor=g.pin(event),
        revision_reason='TEST-ONLY-private-revision-reason', outcome='TEST-ONLY-Z')
    # The resolution and both presented runs share the case's exact intent.
    group = x.repo.get(x.repo.get(event.plan.ref).competing_set.ref)
    assert group.intent == case.intent == prompt.intent
    assert all(x.repo.get(x.repo.get(ref).prompt).intent == case.intent for ref in case.model_runs)
    assert rs.roots(x.repo, (x.clips[0],)) == [event.ref, correction.ref]
    markers = ('TEST-ONLY-private-event', 'TEST-ONLY-private-decision-input',
        'TEST-ONLY-private-indeterminate-reason', 'TEST-ONLY-private-revision-reason',
        'TEST-ONLY-X', 'TEST-ONLY-Z', 'TEST-ONLY-sample-1', 'resolution-v1')
    private = json.dumps([e.model_dump(mode='json') for e in (event, correction)])
    assert all(marker in private for marker in markers)
    if stage == 'revealed':
        submit_pairwise(x.repo, rnd.ref, lab.rater.ref, 'tie', 'TEST-ONLY private vote rationale', created_at=at(60))
    payload = serialize_case(x.repo, case.ref, rnd.ref, lab.rater.ref, mode=mode)
    assert payload['stage'] == stage and payload['mode'] == mode
    if stage == 'revealed':
        assert payload['your_evaluation'] == {'choice': 'tie'}
        assert [row['label'] for row in payload['results']] == ['A', 'B']
    else:
        assert 'results' not in payload and 'your_evaluation' not in payload
    public = json.dumps(payload)
    for marker in markers: assert marker not in public

def test_no_design_still_checks_every_arm_and_indeterminate_retains_residual(build):
    x = build(counts=(1, 1), design=None)
    event = record(x, mode='INDETERMINATE', indeterminate_reason='TEST-ONLY unresolved ambiguity')
    assert states(event) == [('TEST-ONLY-beta', 'INDETERMINATE'), ('TEST-ONLY-alpha', 'INDETERMINATE'), ('RESIDUAL', 'RETAINED')]
    assert [c.count for c in event.counts] == [1, 1]

def test_indeterminate_does_not_waive_sample_requirements(build):
    x = build(counts=(1, 1))
    with pytest.raises(rs.ResolutionUnavailable, match='insufficient samples'):
        record(x, mode='INDETERMINATE', indeterminate_reason='TEST-ONLY unresolved')

def test_instrument_lineage_revisions_and_link_aliases_count_once(build):
    x = build(counts=(1, 1), registered=1)
    draft = x.repo.get(d.Ref(kind='TestPlan', id=x.p.id, revision=1))
    plan = draft.model_copy(update=dict(id='TEST-ONLY-instrument-plan', measurement=tp.Measurement(kind='INSTRUMENT', protocol='TEST-ONLY inert meter'),
        sample_design=tp.SampleDesign(n_per_arm=1, decision_rule='TEST-ONLY compare instrument outputs')))
    x.repo.put(plan); plan = tp.freeze(x.repo, 'TEST-ONLY-instrument-plan@1')
    for index, link in enumerate(x.links):
        run = er.InstrumentRun(id='TEST-ONLY-run-' + str(index), author='TEST-ONLY operator', plan=g.pin(plan),
            arm=link.arm, evidence=link.evidence, executed_at=at(22), tool='TEST-ONLY meter', version='TEST-ONLY 3',
            tool_sha256='a'*64, input_sha256=f'{index+1:064x}', output_sha256=link.evidence.sha256); x.repo.put(run)
        x.repo.put(link.model_copy(update=dict(id='TEST-ONLY-instrument-' + str(index), plan=g.pin(plan), run=g.pin(run))))
    event = record(x, plan=g.pin(plan))
    assert [s.unit for s in event.samples] == ['run:TEST-ONLY-run-0', 'run:TEST-ONLY-run-1']
    run = x.repo.all('InstrumentRun')[0]
    revision = run.model_copy(update=dict(revision=2, predecessor=g.pin(run), revision_reason='TEST-ONLY run arm correction', arm='TEST-ONLY-right')); x.repo.put(revision)
    link = x.repo.get(d.Ref(kind='EvidenceArm', id='TEST-ONLY-instrument-0'))
    x.repo.put(link.model_copy(update=dict(id='TEST-ONLY-run-alias', run=g.pin(revision), arm='TEST-ONLY-right')))
    with pytest.raises(ValueError, match='duplicate sample unit'):
        record(x, id='TEST-ONLY-run-duplicate', plan=g.pin(plan), evidence=x.data['evidence'] + [dict(arm='TEST-ONLY-right', evidence=x.data['evidence'][0]['evidence'])])

@pytest.mark.parametrize('design', ['fixed', 'stopping'])
def test_same_evidence_across_distinct_instrument_runs_rejected(build, design):
    x = build(counts=(1, 0), registered=1, design=design)
    draft = x.repo.get(d.Ref(kind='TestPlan', id=x.p.id, revision=1))
    sample_design = tp.SampleDesign(n_per_arm=1, decision_rule='TEST-ONLY compare outputs') if design == 'fixed' else draft.sample_design
    plan = draft.model_copy(update=dict(id='TEST-ONLY-shared-evidence-plan', sample_design=sample_design,
        measurement=tp.Measurement(kind='INSTRUMENT', protocol='TEST-ONLY inert meter')))
    x.repo.put(plan); plan = tp.freeze(x.repo, 'TEST-ONLY-shared-evidence-plan@1')
    link = x.links[0]; submitted = []
    for index, arm in enumerate(('TEST-ONLY-left', 'TEST-ONLY-right')):
        run = er.InstrumentRun(id=f'TEST-ONLY-shared-run-{index}', author='TEST-ONLY operator', plan=g.pin(plan),
            arm=arm, evidence=link.evidence, executed_at=at(22 + index), tool='TEST-ONLY meter', version='TEST-ONLY 3',
            tool_sha256='a'*64, input_sha256='0'*63+'1', output_sha256=link.evidence.sha256); x.repo.put(run)
        x.repo.put(link.model_copy(update=dict(id=f'TEST-ONLY-shared-link-{index}', plan=g.pin(plan), arm=arm, run=g.pin(run))))
        submitted.append(dict(arm=arm, evidence=link.evidence))
    assert [r.id for r in x.repo.all('InstrumentRun')] == ['TEST-ONLY-shared-run-0', 'TEST-ONLY-shared-run-1']
    assert len(x.repo.all('Evidence')) == 1 and submitted[0]['evidence'] == submitted[1]['evidence']
    changes = dict(id='TEST-ONLY-duplicate-evidence-event', plan=g.pin(plan), evidence=submitted)
    if design == 'stopping': changes['stopping'] = x.data['stopping'] | dict(plan=g.pin(plan), samples=[link.evidence, link.evidence])
    assert resolution_rows(x.repo) == (0, 0)
    with pytest.raises(ValueError, match='duplicate sample unit: repeated Evidence identity'):
        record(x, **changes)
    assert resolution_rows(x.repo) == (0, 0)

def test_duplicate_stopping_references_rejected_before_matching(build):
    x = build(counts=(1, 1), design='stopping'); stop = x.data['stopping']
    assert stop['samples'][0].ref.id == 'TEST-ONLY-sample-1' and stop['samples'][1].ref.id == 'TEST-ONLY-sample-2'
    assert resolution_rows(x.repo) == (0, 0)
    with pytest.raises(ValueError, match='duplicate stopping sample reference'):
        record(x, id='TEST-ONLY-duplicate-stopping-event', stopping=stop | {'samples': stop['samples'] + [stop['samples'][0]]})
    assert resolution_rows(x.repo) == (0, 0)

def test_correction_replay_retains_excluded_heads_from_predecessor_context(build):
    x = build(); first = record(x)
    draft = x.repo.get(d.Ref(kind='TestPlan', id=x.p.id, revision=1))
    x.repo.put(draft.model_copy(update={'id': 'TEST-ONLY-foreign'})); foreign = tp.freeze(x.repo, 'TEST-ONLY-foreign@1')
    for link in x.links:
        x.repo.put(link.model_copy(update=dict(revision=2, predecessor=g.pin(link), plan=g.pin(foreign),
            revision_reason='TEST-ONLY move old link')))
        x.repo.put(link.model_copy(update=dict(id='TEST-ONLY-z-current-' + link.id)))
    second = record(x, revision=2, predecessor=g.pin(first), revision_reason='TEST-ONLY refresh context')
    assert rs.replay(x.repo, second) == second.model_dump(mode='json', include=rs.DERIVED)
    assert {r.link.ref.id for s in second.samples for r in s.roles} == {
        'TEST-ONLY-z-current-TEST-ONLY-sample-1', 'TEST-ONLY-z-current-TEST-ONLY-sample-2',
        'TEST-ONLY-z-current-TEST-ONLY-sample-3', 'TEST-ONLY-z-current-TEST-ONLY-sample-4'}

def test_determinism_survives_enumeration_and_later_hypothesis_plan_revisions(build):
    x = build(); event = record(x)
    hyp = x.hs[0]; x.repo.put(hyp.model_copy(update=dict(revision=2, proposed_cause='TEST-ONLY later cause')))
    draft = x.p.model_dump() | dict(revision=3, predecessor=g.pin(x.p), frozen_at=None, frozen_digest=None)
    x.repo.put(tp.TestPlan(**draft))
    reversed_repo = SimpleNamespace(get=x.repo.get, all=lambda name: tuple(reversed(x.repo.all(name))))
    for repo in (x.repo, reversed_repo):
        candidate = rs.prepare(repo, x.data, 'TEST-ONLY resolver')
        assert [s.status for s in candidate.states] == ['ELIMINATED', 'RETAINED', 'RETAINED']
        assert candidate.model_dump(include=rs.DERIVED) == event.model_dump(include=rs.DERIVED)
        assert rs.replay(repo, event) == event.model_dump(mode='json', include=rs.DERIVED)
