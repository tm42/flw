# Thrifty mode

Read when the interview is to be skipped — `--thrifty`, `[interview] mode = "thrifty"`, or
a request that plainly says it. It subtracts the conversation and none of the steps.

On `--thrifty`, `[interview] mode = "thrifty"`, or a request that plainly says it —
*"don't make me sit through an interview"* — skip the conversation. Write the draft and
**stop**. The user edits the file. Next invocation, re-read, `flw validate`, and ask only
about what is still open.

**Markers go inside the values, not in comments.** Required fields have a minimum length,
so a TOML comment cannot hold one and the draft would not validate:

```toml
criteria = "TODO(flw): what does a human have to check beyond the tests?"
```

`flw validate` finds every `TODO(flw)` and reports the draft as unfinished, which is how
one never ships by accident. Print the same list yourself and stop there.

**Thrifty subtracts the conversation, not the steps.** The plan still goes on disk first —
that rule has no exception, so if there is no plan, spend your one question there. Reading
the code before an amend still happens; it is not conversation. What thrifty removes is
the section-by-section confirmation and the final lock.

**Amending thriftily** writes the version file as a draft and puts an unambiguous edit
into `contract_edit`, not into the contract. Anything genuinely open goes in the version
file's `approach` as a marker, not into `current.toml` — a contract of record with `TODO`
in it is worse than an unfinished draft beside it.

A marker is what you write instead of guessing.
