# What the style check does not measure — design document

- **Status**: draft 2, superseded in part. §5.2's ranking was not built: the user redirected to a
  user-named failure instead, which needs no transcript and so works on every host, and that shipped as
  `skills-flag-what-drifted`. What stays live here is §4's measurement, §4.4's transcript-selection defect and
  §5.3's fix for it. Read §5.2 as a rejected option, not a plan.
- **Date**: 2026-10-06
- **Revision every number below was taken at**: `ddd0c49`
- **Transcript measured**: this session, `b0ea3cb5-1cb6-41f2-90f4-20b6774116dc.jsonl`, 1,256 textual replies

## 1. What this document is

A design for two changes to `flw style check`: it should see the question a reply answered, and it should
report the replies whose length is furthest out of proportion to it. Plus one bug fix that stops the command
reading this session at all.

It is not a change to `core/styles/terse_prose.md`. The rules are already right and already in context.

## 2. The problem

The user's complaint, in their words, is prose that is "dense, yet empty" and "really hard to read". The
command built to catch style drift reports this session as almost clean, and it is not wrong about the rules
it checks — it is checking the wrong things.

`a-rule-nothing-breaks` already established the mechanism and the evidence:

| intervention | measured effect |
|---|---|
| restating the rules | 6–12% (Drift No More?, arXiv:2510.07777) |
| periodic goal re-injection | negative result (When Attention Closes, arXiv:2605.12922) |
| naming specific violations | +8.2 per round, +19.3 cumulative (MultiCodeIF, arXiv:2507.00699) |

and the reason restating fails: constraint restatement accuracy is 97.3% while knows-but-violates runs 8–99%
(DriftBench, arXiv:2604.28031).

So the mechanism is correct and shipped. What is missing is that its rule set cannot express the failure the
user is reacting to, because every rule scores one reply's text in isolation and never sees what was asked.

## 3. What this is not

**Not a new rule in the style guide.** Nothing here edits `terse_prose.md`. Adding a sentence about reply
length would be the 6–12% intervention the table above rules out.

**Not a blocking check.** `flw style check` returns 0 on findings today and keeps doing so. The report is the
intervention; a failing exit code would make the command something to route around.

**Not a hook.** A Stop hook of type `prompt` was already rejected in `a-rule-nothing-breaks`: on `ok:false`
the reason is fed back and the turn continues, so the corrected reply is appended beneath the uncorrected one
the user has already read.

**Not a judgment about whether a long reply was warranted.** §5.2 explains why the design reports a ranking
instead of deciding.

## 4. Measured

**The method, because two earlier drafts of this section disagreed with each other.** One exchange is one
qualifying user turn plus every assistant text block until the next one; records with `isSidechain`,
`agentName`, `isMeta` or a `tool_result` block are dropped, and so are turns opening `Caveat:` or
`[Request interrupted`. A reply's length is its prose words with fenced blocks removed. The relay turns that
carry a dispatched agent's report back into the conversation are excluded from the question counts: they are
not the user asking anything, and a 700-word relay counted as a question moves the median it is meant to
measure. The script is one file and prints all of this before its figures.

The transcript holds 567 exchanges that got a reply, 203 of them relays.

### 4.1 Eight of twelve rules are at zero

`reply_findings` over the last 200 main-agent replies, 32,970 raw and 30,146 prose words. Twelve rules, not
the nine in `REPLY_RULES` — `over-120`, `missing-two-spaces` and `fence-untagged` are added in
`reply_findings` at `style_lint.py:268`:

```text
missing-two-spaces  402      plain-word        0      reaction-opener   0
over-120            313      aphorism          0      closing-offer     0
qualifier            19      participle-tail   0      announcement      0
evaluative            3      fence-untagged    0      signpost          0
```

The two that fire in volume are geometry: line width and trailing spaces. The vocabulary rules — the ones
aimed at filler, praise and padding — find almost nothing. A reader who finds the prose unreadable and a
checker that finds it clean are looking at different properties.

Both geometry counts are window-sensitive: `missing-two-spaces` moves between 402 and 470 across nine
replies of drift. Treat them as an order of magnitude, not a measurement.

### 4.2 What the user is reacting to, and it is not vocabulary

The last 45 non-relay exchanges. 25 of their questions are under 12 words; the median reply to those is
**184 prose words**, and 8 of the 25 were answered with section headings. The five worst, against any
question under 20 words:

