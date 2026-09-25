# Shipment Troubleshooting Guide

## Symptom: shipment stuck in CREATED

Check in this order:

1. **Is a trailer assigned?** Query the shipment row and inspect `trailer_id`. A `NULL` value is
   the single most frequent cause of a stuck `CREATED` shipment. Resolution: assign an active
   trailer, then retry the workflow.
2. **Is the assigned trailer active?** Join to the `trailers` table and check `status`. A trailer
   in `MAINTENANCE` blocks dispatch even though `trailer_id` is populated. Resolution: reassign to
   an active trailer.
3. **Is the location enabled for outbound?** A shipment at an inbound-only facility such as `BOI`
   cannot dispatch. Resolution: transfer the shipment to an outbound-enabled facility.

The log message `No active trailer assignment found` confirms cause 1 or 2. The message
`Location not enabled for outbound dispatch` confirms cause 3.

## Symptom: shipment stuck in READY_FOR_DISPATCH

Usually a missing driver assignment or a missed departure scan. Check the log for
`DriverAssignmentService` warnings.

## Symptom: shipment moved to ON_HOLD

A compliance check failed. `ComplianceService` logs the specific rule. These require a compliance
officer to clear the hold; engineering cannot override it.

## Escalation

If database and log evidence disagree, escalate to the platform team rather than forcing a status
change. Manual status edits bypass validation and corrupt downstream billing.
