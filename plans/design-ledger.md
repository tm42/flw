# flw ledger — design document

**Status**: built, shipped, and corrected once since by an `eng` review that returned 27 findings.
It shipped as `flw ledger`; this document calls it `kb` throughout, because that was its name
while it was being designed. `flw kb` is a different command, designed in `design-memory.md`.
Fourth draft. The first was built around `decisions` alone and §4 is why that was wrong; the second
was reviewed, and the corrections are in §4, §5.2, §6, §7 and §12; the third called this `flw why`,
and §1 is why that was wrong.
· **Date**: 2026-08-27
· **Contract at**: 0.8.1
**Evidence base**: every number below re-measured against this repository's own documents on
2026-08-27, after the `silent-misses` run corrected it. The corpus therefore counts this document
and two version records of its own, which is why §7's example now matches four records rather than
two. The report
that prompted the second draft's corrections is at `.flw/reports/2026-08-27T-design-why.md`; the OKF
review that prompted the work is in §9.

---

## 1. What this document is

A design for one command that makes what flw has already written down **searchable and
addressable** — the contract, the version records, and the project's own prose.

It is a knowledge base over the project's own record. It retrieves text and never rewrites it, so it
answers no question by itself; it puts the paragraph that answers the question in front of you, with
the name of the document it came from.

**The third draft called this `flw why`, and that name was a reduction.** The corpus §4 measures is
not a corpus of reasons. Four of the eight output groups in §5.2 — CONTRACT, REMOVED, CHANGED,
DONE — answer *what is true*, *what is gone*, *what a version did*, and *what was built*. Only
DECISION and WHY answer a why-question at all. A name that frames every query as "why is it like
this" mis-sells the tool to the person typing it and, worse, biases the design: the third draft
ordered its output groups "from answer to lead" with the settled fork first, which is right if the
question is always why and wrong otherwise. §5.2 reorders them.

This is not a spec. It says what the thing is, what it refuses to be, and what is still open.
`flw-spec` turns it into a contract amendment afterwards.

## 2. The problem

flw accumulates reasoning as a byproduct of being used, and nothing reads it back. The only code
that walks the record set is `check_chain` in `core/scripts/validate_spec.py`, which takes each
file's `name` and filename suffix to fold a release number and discards the rest.

The cost is not hypothetical. In one session on 2026-08-26 the major/minor classification rule was
re-derived twice, because the decision that settled it sat in a record nobody could see from the
conversation. A settled decision that cannot be found is a decision that gets made again,
differently.

## 3. What this is not

| command | reads | answers |
|---|---|---|
| `flw validate` | every record, structurally | is this document well-formed and consistent with the set |
| `flw scout` | source files | what does the code here depend on |
| `flw-review` | code and prose, via agents | is this work any good |

`flw validate` is the closest and still the wrong tool: it parses every record and throws the
content away, because its job is agreement between documents rather than what any of them says.

## 4. The corpus, measured — and why the first draft was wrong

The first draft of this document built the command around `decisions[]`. That was a design decision
made without measuring, and the measurement refutes it.

**The corpus is 37 files**: `specs/current.toml`, the 27 records under `specs/versions/`, the two
team configs under `.flw/reviews/`, and the seven markdown files under `plans/` — 82,373 words,
499 KB. Two bodies of prose are excluded and §4.1 says why.

The table counts the two halves by different rules, because they are different kinds of file. For
TOML it counts **field content** — the prose inside `approach`, `desc`, `rationale` — and not the
keys, quoting and table headers around it. For markdown it counts the whole file. That is why
47,302 below and 82,373 above are both right and do not add up.

```text
specs/versions/  (27 records)                 specs/current.toml
  approach                    16,785 words      components: provides,
  dag task descriptions       13,946            properties, surfaces, impl   2,651 words
  decisions                    8,618            removed statements             410
  contract_edit                3,924            assumptions                    249
  summary                        571            open questions                 148
                              ──────                                        ──────
                              43,844                                         3,458

.flw/reviews/                  1,210 words     plans/  (7 .md files)       28,804 words
```

This document is inside the corpus it measures, so `plans/` grows as it is written and 28,804 is
today's figure.

