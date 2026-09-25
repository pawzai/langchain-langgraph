package com.example.investigator.graph.nodes;

import java.util.List;
import java.util.Map;

import com.example.investigator.domain.EvidenceVerdict;
import com.example.investigator.domain.InvestigationPlan;
import com.example.investigator.domain.IssueKind;
import com.example.investigator.domain.IssueUnderstanding;
import com.example.investigator.graph.InvestigationState;
import com.example.investigator.llm.ModelGateway;
import com.example.investigator.tools.SqlQueryTool;
import org.bsc.langgraph4j.action.NodeAction;
import org.springframework.stereotype.Component;

/** Chooses which evidence sources to use and writes the search phrase for each. */
@Component
public class CreatePlanNode implements NodeAction<InvestigationState> {

    private static final String PROMPT = """
            You are planning an investigation for a shipping platform.

            Three read-only sources are available:
            - knowledge: workflow rules, troubleshooting guide, business conditions and approval policy.
            - logs: application log lines from the shipping services.
            - database: shipment, trailer and facility tables.

            Database schema:
            %s

            Choose only the sources that will actually help, and write a precise search phrase for
            each one you choose.

            Guidance:
            - A rules or policy question needs knowledge only.
            - Diagnosing a specific entity needs all three: the rule, the log error and the row itself.
            - The log query works best as a bare identifier such as "SHP-1007".
            - The knowledge query works best as the symptom or the rule name, not the identifier.

            Issue type: %s
            Issue: %s
            Identifiers: %s
            Original request: %s%s""";

    private final ModelGateway models;

    public CreatePlanNode(ModelGateway models) {
        this.models = models;
    }

    @Override
    public Map<String, Object> apply(InvestigationState state) {
        IssueUnderstanding understanding = state.understanding();
        EvidenceVerdict verdict = state.verdict();

        String refinement = "";
        if (verdict != null && !verdict.sufficient()) {
            refinement = """


                    A previous attempt was insufficient. Missing: %s. \
                    Choose different or broader search phrases this time."""
                    .formatted(verdict.missing());
        }

        String entities = understanding.entityIds().isEmpty()
                ? "none"
                : String.join(", ", understanding.entityIds());

        InvestigationPlan plan = models.structured(
                PROMPT.formatted(SqlQueryTool.SCHEMA, understanding.kind().name().toLowerCase(),
                        understanding.summary(), entities, state.question(), refinement),
                InvestigationPlan.class,
                state.fast());

        plan = repair(plan, understanding, state.question());

        return Map.of(
                InvestigationState.PLAN, plan,
                InvestigationState.LOOPS, state.loops() + 1,
                InvestigationState.TRACE, List.of(
                        "Planned to use: %s.".formatted(String.join(", ", plan.chosenSources()))));
    }

    /**
     * The plan drives real branching, so repair obviously bad plans rather than letting the graph
     * fan out to nothing.
     */
    private static InvestigationPlan repair(InvestigationPlan plan, IssueUnderstanding understanding,
                                            String question) {
        if (!plan.searchKnowledge() && !plan.inspectLogs() && !plan.queryDatabase()) {
            plan = plan.withKnowledge(true, plan.knowledgeQuery());
        }
        // A proposed fix must be checked against the documented rules and approval policy, so the
        // model is not allowed to skip the documentation here.
        if (understanding.kind() == IssueKind.REMEDIATION) {
            plan = plan.withKnowledge(true, plan.knowledgeQuery());
        }
        if (plan.searchKnowledge() && plan.knowledgeQuery().isBlank()) {
            String fallback = understanding.summary().isBlank() ? question : understanding.summary();
            plan = plan.withKnowledge(true, fallback);
        }
        if (plan.inspectLogs() && plan.logQuery().isBlank()) {
            String fallback = understanding.entityIds().isEmpty()
                    ? question
                    : understanding.entityIds().getFirst();
            plan = plan.withLogQuery(fallback);
        }
        return plan;
    }
}
