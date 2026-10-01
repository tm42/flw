part 1: Separate the product contract from delivery slices.
One stable feature contract should describe the final behaviour. Pool request-specific records should describe how that contract is delivered. FLW should model:
1. Feature contracts span all integrated, all related, involved services.
2. Repo-specific implementation contracts beneath it.
3. Pull request-specific slices with explicit dependencies.
4. A generated pull request dependency graph.
5. Superseded slices that are visibly dead and excluded from execution.
6. Acceptance criteria mapped from the feature to each slice. This is when acceptance criteria is provided, for example, in a Jira ticket or something.

second, add lifecycle reconciliation.
FLW needs a command that compares its state with Git and the pull request host.

$flw reconcile

it should identify:
1. Records whose implementation has merged.
2. Pending records superseded by later design decisions.
3. Branches behind their dependency or master.
4. Missing or unexpected work trees.
5. PR descriptions whose dependency graph is outdated.
6. Contract components that no longer match the deliverers fileset.
7. Checks that refer to tests belonging to a later pull request.
The users should approve changes, but FOW should prepare the complete reconciliation. Today, stale records survive indefinitely unless somebody remembers to clean them up.

third, make multi-repo features first-class.

The current repo-local model is useful, but cross-repo contracts need an explicit home. FLW should support a lightweight feature workspace with declared repo roots, without writing every symlink. Under a common folder as one project, that workspace should record:
1. The authoritative owner of each field
2. Consumers that duplicate the contract
3. Required release ordering or proof of order independence
4. Cross-repo acceptance tests
5. Feature flags and deployment configuration
6. Which parts can be merged independently
A schema change, such as content to items or adding some sort of new field, should immediately show every affected repo.

4th, turn interface contracts into executable checks.

The example repo contract was hand-declared, and both repos involved could pass independently while disagreeing on field names, aliases, or nullableability. FLW should let a feature define a small shared wire fixture, some sort of an object where the feature would have some schema for that. Each reaper would validate that fixture against its own schema.

This does not require generated clients or a new shared package. It simply turns an important written contract into a cheap executable check. The same mechanism could cover error codes, endpoint path, and required request fields.

5th, Improve knowledge provenance and staleness.

flw know is available, but directory-level revision tracking is noisy. In the runner repo, unrelated changes marked six knowledge pages as changed, even though their claims may still be correct. Knowledge claims should be able to cite their evidence. Source would be a code file and a class reference, for example, something.py:class name. Then FLW could distinguish:
1. The cited symbol changed.
2. Another file in the directory changed.
3. The search disappeared to move.
4. The claim was manually verified against the new revision.
5. Across-repository dependencies changed.

It would also help to distinguish three types of material:
A. Facts: what the code does now.
B. Rules: how future work should preserve a boundary.
C. Decisions: why one design was chosen over another.

6. Make specification amendments cheaper.
Strict path contracts caught real gaps, such as missing code files. That was very useful, but the amendment process was heavier than the risk justified. An executor should be able to emit a structured proposal using the same TOML structure:
- scope
- amendments
- file name
- reason
- product behaviour
For example, that would be a

scope amendment:
    add path/path/path/something.py
    reason: existing registration point required by the accepted behaviour
    product_behaviour unchanged

After approval, FLW should update the contract and resume from the stopped phase. It should not require a broad respect for a mechanically necessary integration file.
Conversely, a change from durable jobs to process local buffer, for example, is architectural and should require a new contract version. FLW could classify the difference and recommend the right path.

7. Scope checks per delivery slice.
The executor agent of one of the steps/phase on the spec stopped because the shared FOW check referenced the test that belonged to a later spec. That was correct according to the file, but the file did not represent the current slice. Checks should belong to:
1. the feature
2. a repo
3. a delivery slice
4. a phase within the slice
An executor should run only checks whose required path exists in the slice. A final integration validator can run the complete feature set.
FLW should also understand repo test ownership:
- executor: formatting style and focus tests
- validator: focus tests plus the allowed focus use
- user-owned: expensive or environment-sensitive checks
- infrastructure: failure (Docker or whatever other service), tunnel failure that is unrelated to the diff itself, etc.

8th, Add work tree and stack awareness.

Large amounts of effort in the current work went into answering which directory this branch is in. Replace stacked branches and repair dependency diagrams. FLW should maintain a local work tree registry

slice, its branch, its work tree, and the base of the branch

Useful operations would include:
1. Show the real stack.
2. Detect a missing work tree.
3. Create the next slice from the correct base.
4. Rebase descendants after parent changes.
5. Regenerate every PR's highlighted dependency diagram.
6. Detect that the pull request host and local branch disagree.

9th, Add review feedback ingestion.

Review comments repeatedly cause the cycle of writing comments, deciding whether they require respect, preparing and fixing, updating and replying to drafts, and rebasing descendants. FLW could ingest comments into a local review ledger and classify each as:
1. Behavioural control change
2. Correctness defect
3. Missing test
4. Compatibility question
5. Style or convention
6. Rejected suggestion with rationale
By comments here, we mean comments from pull requests.
It should then show which comments require a specification amendment and which can be fixed inside the existing contract. Draft replies should stay local until the user explicitly publishes them manually.

10th, make operational verification part of the contract.

The implementation passed tests, but the most valuable evidence came from a real run. FLW should support a post-deployment verification section with evidence fields. This should remain separate from unit and functional tests. It verifies configuration, feature flags, deployment topology, and external services the AWS local tests cannot prove.

11th, Encode autonomy boundaries.
flw can eliminate much of the need for a separate manager agent if it records:
1. decisions already approved
2. decisions that still require the user
3. files and behaviour the executor may change
4. which failures permit retry
5. which failures require a contract amendment
6. which tests and commits are authorised
7. which external alterations remain user-owned
A spec agent plus an executor and a final reviewer is usually enough. A management agent becomes useful only when several deliver slices are active concurrently. Without a reliable shared ledger, that extra agent mostly repeats context and raises costs.

suggested priority:
1. Life cycle reconciliation and supersession
2. Product contract versus pull request deliver slices
3. Multi-repo interface contracts and executable features
4. Work tree branch and pull request tag registry
5. More precise knowledge provenance and sterness
6. Review comment ingestion
7. Post-deployment verification records
The core lesson is that FOW already constrains execution well. Its next step would be maintaining truth as the feature changes shape. That would give agents more autonomy because they could reliably determine what is current, what has been approved, what remains, and what evidence proves completion.
