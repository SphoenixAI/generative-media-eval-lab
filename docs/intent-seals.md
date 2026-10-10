# Local intent seals

`eval-pilot --root WORKSPACE seal-intent FILE` imports a complete human-authored
IntentSpecV2 JSON file and appends a private seal. Supply explicit `id`,
`schema_version: 2`, `revision`, and timezone-bearing `created_at`, plus the v2
owner, objective, use context, criteria and revision reason. Later revisions
require the immediate predecessor's exact reference and artifact digest.
Legacy v1 forms still use `eval-pilot intent`. The source is read once and never
rewritten; missing human content is not generated.

The file digest is SHA-256 of RFC 8785 canonical JSON under the narrower
`safe-integer-tokens-v1` profile: objects, arrays, Unicode strings, booleans, null
and integer literals in [-9007199254740991, 9007199254740991]. Object keys sort
by unsigned UTF-16 units; arrays keep their order and strings are not normalized.
Duplicate decoded keys, invalid Unicode, non-finite numbers, fractional/exponent
tokens (including `1.0` and `1e0`) and out-of-range integers are rejected. Use an
integer literal for an exact in-range integer; otherwise use a human-authored
representation in a schema-permitted text field or seek a separately approved
numeric extension. No automatic conversion is performed. Negative zero becomes 0.

The private SealRecord retains canonical source text, its file digest, method
and profile, UTC seal time, tool version, resolved source path and the exact
intent reference plus its existing artifact digest. The latter hashes typed
artifact content and remains unchanged; it is distinct from the file digest.
Optional `--git-commit HASH --git-remote URL` must be supplied together. These
are declarations only; no Git lookup or network request is made.

`eval-pilot --root WORKSPACE verify-seal ID|FILE` checks stored integrity, the
archived canonical source, exact intent pin and current original source file.
FILE is the original intent file, not a portable seal certificate. Filename
lookup compares every retained seal with one captured source digest (or read/parse
failure) per resolved path for that operation, so a recent seal
cannot hide an earlier mismatch. Verification is read-only and never creates a
workspace, repairs data or reseals. Results are VERIFIED (exit 0), UNKNOWN for
unavailable evidence (exit 2), or INTEGRITY_FAILURE for corruption/mismatch
(exit 2). An integrity failure takes precedence over UNKNOWN across results.

Repeated sealing creates distinct revision-1 events. Existing events and times
cannot be overwritten or revised. Conflicting intent content under the same
revision fails. If seal admission fails after intent import, the command reports
that the intent is retained and no seal was stored; retry with that exact input.
Moving/removing the source leaves verification UNKNOWN even with archived text.

For TEST-ONLY fixtures use an explicit temporary workspace, for example
`eval-pilot --root /tmp/TEST-ONLY-seals seal-intent /tmp/TEST-ONLY-intent.json`
and `eval-pilot --root /tmp/TEST-ONLY-seals verify-seal /tmp/TEST-ONLY-intent.json`.
The local clock, hash and declared witness establish neither authorship nor
generation order nor externally witnessed time. They supply no quality verdict
or provenance promotion. An administrator replacing records and their hashes
is outside this local integrity guarantee. Canonical text, paths and witness
metadata remain private; public/embed output does not expose seals.

Private dataset snapshots include seal events for the exact intent revisions
already in their dependency history, including predecessor intents. Each event
has an artifact digest pin and retains its canonical source, file digest and time.
Unrelated intent revisions are excluded. Appending a seal affects only future
snapshots; earlier snapshots and exports stay fixed.