```text
reply words   headings   the question
        755          3   what would you suggest next? speaking globally, … (16 words)
        645          4   look at ~/codex-feedback-real-world-work.md (3 words)
        583          3   what is your assessment of the current state? (8 words)
        578          2   let's do it (3 words)
        546          3   all makes sense. do you think we're ready for a spec? (11 words)
```

`let's do it` is the clearest case in the set: three words of assent, 578 words back, two headings. Nothing
in it was asked for.

### 4.3 A threshold is the wrong shape

Sweeping cutoffs over the same 45 exchanges:

```text
question ≤   reply >   fires
       12       150      14
       12       200      11
       20       200      17
       20       300      13
```

At every setting the fires include the 755-word reply to "what would you suggest next? speaking globally,
including agentic guidance and token economy" — a short question that explicitly asked for breadth, where
length is defensible. A regex cannot distinguish that from "where we at". A threshold therefore reports false
positives at any cutoff, and a check that cries wolf is one its reader learns to skip.

### 4.4 The command cannot read this session

`flw style check` exited 1 twice today with "the newest transcript holds 54 replies and all of them are a
dispatched agent's … run this from the session you want measured, not from a dispatched agent". The diagnosis
was wrong: the caller was this session, which had dispatched four subagents.

`session_transcripts` is correct — it returns every matching transcript newest first, and its docstring says
"The caller takes the first that actually holds prose." The caller does not. The loop opens at `cli/flw.py:1312` and the early return is at `:1336`:

```python
for candidate in candidates:
    found, dispatched = engine.read_replies(candidate, args.last)
    if found:
        transcript, replies = candidate, found
        break
    if dispatched:
        ...
        return 1          # <- leaves the loop instead of trying the next candidate
```

A subagent transcript being newest does not mean the caller is a subagent. It means the caller dispatched
one, which is the ordinary case for any session that uses them. The `if transcript is None` branch after the
loop already handles the real case — no candidate anywhere holds a main-agent reply — which is what a session
running inside a dispatched agent actually looks like.

## 5. The design

### 5.1 Parse the question, which nothing currently does

`read_replies` never opens a user record. `style_lint.py:400` skips any line without `"assistant"` in it and
`:406` skips any record whose type is not `assistant`, so reply boundaries come from the record type alone.
This is new parsing rather than a retained value, and the cost in §8 says so.

**The filter is part of the behaviour, not a detail of the measurement.** A `type: "user"` record is also
every `tool_result`, every `system-reminder` injection, every hook stdout, every slash-command expansion and
every relay carrying a dispatched agent's report back. §4's method states the exclusions, and they are not
cosmetic: excluding the relays alone moves the median from 204 to 184 prose words and the short-question
count from 20 to 25. Ship the filter §4 used, and name it in the output so a reader knows what was counted.

**The nine rules in `REPLY_RULES` keep taking a string and do not move.** They are `(name, pattern, message)`
tuples applied per line at `style_lint.py:290`, and nothing in them sees a reply, let alone a pair. The
fifteen `reply_findings(...)` calls in `tests/test_style_lint.py:222–308` all pass a string and keep working,
because the pair-aware report is **a new function** rather than a changed signature on `reply_findings`.

### 5.2 Report a ranking, not a verdict

Rather than a threshold that fires, the check gains one section listing the three replies whose prose length
is largest relative to the question that prompted it, each with its word counts and its heading count:

```text
style check — last 20 replies · ~/.claude/projects/…/b0ea3cb5.jsonl
  qualifier: 2
    one honest: ### one honest cost of the scheme you picked
  longest against the ask
    755 words · 3 headings  ← "what would you suggest next? speaking globally, …" (16 words)
    645 words · 4 headings  ← "look at ~/codex-feedback-real-world-work.md" (3 words)
    578 words · 2 headings  ← "let's do it" (3 words)
```

This is a measurement rather than a finding, so §4.3's false-positive problem disappears: a long reply to
"give me the state of the union quick report" appears in the ranking and the reader sees immediately that it
was asked for. Nothing is tuned and nothing is refused. The exit code does not move because
`style_check` returns a literal 0 at the end of its body whatever it found — `verdict` governs `style lint`
only, from `cli/flw.py:1251`, and never this path.

It is also the form that reached the author today. Being shown "578 words to let's do it" in a table is a
specific violation named, which §2's table says is the intervention with an effect; being shown the rules is
the one it says has none. Whether it changes the next replies is not something this document can claim — an
earlier draft asserted a seven-reply improvement and the transcript did not support it.

