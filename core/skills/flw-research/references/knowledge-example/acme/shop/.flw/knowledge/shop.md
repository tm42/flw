+++
type = "Repository"
description = "Serves the storefront and the order API. Writes each order to the fulfilment queue."
revision = "1f4ac02"
measured = "compose up, one POST /orders, then read the worker's log"

[[connects]]
to = "worker"
how = "queue"
carries = "Order"
+++
# shop

The customer-facing half. It renders the storefront, accepts orders over HTTP,
and writes each accepted one onto the fulfilment queue as an `Order`. It owns
the order record and is the only writer of it.

The order API is [api/api.md](api/api.md) — a link, because that file is in this
same store. The queue edge goes to `worker`, which is another repository, so it
is named here in text and never as a path into a sibling checkout.
