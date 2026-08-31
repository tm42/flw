# The note store reads every body into memory, and nothing refuses a huge note

`walk` parses both roots on every query and holds every note's body at once — which is what buys
the store having no index, no cache and nothing that can go stale against the files.

**Measured.** A single 256 MB note writes at exit 0, reports `67108.9k tokens`, and every later
query reads it: `flw kb -s` still returns in 0.15s but peaks at 568 MB RSS. No crash. Nothing
refuses the write and nothing warns.

**Why it is not urgent.** No realistic store reaches this. A note is prose an agent wrote, and the
write path already prints the size.

**What would settle it.** The shape of the memory curve on a machine with less RAM than an M3 Pro,
which is what `docs/measuring.md` asks a remote agent for. If it bites, the fix is a size ceiling
on the write path rather than streaming the read, because the read's simplicity is the design.
