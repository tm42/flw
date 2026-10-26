# Extending flw

Two ways: a bundle adds a skill, an extension amends one you already have. There is no
plugin API — a bundle is a folder shaped like flw's own, and an extension is prose.

---

## An extension amends a skill, in one repository

`<project root>/.flw/extensions/<skill name>.md`. The name is the skill's own, exactly:
`flw-spec` reads `.flw/extensions/flw-spec.md`. Nothing else reads it and no other file
names it. `shared.md` is the one other name, read by every skill.

**It is a chain, not a directory.** Every project root at or above the resolved one and
below `$HOME` is read, outermost first, so a parent holding several checkouts can carry
conventions all of them obey; within a level `shared.md` comes before the skill's own
file. A nearer level beats a farther one, and within one level a skill's own file beats
`shared.md`.

It is read after the shared context and before the skill starts work. Put in it what that
skill needs to know about **this** repository — how tests are actually invoked, where new
code goes, what a reviewer should judge against.

**Write one per skill, holding only what that skill needs.** Do not restate across them.

**An extension amends how a skill works here; it cannot waive a Rule.** A skill told to
ignore its own lane will surface that rather than comply.

### The path is fixed

There is no config key pointing at an extension, so the name is derivable and `flw doctor`
can check it. The failure worth catching is a file named `spec.md` when the skill is
`flw-spec`: it looks right and nothing reads it.

```text
extensions: ~/work/.flw/extensions
  ✓ shared.md — read by every skill (61 B)

extensions: ~/work/ds/.flw/extensions
  ✓ flw-spec.md — read by flw-spec (50 B)
  ✗ spec.md — read by nobody: no installed skill is named 'spec'
      skills here: flw-execute, flw-research, flw-review, flw-spec, and shared.md
```

### Generated, not typed

`flw-research` writes these by reading the repository. You can hand-write one, but the
usual path is to run research and edit what it drafted — it shows you everything before
writing anything.

Whether they are committed is your call, and the directory is in your repo either way. A
tracked extension is a shared convention; an ignored one is your local setup.

---

## A bundle adds a skill

A directory with `skills/` in it, each skill a folder containing `SKILL.md`:

```text
my-bundle/
  skills/
    my-skill/
      SKILL.md
      references/          optional, loaded only when that path is taken
      scripts/             optional
```

```sh
flw add ~/path/to/my-bundle
flw install
```

`flw list` shows registered bundles, `flw remove <name>` deregisters and unlinks them.

### Copy the shape of an existing skill

Read `core/skills/flw-review/SKILL.md`. The frontmatter needs `name` and `description`;
`description` is what a host matches against when deciding whether to load your skill, so
write it for that, not as a title.

The body is prose an agent follows. What holds up in practice:

- **Open with one call: `flw context <skill name>`.** It prints the shared context, the
  resolved root and where it came from, every extension on the chain, the note store
  listing and the contract's components — the reads a skill used to make one at a time,
  described in prose four files had to keep in step. Say to run it silently; otherwise the
  agent narrates it every time. If `flw` is not on PATH, run it out of the checkout by
  absolute path from `${FLW_HOME:-$HOME/.flw}/root`: a skill folder is installed as a
  symlink, and a relative path that escapes it is collapsed before the filesystem sees it.
- **State the lane, including what the skill must not do.** The negative half is what stops
  a skill quietly growing into another one.
- **Give reasons, not just rules.** A rule with the failure behind it survives a reader who
  is in a hurry. A bare rule gets read past.
- **Reference files load lazily.** Put the rare path in `references/` and name it at the
  point of use, so it costs nothing on the runs that do not need it.

### How a skill gets checked

Two things are tested, both in `tests/test_validate_spec.py`: `SKILL.md` frontmatter, which
the hosts require in a fixed shape and refuse to load without, and the review configs, which
are data with a schema. The prose is not, because there is no fixed behaviour to assert
against.

The check that works is **giving the skill to an agent that has never seen it and asking
where it had to guess.**

### Overrides are reported, never silent

Resolution is core first, then bundles in registration order, later winning. A bundle skill
that shadows a core one is a debugging nightmare when implicit, so `flw
install` and `flw doctor` both name it — in different words, because install has the
shadowed path to hand and doctor is reporting a state:

```text
  override: flw-spec from [my-bundle] shadows [core] (/path/to/flw/core/skills/flw-spec)
```

```text
  ! flw-spec: [my-bundle] shadows [core]
```

`doctor` also catches an orphan — a link left behind by a bundle that was deregistered
without being uninstalled.

---

## What is deliberately not offered

**A code plugin API.** Extensions are prose.

**Remote bundles.** Local paths only.

**Hooks.** flw does not intercept, wrap or police tool calls. Hosts have their own permission
systems. flw's entire runtime presence is skills a host chooses to load.
