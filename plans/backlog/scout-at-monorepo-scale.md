# The scout has never been measured on real code at scale

The contract claims a ranked orientation "in a few seconds at twenty thousand files". Measured on
generated Python trees on an M3 Pro: 0.10s at 500 files, 0.32s at 2,000, 1.31s at 8,000 — linear,
extrapolating to roughly 3s at 20,000, which is the claim.

**Why that is not the same as verified.** Generated imports resolve cleanly. Real ones do not:
re-export barrels, `sys.path` mutation, conditional imports, vendored trees, generated code. The
scout's ranking quality and its speed both depend on how many edges resolve, and a generated tree
tells you nothing about either.

**What would settle it.** `flw scout` on a real monorepo of 10k+ files, with the wall time and a
look at whether the top twenty are the files someone who knows the repo would name.
`docs/measuring.md` has the protocol.
