package com.example.investigator.graph.nodes;

import java.util.List;
import java.util.Map;

import com.example.investigator.domain.EvidenceItem;
import com.example.investigator.graph.InvestigationState;
import com.example.investigator.tools.KnowledgeTool;
import org.bsc.langgraph4j.action.NodeAction;
import org.springframework.stereotype.Component;

/** Retrieves the documented rules relevant to the issue. */
@Component
public class SearchKnowledgeNode implements NodeAction<InvestigationState> {

    private final KnowledgeTool knowledgeTool;

    public SearchKnowledgeNode(KnowledgeTool knowledgeTool) {
        this.knowledgeTool = knowledgeTool;
    }

    @Override
    public Map<String, Object> apply(InvestigationState state) {
        if (state.plan() == null || !state.plan().searchKnowledge()) {
            return Map.of();
        }
        String query = state.plan().knowledgeQuery();
        String passages = knowledgeTool.search(query);

        return Map.of(
                InvestigationState.EVIDENCE, List.of(new EvidenceItem("knowledge", passages)),
                InvestigationState.TRACE, List.of("Searched documentation for \"%s\".".formatted(query)));
    }
}
