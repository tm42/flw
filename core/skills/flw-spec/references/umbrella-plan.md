# The umbrella plan

Read when a change spans more than one repository, before any repository specs its own
record. It gives that plan a standard shape, so the next one is comparable to the last
instead of invented again.

The plan lives in the project whose config declares `[project.roots]`. `[project.roots]`
does not require nesting, so a set of siblings has no parent directory to hold anything —
the config that names the set is the only thing that locates them all.

**Rewrite it rather than patch it.** A hand-maintained picture goes stale and nothing will
say so. Whenever a spec session touches this feature, redraw the plan from what is true
now. The template is small enough that redrawing beats editing, and that is the whole
mitigation — treat a stale diagram as expected rather than as a defect in the method.

**flw parses none of it.** Not the slices, not the status words, not the pull request
numbers. A number on a slice line is text for a human to follow; flw never asks a host
about it.

## The six sections, in this order

```text
# <feature> — umbrella plan

## What this is
One paragraph. The behaviour all the repos are serving, and what would make it a failure.

## Repos and what each owns
**datastore** — owns the items table and its schema.
**runner** — reads items. Owns nothing in the wire shape.
**api** — exposes items outward. Owns the public field names.

## The seam
**items[].id** — datastore owns, runner and api read.
**items[].label** — datastore owns, api renames to `title` outward.
**items[].retired_at** — datastore owns, nullable, runner must tolerate null.

## Slices
Indentation is dependency: a line needs the line it sits under.

datastore:add-items-field          landed        #412
  runner:read-items                open          #418
    runner:surface-items           not started
  api:expose-items                 open          #419
       (also needs runner:read-items)

## Order that matters, and order that does not
runner:read-items and api:expose-items are independent of each other.
Nothing requires api before runner.

## What we expect to change
The retired_at nullability is unsettled. If it becomes non-null,
runner:read-items is rewritten and surface-items is unaffected.
```

## The rules the sections follow

**Indentation is the only dependency notation.** A line needs the line it sits under. One
rule, it survives renaming, and a new slice costs one line at one depth. A box-drawing
layout was drafted first and thrown away: an agent redrawing a `└─▶` picture after one
slice moves produces a different layout each time, and a template whose purpose is to be
standard cannot be the part that drifts.

**A slice needing two parents gets `(also needs <slice>)` underneath it.** Indentation
cannot express that shape, and one prose escape hatch beats a notation trying to cover
shapes nobody has seen yet.

**Three status words and no others: `landed`, `open`, `not started`.** `landed` is
deliberately the contract's `applied` read in plainer words, so the plan and the contract
mean the same thing by it.

**The seam section names an owner per field.** Which repository owns it, which ones read
it, which one renames it on the way out, and whether it may be null. A field with no owner
named is the disagreement this section exists to prevent.

## The shared wire fixture, which is a convention and not a mechanism

Where the seam is worth checking rather than only agreeing, put one fixture at the project
that declares the roots, describing the wire shape, and have each member declare a check in
its own `[tests] checks` that validates that fixture against its own schema. It catches the
case prose cannot: two repositories passing their own suites while disagreeing on a field
name, an alias or a nullability.

**Nothing new is needed to support this.** The fixture is a file and the check is a line in
a config file flw already reads. There is no flw command for it and no plan to add one — if
two repositories adopt it and it holds, that is when to ask whether it deserves one.
Building the command first would be designing for a usage pattern with one data point.