**Decisions are 8,618 words of 47,302 in `specs/` — 18%.** A command built on them searches a sixth
of what has been written and answers "nothing was decided about that" for the other five sixths.

The tier the first draft missed entirely is **dag task descriptions: 13,946 words across 254
tasks**, and it is the most specifically searchable content in the repository. Task descriptions
name files and line numbers, so they are the only place that answers "what has been done to
`validate_spec.py`, and in which version".

So: search everything inside the boundary. Do not filter the corpus; **stratify the output**
instead.

### 4.1 The two exclusions

**`plans/*.html` — three files, rendered research reports.** Searching them means searching markup:
`code-graph-report.html` alone holds 73 whole-word occurrences of `font` and 16 of `background`, so
`flw kb font` would print CSS. What they say is already in the markdown beside them. `plans/` means
`plans/*.md`.

**`.flw/reports/` — 14 markdown files, 31,082 words, and gitignored.** This is the harder call,
because review findings are the same kind of content the corpus is made of, and the body is
comparable in size to `plans/`. It stays out because `.gitignore:9` excludes the directory: a
knowledge base whose corpus does not travel gives a different answer on every clone, and gives no
answer at all on a fresh one. flw's own doctrine agrees from the other side — a report is
scaffolding, and its durable half is copied into a version record's `approach` when the version is
specced. What survives is already in the corpus; what does not was meant not to.

Two consequences worth stating, because both are real costs rather than tidy ones. A finding that
was filed and never specced is invisible to this command, and the `flw-review` instruction §11.3
quotes — *do not report anything already deliberately decided* — is exactly the case where a prior
finding would have been worth surfacing. And this couples the corpus to a project's `.gitignore`,
so a project that tracks its reports still does not get them searched. Both are §12.

## 5. The command

### 5.1 Surface

```text
flw kb <term> [term …]        search the corpus, grouped by what kind of thing matched
flw kb --show <name>          one record or contract component, printed whole
flw kb                        census: what the record set contains, by kind
```

Multiple terms are AND. Quoted terms are phrases. Nothing written, nothing cached, no persistent
index: the 37 files of §4 are 499 KB and parse in well under a second, and the argument that settled
this for `flw scout` settles it here — an artifact on disk is a second copy that goes stale, and
regenerating costs less than noticing that it has.

### 5.2 Output is grouped by what kind of thing matched

The grouping is the whole design. It does the work a relevance score would otherwise do, without
inventing a score there is no signal for. Groups appear in this order, from **binding** through
**historical** to **reasoned**:

```text
── binding now ──
CONTRACT            what is claimed to be true — provides, properties, assumptions
REMOVED             what is deliberately gone, and the check that keeps it gone
── what settled it ──
DECISION            a fork that was settled, with what it was settled against
── what happened ──
CHANGED             contract_edit — what a version added or took away, and which one did
DONE                dag task descriptions — what was actually built, task by task
── what was reasoned ──
WHY                 approach prose — the reasoning, and what the work was not
REVIEWS             a team config's perspective — what a lens is told to hunt for
PLANS               design documents; may be superseded — see §6
```

REVIEWS is the correction the build found: the third draft counted the team configs as a
corpus tier in §4 and then gave the seven groups no home for them. It sits with the reasoned
tier because a perspective is prose describing an intent, and above PLANS because it is
current — a team config governs the next review, where a design document may already be
history.

The third draft led with DECISION on the grounds that a settled fork is the answer and everything
else is a lead. That holds for one question. Ask this corpus about `validate_spec.py` and the answer
is DONE and CONTRACT; ask it about an assumption and the answer is CONTRACT alone. What is
invariant is not which group answers but which groups **bind**: the contract is what the project
must be, a decision is why, and an `approach` is one person's reasoning on one day. Ordering by that
is true of every query.

**CONTRACT and CHANGED print overlapping text by construction**, because an applied `contract_edit`'s
payload becomes contract prose: all 17 records carrying one share at least 23 ten-word runs with
`current.toml` today, and the largest — `shape-independence` — shares 404. CHANGED still earns its
place: it is the only group that says which version introduced a sentence and what it replaced, so
it prints the version and the classification on every hit. Without those, the duplicate is only a
duplicate.

