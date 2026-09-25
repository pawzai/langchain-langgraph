package com.example.investigator.graph.nodes;

import java.util.List;
import java.util.Map;

import com.example.investigator.domain.EvidenceItem;
import com.example.investigator.graph.InvestigationState;
import com.example.investigator.tools.LogSearchTool;
import org.bsc.langgraph4j.action.NodeAction;
import org.springframework.stereotype.Component;

/** Searches the application log for lines mentioning the issue. */
@Component
public class InspectLogsNode implements NodeAction<InvestigationState> {

    private final LogSearchTool logSearchTool;

    public InspectLogsNode(LogSearchTool logSearchTool) {
        this.logSearchTool = logSearchTool;
    }

    @Override
    public Map<String, Object> apply(InvestigationState state) {
        if (state.plan() == null || !state.plan().inspectLogs()) {
            return Map.of();
        }
        String query = state.plan().logQuery();
        String matches = logSearchTool.searchAsText(query);

        return Map.of(
                InvestigationState.EVIDENCE, List.of(new EvidenceItem("logs", matches)),
                InvestigationState.TRACE, List.of("Searched logs for \"%s\".".formatted(query)));
    }
}
