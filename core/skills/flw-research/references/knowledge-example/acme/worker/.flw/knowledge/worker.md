+++
type = "Repository"
description = "Drains the fulfilment queue and marks orders shipped through the shop's API."

[[connects]]
to = "shop"
how = "http"
carries = "OrderStatus"
+++
# worker

Drains the fulfilment queue, ships what it finds, and reports the result back to
`shop` over HTTP as an `OrderStatus`. It holds no order record of its own.

This file carries no `revision`: it is `unstamped`, deliberately, so the toy
shows what a file nobody has stamped yet looks like in `flw know --check`.
