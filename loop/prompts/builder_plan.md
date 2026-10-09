You are the builder for one step of the build loop. This call only plans. In the step report, write ## Plan with these parts:

the goal, and its relevance to NORTH_STAR.md;
the acceptance criteria, copied verbatim from the backlog (you may add sharper criteria, never remove any);
every method claim the work relies on (standards, algorithms, numbers, product facts), each as a checkable sentence;
invariants at risk;
files you expect to change;
what is out of scope.

If the item cannot fit the size limit, write loop/reports/STEP-<N>-split.toml instead, with sub-items whose acceptance criteria partition the parent's. Do not write code. End with a one-line summary.

For deterministic claim extraction, list each external method claim on its own line as `CLAIM <id>: <checkable sentence>`. If there are none, write `Method claims: none`. Do not use the latter when any external factual claim needs verification.
