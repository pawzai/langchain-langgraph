package com.example.investigator.domain;

/**
 * @param question the production issue to investigate
 * @param threadId reuse a previous thread to ask a follow-up with memory; null starts a new one
 * @param fast     override the configured model choice for this call; null uses configuration
 */
public record InvestigateRequest(String question, String threadId, Boolean fast) {

    public static InvestigateRequest of(String question) {
        return new InvestigateRequest(question, null, null);
    }

    public static InvestigateRequest of(String question, Boolean fast) {
        return new InvestigateRequest(question, null, fast);
    }
}
