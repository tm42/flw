# What lives where

Two things a newcomer gets wrong: which files are loaded whether you want them or not, and which
files are in git. Both are decided by where a file sits, so this says where.

## Loaded, or found

**Runtime documents are read on every run of something.** They cost context whether or not they
are relevant, so each has to earn that on the run where it earns nothing.

```text
core/skills/<skill>/SKILL.md        read when that skill runs
core/shared/context.md              read first by every skill
core/styles/terse_prose.md          read by every skill, and handed to every reviewer
.flw/extensions/<skill>.md          read on every run of that skill, in this repo only
~/.flw/config.toml                  merged under the project's; test, validate, ledger, kb
<project>/.flw/config.toml          merged over the global one; the same four
```

**Reference documents are found when someone goes looking.** Nothing loads them. They can be as
long as their subject deserves.

```text
docs/                               install, extending, measuring, this file
plans/*.md                          design prose: why something is shaped the way it is
plans/backlog/                      known and not yet specced, one file per item
README.md                           what flw is, and the commands
```

`docs/measuring.md` is the clearest case of the distinction: a protocol read perhaps once a
month, by a human pointing an agent at it. In the runtime tier it would tax every run of every
skill for that.

**The records are neither.** They are data with a schema, read by the commands that need them.

```text
specs/current.toml                  the contract — what is true when the work is done
specs/versions/<name>.toml          one per version — how that version came about
.flw/reviews/<team>.toml            a reviewer team, as data
```

## Tracked, or ignored — and nothing in between

**`.gitignore` is the only way something goes untracked.** A file that is neither tracked nor
ignored is an accident, not a decision, however deliberate it felt when it was created.

Three reasons, none of them tidiness:

- `flw-execute` forbids `git add -A` explicitly, because a blanket add sweeps such a file into a
  commit as though the run produced it. That rule exists because such a file once existed here.
- It lives on one machine. No clone has it, so any claim it makes about the project is a claim
  only one working tree can honour.
- `git status` is never clean, so a genuinely accidental file has somewhere to hide.

Today two kinds of flw record are ignored:

```text
.flw/reports/                       review reports — scaffolding, disposable once specced from
.flw/reviews/publish*.toml          a reviewer team written for one round, not for reuse
```

A review report is disposable because what survives it is the version record `flw-spec` drafts
from it, carrying the coverage line and any measurement forward. The report itself can then go.

A team config is normally tracked — the four in `.flw/reviews/` are, and a project copy of a
shipped team is meant to travel with the repo. The ignored pattern is for one written against a
particular round, whose lenses name what that round was worried about and mean nothing after it.

## References that do not resolve

Version records and design documents cite two kinds of thing you cannot open.

**Short commit hashes** — `1aa8775`, `9cb9255`, `cd4aca9` — name changes made before this
repository's history begins.

**Paths to files that are gone**: `docs/verified.md`, deleted with its rationale at
`specs/current.toml:58`; `.flw/reports/*`, gitignored by the rule above; and two `plans/`
documents retired during the v3 build.

**Both are labels, not directions.** They are kept because the sentence around each one is
still true, and replacing an exact reference with a vague one loses more than the dangling
reference costs. Where such a path appeared as an instruction to go and read it, it has been
rewritten; where it appears as the provenance of a claim, it stands.

## Amending this

It is a convention, not a rule the code enforces — nothing checks it, and `flw doctor` will not,
because flw runs no VCS command by stated principle. Edit it when the shape of the repository
stops matching it. That is the normal case, not a failure of the document.
