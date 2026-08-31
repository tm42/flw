# A skill that turns a design into a navigable map

status: parked. One artefact built, no skill written, no decision taken.

## What exists

`.flw/reports/2026-08-29-memory-design.html` renders `plans/design-memory.md` as a zoomable
board: a blueprint at the centre showing one note from written to found, six branches around
it, thirteen panels, and numbered markers that jump from a line of the blueprint to the panel
arguing it. It was built by hand over one session, rebuilt three times, and published as an
artifact.

The question is whether the reusable half of that is a skill — `flw map <document>` — and the
answer is not yet. This file records what was learned so the next attempt does not start from
the same three mistakes.

## What is reusable

The shell, and it is most of the file:

- **Layout is computed, never authored.** No panel has a fixed height. `.branch` flows in a
  `.col`, JS measures the result and places columns, and the wires are drawn from measured
  positions afterwards. Every version that authored coordinates or heights clipped its own
  content the moment the text changed.
- **Two modes off one measurement.** Above 820px the panels in a branch sit in a `.row` fanning
  away from the trunk; below it everything reflows to one column at the device's width. The
  narrow path is not a media query — it is the same layout function reading a different width.
- **Tap detection on `pointerup`, not `click`.** `setPointerCapture` retargets `click` to the
  viewport, so `e.target.closest('.p')` is always null. A tap is a pointerdown-to-pointerup
  distance under 7px, measured per gesture rather than accumulated. This was found in Safari
  after passing in Chrome.
- **The three invariants, checked in-page rather than by eye.** Panels whose `scrollHeight`
  exceeds `clientHeight`; pairwise rectangle intersection; and SVG path sample points landing
  inside a panel rectangle, sampling only the interior because a connector legitimately
  terminates on an edge. Every rebuild was verified against all three in both modes. Eyeballing
  a 7000px board finds none of them.

## What is not reusable, and is the actual work

**Decomposing a document into root, branches and panels.** This is the part that was wrong
twice, and neither failure was cosmetic:

- The first pass hung panels off nothing — thirteen boxes in a grid with a trunk running
  underneath them, and no reader could tell which branch a panel belonged to.
- The second gave every branch a title pill that was inert and nearly invisible, so the grouping
  existed in the markup and not on the screen.

What fixed it was not a rule: it was reading the document again and noticing it has a natural
centre — one worked example that every section is a decision about. The blueprint came from
that, and the markers came from the blueprint. A different design document may have no such
centre, and then the whole layout is wrong for it.

So the open question is not "can this be templated" but **"how many documents does the centre
trick survive?"** One is not a sample.

## What a skill would have to decide

1. Where the shell lives. `core/templates/` is the obvious place and freezing it there is the
   commitment this file is deferring.
2. Whether decomposition is prompted or mechanical. Prompted means the skill hands the model
   the shell and the document and says what a good map looks like — which is what happened here,
   badly, twice. Mechanical means headings map to branches, which produces the rigid grid the
   first attempt already proved does not read.
3. What it does when a document has no centre. Refusing is honest. Falling back to a plain
   branch layout is more useful and is the version that produces the map nobody navigates.
4. Whether the invariant checks ship with it. They should: a map that clips its own content is
   worse than no map, and the checks are twenty lines of JS that a skill can run in a browser it
   already has.

## What would tell you it is worth building

Two more documents mapped by hand with the same shell, at least one of which is not a design
document — a review report or a roadmap. If the shell survives both without structural edits,
the shell is a template. If decomposing the second one takes as long as the first did, the
decomposition is the skill and the shell is scaffolding around it.
