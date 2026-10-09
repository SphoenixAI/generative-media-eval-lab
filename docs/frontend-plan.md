# Frontend plan: deliberately deferred

The brief requires backend validity before visual polish. No product frontend has been built. First use the CLI and typed outputs to verify the evaluation workflow.

Later, reusable components should expose the same API records: MediaComparison, RatingPanel, RubricInspector, EvidenceTimeline, HumanConsensusPanel, AgentDisagreementMap, HypothesisGraphView, RegressionMatrix, GoldExampleInspector, EvaluatorValidationPanel and VFXSalvagePanel. Full lab, Think With Me and project embeds compose these components rather than duplicating logic.

Preserve the viewer's active evaluation context, server-side blinding, tie/unknown distinction, evidence intervals and uncertainty. Use graphs only where edge purpose and intent improve understanding. A graph visualization is not a substitute for the flat-log baseline usability test. Build the internal inspection interface before the public experience.
