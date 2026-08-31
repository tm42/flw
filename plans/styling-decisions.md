# Styling — decisions

Recorded before spec work. Answers are the user's; rationale is theirs, not inferred.

## D1 — does `flw install` write the style into host config?

Optional, never automatic. Install mentions it exists; a separate command does the work.

```
flw style install            install the shipped style into every host
flw style install <name>     install a named custom style
flw style uninstall          remove it everywhere
```

Without it, the style applies only to flw's own outputs — reports, proposals, skill
responses — via the skills reading it.

## D2 — one style file or two?

One. Merged.

## D3 — how does a repo consume it?

It does not. The style is global, not repo-level, so it is not an extension.

## D4 — spec version

3.2. Not a breaking change.

Noted for future numbering: a major version does not have to be breaking. A large enough
addition can justify one.

## Scope beyond the original three points

All prose guidance already in the package is read against the new rules and fixed where it
breaks them, including `core/shared/ambient.md` Posture and every `SKILL.md`. What that
turned out to mean is recorded in the version file: the package was already written in this
voice, and three phrases changed.
