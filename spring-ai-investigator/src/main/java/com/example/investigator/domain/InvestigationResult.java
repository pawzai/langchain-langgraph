package com.example.investigator.domain;

import java.util.List;

/** Everything the UI or an API client needs to render one investigation. */
public record InvestigationResult(
        String threadId,
        IssueKind kind,
        String summary,
        InvestigationPlan plan,
        List<EvidenceItem> evidence,
        RootCauseReport report,
        String answer,
        int loops,
        boolean awaitingApproval,
        List<String> trace) {

    public InvestigationResult {
        evidence = (evidence == null) ? List.of() : List.copyOf(evidence);
        trace = (trace == null) ? List.of() : List.copyOf(trace);
        answer = (answer == null) ? "" : answer;
        summary = (summary == null) ? "" : summary;
    }

    public boolean hasReport() {
        return report != null;
    }

    public boolean hasAnswer() {
        return !answer.isBlank();
    }

    /** True when the graph re-planned at least once to close an evidence gap. */
    public boolean rePlanned() {
        return loops > 1;
    }
}
