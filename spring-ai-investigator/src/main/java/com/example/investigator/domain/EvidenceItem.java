package com.example.investigator.domain;

import java.io.Serializable;

/**
 * One block of gathered evidence.
 *
 * <p>{@link Serializable} because checkpoint savers may serialize graph state.
 *
 * @param source one of {@code knowledge}, {@code logs} or {@code database}
 * @param content the raw text shown to the model and to the user
 */
public record EvidenceItem(String source, String content) implements Serializable {

    public String displayName() {
        return switch (source) {
            case "knowledge" -> "Documentation";
            case "logs" -> "Application logs";
            case "database" -> "Database";
            default -> source;
        };
    }
}
