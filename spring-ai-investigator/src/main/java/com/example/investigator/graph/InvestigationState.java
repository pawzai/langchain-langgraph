package com.example.investigator.graph;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import com.example.investigator.domain.EvidenceItem;
import com.example.investigator.domain.EvidenceVerdict;
import com.example.investigator.domain.InvestigationPlan;
import com.example.investigator.domain.IssueUnderstanding;
import com.example.investigator.domain.RootCauseReport;
import org.bsc.langgraph4j.state.AgentState;
import org.bsc.langgraph4j.state.Channel;
import org.bsc.langgraph4j.state.Channels;

/**
 * Shared state for the investigation graph.
 *
 * <p>{@code evidence} and {@code trace} use appending channels because the knowledge, log and
 * database nodes run as parallel branches and all write to them in the same superstep. Every
 * other key is last-write-wins.
 */
public class InvestigationState extends AgentState {

    public static final String QUESTION = "question";
    public static final String FAST = "fast";
    public static final String UNDERSTANDING = "understanding";
    public static final String PLAN = "plan";
    public static final String VERDICT = "verdict";
    public static final String REPORT = "report";
    public static final String EVIDENCE = "evidence";
    public static final String TRACE = "trace";
    public static final String ANSWER = "answer";
    public static final String LOOPS = "loops";
    public static final String APPROVAL_DECISION = "approvalDecision";

    public static final Map<String, Channel<?>> SCHEMA = Map.of(
            EVIDENCE, Channels.appender(ArrayList::new),
            TRACE, Channels.appender(ArrayList::new));

    public InvestigationState(Map<String, Object> initData) {
        super(initData);
    }

    public String question() {
        return this.<String>value(QUESTION).orElse("");
    }

    /** Null means "fall back to configuration", which is why this is a boxed Boolean. */
    public Boolean fast() {
        return this.<Boolean>value(FAST).orElse(null);
    }

    public IssueUnderstanding understanding() {
        return this.<IssueUnderstanding>value(UNDERSTANDING).orElse(null);
    }

    public InvestigationPlan plan() {
        return this.<InvestigationPlan>value(PLAN).orElse(null);
    }

    public EvidenceVerdict verdict() {
        return this.<EvidenceVerdict>value(VERDICT).orElse(null);
    }

    public RootCauseReport report() {
        return this.<RootCauseReport>value(REPORT).orElse(null);
    }

    public List<EvidenceItem> evidence() {
        return this.<List<EvidenceItem>>value(EVIDENCE).orElseGet(List::of);
    }

    public List<String> trace() {
        return this.<List<String>>value(TRACE).orElseGet(List::of);
    }

    public String answer() {
        return this.<String>value(ANSWER).orElse("");
    }

    public int loops() {
        return this.<Integer>value(LOOPS).orElse(0);
    }

    public String approvalDecision() {
        return this.<String>value(APPROVAL_DECISION).orElse("");
    }

    /** All gathered evidence rendered for a prompt. */
    public String renderEvidence() {
        List<EvidenceItem> items = evidence();
        if (items.isEmpty()) {
            return "(no evidence collected)";
        }
        StringBuilder out = new StringBuilder();
        for (EvidenceItem item : items) {
            if (!out.isEmpty()) {
                out.append("\n\n");
            }
            out.append("### ").append(item.source()).append('\n').append(item.content());
        }
        return out.toString();
    }
}
