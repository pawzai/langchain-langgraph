package com.example.investigator.graph.nodes;

import java.util.List;
import java.util.Map;

import com.example.investigator.graph.InvestigationState;
import org.bsc.langgraph4j.action.NodeAction;
import org.springframework.stereotype.Component;

/**
 * Marks the transition back to planning after an insufficient verdict.
 *
 * <p>It holds no logic of its own: the verdict is already in state and the planner reads it. The
 * node exists so that re-planning is visible in the graph diagram and in the trace, rather than
 * being an invisible backward edge.
 */
@Component
public class RefinePlanNode implements NodeAction<InvestigationState> {

    @Override
    public Map<String, Object> apply(InvestigationState state) {
        return Map.of(InvestigationState.TRACE,
                List.of("Evidence was thin, so re-planning with different searches."));
    }
}