Within a group, newest record first — and "newest" needs saying, because the record set carries two
orderings rather than one. The 17 records named in the contract's `applied` order by their position
in it. The other nine sit before the legacy anchor, are named nowhere in `applied`, and order by the
version number in their filename. The two concatenate only because every one of the nine sorts
before `4.0`; and a named record like `stale-claims` has no number at all, so `applied` is the only
thing that can place it. Recency is a real signal where importance is not.

### 5.3 With a term

```text
flw kb locking

DECISION   install-robustness — whether to lock links.toml against concurrent writers
  chose    Do not lock.
  over     Take an fcntl lock around the read-modify-write, preventing the race outright.
           Lock behind a platform guard, with a fallback for anywhere fcntl is unavailable.
  because  fcntl is POSIX-only and this contract states no platform assumption anywhere, so
           a lock commits flw to POSIX by implication … [157 words, printed whole]

DONE       install-robustness · atomic-write
  "write through a temp file in the same directory as links.toml and os.replace onto it …"

WHY        install-robustness
  "…WHY NO LOCK. fcntl is POSIX-only and this contract states no platform assumption at
   all, so taking a lock commits flw to POSIX or adds a fallback path harder to test…"
```

Rationale and statements print **whole and verbatim, never summarised**. A paraphrased decision is a
decision misrepresented, and the tool has no model to paraphrase with and should not acquire one.
Long prose hits print a window around the match with the record named, because an `approach` runs to
1,201 words at its longest.

The example above prints one rationale twice, under DECISION and again under WHY, and that is the
exception rather than the shape. Measuring restatement as a shared ten-word run between a decision's
`rationale` and its record's `approach`: **four of 27 records, across 78 decisions**. The two groups
do not generally collapse into each other.

### 5.4 With `--show`

Two kinds of thing are addressable by name, and both are things the filesystem cannot find for you:

- **A record**, by its `name` — `flw kb --show shape-independence`. Names do not map to filenames.
  The record is in `shape-independence-major.toml` and the suffix is the classification, which is
  what you were going to ask the record about. `ls specs/versions/ | grep` is the current answer and
  it is worse than a lookup.
- **A contract component**, by its `name` — `flw kb --show 'validation and checks'`. There are five
  of them, they are nested three levels into the contract file, and a component's `paths`,
  `provides`, `properties` and `surfaces` are what somebody about to touch that code needs.

Rendering is the point rather than a nicety: `cat` on `shape-independence-major.toml` prints 255
lines of TOML with the `approach` as one unwrapped string. `--show` prints the same content as
paragraphs, the dag as its phases and tasks, and each decision as chose / over / because.

Record names are kebab-case and component names are prose with spaces, so the two namespaces cannot
collide today. If a future name is ambiguous, print both and say so — never guess.

### 5.5 With no term

A census rather than a listing: how many of each kind exist, the newest few in each, and the
standing contract state — assumptions, open questions, what is removed. Enough to know what is there
and what to ask about, and the natural first thing an agent runs in a repository it did not set up.

### 5.6 No silent caps

When a group has more matches than it prints, it says so and says how to see the rest. A truncated
result set that does not announce its truncation reads as a complete answer, which is the failure
this command exists to prevent, one level up.

## 6. `plans/` is searched, and quarantined

28,804 words of design reasoning sit in the seven markdown files under `plans/`, against 47,302 of
field content in `specs/`, and this document is one of them. Excluding them would drop the largest
body of reasoning in the repository outside the records themselves.

The markdown is not current by construction. `specs/` is validated, ordered, and linked to a
contract; `plans/design-v3.md` opens with **"The design is history."** A superseded answer presented
beside current ones is worse than a missing answer, so plans get their own group, last, labelled as
possibly superseded. Not a flag: excluding them by default hides two fifths of the corpus behind an
option nobody will find, and including them silently mixes what is true with what used to be.

## 7. Matching

Whole words, case-insensitive, with the obvious plural and participle forms. This is not a
preference. Measured against this record set:

```text
substring    "lock"                        16 of 27 records matched
whole word   lock|locks|locking|locked      4 of 27 records matched
```