**Prose words only, fenced blocks excluded**, as §4's method states. A reply quoting a 200-line diff is not a
long reply.

### 5.3 Read the transcript the host names, rather than guessing the newest

The first draft of this section proposed falling through to the next candidate when the newest transcript
holds only a dispatched agent's replies. **That is the option `say-what-it-checks` already refused**, and its
rationale names the number: "The defect the review reproduced is the fall-through, not the filter: 91 of 298
transcripts hold only `agentName` records, and a session inside one of them silently gets another session's
replies." The draft's counter-argument — that the risk is pre-existing — never engaged with that figure.

The fix is not to re-open the decision. It is that the command never had to guess. The host sets
`CLAUDE_CODE_SESSION_ID`, and its value is this session's transcript stem: measured here, it resolves to
`b0ea3cb5-1cb6-41f2-90f4-20b6774116dc.jsonl` under the project's transcript directory.

So when the variable is set and that file exists, read it and stop. Fall back to the existing newest-first
scan when it is not, with the refusal and the filter exactly as they are today.

This is strictly better than either option that decision weighed. A session running inside a dispatched agent
has its own session id, whose transcript holds only `agentName` records, so the refusal fires for the right
reason and no other session's replies are ever read — the 91-of-298 case is answered rather than traded away.
It also closes the caveat `flw-style` carries today, that under concurrent sessions the command "reports the
newest transcript holding prose, which may not be this one".

**Reading a host-specific environment variable belongs in `cli/flw.py` and not in the engine.** That is the
boundary `session_transcripts` already draws: `base` is handed in rather than derived, because "which
directory a host writes transcripts to is a fact about the host and the CLI is the only part of flw that
holds those". A session id is the same kind of fact.

## 6. Deliberately not built

**A rule for reply length in `terse_prose.md`.** §3.

**A threshold that fires.** §4.3.

**Falling through to the next transcript when the newest is a dispatched agent's.** Refused by
`say-what-it-checks-minor.toml`, which measured 91 of 298 transcripts holding only `agentName` records. §5.3
reads the session the host names instead, which needs no fall-through.

**Anything that blocks a reply.** §3, and the Stop-hook decision in `a-rule-nothing-breaks`.

**A fix for `over-120` and `missing-two-spaces`.** They are the two rules that do fire, at 299 and 459 hits,
and they are already correctly reported — the author ignored them, which is a behaviour problem and not a
tooling one.

**Measuring a dispatched agent's prose.** `read_replies` excludes it for a measured reason: a dispatched
agent breaks `announcement` at 6.18 per 10,000 words against the main agent's 2.29, because it never receives
the host's output style. That stays.

## 7. Where it sits

```text
cli/flw.py                   the session-id lookup (§5.3) and the new output section (§5.2)
core/scripts/style_lint.py   read_replies returns pairs (§5.1); a new pair-aware report beside
                             reply_findings, not a change to it
tests/test_style_lint.py     the four tests pinning the current return shapes — :333 on
                             recent_replies, and :344, :348, :355 on read_replies — plus the
                             question filter and a fixture where the session id names the file
```

No new command, no new flag, no schema change. `flw style check` keeps its signature and its exit codes.

## 8. Cost

One record. The selection fix reads one environment variable and keeps every existing branch as a fallback.
The pairing is new parsing — a user-record reader and the question filter §5.1 names — and a return-shape
change in a function with **two** callers: `cli/flw.py:1314` and `recent_replies` at `style_lint.py:426`,
which `.flw/reviews/style-checks.toml` tells reviewers to use. Four tests pin the current shapes. The ranking
is a sort and three lines of output.

The contract edit is one `provides` sentence on the validation and checks component, because what the command
reports is user-visible behaviour.

## 9. Open questions

**Is three the right number of rows?** Three fits a terminal and covers the tail measured here. Ten would
turn a section into a table nobody reads.

**Should the ranking sort by absolute length or by ratio?** The table in §4.2 is sorted by absolute prose
words, and the 3-word question happens to top both. A ratio would promote a 150-word reply to a 2-word
question over a 500-word reply to a 40-word one, and it is not obvious which is the worse failure.

**Does this generalise past the author?** Every number here comes from one session and one agent. The
mechanism is general; the claim that length-against-the-ask is *the* dominant failure is measured on a single
transcript.
