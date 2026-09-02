+++
type = "Area"
description = "The order API. OrderStatus is a string enum that crosses to the worker unchanged."
revision = "8be0117"

[[connects]]
to = "worker"
how = "queue"
carries = "Order"
+++
# shop/api

`POST /orders` validates and persists, then enqueues. `PATCH /orders/{id}`
is what `worker` calls back into when an order ships.

`OrderStatus` is a string enum and crosses to `worker` unchanged, which is why
this file exists at all: the enum is the contract, and reading it here removes
reading both sides of the queue.
