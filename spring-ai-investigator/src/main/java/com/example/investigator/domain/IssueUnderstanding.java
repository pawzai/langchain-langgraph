package com.example.investigator.domain;

import java.io.Serializable;
import java.util.List;

import com.fasterxml.jackson.annotation.JsonPropertyDescription;

/**
 * Structured result of the Understand Issue node.
 *
 * <p>{@link Serializable} because the checkpoint saver deep-copies graph state between supersteps.
 */
public record IssueUnderstanding(

        @JsonPropertyDescription("""
                KNOWLEDGE = answerable from documentation alone and no specific incident is named; \
                INVESTIGATION = a specific entity is misbehaving and evidence is needed; \
                REMEDIATION = the user wants a fix applied to a specific incident""")
        IssueKind kind,

        @JsonPropertyDescription("One sentence restating the issue.")
        String summary,

        @JsonPropertyDescription("Identifiers mentioned, for example ['SHP-1007']. Empty if none.")
        List<String> entityIds) implements Serializable {

    public IssueUnderstanding {
        if (kind == null) {
            kind = IssueKind.INVESTIGATION;
        }
        if (summary == null) {
            summary = "";
        }
        entityIds = (entityIds == null) ? List.of() : List.copyOf(entityIds);
    }

    /** First shipment identifier mentioned, if any. */
    public String primaryShipmentId() {
        return entityIds.stream()
                .map(id -> id.trim().toUpperCase())
                .filter(id -> id.startsWith("SHP-"))
                .findFirst()
                .orElse(null);
    }
}
