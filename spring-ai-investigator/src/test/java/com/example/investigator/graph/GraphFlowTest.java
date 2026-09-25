package com.example.investigator.graph;

import static org.assertj.core.api.Assertions.assertThat;

import com.example.investigator.domain.ApprovalRequest;
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
 * Exercises the graph shape against real models. Uses the fast model throughout to keep the run
 * time reasonable; correctness of routing is what is being asserted, not answer quality.
 */
@SpringBootTest
class GraphFlowTest {

    @Autowired
    private InvestigationService service;

    @Autowired
    private KnowledgeIndexer knowledgeIndexer;

    @BeforeEach
    void ensureIndex() {
        knowledgeIndexer.loadOrBuild();
    }

    @Test
    void investigationGathersEvidenceFromAllThreeSourcesAndNamesTheCause() {
        InvestigationResult result = service.investigate(
                InvestigateRequest.of("Why is shipment SHP-1007 stuck in CREATED status?", true));

        assertThat(result.kind()).isIn(IssueKind.INVESTIGATION, IssueKind.REMEDIATION);
        assertThat(result.evidence()).isNotEmpty();
        assertThat(result.hasReport()).isTrue();

        // The database branch must have run and surfaced the NULL trailer.
        assertThat(result.evidence())
                .anySatisfy(item -> assertThat(item.source()).isEqualTo("database"));
        String database = result.evidence().stream()
                .filter(item -> item.source().equals("database"))
                .findFirst().orElseThrow().content();
        assertThat(database).contains("trailer_id: NULL");

        assertThat(result.report().rootCause()).isNotBlank();
        assertThat(result.trace()).isNotEmpty();
    }

    @Test
    void aRulesQuestionTakesTheShortPathAndSkipsTheReport() {
        InvestigationResult result = service.investigate(
                InvestigateRequest.of("What conditions must be met before a shipment can be "
                        + "marked READY_FOR_DISPATCH?", true));

        assertThat(result.kind()).isEqualTo(IssueKind.KNOWLEDGE);
        assertThat(result.hasAnswer()).isTrue();
        assertThat(result.hasReport()).isFalse();
        assertThat(result.awaitingApproval()).isFalse();
    }

    @Test
    void aRemediationRequestPausesForApprovalAndResumes() {
        InvestigationResult paused = service.investigate(
                InvestigateRequest.of("Fix shipment SHP-1007 so it can be dispatched.", true));

        assertThat(paused.awaitingApproval()).isTrue();
        assertThat(paused.hasReport()).isTrue();
        assertThat(paused.report().requiresApproval()).isTrue();

        InvestigationResult approved = service.resume(
                new ApprovalRequest(paused.threadId(), "approve"));

        assertThat(approved.awaitingApproval()).isFalse();
        assertThat(approved.trace()).anyMatch(line -> line.contains("approved"));
    }

    @Test
    void aRejectedActionIsRecordedAndNothingIsApplied() {
        InvestigationResult paused = service.investigate(
                InvestigateRequest.of("Assign a trailer to SHP-1007 to unblock it.", true));

        assertThat(paused.awaitingApproval()).isTrue();

        InvestigationResult rejected = service.resume(
                new ApprovalRequest(paused.threadId(), "reject"));

        assertThat(rejected.awaitingApproval()).isFalse();
        assertThat(rejected.trace()).anyMatch(line -> line.contains("rejected"));
    }
}
