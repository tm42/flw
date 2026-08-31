# The TypeScript scout has no measurements at all

`core/scripts/scout.mjs` is 480 lines and nobody has ever timed it or checked its ranking on a
real repository. It runs on the *target* repo's own `typescript`, which is what keeps flw
dependency-free, and which also means it can only be measured somewhere that has one.

**What would settle it.** Run it against a TypeScript monorepo with path aliases and barrel files
— the two things the Python scout does not have to deal with and the contract's re-export
property claims this one handles. Report the wall time and whether barrels take rank they should
not.

Related: `plans/backlog/scout-at-monorepo-scale.md` is the same gap for Python.
