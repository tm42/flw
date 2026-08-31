# Backlog

Work that is understood and not yet scheduled. One file per item; this file holds the order and
the status, and nothing else — an index that restated what the items say would be a second place
for the same fact, drifting from the first.

**An item leaves this directory exactly two ways**: it becomes a version record under
`specs/versions/`, or it is dropped with the reason written into the file before the file goes.
Nothing else. An item that quietly disappears was never decided about.

This is not the contract's `open_questions`. Those are things the design cannot yet answer. A
backlog item is work nobody is confused about — it just is not specced.

## Order

Ranked by what would change a decision, not by size.

| | item | why it is here | blocked on |
|---|---|---|---|
| 1 | [the note store's deferred half](note-store-deferred-half.md) | the largest body of known-unbuilt work, and every piece has a trigger the design already names | use |
| 2 | [the scout at monorepo scale](scout-at-monorepo-scale.md) | the contract claims a number nobody has checked on real code | a 10k+ file repo |
| 3 | [the TypeScript scout, unmeasured](typescript-scout-unmeasured.md) | 480 lines with no evidence of any kind | a real TS monorepo |
| 4 | [every body in memory](store-holds-every-body-in-memory.md) | measured and bounded; unlikely to bite before it is noticed | a smaller machine |
| 5 | [concurrent writes have no lock](concurrent-writes-have-no-lock.md) | inherent to the store's shape; the fix is larger than the risk | seeing it happen |
| 6 | [two unwritten note offers](unwritten-note-offers.md) | both passed the write test and neither was written | starting the store |

Elsewhere, because it has its own file and duplicating it here is how the two would drift:
**[a skill that turns a design into a navigable map](../map-skill.md)** — parked until the shell
survives two more documents mapped by hand.

## Nothing reads this directory

`flw ledger` globs `plans/*.md` and does not descend, and `flw kb` reads `plans/notes/` only. So
these files are found by looking, not by searching. At six items that is fine; at fifty it would
be an argument for widening the ledger's corpus, which is a contract property and therefore a
version record.
