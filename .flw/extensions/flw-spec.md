# Speccing in flw

**One record per version under `specs/versions/`, named for what it does.**
`flw ledger <term>` searches them and is faster than reading — a fork this project already
settled is usually in some record's `decisions`, with the option it beat.

**Six components carve the tree** and their `paths` decide what a change may touch;
`flw context flw-spec` prints them. A component listing specific files does not stretch to
a sibling, so a new script under `core/scripts/` is a contract edit rather than a free
addition.

**A record adding a subcommand or a flag writes the `flw <name> [flags...]` line into the
CLI component's `surfaces` at spec time.** The suite holds the parser to that line, so a
record that defers it deadlocks against its own check.
