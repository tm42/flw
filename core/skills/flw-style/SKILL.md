---
name: flw-style
description: Find your own instances of a writing failure the user has just named, then stop doing it in the same turn. Takes a flag for the category — vocabulary, length, formatting, shape, coherence — or free-form critique, and -h to list them. It names violations and never restates the rules, because restating them is measured as the intervention that does not work.
argument-hint: "[--vocab|--verbose|--format|--shape|--coherence] [critique] [--last N] [-h]"
---

# flw-style — name what drifted, then stop doing it

## `-h` or `--help`

Print the block below verbatim and stop. Do no correction, read no transcript, run nothing.
These are this skill's flags. `flw style check --help` is a different surface and lists only
`--last`.

```text
/flw-style [flags] [free-form critique]

  --vocab       filler, praise, hedging, balanced aphorisms
  --verbose     length out of proportion to what was asked
  --format      trailing spaces, untagged fences, headings on a short answer
  --shape       what the reply is, and whether the decisions come first
  --coherence   contradicting yourself across the session, or a recorded decision

  no flags      all five
  free form     e.g. "you're incoherent in judgement this session" — goes in as the
                critique; find the instances rather than agree with it
  --last N      how many of your own turns to re-read (default 5)
```

## What this skill is for

The user has named a failure. Your job is to find your own instances of it and then not do
it again in the same turn. The correction **is the next reply**, not a report about the
drift.

**Do not re-read the rule.** It is already in your context as the output style, and reading
it again is the intervention measured at 6–12% (Drift No More?, arXiv:2510.07777) — while
naming your specific violations is measured at +8.2 per round and +19.3 cumulative
(MultiCodeIF, arXiv:2507.00699). The reason restating fails: constraint restatement accuracy
is 97.3% while knows-but-violates runs 8–99% (DriftBench, arXiv:2604.28031). An agent that
can recite the rule is not helped by reciting it.

The refs in the table below are there to cite by name when you quote an instance, and for
the user to check your work against. They are not a reading list.

## 1. Re-read your own last turns

Default 5, or `--last N`. They are in your context already, so this costs nothing — look at
what you actually wrote, not at what you remember writing.

**Past a compaction, or further back than your context holds**, run `flw style check` for
the countable rules. It reads this project's transcript and works on Claude Code only; Codex
and OpenCode write no session record it parses. It cannot read a session whose newest
transcript belongs to a dispatched agent, so a session that spawned subagents gets nothing
from it — say so and work from context instead of reporting the command's refusal as a
finding.

## 2. Find instances of what was flagged

| flag | what to look for | cite |
|---|---|---|
| `--vocab` | qualifiers that change nothing, evaluative words with no measurement, a longer word where a plain one exists, balanced aphorisms, an abstraction as the subject of a verb it cannot do, a pre-assembled figure of speech, a finding held back for effect, reaction openers, closing offers, announcements, signposts | `terse_prose.md` §Words, §What to leave out |
| `--verbose` | your reply's prose word count against the word count of what was asked; a short question answered at length; the same point made twice at the same level of detail | `terse_prose.md` §Length, §What to put in |
| `--format` | a line ending in two trailing spaces, a fence with no language, a heading deeper than `###`, headings on a reply to a short question, a paragraph hard-wrapped across several lines | `terse_prose.md` §Structure and formatting |
| `--shape` | the reply never says what kind of thing it is; decisions you made that the user could have made differently are not first, or not named at all; a sentence that has to be read twice | `terse_prose.md` §Before you write, §Sentences |
| `--coherence` | a recommendation that contradicts one you made earlier in this session; a thing you argued against and then did; a decision already settled in `specs/versions/*.toml` that you re-proposed | the record's own `decisions`, found with `flw ledger <term>` |

With no flag, look for all five. With free-form text and no flag, take the text as the
category and find instances of that.

**Count what is countable rather than judging it.** Word counts, line widths, heading
counts and the ratio of a reply to its question are arithmetic. Do the arithmetic.

**You are a biased reader of your own prose** — you wrote it because you believed it was
right. What makes this work is that the user named the category, so you are searching for a
named failure rather than judging quality. Searching for a named failure finds more.

## 3. Say what you found, in the smallest form that identifies it

One line per instance. The quote or the number, and the rule's name. Nothing else.

```text
--verbose   578 words and 2 headings in answer to "let's do it" (3 words)
--vocab     "the critic earned it" — evaluative, no measurement behind it
--coherence recommended retiring the review teams, then dispatched two
```

**Three instances at most, even when there are more.** A longer list is a report, and a
report about verbosity is the disease. If you found nothing, say the last N turns were clean
and stop — an empty result is the common case in a tidy session and not a reason to look
harder.

## What never goes in the output

- An apology, or any sentence about how you feel about the drift.
- A summary of the drift, or a count of how many times it happened.
- The rule, restated. The user has it; so do you.
- A promise to do better. The next reply is the promise or it is nothing.
- A proposal for a new rule, a new lint or a new skill. That is a separate request.

## 4. Then behave differently, in the same turn

Whatever the user asked for alongside the flag, answer it now, without the flagged failure.
This is the only part of the skill that matters. The lines in step 3 exist to make this part
possible, not to stand in for it.

## Lane

Reads and reports. It changes no file, fixes no other prose, and never edits
`core/styles/terse_prose.md` — a rule that needs changing is the user's call and a separate
request. For prose already written to disk, `flw style lint <paths>` reads files rather than
turns and works on every host.
