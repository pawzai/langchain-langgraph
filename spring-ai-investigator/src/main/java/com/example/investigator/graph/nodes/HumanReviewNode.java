package com.example.investigator.graph.nodes;

import java.util.List;
import java.util.Map;

import com.example.investigator.domain.RootCauseReport;
import com.example.investigator.graph.InvestigationState;
import org.bsc.langgraph4j.action.NodeAction;
import org.springframework.stereotype.Component;

/**
 * Records the reviewer's decision.
 *
 * <p>The pause itself is not implemented here. The graph is compiled with
 * {@code interruptBefore("humanReview")}, so execution stops before this node runs and the
 * checkpoint holds the state until a decision arrives. This node then runs on resume, which means
 * a decision is always present by the time it executes.
 */
@Component
public class HumanReviewNode implements NodeAction<InvestigationState> {

    public static final String APPROVE = "approve";
    public static final String REJECT = "reject";

    @Override
    public Map<String, Object> apply(InvestigationState state) {
        String decision = state.approvalDecision().strip();
        RootCauseReport report = state.report();

        if (decision.equalsIgnoreCase(APPROVE)) {
            return Map.of(InvestigationState.TRACE,
                    List.of("A human approved the recommended action."));
        }

        if (decision.equalsIgnoreCase(REJECT)) {
            return Map.of(InvestigationState.TRACE,
                    List.of("A human rejected the recommended action; nothing was applied."));
        }

        if (!decision.isBlank() && report != null) {
            return Map.of(
                    InvestigationState.REPORT, report.withRecommendedAction(decision),
                    InvestigationState.TRACE,
                    List.of("A human replaced the recommended action with their own."));
        }

        return Map.of(InvestigationState.TRACE, List.of("Review completed without a decision."));
    }
}
