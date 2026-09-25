package com.example.investigator.graph.nodes;

import java.util.List;
import java.util.Map;

import com.example.investigator.domain.IssueKind;
import com.example.investigator.domain.RootCauseReport;
import com.example.investigator.graph.InvestigationState;
import com.example.investigator.llm.ModelGateway;
import org.bsc.langgraph4j.action.NodeAction;
import org.springframework.stereotype.Component;

/** Turns the gathered evidence into a root-cause report with a recommended action. */
@Component
public class GenerateReportNode implements NodeAction<InvestigationState> {

    private static final String PROMPT = """
            Write a root-cause analysis from the evidence below.

            Rules:
            - Name one specific cause, not a list of possibilities.
            - Ground every evidence bullet in the material below. Quote the exact value or log
              message, for example "trailer_id is NULL" or the exact ERROR line.
            - Do not invent evidence. If something is not shown below, do not claim it.
            - Set confidence honestly: high only when the evidence is direct and specific.
            - Set requiresApproval to true if the recommended action would change production data,
              such as assigning a trailer, changing a status, or releasing a hold.

            Issue: %s

            Evidence:
            %s""";

    private final ModelGateway models;

    public GenerateReportNode(ModelGateway models) {
        this.models = models;
    }

    @Override
    public Map<String, Object> apply(InvestigationState state) {
        RootCauseReport report = models.structured(
                PROMPT.formatted(state.question(), state.renderEvidence()),
                RootCauseReport.class,
                state.fast());

        // A remediation request is a write by definition, so the gate is not left to the model.
        if (state.understanding() != null
                && state.understanding().kind() == IssueKind.REMEDIATION
                && !report.requiresApproval()) {
            report = report.requiringApproval();
        }

        return Map.of(
                InvestigationState.REPORT, report,
                InvestigationState.TRACE, List.of(
                        "Wrote the root-cause report (%d%% confidence).".formatted(report.confidence())));
    }
}
