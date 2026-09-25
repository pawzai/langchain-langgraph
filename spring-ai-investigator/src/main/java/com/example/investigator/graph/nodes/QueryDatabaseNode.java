package com.example.investigator.graph.nodes;

import java.util.List;
import java.util.Map;

import com.example.investigator.domain.EvidenceItem;
import com.example.investigator.graph.InvestigationState;
import com.example.investigator.llm.ModelGateway;
import com.example.investigator.tools.SqlQueryTool;
import org.bsc.langgraph4j.action.NodeAction;
import org.springframework.stereotype.Component;

/**
 * Reads the shipping tables.
 *
 * <p>When a shipment identifier is known, a fixed query runs instead of a generated one. That is
 * the single most important correctness decision in the workflow: the fixed query LEFT JOINs the
 * trailer, so an unassigned trailer shows up as NULL. A model-written inner join returns zero rows
 * and the root cause disappears. Only the open-ended case falls back to a generated query.
 */
@Component
public class QueryDatabaseNode implements NodeAction<InvestigationState> {

    private static final String SQL_PROMPT = """
            Write one read-only SQLite SELECT that helps answer the question.

            Schema:
            %s

            Rules:
            - Return only the SQL, with no explanation and no code fence.
            - A single SELECT statement, no semicolon.
            - Use LEFT JOIN so that missing related rows stay visible.
            - Include a LIMIT of at most 20.

            Question: %s""";

    private final SqlQueryTool sqlQueryTool;
    private final ModelGateway models;

    public QueryDatabaseNode(SqlQueryTool sqlQueryTool, ModelGateway models) {
        this.sqlQueryTool = sqlQueryTool;
        this.models = models;
    }

    @Override
    public Map<String, Object> apply(InvestigationState state) {
        if (state.plan() == null || !state.plan().queryDatabase()) {
            return Map.of();
        }

        String shipmentId = state.understanding() == null
                ? null
                : state.understanding().primaryShipmentId();

        String output;
        String traceLine;
        if (shipmentId != null) {
            output = sqlQueryTool.describeShipment(shipmentId);
            traceLine = "Queried the database for %s and its trailer and facility.".formatted(shipmentId);
        } else {
            String sql = cleanSql(models.text(
                    SQL_PROMPT.formatted(SqlQueryTool.SCHEMA, state.question()), state.fast()));
            output = sqlQueryTool.runQuery(sql);
            traceLine = "Ran a generated query: %s".formatted(sql);
        }

        return Map.of(
                InvestigationState.EVIDENCE, List.of(new EvidenceItem("database", output)),
                InvestigationState.TRACE, List.of(traceLine));
    }

    /** Models wrap SQL in fences even when told not to. */
    private static String cleanSql(String raw) {
        String sql = raw.strip();
        if (sql.startsWith("```")) {
            sql = sql.replaceAll("^```(?:sql)?\\s*", "").replaceAll("```\\s*$", "").strip();
        }
        return sql;
    }
}
