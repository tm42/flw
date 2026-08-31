# Extending flw

Two ways, and the difference is whether you are adding a skill or amending one you already
have. There is no plugin API in either case: a bundle is a folder shaped like flw's own,
and an extension is prose. Both are things you can write by hand, which is why an agent can
write one by copying the shape of something that exists.

---

## An extension amends a skill, in one repository

`<project root>/.flw/extensions/<skill name>.md`. The name is the skill's own, exactly:
`flw-spec` reads `.flw/extensions/flw-spec.md`. Nothing else reads it and no other file
names it.

It is read after the shared context and before the skill starts work. Put in it what that
skill needs to know about **this** repository — how tests are actually invoked, where new
code goes, what a reviewer should judge against.

**Write one per skill, holding only what that skill needs.** Do not restate across them.

**An extension amends how a skill works here; it cannot waive a Rule.** A skill told to
ignore its own lane will surface that rather than comply.

### The path is fixed, and that is the point

There is no config key pointing at an extension. A configurable path could point anywhere,
which means nothing could ever verify it — and the failure worth catching is a file named
`spec.md` when the skill is `flw-spec`. It looks right, it is read by nobody, and nothing
says so.

Because the name is derivable, `flw doctor` can check it:

```
extensions: /path/to/project/.flw/extensions
  ✓ flw-spec.md — read by flw-spec
  ✗ spec.md — read by nobody: no installed skill is named 'spec'
      skills here: flw-execute, flw-research, flw-review, flw-spec
```

That check and a configurable path are mutually exclusive features. The checkable one won.

### Generated, not typed

`flw-research` writes these by reading the repository. You can hand-write one, but the
usual path is to run research and edit what it drafted — it shows you everything before
writing anything.

Whether they are committed is your call, and the directory is in your repo either way. A
tracked extension is a shared convention; an ignored one is your local setup.

---

## A bundle adds a skill

A directory with `skills/` in it, each skill a folder containing `SKILL.md`:

```
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

- **Open by resolving flw and reading the shared context**, by absolute path from
  `${FLW_HOME:-$HOME/.flw}/root`. Relative paths that escape a skill folder do not work —
  see the comment at the top of any skill's SKILL.md. Say to do it silently; otherwise the
  agent narrates it every time.
- **State the lane, including what the skill must not do.** The negative half is what stops
  a skill quietly growing into another one.
- **Give reasons, not just rules.** A rule with the failure behind it survives a reader who
  is in a hurry. A bare rule gets read past.
- **Reference files load lazily.** Put the rare path in `references/` and name it at the
  point of use, so it costs nothing on the runs that do not need it.

### It cannot be unit-tested

A skill is prose, and there is no fixed behaviour to assert against. flw tried it — a test
per phrase a cold reader had tripped on — and the tests only ever fired on deliberate
rewrites, so each failure was answered by editing the test to match. A check that is always
wrong when it fails trains you to stop reading it. They were deleted in full.

What is still tested is the part that is not prose: `SKILL.md` frontmatter, which the hosts
require in a fixed shape and silently refuse to load without, and the review configs, which
are data with a schema. Both live in `tests/test_validate_spec.py`.

The real check is **giving the skill to an agent that has never seen it and asking where it
had to guess.** Every flw skill has been through that, and each time it found a
contradiction that reading it had not. Rewrite skills deliberately, and re-read them cold —
that is the control, not a test suite.

### Overrides are reported, never silent

Resolution is core first, then bundles in registration order, later winning. A bundle skill
that shadows a core one is powerful and a debugging nightmare when implicit, so `flw
install` and `flw doctor` both name it:

```
  ! flw-spec: [my-bundle] shadows [core]
```

`doctor` also catches an orphan — a link left behind by a bundle that was deregistered
without being uninstalled.

---

## What is deliberately not offered

**A code plugin API.** Extensions are prose. A plugin API is where lean tools become
frameworks, and every mechanism flw might add to police an agent is redundant with the
human who reads the diff.

**Remote bundles.** Local paths only. Remote fetch means trust, verification and update
semantics — a materially larger surface for no benefit here.

**Hooks.** flw does not intercept, wrap or police tool calls. Hosts have their own
permission systems and theirs are better. flw's entire runtime presence is skills a host
chooses to load.
