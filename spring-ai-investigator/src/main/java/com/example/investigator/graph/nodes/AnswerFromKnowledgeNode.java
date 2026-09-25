package com.example.investigator.graph.nodes;

import java.util.List;
import java.util.Map;

import com.example.investigator.graph.InvestigationState;
import com.example.investigator.llm.ModelGateway;
import org.bsc.langgraph4j.action.NodeAction;
import org.springframework.stereotype.Component;

/**
 * Answers a documentation question directly.
 *
 * <p>The short path: a rules question does not need a root-cause report or an approval gate, and
 * forcing it through them would be slower and would read as bureaucratic nonsense.
 */
@Component
public class AnswerFromKnowledgeNode implements NodeAction<InvestigationState> {

    private static final String PROMPT = """
            Answer the question using only the documentation below.

            Be direct and concise. If the documentation lists conditions or steps, keep them as a
            list. If the documentation does not cover the question, say so plainly.

            Question: %s

            Documentation:
            %s""";

    private final ModelGateway models;

    public AnswerFromKnowledgeNode(ModelGateway models) {
        this.models = models;
    }

    @Override
    public Map<String, Object> apply(InvestigationState state) {
        String answer = models.text(
                PROMPT.formatted(state.question(), state.renderEvidence()), state.fast());

        return Map.of(
                InvestigationState.ANSWER, answer,
                InvestigationState.TRACE, List.of("Answered directly from the documentation."));
    }
}
