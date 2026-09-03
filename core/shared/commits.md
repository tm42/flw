# Commits

What a commit is, what its message says, and what never appears in one. Every skill cites
this file; none restates it.

## What a commit is

**One part of the product, named from the outside.** Not one file, not one fix, not one
bug. The subject names what a user has — a capability, a command, a document — rather
than the file you edited or the defect you chased.

**It carries everything that changed for that part**: the code, the check that proves it,
the prose that describes it, the contract sentence that claims it. Not the fix in one
commit and its test in another.

**Two changes to the same part, in the same step, are one commit** — even when each could
stand alone. The four tests below are a floor, not the grouping.

A commit is right-sized when all four hold:

1. **Complete.** A reviewer reading only this commit has what they need to judge it. A fix
   without its check cannot be judged; a check without its fix is red.
2. **Verifiable alone.** Every declared check passes at this commit. A red commit poisons
   `git bisect` for everything after it.
3. **Not divisible** without breaking 1 or 2. If splitting it yields a half nobody can
   verify, it was one commit.
4. **Not mergeable** with its neighbour without "and". If the merged subject needs "and"
   between unrelated halves, it was two.

The test that settles the rest: **could this be a line in a release note?** "install and
doctor now report what is actually on the machine" is a part. "Corrected a line number" is
not — it folds into whatever part owns that document.

## Fold by default

**A follow-up that completes, corrects or tests something already in this branch belongs
inside it.** The history records what changed, not the order you discovered it.

Never its own commit:

- a fix to something you introduced earlier in this branch
- a lint or formatting fix for this branch's own code
- a test for this branch's own change
- rewrapping, renaming, reordering

**The consequence: commit at the end of a verified step, not at each discovery inside it.**
A dirty tree mid-step is fine. Folding after the fact rewrites every commit above the one
you touch, and that rebuild is where the mistakes happen.

Neither half of that repair needs a terminal. `GIT_SEQUENCE_EDITOR=true git rebase -i
HEAD~3` runs without one, and a `sed` script in that variable squashes or reorders. One
file's changes split across two commits with `git diff -U0`, then `git apply --cached
--unidiff-zero` on the hunks that belong to the first. So a partition you can describe is
one you can make, and a red commit below the tip can be fixed where it stands.

**Measured, on flw itself.** Two review rounds were executed under rules that covered
only the message. They produced 44 commits for work that reads as 9 — same tree, every
subject a line you could put in a release note. Nine of the 44 existed only because the
same defect was found twice and its correction committed separately; merged, each is one
coherent change rather than a fix and its repair.

## The message

**One line naming what changed and how.** Test the subject two ways: someone who has not
seen the diff can say what it did, and someone scanning ten subjects that all touch this
file can pick this one out.

- Verbs that name an action: add, delete, rename, refuse, pin, parse, stop, only.
- Not verbs that name an intention: harden, improve, enhance, clean up, tidy, polish,
  handle, address, better, robustify. They fit every commit ever made.
- Not a count of what was done — "five fixes", "three lenses" — and not the reason
  standing in for the change: "fix what a reader could not follow" names neither.

A body only for what the diff cannot show: the reason, the rejected alternative, the trap.
Most commits have none.

The sentence itself follows `$FLW/core/styles/terse_prose.md` like any other writing.

## What never appears

- A trailer naming a tool, a model or a session. The work is the user's, whoever typed it.
- `Co-Authored-By`, for the same reason.
- A count of what was done.
- Emoji.
- An "and" joining two unrelated halves — that is two commits telling you so.

## Never leave a commit that fails a declared check

Every commit passes on its own, not only the last one. Verify before committing, and if a
commit is already made and red, fix it in place rather than committing on top — a green
tip over a red middle is a history nobody can bisect.
