# Surveying a system that spans repositories

Read first when the survey covers more than one root — several checkouts under one parent,
or `[project.roots]` declared. Nothing here applies to a single-repository survey.

**More than one root inverts this order.** For a system spanning several repos, read the
deployment topology first and scout each root after: what talks to what has to be settled
before what is central *here* is even a well-posed question, and a per-repo ranking read
first lets every seam between them stay vague.

**With `[project.roots]` declared, the survey is every member and the parent pass comes
first.** One pass over the topology, the shared literals and one transaction traced end to
end, then one pass per member. The parent gets `system.md`, which is read by declaration and
so reaches every member wherever it sits.

**A parent `shared.md` reaches only members that nest under it.** Extensions are read by
filesystem ancestry and `[project.roots]` does not require nesting — a member declared as
`../datastore` is a sibling, and no session inside it reads a line the parent wrote. So
write a convention at the parent only when every declared member resolves under the parent's
own directory. Otherwise say the convention has to go into each member, and say why, rather
than writing one file that `flw doctor` will report as live and nobody will read.

**Across repos, grep for the duplicated literal.** Two repos are one system only where
they both hardcode the same string — an endpoint path, a table name, an environment
variable, a topic, an image tag, a status enum — and nothing in either type system checks
that the two still agree. That makes the map mechanically findable rather than a matter of
reading well:

```sh
# every quoted literal of some length, per root, and which appear in more than one
grep -rhoE '"[^"]{6,60}"' repo-a repo-b --include=*.py --include=*.ts --include=*.go \
  | sort -u > /tmp/a-b.txt
```

Order what comes back by rarity and stop reading when it stops paying: a long odd string
in exactly two repos is the strongest signal, and `id`, `error` and every HTTP verb sink to
the bottom on their own. **Past two repositories, take each pairwise intersection and
subtract the full one.** What every repository shares is HTTP header names and environ keys;
what exactly two share is their contract. On three ASGI libraries that subtraction returned
the ASGI protocol vocabulary and almost nothing else, and it is what found a seam no import
edge crosses. This is the same discovery as the framework greps above from the
other side — theirs is cleaner where the framework is known, this one covers table names,
queue topics and image tags in languages nobody wrote a pattern for. Beyond HTTP and SQL,
the literals that break silently are JWT claim names and scope strings, metric and log
field names consumed by a dashboard in a repo nobody scouted, bucket names and key
prefixes, feature-flag keys, and status values crossing the wire as strings.

**Then trace one transaction end to end**, every repo, one hop at a time: a user changes a
setting, a request goes out, something is written, another service reads it, a result comes
back. This is the step that produces understanding, and a summary per repo does not
substitute for it — each side gets described in its own vocabulary and the mismatch never comes
to light. A trace forces every hop to resolve to a named function receiving a named
payload, and it fails loudly at exactly the hop that was got wrong, which is the hop worth
knowing about. **Record where you lost it.** That is the finding, not a failure of the
method.

Where it can be run, run it: `docker compose up`, one `curl`, and read what the other
services log. Ten seconds of real requests settles the payload shape, the auth header and
which of two code paths is live — all things reading only guesses at.

Two traps specific to the sweep. A caller does not prove a callee exists — dead client code
calling a renamed route greps identically to a live edge, and only running it separates
them. And a matched name is not a matched meaning: `user_id` on both sides can be two ID
spaces with a translation between them.

**A seam file names an owner per field.** Writing "these two agree on the item shape"
records that a seam exists and settles nothing. Name, field by field, which side owns it,
which sides read it, which side renames it on the way out, and whether it may be null —
the same vocabulary the umbrella plan's `## The seam` section uses, at
`$FLW/core/skills/flw-spec/references/umbrella-plan.md`, so the plan above the change and
the store describing it do not need translating between.
