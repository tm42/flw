# The spec critic

An optional second read on a contract, offered at the end of `flw-spec`. Dispatch it as a
subagent so it arrives without the interview in its context — the whole value is a reader
who was not there when the decisions felt obvious.

## What it is for

`flw validate` checks shape: required fields, types, unique component names, a dag with no
cycles. It cannot check meaning. A contract can be perfectly valid and still describe the
wrong thing, or describe the right thing incompletely.

The critic looks for exactly the gaps validation structurally cannot see.

## The prompt to give it

> You are reviewing a contract for semantic gaps. Read only; change nothing.
>
> - The plan: `<plan path>`
> - The contract: `<contract path>`
> - What a good contract looks like: `<this directory>/good-contract.md`
> - The shape it must satisfy: `<schemas>/spec-v4.schema.json`
>
> The contract already passes validation. Do not report anything a schema check would
> catch.
>
> Look for these five, and stop:
>
> 1. **Coverage gap** — something the plan asks for that no component provides.
> 2. **Hidden assumption** — something the contract relies on that is not in
>    `assumptions`. Scale, concurrency, encoding, failure behaviour, and what happens on
>    a second run are where these hide.
> 3. **Plan drift** — the contract quietly decided something the plan left open, or
>    contradicts something the plan settled.
> 4. **Unfalsifiable claim** — a `provides` nobody could check without reading the code,
>    or a `criteria` that says nothing testable.
> 5. **A test that will not run** — a command referencing a tool, path or runner that does
>    not exist in this repo.
>
> For each: quote the line, say which of the five it is, and give the smallest fix.
>
> Report nothing else. No style notes, no suggestions to add fields, no praise. If you
> find nothing, say "No semantic gaps found." Four findings you can defend beat fifteen
> observations.

## Handling what comes back

Walk each finding with the user as an interview turn. Two outcomes:

- **Resolve** — edit the contract, then `flw validate` again.
- **Accept as known** — append it to `open_questions` rather than fixing it.

**One cycle only.** Do not loop the critic until it goes quiet. If the user wants another
pass after resolving, that is a new request they can make.

## When not to bother

A small contract, an obvious one, or a `quick_fix`-sized change. The critic is a fresh
context, which costs real tokens, and on a three-component contract it will find nothing
the interview did not already surface. Offer it; do not push it.
