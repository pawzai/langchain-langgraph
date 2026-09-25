package com.example.investigator.domain;

/** How a request should be handled, which drives routing in the graph. */
public enum IssueKind {
    /** Answerable from the documentation alone. */
    KNOWLEDGE,
    /** Needs log or database evidence to establish a cause. */
    INVESTIGATION,
    /** Asks for a fix to be applied, so it always needs human approval. */
    REMEDIATION
}
