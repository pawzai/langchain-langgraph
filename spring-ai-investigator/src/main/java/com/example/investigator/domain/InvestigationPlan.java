package com.example.investigator.domain;

import java.io.Serializable;
import java.util.ArrayList;
import java.util.List;

import com.fasterxml.jackson.annotation.JsonPropertyDescription;

/** Structured result of the Create Investigation Plan node. It drives the parallel fan-out. */
public record InvestigationPlan(

        @JsonPropertyDescription("True to search the workflow rules and troubleshooting guide.")
        boolean searchKnowledge,

        @JsonPropertyDescription("True to search the application log files.")
        boolean inspectLogs,

        @JsonPropertyDescription("True to query the shipping database.")
        boolean queryDatabase,

        @JsonPropertyDescription("Search phrase for the documentation. The symptom or rule name works best, not the identifier.")
        String knowledgeQuery,

        @JsonPropertyDescription("Search term for the logs. A bare identifier such as SHP-1007 works best.")
        String logQuery,

        @JsonPropertyDescription("One sentence explaining why these sources were chosen.")
        String reasoning) implements Serializable {

    public InvestigationPlan {
        knowledgeQuery = (knowledgeQuery == null) ? "" : knowledgeQuery;
        logQuery = (logQuery == null) ? "" : logQuery;
        reasoning = (reasoning == null) ? "" : reasoning;
    }

    /** Human-readable list of the sources this plan selected. */
    public List<String> chosenSources() {
        List<String> chosen = new ArrayList<>();
        if (searchKnowledge) {
            chosen.add("knowledge");
        }
        if (inspectLogs) {
            chosen.add("logs");
        }
        if (queryDatabase) {
            chosen.add("database");
        }
        return chosen;
    }

    public InvestigationPlan withKnowledge(boolean enabled, String query) {
        return new InvestigationPlan(enabled, inspectLogs, queryDatabase, query, logQuery, reasoning);
    }

    public InvestigationPlan withLogQuery(String query) {
        return new InvestigationPlan(searchKnowledge, inspectLogs, queryDatabase, knowledgeQuery, query, reasoning);
    }
}
