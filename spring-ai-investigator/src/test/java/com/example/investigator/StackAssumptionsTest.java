package com.example.investigator;

import static org.assertj.core.api.Assertions.assertThat;
import static org.bsc.langgraph4j.StateGraph.END;
import static org.bsc.langgraph4j.StateGraph.START;
import static org.bsc.langgraph4j.action.AsyncNodeAction.node_async;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import org.bsc.langgraph4j.CompileConfig;
import org.bsc.langgraph4j.CompiledGraph;
import org.bsc.langgraph4j.GraphInput;
import org.bsc.langgraph4j.RunnableConfig;
import org.bsc.langgraph4j.StateGraph;
import org.bsc.langgraph4j.checkpoint.MemorySaver;
import org.bsc.langgraph4j.state.AgentState;
import org.bsc.langgraph4j.state.Channel;
import org.bsc.langgraph4j.state.Channels;
import org.junit.jupiter.api.Test;
import org.springframework.ai.embedding.EmbeddingModel;
import org.springframework.ai.ollama.api.OllamaChatOptions;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import org.springframework.ai.chat.client.ChatClient;

/**
 * Pins the assumptions this application makes about its dependencies, independently of any
 * application logic: a graph runs, an interrupt pauses and resumes, a prompt populates a record,
 * and the embedding model returns the expected width.
 *
 * <p>Started life as a throwaway spike checking that Spring Boot 4's Jackson 3 did not collide
 * with LangGraph4j. It is kept because these are exactly the things a dependency upgrade breaks
 * quietly, and a failure here points at the library rather than at the workflow.
 */
@SpringBootTest
class StackAssumptionsTest {

    @Autowired
    private ChatClient.Builder chatClientBuilder;

    @Autowired
    private EmbeddingModel embeddingModel;

    /** Minimal state with one appending channel, mirroring the real trace/evidence channels. */
    static class ProbeState extends AgentState {
        ProbeState(Map<String, Object> initData) {
            super(initData);
        }

        List<String> steps() {
            return this.<List<String>>value("steps").orElseGet(List::of);
        }
    }

    private static final Map<String, Channel<?>> SCHEMA =
            Map.of("steps", Channels.appender(ArrayList::new));

    @Test
    void graphRunsInterruptsAndResumes() throws Exception {
        CompiledGraph<ProbeState> graph = new StateGraph<>(SCHEMA, ProbeState::new)
                .addNode("first", node_async(s -> Map.of("steps", List.of("first"))))
                .addNode("second", node_async(s -> Map.of("steps", List.of("second"))))
                .addEdge(START, "first")
                .addEdge("first", "second")
                .addEdge("second", END)
                .compile(CompileConfig.builder()
                        .checkpointSaver(new MemorySaver())
                        .interruptBefore("second")
                        .build());

        RunnableConfig config = RunnableConfig.builder().threadId("assumptions-1").build();

        // 1 + 2. Runs, then pauses before the interrupted node.
        var paused = graph.invoke(GraphInput.args(Map.of()), config);
        assertThat(paused).isPresent();
        assertThat(paused.get().steps()).containsExactly("first");
        assertThat(graph.getState(config).next()).isEqualTo("second");

        // Resume from the persisted checkpoint and run to completion.
        var finished = graph.invoke(GraphInput.resume(), config);
        assertThat(finished).isPresent();
        assertThat(finished.get().steps()).containsExactly("first", "second");
    }

    /** Appending channels must merge writes from nodes running in the same superstep. */
    @Test
    void parallelNodesMergeIntoAppendingChannel() throws Exception {
        CompiledGraph<ProbeState> graph = new StateGraph<>(SCHEMA, ProbeState::new)
                .addNode("fanout", node_async(s -> Map.of("steps", List.of("plan"))))
                .addNode("a", node_async(s -> Map.of("steps", List.of("a"))))
                .addNode("b", node_async(s -> Map.of("steps", List.of("b"))))
                .addNode("join", node_async(s -> Map.of()))
                .addEdge(START, "fanout")
                .addEdge("fanout", "a")
                .addEdge("fanout", "b")
                .addEdge("a", "join")
                .addEdge("b", "join")
                .addEdge("join", END)
                .compile();

        var result = graph.invoke(GraphInput.args(Map.of()), RunnableConfig.builder().build());

        assertThat(result).isPresent();
        assertThat(result.get().steps()).containsExactlyInAnyOrder("plan", "a", "b");
    }

    record ProbePlan(boolean needsDatabase, String entityId) {}

    @Test
    void structuredOutputPopulatesARecord() {
        ProbePlan plan = chatClientBuilder.build()
                .prompt()
                .user("Shipment SHP-1007 is stuck in CREATED. Decide whether the database is "
                        + "needed and extract the shipment identifier.")
                .options(OllamaChatOptions.builder()
                        .model("qwen3:8b")
                        .disableThinking())
                .call()
                .entity(ProbePlan.class);

        assertThat(plan).isNotNull();
        assertThat(plan.entityId()).containsIgnoringCase("SHP-1007");
    }

    @Test
    void embeddingsReturnExpectedDimensions() {
        float[] vector = embeddingModel.embed("trailer assignment rules");
        assertThat(vector).hasSize(1024);
    }
}