The 16 match through `block` and `blocked_by`. The records hold 60 whole-word occurrences of `block`
and its forms against 37 of `lock` and its forms, and 35 of those 37 sit in three records:
`install-robustness`, which decided not to take one, and the two records that quote this
measurement. Substring matching returns over half the corpus for a one-word query, which
reads as *nothing specific was decided* when the opposite is true.

## 8. Deliberately not built

- **No summarisation.** It surfaces text and never rewrites it. §5.3.
- **No persistent index, cache or database.** §5.1.
- **No relevance score.** The grouping in §5.2 replaces it. A score over 37 documents is tuning with
  no ground truth to tune against.
- **No writing.** `flw kb` never modifies a document. Deciding is `flw-spec`'s job.
- **No cross-repository reading.** One project's documents, resolved by `nearest_project()` like
  every other command.
- **No code search.** `flw scout` ranks source files and `grep` exists. This reads what was written
  *about* the work, never the work.
- **No natural-language query.** `flw kb why did we not lock` is four AND-ed terms and will match
  nothing. Terms, not questions — and the name no longer implies otherwise.

## 9. Export formats are deferred, not refused

The prompt for this was Google's Open Knowledge Format (v0.1, June 2026): a directory of markdown
files with YAML frontmatter, one required field, no SDK. The observation behind the suggestion is
right — flw's records are exactly the durable *why* that agents need and that nothing collects.

Adopting it is still the wrong first move, and the reason is sequencing rather than principle. flw's
value is in TOML validated against schemas; OKF needs an exporter, and an exporter is a separate
tool writable at any time. The second consumer does not exist — flw's documents are read by agents
in the same repository, which read `specs/` directly. And a generated bundle is a third copy of what
the contract and records already hold, which is the failure `stale-claims` and `install-robustness`
spent two versions removing.

The extraction is the hard and useful half. Once it exists, emitting OKF — or JSON, or anything else
— is a formatting pass over data already in memory. A knowledge base with no way to hand its
contents to another tool is visibly incomplete in a way a `why` command would not have been; that is
an argument for building the export second, not for refusing it.

## 10. Why a new command, and why `kb`

flw has 13 subcommands and a stated preference against growing that number. The alternative
considered was `flw scout --decisions`: rejected, because `scout` ranks source files in two
languages and knows nothing about `specs/`. Folding this in makes one name cover two tools, and
`flw scout --help` already spends its length explaining what its ranking does and does not mean.

`kb` names the thing as a store rather than as a question, which is what §1 corrects. It has one
cost and it is worth stating: it is the only initialism among fourteen subcommand names, all of
which are otherwise words. The names that are words all mis-sell it. `why` reduces the corpus to its
reasons. `ask` and `know` imply something answers, and §8 refuses the model that would. `find`
invites the code search §8 also refuses, and `grep` already owns that verb. `recall` reads as a
model's memory of a conversation, which is the opposite of a durable record on disk.

## 11. Where it sits in the machinery

### 11.1 The CLI and the script

A fourteenth subcommand in `cli/flw.py`, dispatching to `core/scripts/ledger.py` — the pattern `test`,
`scout` and `validate` already follow.

**This needs a contract amendment before a line is written.** The "validation and checks"
component's `paths` are five named entries:

```toml
paths = ["core/scripts/validate_spec.py", "core/scripts/run_tests.py",
         "core/scripts/scout.py", "core/scripts/scout.mjs", "tests/"]
```

A path naming specific files does not extend to a sibling, so `core/scripts/ledger.py` is covered by
nothing and `flw-execute` is required to stop on it. That is the rule working, not an obstacle: the
component is named for validation and would be acquiring a search tool, so the amendment is where
somebody decides whether that is the right home or whether the component is misnamed. `scout.py`
already sits there and is not validation either.

### 11.2 The corpus reader is already half-written

`validate_spec.py` walks the whole record set today — `check_chain` opens every file,
`parse_record_filename` splits name from classification, and the fold reads `applied` in order.
`ledger.py` needs exactly that walk and then keeps what validation throws away.

Two of those in one repository is the duplication flw removes on sight, so the walk gets extracted
and both call it. Which module owns it is a spec question, not a design one.

### 11.3 The skills — one strong case, and three weaker than they look

