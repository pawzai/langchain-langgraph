package com.example.investigator.graph.nodes;

import java.util.List;
import java.util.Map;

import com.example.investigator.domain.IssueUnderstanding;
import com.example.investigator.graph.InvestigationState;
import com.example.investigator.llm.ModelGateway;
import org.bsc.langgraph4j.action.NodeAction;
import org.springframework.stereotype.Component;

/** Classifies the request and extracts identifiers, which drives all downstream routing. */
@Component
public class UnderstandIssueNode implements NodeAction<InvestigationState> {

    private static final String PROMPT = """
            You triage production issues for a shipping platform.

            Classify the user's request and extract any identifiers.

            Classify as:
            - KNOWLEDGE when the answer is a documented rule or policy and no specific incident is named.
            - INVESTIGATION when a specific entity is misbehaving and evidence is needed to find the cause.
            - REMEDIATION when the user wants a fix applied or asks how to fix a specific incident.

            Shipment identifiers look like SHP-1007. Trailer identifiers look like TRL-311.

            Request: %s""";

    private final ModelGateway models;

    public UnderstandIssueNode(ModelGateway models) {
        this.models = models;
    }

    @Override
    public Map<String, Object> apply(InvestigationState state) {
        IssueUnderstanding understanding = models.structured(
                PROMPT.formatted(state.question()), IssueUnderstanding.class, state.fast());

        return Map.of(
                InvestigationState.UNDERSTANDING, understanding,
                InvestigationState.TRACE, List.of(
                        "Reasoning with %s.".formatted(models.modelName(state.fast())),
                        "Understood the request as a %s question."
                                .formatted(understanding.kind().name().toLowerCase())));
    }
}
