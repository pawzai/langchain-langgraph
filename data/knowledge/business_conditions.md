# Business Conditions and Service Levels

## Trailer assignment policy

- A trailer serves one active shipment at a time.
- Trailers must pass inspection every 90 days. An overdue inspection moves the trailer to
  `MAINTENANCE` automatically overnight, which can silently break shipments that were assigned to
  it the previous day.
- Reassigning a trailer does not require approval when the shipment is still in `CREATED`.

## Dispatch service levels

| Priority | Dispatch target | Escalate after |
| --- | --- | --- |
| EXPRESS | 2 hours from creation | 4 hours |
| STANDARD | 24 hours from creation | 48 hours |
| ECONOMY | 72 hours from creation | 96 hours |

A shipment exceeding its escalation window should be reported to the duty manager.

## Change control

Any action that writes to production — assigning a trailer, changing a status, clearing a hold —
requires human approval before execution. Read-only investigation needs no approval.
