# Public, private and embed boundaries

The implemented presentation functions are trusted backend contracts. They are **not exposed as public HTTP rating endpoints**. A caller must bind rater identity to its authenticated/anonymous server session. Letting a visitor supply another rater's ID would undermine reveal gating; that session service is a future requirement.

Public and embed modes use the same curated case and round. Before submission they reveal a neutral title, prompt, A/B presentation tokens and choices. They exclude generating model identity, actual run IDs, private notes, raw evidence, consensus and agent judgments. After a stored pairwise submission, the same rater receives allowlisted score distributions and fixture results. Tie and cannot-determine stay separate. The response explicitly states that media and judgments are synthetic.

Agent results are pinned by the case's `published_assessments`, not gathered from every stored reevaluation. A case revision explicitly changes its publication snapshot; evaluator digests distinguish exposed instruments. The Phase 4 serializer rejects nonfixture media. Real media presentation and broader disclosure require the later curation/service layer.

Private cases and administrative serialization are rejected. No storage paths or provider exceptions are copied into public output. Titles and prompts still require human curation because text can leak identity or expected answers. Protected media delivery, expiring session tokens, anonymous abuse controls, CSRF/CORS, retention/consent and disclosure-reviewed summaries are not implemented.

`api.py` provides `/health` and a `/private/execute` route that always denies. There is no credential-handling or live generation path. A provider's local `mode` flag is not an operating-system sandbox. Before introducing providers, isolate untrusted media, defend URL/file ingestion, enforce network/tool capabilities and reserve actual costs atomically. Public visitors should see precomputed results and never trigger paid execution.
