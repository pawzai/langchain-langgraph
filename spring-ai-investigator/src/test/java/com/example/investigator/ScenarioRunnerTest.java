package com.example.investigator;

import static org.assertj.core.api.Assertions.assertThat;

import com.example.investigator.domain.InvestigateRequest;
import com.example.investigator.domain.InvestigationResult;
import com.example.investigator.domain.IssueKind;
import com.example.investigator.rag.KnowledgeIndexer;
import com.example.investigator.service.InvestigationService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

/**
 * The five demo scenarios.
 *
 * <p>The last two exist to prove the agent is reading evidence rather than replaying one memorised
 * answer: three shipments are stuck for three different reasons, and only the database row
 * distinguishes them.
 */
@SpringBootTest
class ScenarioRunnerTest {

    @Autowired
    private InvestigationService service;

    @Autowired
    private KnowledgeIndexer knowledgeIndexer;

    @BeforeEach
    void ensureIndex() {
        knowledgeIndexer.loadOrBuild();
    }

    private InvestigationResult run(String question) {
        return service.investigate(InvestigateRequest.of(question, true));
    }

    private static String databaseEvidence(InvestigationResult result) {
        return result.evidence().stream()
                .filter(item -> item.source().equals("database"))
                .map(item -> item.content())
                .findFirst()
                .orElse("");
    }

    @Test
    void scenarioOneStuckShipmentFindsTheMissingTrailer() {
        InvestigationResult result = run("Why is shipment SHP-1007 stuck in CREATED status?");

        assertThat(result.hasReport()).isTrue();
        assertThat(databaseEvidence(result)).contains("trailer_id: NULL");
        assertThat(result.report().confidence()).isGreaterThan(0);
    }

    @Test
    void scenarioTwoRulesQuestionAnswersFromDocumentation() {
        InvestigationResult result = run(
                "What conditions must be met before a shipment can be marked READY_FOR_DISPATCH?");

        assertThat(result.kind()).isEqualTo(IssueKind.KNOWLEDGE);
        assertThat(result.hasAnswer()).isTrue();
        assertThat(result.answer().toLowerCase()).contains("trailer");
    }

    @Test
    void scenarioThreeRemediationStopsAtTheApprovalGate() {
        InvestigationResult result = run("Fix shipment SHP-1007 so it can be dispatched.");

        assertThat(result.awaitingApproval()).isTrue();
        assertThat(result.report().requiresApproval()).isTrue();
    }

    @Test
    void scenarioFourDetectsATrailerInMaintenance() {
        InvestigationResult result = run("Why can't shipment SHP-1010 be dispatched?");

        String database = databaseEvidence(result);
        assertThat(database).contains("trailer_status: MAINTENANCE");
        // A trailer *is* assigned here, so the SHP-1007 answer would be wrong.
        assertThat(database).doesNotContain("trailer_id: NULL");
        assertThat(result.hasReport()).isTrue();
    }

    @Test
    void scenarioFiveDetectsAnInboundOnlyFacility() {
        InvestigationResult result = run("Why is shipment SHP-1013 not moving?");

        String database = databaseEvidence(result);
        assertThat(database).contains("outbound_enabled: 0");
        assertThat(database).contains("trailer_status: ACTIVE");
        assertThat(result.hasReport()).isTrue();
    }
}
