package com.example.shipping.workflow;

import java.time.Duration;
import java.time.Instant;
import java.util.Optional;

/**
 * Advances shipments through the status lifecycle.
 *
 * This is the service named in the application log lines. It is included in the knowledge base
 * so an investigation can quote the code that produced an error, not just the error text.
 */
public class ShipmentWorkflowService {

    private static final Logger log = LoggerFactory.getLogger(ShipmentWorkflowService.class);

    private final ShipmentRepository shipments;
    private final TrailerRepository trailers;
    private final FacilityRepository facilities;

    public ShipmentWorkflowService(
            ShipmentRepository shipments,
            TrailerRepository trailers,
            FacilityRepository facilities) {
        this.shipments = shipments;
        this.trailers = trailers;
        this.facilities = facilities;
    }

    /**
     * Attempt the CREATED -> READY_FOR_DISPATCH transition.
     *
     * All three preconditions must hold. On failure the shipment is deliberately left in
     * CREATED and an error is logged; there is no automatic retry, because a retry cannot fix
     * a missing trailer or a disabled facility.
     */
    public TransitionResult readyForDispatch(String shipmentId) {
        Shipment shipment = shipments.findById(shipmentId)
                .orElseThrow(() -> new ShipmentNotFoundException(shipmentId));

        if (shipment.getStatus() != Status.CREATED) {
            return TransitionResult.skipped(
                    "Shipment " + shipmentId + " is not in CREATED.");
        }

        if (shipment.getTrailerId() == null) {
            log.error("No active trailer assignment found for {}.", shipmentId);
            return TransitionResult.blocked(BlockReason.MISSING_TRAILER);
        }

        Optional<Trailer> trailer = trailers.findById(shipment.getTrailerId());
        if (trailer.isEmpty() || trailer.get().getStatus() != TrailerStatus.ACTIVE) {
            log.error(
                    "Trailer {} for shipment {} is not ACTIVE.",
                    shipment.getTrailerId(),
                    shipmentId);
            return TransitionResult.blocked(BlockReason.TRAILER_UNAVAILABLE);
        }

        Facility facility = facilities.findByCode(shipment.getLocation())
                .orElseThrow(() -> new FacilityNotFoundException(shipment.getLocation()));

        if (!facility.isOutboundEnabled()) {
            log.error(
                    "Facility {} is not enabled for outbound dispatch; shipment {} cannot leave.",
                    facility.getCode(),
                    shipmentId);
            return TransitionResult.blocked(BlockReason.FACILITY_DISABLED);
        }

        shipment.setStatus(Status.READY_FOR_DISPATCH);
        shipments.save(shipment);
        log.info("Shipment {} moved to READY_FOR_DISPATCH.", shipmentId);
        return TransitionResult.advanced(Status.READY_FOR_DISPATCH);
    }

    /**
     * Advance a dispatched shipment. Requires a driver on the trailer and a departure scan.
     */
    public TransitionResult inTransit(String shipmentId) {
        Shipment shipment = shipments.findById(shipmentId)
                .orElseThrow(() -> new ShipmentNotFoundException(shipmentId));

        if (shipment.getStatus() != Status.READY_FOR_DISPATCH) {
            return TransitionResult.skipped(
                    "Shipment " + shipmentId + " is not READY_FOR_DISPATCH.");
        }

        Trailer trailer = trailers.findById(shipment.getTrailerId())
                .orElseThrow(() -> new TrailerNotFoundException(shipment.getTrailerId()));

        if (trailer.getDriverId() == null) {
            log.error("No driver assigned to trailer {}.", trailer.getTrailerId());
            return TransitionResult.blocked(BlockReason.NO_DRIVER);
        }

        if (!shipment.hasDepartureScan()) {
            log.warn("Departure scan missing for shipment {}.", shipmentId);
            return TransitionResult.blocked(BlockReason.NO_DEPARTURE_SCAN);
        }

        shipment.setStatus(Status.IN_TRANSIT);
        shipments.save(shipment);
        return TransitionResult.advanced(Status.IN_TRANSIT);
    }

    /**
     * Classify how long a shipment has been blocked, for SLA reporting.
     */
    public boolean isBreachingSla(Shipment shipment, Instant now) {
        Duration blocked = Duration.between(shipment.getCreatedAt(), now);
        return blocked.compareTo(slaWindow(shipment.getPriority())) > 0;
    }

    private Duration slaWindow(Priority priority) {
        return switch (priority) {
            case EXPRESS -> Duration.ofHours(2);
            case STANDARD -> Duration.ofHours(24);
            case ECONOMY -> Duration.ofHours(72);
        };
    }
}
