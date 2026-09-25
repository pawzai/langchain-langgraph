package com.example.investigator.service;

import java.util.HashMap;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

import com.example.investigator.domain.ApprovalRequest;
import com.example.investigator.domain.InvestigateRequest;
import com.example.investigator.domain.InvestigationResult;
import com.example.investigator.domain.IssueKind;
import com.example.investigator.graph.GraphConfig;
import com.example.investigator.graph.InvestigationState;
import org.bsc.langgraph4j.CompiledGraph;
import org.bsc.langgraph4j.GraphInput;
import org.bsc.langgraph4j.RunnableConfig;
import org.springframework.stereotype.Service;

/**
 * Entry point shared by the web UI and the JSON API.
 *
 * <p>Owns the thread identifier, which is what ties a paused investigation to the approval that
 * later resumes it.
 */
@Service
public class InvestigationService {

    private final CompiledGraph<InvestigationState> graph;

    public InvestigationService(CompiledGraph<InvestigationState> graph) {
        this.graph = graph;
    }

    /** Run an investigation, which may stop at the approval gate. */
    public InvestigationResult investigate(InvestigateRequest request) {
        String threadId = (request.threadId() == null || request.threadId().isBlank())
                ? UUID.randomUUID().toString()
                : request.threadId();

        RunnableConfig config = RunnableConfig.builder().threadId(threadId).build();

        Map<String, Object> input = new HashMap<>();
        input.put(InvestigationState.QUESTION, request.question());
        input.put(InvestigationState.FAST, request.fast());
        input.put(InvestigationState.LOOPS, 0);

        Optional<InvestigationState> state = graph.invoke(GraphInput.args(input), config);
        return toResult(threadId, state);
    }

    /** Apply a reviewer's decision to a paused investigation and run it to completion. */
    public InvestigationResult resume(ApprovalRequest request) {
        RunnableConfig config = RunnableConfig.builder().threadId(request.threadId()).build();

        if (!isAwaitingApproval(request.threadId())) {
            throw new IllegalStateException(
                    "No investigation is awaiting approval for thread " + request.threadId()
                            + ". Approvals are held in memory, so they do not survive a restart.");
        }

        try {
            // Write the decision into the checkpoint, then let the interrupted node run.
            RunnableConfig resumeConfig = graph.updateState(config,
                    Map.of(InvestigationState.APPROVAL_DECISION, request.decision()));

            Optional<InvestigationState> state = graph.invoke(GraphInput.resume(), resumeConfig);
            return toResult(request.threadId(), state);
        } catch (Exception ex) {
            throw new IllegalStateException("Could not resume thread " + request.threadId(), ex);
        }
    }

    /**
     * Whether the thread is parked at the approval gate.
     *
     * <p>Deliberately built from the thread id alone. The config returned by {@code updateState}
     * pins a specific checkpoint id, and querying with that would report the state as it was when
     * the decision was written rather than after the graph finished.
     */
    private boolean isAwaitingApproval(String threadId) {
        RunnableConfig latest = RunnableConfig.builder().threadId(threadId).build();
        return graph.stateOf(latest)
                .map(snapshot -> GraphConfig.REVIEW.equals(snapshot.next()))
                .orElse(false);
    }

    private InvestigationResult toResult(String threadId, Optional<InvestigationState> maybeState) {
        InvestigationState state = maybeState.orElseThrow(
                () -> new IllegalStateException("The graph returned no state for thread " + threadId));

        boolean awaiting = isAwaitingApproval(threadId);

        return new InvestigationResult(
                threadId,
                state.understanding() == null ? IssueKind.INVESTIGATION : state.understanding().kind(),
                state.understanding() == null ? "" : state.understanding().summary(),
                state.plan(),
                state.evidence(),
                state.report(),
                state.answer(),
                state.loops(),
                awaiting,
                state.trace());
    }
}