**`flw-review` is the strongest, and it is not a new idea.** The discipline injected verbatim into
every reviewer already says, at `core/skills/flw-review/SKILL.md:166`:

> **Do not report anything already deliberately decided.** Check the contract, the version files
> under `specs/versions/` before calling something a mistake — a thing recorded as a decision with a
> rationale is not a finding.

That instruction exists, is given to every reviewer, and has no tool behind it. A reviewer is
dispatched into a fresh context precisely so it carries none of this repository's history, and is
then told to check 27 records by hand before filing anything. `flw kb <the thing I am about to call
a mistake>` is that instruction, executable.

**`flw-spec` is second.** Step 2's "Look before declaring" searches the repo for *names and symbols*
a component would introduce — the code-level check. There is no reasoning-level equivalent, which is
exactly how the major/minor rule came to be re-derived twice in one session while a settled decision
sat in a record.

**`flw-execute` is weak.** It already has the record it is running open, and `approach` outranks
`dag` by its own rule, so the reasoning that governs its work is in front of it. The only gap is
prior versions' decisions constraining the current one, which is real but rare.

**`flw-research` is near zero for search and non-zero for `--show`.** It exists for repositories flw
did not set up, and those have no records to read. But `flw kb` with no term is a census, and a
repository that already has a contract is exactly where a research pass would start.

### 11.4 What does not change

- **No configuration.** Not a check, so nothing in `.flw/config.toml` and nothing in
  `success_criteria`.
- **No schema change.** It reads the documents as they are. If it needed a new field, the design
  would be wrong — the value of the corpus is that it was written for other reasons.
- **`flw doctor` does not learn about it.** Doctor verifies an install; this reads a project.
- **No skill depends on it.** Skills read `specs/` directly today and would keep working if the
  command were deleted. It makes an existing instruction cheap to follow; it does not become a step
  anything requires. That is the difference between a convenience and a dependency, and it decides
  how much this is allowed to break.

## 12. Open questions

- **A later record can overturn an earlier one, and nothing marks it.** §6 argues that a superseded
  answer beside a current one is worse than a missing answer, then applies that standard only to
  `plans/`. `specs/` has the same problem: `v3.0` adopted aider's weight heuristics and `v4.4`
  deleted them — *"THE WEIGHTING EARNS NOTHING AND GOES"* — and `flw kb weight` matches six records
  with nothing saying which of them still holds. Newest-first is the only mitigation and it is a
  weak one, putting the reversal above the adoption without saying that is what happened. The fix
  that suggests itself is a field marking a record superseded, which §11.4 rules out and for a
  reason that still stands, so this is open.
- **The corpus boundary is a project's `.gitignore`, by consequence rather than by design.** §4.1
  excludes `.flw/reports/` because this repository ignores it, and that reasoning does not
  generalise: a project that tracks its reports gets the same exclusion and no way to say otherwise.
  Whether the rule should be *what is tracked* rather than *what is in these directories* is open,
  and answering it means reading a VCS, which no flw command does.
- **Does surfacing this help?** The contract carries a standing open question about whether a ranked
  structural scout escapes the published negative result on static repo overviews. This is the same
  class of doubt. The case here is narrower — it prevents re-deciding something already settled, a
  specific failure with a specific cost, observed in this repository on 2026-08-26. That is an
  argument, not evidence.
- **Do eight groups survive contact?** §5.2 orders them by what binds. Two or three may turn out to
  be noise, and the honest way to find out is to use it. Collapsing groups later is cheap; a score
  fitted to them now would not be.
- **Does `--show` earn a flag, or is it the whole command?** §5.4 argues addressing is worth having
  because names do not map to filenames. If it turns out to be what people run and search is the
  rarity, the surface is upside down and `flw kb <name>` should resolve to a record before it
  searches for a term.
- **What happens at 300 records?** Measured against 27. Nothing here proposes paging, date filters,
  or narrowing by record. Deferred deliberately: guessing at the shape of a problem nobody has is
  how the scout's weighting heuristics came to be built, measured, and deleted.
- **Does `plans/` quarantine actually work?** §6 assumes a labelled trailing group is enough to stop
  a superseded answer being read as current. If it is not, the alternative is dropping `plans/`
  entirely rather than adding a flag.
