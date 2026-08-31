# The half of the note store that was deferred

`note-store` scoped v1 deliberately and listed what it left out. None of it is designed away —
each was judged to have no subject yet.

- `flw kb promote <slug> <category>` — move a note from the project root to the machine-wide one.
- The `supersedes` reverse lookup: the key is written and parsed, nothing reads it backwards, so a
  superseded note surfaces unmarked.
- `index.md` as a category description, its `orphans` lint check, and any special treatment of a
  category that has one.
- Nine of fourteen lint rows: orphans, dangling links, dangling supersedes, untitled, tag/type
  collision, labels, ages, sizes, empty categories.

**What would settle it.** Use. Each of these has a trigger the design already names — `promote`
when a note is misfiled across roots, `supersedes` the first time one is genuinely superseded,
`index.md` when a category outgrows a title listing, the lint rows when there is enough to prune.

**Cheap to restore.** A note is markdown and every frontmatter key is optional, so each of these
reads more directories or more keys and migrates nothing already written.
