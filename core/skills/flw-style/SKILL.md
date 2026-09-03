---
name: flw-style
description: Report what the writing style has drifted from in this session's own recent replies, and repair it forward. Use when the prose has gone off — wrapping lost, structure gone, filler words back — or after a long session. It names violations and never restates the rules.
argument-hint: "[--last N]"
---

# flw-style — what drifted, not what the rules are

## Do this

```sh
flw style check
```

Pass `--last N` when the request names a number of replies. Default is 10.

## Then act on what it named

Fix it forward in the next reply. Do not apologise, do not summarise the drift, and do not
restate the rule that was broken — the rules are already in context, which is exactly why
repeating them changes nothing.

**Why this skill does not print the style.** Models restate a constraint accurately 97.3%
of the time while still violating it, so an agent that can recite the rule is not helped
by reading it again. Naming the specific violation is the intervention with a measured
effect. That is the whole difference between this skill and a reminder.

## When the output is empty

Say the last N replies were clean and stop. An empty report is the common case late in a
tidy session and it is not a reason to look harder.

## When it cannot find a transcript

`flw style check` exits 1 and says so. That means this host keeps no transcript where flw
reads them, and there is nothing to measure. Say that; do not guess at your own prose from
memory, which is the bias the command exists to route around.

Under concurrent sessions on one project it reports the newest transcript holding prose,
which may not be this one. It prints the path it read — check that the path is this
session's before acting on the counts.

## Lane

This skill reads and reports. It changes no file, fixes no other prose, and does not touch
`core/styles/terse_prose.md`. For prose already written to disk, that is `flw style lint
<paths>`, which is a different command over a different rule set: geometry against files,
vocabulary against replies.
