package com.example.investigator.service;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import com.example.investigator.config.AppProperties;
import com.example.investigator.rag.KnowledgeIndexer;
import com.example.investigator.tools.KnowledgeTool;
import com.example.investigator.tools.LogSearchTool;
import com.example.investigator.tools.SqlQueryTool;
import org.springframework.ai.embedding.EmbeddingModel;
import org.springframework.stereotype.Service;

/**
 * The pre-demo checklist: five checks that between them prove every moving part is working.
 *
 * <p>Each check fails with a message that says what to do about it, because the point is to
 * diagnose a broken environment before a demo rather than during one.
 */
@Service
public class HealthCheckService {

    public record Check(String name, boolean passed, String detail) {}

    public record Report(boolean healthy, List<Check> checks) {}

    private final AppProperties properties;
    private final EmbeddingModel embeddingModel;
    private final SqlQueryTool sqlQueryTool;
    private final LogSearchTool logSearchTool;
    private final KnowledgeTool knowledgeTool;
    private final KnowledgeIndexer knowledgeIndexer;

    public HealthCheckService(AppProperties properties, EmbeddingModel embeddingModel,
                              SqlQueryTool sqlQueryTool, LogSearchTool logSearchTool,
                              KnowledgeTool knowledgeTool, KnowledgeIndexer knowledgeIndexer) {
        this.properties = properties;
        this.embeddingModel = embeddingModel;
        this.sqlQueryTool = sqlQueryTool;
        this.logSearchTool = logSearchTool;
        this.knowledgeTool = knowledgeTool;
        this.knowledgeIndexer = knowledgeIndexer;
    }

    public Report run() {
        List<Check> checks = new ArrayList<>();
        checks.add(ollamaReachable());
        checks.add(databaseSeeded());
        checks.add(sqlSafetyRejectsWrites());
        checks.add(logSearchFindsTheError());
        checks.add(knowledgeIndexAnswers());

        boolean healthy = checks.stream().allMatch(Check::passed);
        return new Report(healthy, checks);
    }

    private Check ollamaReachable() {
        try {
            int dimensions = embeddingModel.embed("health check").length;
            return new Check("Ollama reachable and the embedding model responds", true,
                    "%s returned a %d-dimension vector".formatted(properties.embeddingModel(), dimensions));
        } catch (RuntimeException ex) {
            return new Check("Ollama reachable and the embedding model responds", false,
                    "Could not reach Ollama. Start it with 'ollama serve' and confirm "
                            + properties.embeddingModel() + " is pulled. " + ex.getMessage());
        }
    }

    private Check databaseSeeded() {
        try {
            List<Map<String, Object>> rows = sqlQueryTool.select(
                    "SELECT shipment_id, trailer_id FROM shipments WHERE shipment_id = 'SHP-1007'");
            if (rows.isEmpty()) {
                return new Check("Database seeded with the demo data", false,
                        "SHP-1007 is missing. Delete data/shipping.db and restart to re-seed.");
            }
            boolean nullTrailer = rows.getFirst().get("trailer_id") == null;
            return new Check("Database seeded with the demo data", nullTrailer,
                    nullTrailer
                            ? "SHP-1007 exists and has no trailer assigned, as the demo expects"
                            : "SHP-1007 has a trailer, so the headline demo will not show a failure");
        } catch (Exception ex) {
            return new Check("Database seeded with the demo data", false, ex.getMessage());
        }
    }

    private Check sqlSafetyRejectsWrites() {
        String result = sqlQueryTool.runQuery("DELETE FROM shipments");
        boolean rejected = result.startsWith("Query rejected");
        return new Check("SQL safety rejects writes", rejected,
                rejected ? "A DELETE was refused before reaching the database" : result);
    }

    private Check logSearchFindsTheError() {
        List<String> lines = logSearchTool.search("SHP-1007");
        boolean found = !lines.isEmpty() && lines.getFirst().contains("ERROR");
        return new Check("Log search finds the ERROR line", found,
                found ? lines.getFirst()
                        : "No ERROR line for SHP-1007. Check data/logs/application.log.");
    }

    private Check knowledgeIndexAnswers() {
        try {
            if (knowledgeIndexer.isEmpty()) {
                return new Check("Knowledge index returns the dispatch rules", false,
                        "The index is empty. Restart the application to rebuild it.");
            }
            String passages = knowledgeTool.search("conditions required for READY_FOR_DISPATCH");
            boolean relevant = passages.toLowerCase().contains("trailer");
            return new Check("Knowledge index returns the dispatch rules", relevant,
                    relevant ? "Retrieval returned the dispatch rules"
                            : "Retrieval returned something unrelated: " + truncate(passages));
        } catch (RuntimeException ex) {
            return new Check("Knowledge index returns the dispatch rules", false, ex.getMessage());
        }
    }

    private static String truncate(String text) {
        return text.length() <= 160 ? text : text.substring(0, 160) + "...";
    }
}
