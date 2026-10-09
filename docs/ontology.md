# Intent-aware ontology: implemented Phase 4 scope

The ontology is a typed application model in `src/eval_lab/domain.py`, backed by versioned SQLite records. It preserves why a relationship matters as well as what it connects. It is not an RDF store, an OWL reasoner, or a SHACL-conformant graph implementation.

## Intent is part of the measurement context

An `IntentSpec` records the owner, objective, audience, context, textual constraints, prohibited outcomes, and dimension criteria. Each `Criterion` identifies a dimension, its applicability (`required`, `optional`, or `not_applicable`), its rationale and its acceptance description. A `PromptSpec` references one exact intent revision; every generated `ModelRun` references the prompt and its media asset.

`authority` distinguishes `human_declared` from `agent_proposed`. A declared intent requires an `approved_by` string. These are **trusted fixture assertions**, not authenticated signatures or real approval records. Current agents cannot turn a proposed intent into authorization simply by producing a confident assessment. The scoring engine does not issue a pass when the intent is only proposed.

The current constraints and acceptance descriptions are human-readable strings. They do not implement machine-checked quantity constraints, conflicting-objective resolution, delegation, revocation or authority grants. Those are documented future extensions in the research report, not completed features.

## Evidence, hypotheses and relation claims

`Evidence` references an exact asset and records observation text, observer, method, source kind, independence group and temporal coverage. Coverage can describe a full clip, an interval, sampled frames or unknown coverage. These fields assert the observation's scope; the Phase 4 fixture provider does not decode or verify real media.

`Hypothesis` distinguishes a proposed mechanism from its supporting and contradicting evidence. It retains required evidence, a discriminating-test description, predicted and falsifying observations, and unresolved status. A confidence value is explicitly `subjective_unvalidated`. There is no Bayesian updater, causal-identification engine, executed experiment or automatic adjudication at this checkpoint.

Every `RelationClaim` includes subject, predicate, object, intent, epistemic status, evidence, asserted-by identity, purpose, scope and a validity interval. Permitted relations are deliberately small:

- Evidence `supports` or `contradicts` a hypothesis.
- A hypothesis is `motivated_by` an intent.
- Evidence `fulfills` or `violates` an intent.
- A hypothesis is `alternative_to` another hypothesis.

The relation validator checks each predicate's permitted subject/object types. Hypothesis relations cannot be marked `observed`; they remain asserted or proposed interpretations. An observed relation requires evidence. The validity interval requires timezone-aware dates and, when present, an end later than its start. A conformance claim such as `fulfills` remains an accountable assertion; storing it does not prove the interpretation correct.

## Graph integrity

A `HypothesisGraph` contains explicit node references, embedded relation snapshots and unresolved questions. Edges cannot point outside its nodes or carry a different intent. Persistence requires each embedded relation to already exist and match its stored revision digest. Hypotheses referenced by relations and graphs must carry the same intent; no implicit cross-intent mapping is performed.

Hypothesis evidence must trace to a model run whose prompt uses that intent. The same requirement applies to a relation's cited evidence and to its subject when the subject is an `Evidence` record, including claims with an empty additional evidence list. Dimension ratings must cite evidence from their own model output. These checks prevent several forms of accidental cross-case evidence reuse; they do not prove that an observation is true or relevant enough to support a mechanism.

## Explicit case publication

An `EvaluationCase` names the exact `AgentAssessment` revisions approved for its presentation in `published_assessments`, which defaults to empty. Persistence rejects duplicate references and assessments outside the case's model runs or rubric. Marking a case curated does not implicitly publish every assessment associated with its runs. After a human submission, the fixture serializer exposes only these selected assessments and each evaluator snapshot's digest. This is an explicit data-selection contract; publication and approval remain trusted local assertions rather than authenticated authorization.

## Interoperability direction

The current concepts can later project to PROV-O entities, activities, agents and qualified plans. SHACL could then validate the exported graph. Stable references, explicit scope and provenance make this extension feasible without requiring a graph database now. Neither future RDF validation nor dense relational connectivity would establish factual truth or causality.

See `research/methods-standards.md` for the source-backed expansion plan and `review-methodology.md` for the independently tested boundaries.
