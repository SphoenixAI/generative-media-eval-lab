# Research identifier hotfix

The step 0002 stop was a harness infrastructure failure: the plan and evaluator both emitted `C1` before the researcher ran. The original step remains ABANDONED. Its evidence is unchanged; `STEP-0002/infrastructure-classification.json` appends the classification and pins the original decision hash. L02 has zero product retries and remains eligible. Its existing evaluator findings remain evidence, not a completed product-failure decision.

The harness assigns request handles when preparing the research view. After the researcher output passes the strict schema, it assigns `R<STEP>-C<INDEX>` IDs by output order, independently of every model-authored ID. A multiset comparison and occurrence queues preserve each requested claim, including identical claims. Reordered output is mapped to the correct request occurrence. No ID-based deduplication occurs.

`research.raw.json` preserves the unmodified role output as non-authoritative evidence. The canonical `research.json`, research view, reports, ledger, enhancer input, amendments and decisions use harness IDs. Normalization is deterministic and hash-checked on replay. New IDs are checked against the entire ledger; historical ledger rows are not rewritten. Step allocation also checks committed history, so an empty RUNS directory cannot reuse a historical number.

Proposal references must use harness-issued request handles. An unrecognized reference is retained in raw evidence, recorded as unresolved, and its proposal is restricted to human review. The harness never guesses which duplicate label was intended.

The full dry run now explicitly reopens L00 only inside its disposable clone. It exercises a colliding plan/evaluator input and a researcher output containing two `C1` labels, against actual gates and a local bare remote. Real backlog state, RUNS, and remotes remain outside that fixture run.

## Other identifier classes inspected

- Evaluator `blocking_findings.id`: sets in `loopctl.decision` can collapse repeated labels.
- Evaluator `prior_findings.ref` and enhancer `resolutions.ref`: dictionaries in `loopctl.decision` can overwrite repeated references. A finding identity shared across rounds needs a separate contract.
- Proposal IDs: already assigned by the harness as step-scoped IDs. Research proposal references are handled by this hotfix.
- Plan amendment research references: now checked against canonical research IDs; G11 continues to require an affecting CONTRADICTED or OUTDATED claim.

`P-HARNESS-IDS-01` records the finding/response work as PROPOSED, without auto-approval. No evaluator identifier contract, product code, accepted artifact, invariant, retry limit, or continuous-mode limit was changed in this hotfix.
