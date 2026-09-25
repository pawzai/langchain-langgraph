package com.example.investigator.domain;

import java.io.Serializable;

import com.fasterxml.jackson.annotation.JsonPropertyDescription;

/** Structured result of the Validate Evidence node, which decides whether to re-plan. */
public record EvidenceVerdict(

        @JsonPropertyDescription("True if a root cause can be stated with confidence from the evidence given.")
        boolean sufficient,

        @JsonPropertyDescription("If not sufficient, what evidence is still missing.")
        String missing) implements Serializable {

    public EvidenceVerdict {
        missing = (missing == null) ? "" : missing;
    }

    public static EvidenceVerdict forced(String reason) {
        return new EvidenceVerdict(true, reason);
    }
}
