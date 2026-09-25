package com.example.investigator.tools;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;

import com.example.investigator.rag.KnowledgeIndexer;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

/** Exercises the three evidence sources against the real seeded data and local embeddings. */
@SpringBootTest
class ToolsIntegrationTest {

    @Autowired
    private SqlQueryTool sqlQueryTool;

    @Autowired
    private LogSearchTool logSearchTool;

    @Autowired
    private KnowledgeTool knowledgeTool;

    @Autowired
    private KnowledgeIndexer knowledgeIndexer;

    @Test
    void databaseExposesTheNullTrailerThatCausesTheDemoFailure() {
        String output = sqlQueryTool.describeShipment("SHP-1007");

        assertThat(output).contains("SHP-1007");
        assertThat(output).contains("status: CREATED");
        // The LEFT JOIN is what makes this visible; an inner join would return no rows.
        assertThat(output).contains("trailer_id: NULL");
        assertThat(output).contains("facility_name: Seattle");
    }

    @Test
    void databaseDistinguishesTheOtherTwoCauses() {
        assertThat(sqlQueryTool.describeShipment("SHP-1010")).contains("trailer_status: MAINTENANCE");
        assertThat(sqlQueryTool.describeShipment("SHP-1013")).contains("outbound_enabled: 0");
    }

    @Test
    void unsafeQueriesAreRejectedAtTheToolBoundary() {
        assertThat(sqlQueryTool.runQuery("DELETE FROM shipments"))
                .startsWith("Query rejected by safety validation");
    }

    @Test
    void logSearchFindsTheErrorLineFirst() {
        List<String> lines = logSearchTool.search("SHP-1007");

        assertThat(lines).isNotEmpty();
        assertThat(lines.getFirst()).contains("ERROR");
        assertThat(lines.getFirst()).contains("No active trailer assignment found");
    }

    @Test
    void retrievalSurfacesTheDispatchRules() {
        knowledgeIndexer.loadOrBuild();

        String passages = knowledgeTool.search("conditions required for READY_FOR_DISPATCH");

        assertThat(passages).containsIgnoringCase("trailer");
        assertThat(passages).contains("shipment_workflow.md");
    }
}
