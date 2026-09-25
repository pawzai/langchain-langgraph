# Shipment Workflow Rules

## Status lifecycle

A shipment moves through these statuses in order:

`CREATED` -> `READY_FOR_DISPATCH` -> `IN_TRANSIT` -> `DELIVERED`

A shipment may also enter `ON_HOLD` from any status when a compliance check fails.

## Transition: CREATED -> READY_FOR_DISPATCH

This is the most commonly blocked transition. All three conditions must hold:

1. **Trailer assigned.** The shipment must have a non-null `trailer_id`.
2. **Trailer active.** The referenced trailer must have `status = 'ACTIVE'`. Trailers in
   `MAINTENANCE` or `RETIRED` are rejected.
3. **Location validation.** The shipment `location` must be a facility code enabled for
   outbound dispatch.

If any condition fails, `ShipmentWorkflowService` leaves the shipment in `CREATED` and emits an
error to the application log. The workflow does not retry automatically.

## Transition: READY_FOR_DISPATCH -> IN_TRANSIT

Requires a driver assigned to the trailer and a confirmed departure scan.

## Transition: IN_TRANSIT -> DELIVERED

Requires a proof-of-delivery record and an arrival scan at the destination facility.

## Enabled outbound facilities

| Code | Facility | Outbound dispatch |
| --- | --- | --- |
| SEA | Seattle | Enabled |
| PDX | Portland | Enabled |
| DFW | Dallas Fort Worth | Enabled |
| BOI | Boise | Disabled — inbound only |
