package com.example.investigator.domain;

/**
 * @param threadId the paused investigation to resume
 * @param decision "approve", "reject", or replacement text for the recommended action
 */
public record ApprovalRequest(String threadId, String decision) {
}
