# `release_line`

Read when a record moves the product to a new release line, which is rare. Most records
omit the field and never read this file.

**`release_line`, when this record moves the product to a new line** — 1 being
whatever reached production. Declaring it restarts the count, so the release this
record produces is `1.0.0` and the next minor is `1.0.1`. A record that is not
moving the line omits the field entirely. The contract carries no separate key for
it: the line is the first part of `spec_version`, so there is one place it can be
read and nothing to disagree with.
