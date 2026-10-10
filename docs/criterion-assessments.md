# Private technical observations and criterion assessments

These append-only records separate observed deviations from human acceptability.
They do not score prose, interpret video, or produce a terminal quality verdict.
The intent-flip tests use generated TEST-ONLY patterns and explicitly authored
statuses; they establish software behavior, not empirical validity.

Use `eval-pilot --root PRIVATE_WORKSPACE --author HUMAN technical-observation CLIP --file FILE`
or `eval-pilot --root PRIVATE_WORKSPACE --author HUMAN criterion-assessment CLIP --file FILE`.
The file must contain the complete human-authored record. `schema` exposes both
record schemas. `show CLIP` returns both histories privately, alongside existing
submissions and lifecycle context. Existing Pilot 0 observations remain Evidence;
they are not migrated or automatically converted to technical observations.

Both records require `id`, `author` (matching `--author`), and `media`.
Every pin has exactly this shape, with an existing record's actual digest:
`{"ref":{"kind":"MediaAsset","id":"EXISTING_ID","revision":1},"sha256":"64 lowercase hexadecimal characters"}`.
Omitted reference revisions are rejected; no lookup silently selects latest.
For a correction, retain the ID, supply the next `revision`, `predecessor` pin,
and nonblank `revision_reason`. The original media pin stays fixed.
`created_at` is an optional declared timestamp; omitted values use local time.
The import records the application `tool_version`; do not supply it in the file.
Authorship is declared, not authenticated. Each validated import writes one record.

TechnicalObservation also requires:

- `dimension`: an existing domain dimension, e.g. `motion_plausibility`.
- `deviation`: `NONE`, `MINOR`, `MATERIAL`, `SEVERE`, `CATASTROPHIC`, or `UNKNOWN`.
- `span`: `[start_seconds,end_seconds]`, finite, nonnegative, ordered and within media duration.
- `evidence`: exact Evidence pins for that media; empty support requires `UNKNOWN`.
- `viewing_profile`: `FEED` or `STUDIO`.

It cannot reference intent, criteria, bindings, statuses, decisions, or PilotClip.
This is structural validation; it cannot detect creative intent mentioned in prose.

CriterionAssessment also requires `criterion_id`, `intent` (IntentSpecV2 pin),
`binding` (IntentBinding pin with retained BindingContext), `observations`
(TechnicalObservation pins), `rationale`, and `status`: `SATISFIED`, `VIOLATED`,
`NOT_APPLICABLE`, or `UNKNOWN`. Binding, intent, media and criterion dimension must
agree. Rationale must be nonblank and should explain evidence gaps when UNKNOWN.
No observations, or any UNKNOWN deviation, permits only UNKNOWN; contradictory
submissions are rejected without rewriting them. Known support may still be UNKNOWN.
NOT_APPLICABLE is an explicit supported human assertion, never a missing-data default.

A SATISFIED assessment citing MATERIAL or worse requires a matching expected
deviation and SEALED provenance, or CONTEMPORANEOUS provenance with
`flags:["CONTEMPORANEOUS_INTENT"]`. Other assessments use `flags:[]` (the default).
RECONSTRUCTED and PROMPT_ONLY cannot excuse that deviation. Later revisions never
reinterpret earlier assessments. Changing criterion, intent or binding requires a
new assessment ID; these pins cannot change within a correction lineage.

Private snapshots discover records by exact media and binding context, including
direct repository admissions, history and pinned dependencies. Old exports remain
frozen. Missing media later appears separately as availability UNKNOWN; historical
records remain authored facts about what was submitted. Forged or corrupt pins are
errors, not successful UNKNOWN records. Public/embed serializers exclude these
private records. Seals and ingestion retain their existing versions and hashes.
