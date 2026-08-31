# Two concurrent writes of the same note both succeed

`flw kb write` refuses a slug already taken in the target category by reading the store and then
writing — check-then-write, with nothing between. Two processes writing the same title into the
same category both pass the check and both write; the later one wins and the earlier body is gone.

**Inherent to the shape.** The store is a directory of files with no index and no database, which
is the design's central bet. A lock is the only fix and it is a real mechanism to add to something
whose whole claim is that any agent that can write a file can write a note.

**How likely.** Two agents writing the same title in the same second, on one machine. Not zero —
this session ran four reviewers in parallel and every one of them was offered a write.

**What would settle it.** Seeing it happen once. Until then the honest response is that
`flw kb lint` reports near-duplicates and a lost body is not detectable at all.
