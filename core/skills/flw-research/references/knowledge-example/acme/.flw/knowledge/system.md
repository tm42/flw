+++
type = "System"
description = "One shop, one worker. The shop takes orders over HTTP; the worker fulfils them from a queue the shop writes."
revision = { shop = "1f4ac02", worker = "3c81d90" }
+++
# acme

Two repositories and one queue between them. A customer places an order through
the shop's HTTP API; the shop writes it to the fulfilment queue; the worker
drains that queue, ships the order, and calls back into the shop's API to mark
it shipped.

The seam is the queue, and both sides declare it: `shop` says it writes `Order`
onto it, `worker` says it reads from it and answers over `http` with an
`OrderStatus`. Neither repository holds the other's file, so this one revision
table is keyed by member directory and checked in each member's own repo.
