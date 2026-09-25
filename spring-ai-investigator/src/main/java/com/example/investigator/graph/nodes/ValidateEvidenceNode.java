package com.example.investigator.graph.nodes;

import java.util.List;
import java.util.Map;

import com.example.investigator.config.AppProperties;
import com.example.investigator.domain.EvidenceVerdict;
import com.example.investigator.graph.InvestigationState;
import com.example.investigator.llm.ModelGateway;
import org.bsc.langgraph4j.action.NodeAction;
import org.springframework.stereotype.Component;

/**
 * Decides whether the gathered evidence actually supports a conclusion.
 *
 * <p>This is the quality gate that lets the graph loop back and re-plan instead of confidently
 * inventing a cause. The loop is bounded so a stubborn question cannot spin forever.
 */
@Component
public class ValidateEvidenceNode implements NodeAction<InvestigationState> {

    private static final String PROMPT = """
            You are checking whether the evidence below is enough to state a root cause with
            confidence.

            Answer sufficient = true only if the evidence identifies a concrete, specific cause.
            Answer sufficient = false if the evidence is empty, generic, or does not explain the
            symptom, and say what is missing.

            Issue: %s

            Evidence:
            %s""";

    private final ModelGateway models;
    private final AppProperties properties;

    public ValidateEvidenceNode(ModelGateway models, AppProperties properties) {
        this.models = models;
        this.properties = properties;
    }

    @Override
    public Map<String, Object> apply(InvestigationState state) {
        if (state.loops() >= properties.maxInvestigationLoops()) {
            EvidenceVerdict forced = EvidenceVerdict.forced(
                    "Loop limit reached; reporting on the evidence available.");
            return Map.of(
                    InvestigationState.VERDICT, forced,
                    InvestigationState.TRACE, List.of(
                            "Reached the %d-attempt limit, so proceeding with what was found."
                                    .formatted(properties.maxInvestigationLoops())));
        }

        EvidenceVerdict verdict = models.structured(
                PROMPT.formatted(state.question(), state.renderEvidence()),
                EvidenceVerdict.class,
                state.fast());

        String traceLine = verdict.sufficient()
                ? "Checked the evidence: sufficient to name a cause."
                : "Checked the evidence: insufficient (%s).".formatted(verdict.missing());

        return Map.of(
                InvestigationState.VERDICT, verdict,
                InvestigationState.TRACE, List.of(traceLine));
    }
}
