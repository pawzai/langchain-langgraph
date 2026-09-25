package com.example.investigator.graph;

import static org.bsc.langgraph4j.StateGraph.END;
import static org.bsc.langgraph4j.StateGraph.START;
import static org.bsc.langgraph4j.action.AsyncEdgeAction.edge_async;
import static org.bsc.langgraph4j.action.AsyncNodeAction.node_async;

import java.util.Map;

import com.example.investigator.domain.IssueKind;
import com.example.investigator.graph.nodes.AnswerFromKnowledgeNode;
import com.example.investigator.graph.nodes.CreatePlanNode;
import com.example.investigator.graph.nodes.GenerateReportNode;
import com.example.investigator.graph.nodes.HumanReviewNode;
import com.example.investigator.graph.nodes.InspectLogsNode;
import com.example.investigator.graph.nodes.QueryDatabaseNode;
import com.example.investigator.graph.nodes.RefinePlanNode;
import com.example.investigator.graph.nodes.SearchKnowledgeNode;
import com.example.investigator.graph.nodes.UnderstandIssueNode;
import com.example.investigator.graph.nodes.ValidateEvidenceNode;
import org.bsc.langgraph4j.CompileConfig;
import org.bsc.langgraph4j.CompiledGraph;
import org.bsc.langgraph4j.GraphStateException;
import org.bsc.langgraph4j.StateGraph;
import org.bsc.langgraph4j.checkpoint.MemorySaver;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Assembles the investigation workflow.
 *
 * <p>The three evidence nodes fan out from {@code gatherEvidence} and rejoin at
 * {@code combineEvidence}, so they run in the same superstep and their writes merge through the
 * appending channels. Each one no-ops when the plan did not select it, which keeps the graph shape
 * fixed while the plan still decides what actually happens.
 */
@Configuration
public class GraphConfig {

    public static final String UNDERSTAND = "understandIssue";
    public static final String PLAN = "createPlan";
    public static final String GATHER = "gatherEvidence";
    public static final String KNOWLEDGE = "searchKnowledge";
    public static final String LOGS = "inspectLogs";
    public static final String DATABASE = "queryDatabase";
    public static final String COMBINE = "combineEvidence";
    public static final String VALIDATE = "validateEvidence";
    public static final String REFINE = "refinePlan";
    public static final String REPORT = "generateReport";
    public static final String ANSWER = "answerFromKnowledge";
    public static final String REVIEW = "humanReview";

    @Bean
    CompiledGraph<InvestigationState> investigationGraph(
            UnderstandIssueNode understandIssue,
            CreatePlanNode createPlan,
            SearchKnowledgeNode searchKnowledge,
            InspectLogsNode inspectLogs,
            QueryDatabaseNode queryDatabase,
            ValidateEvidenceNode validateEvidence,
            RefinePlanNode refinePlan,
            GenerateReportNode generateReport,
            AnswerFromKnowledgeNode answerFromKnowledge,
            HumanReviewNode humanReview) throws GraphStateException {

        StateGraph<InvestigationState> graph =
                new StateGraph<>(InvestigationState.SCHEMA, InvestigationState::new)

                        .addNode(UNDERSTAND, node_async(understandIssue))
                        .addNode(PLAN, node_async(createPlan))
                        // Pass-through nodes that open and close the parallel section.
                        .addNode(GATHER, node_async(state -> Map.of()))
                        .addNode(KNOWLEDGE, node_async(searchKnowledge))
                        .addNode(LOGS, node_async(inspectLogs))
                        .addNode(DATABASE, node_async(queryDatabase))
                        .addNode(COMBINE, node_async(state -> Map.of()))
                        .addNode(VALIDATE, node_async(validateEvidence))
                        .addNode(REFINE, node_async(refinePlan))
                        .addNode(REPORT, node_async(generateReport))
                        .addNode(ANSWER, node_async(answerFromKnowledge))
                        .addNode(REVIEW, node_async(humanReview))

                        .addEdge(START, UNDERSTAND)
                        .addEdge(UNDERSTAND, PLAN)
                        .addEdge(PLAN, GATHER)

                        .addEdge(GATHER, KNOWLEDGE)
                        .addEdge(GATHER, LOGS)
                        .addEdge(GATHER, DATABASE)
                        .addEdge(KNOWLEDGE, COMBINE)
                        .addEdge(LOGS, COMBINE)
                        .addEdge(DATABASE, COMBINE)

                        // A rules question is done once the documentation has been read.
                        .addConditionalEdges(COMBINE,
                                edge_async(state -> isKnowledgeQuestion(state) ? "answer" : "validate"),
                                Map.of("answer", ANSWER, "validate", VALIDATE))

                        // Loop back only while the evidence is thin and the budget allows.
                        .addConditionalEdges(VALIDATE,
                                edge_async(state -> {
                                    var verdict = state.verdict();
                                    return (verdict != null && !verdict.sufficient()) ? "refine" : "report";
                                }),
                                Map.of("refine", REFINE, "report", REPORT))
                        .addEdge(REFINE, PLAN)

                        // Only a production-changing action goes through the approval gate.
                        .addConditionalEdges(REPORT,
                                edge_async(state -> {
                                    var report = state.report();
                                    return (report != null && report.requiresApproval()) ? "review" : "done";
                                }),
                                Map.of("review", REVIEW, "done", END))

                        .addEdge(ANSWER, END)
                        .addEdge(REVIEW, END);

        return graph.compile(CompileConfig.builder()
                .checkpointSaver(new MemorySaver())
                .interruptBefore(REVIEW)
                .build());
    }

    private static boolean isKnowledgeQuestion(InvestigationState state) {
        return state.understanding() != null && state.understanding().kind() == IssueKind.KNOWLEDGE;
    }
}
