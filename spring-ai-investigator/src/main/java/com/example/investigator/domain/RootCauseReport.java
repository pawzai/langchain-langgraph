package com.example.investigator.domain;

import java.io.Serializable;
import java.util.List;

import com.fasterxml.jackson.annotation.JsonPropertyDescription;

/** Structured result of the Generate Root-Cause Report node. */
public record RootCauseReport(

        @JsonPropertyDescription("The single most likely cause, in one or two sentences.")
        String rootCause,

        @JsonPropertyDescription("Concrete findings that support the cause, such as a NULL column or an exact log message.")
        List<String> evidence,

        @JsonPropertyDescription("Confidence percentage between 0 and 100.")
        int confidence,

        @JsonPropertyDescription("The operational step that resolves the issue.")
        String recommendedAction,

        @JsonPropertyDescription("True if the recommended action would write to production, such as assigning a trailer or changing a status.")
        boolean requiresApproval) implements Serializable {

    public RootCauseReport {
        rootCause = (rootCause == null) ? "" : rootCause;
        recommendedAction = (recommendedAction == null) ? "" : recommendedAction;
        evidence = (evidence == null) ? List.of() : List.copyOf(evidence);
        confidence = Math.clamp(confidence, 0, 100);
    }

    public RootCauseReport requiringApproval() {
        return new RootCauseReport(rootCause, evidence, confidence, recommendedAction, true);
    }

    public RootCauseReport withRecommendedAction(String action) {
        return new RootCauseReport(rootCause, evidence, confidence, action, requiresApproval);
    }
}
