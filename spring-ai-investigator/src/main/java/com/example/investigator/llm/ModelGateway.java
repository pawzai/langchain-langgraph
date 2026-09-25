package com.example.investigator.llm;

import com.example.investigator.config.AppProperties;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.ollama.api.OllamaChatOptions;
import org.springframework.stereotype.Component;

/**
 * The single place a model provider is chosen.
 *
 * <p>Swapping to Anthropic or OpenAI later means editing this class only: the graph, tools and
 * retrieval layers depend on the two methods below, not on Ollama.
 *
 * <p>Two deliberate choices carried over from the Python implementation:
 * <ul>
 *   <li>{@code disableThinking()} — qwen3 otherwise emits its reasoning trace as plain text,
 *       which both triples latency and breaks structured-output parsing. Set programmatically
 *       because the equivalent {@code spring.ai.ollama.chat.options.think-option} property has a
 *       known binding failure.
 *   <li>{@code validateSchema()} — if the model still returns something that does not satisfy the
 *       schema, Spring AI retries with the validation error fed back into the prompt.
 * </ul>
 */
@Component
public class ModelGateway {

    private final ChatClient chatClient;
    private final AppProperties properties;

    public ModelGateway(ChatClient.Builder chatClientBuilder, AppProperties properties) {
        this.chatClient = chatClientBuilder.build();
        this.properties = properties;
    }

    /** Ask the model for a typed answer. {@code fast} may be null to fall back to configuration. */
    public <T> T structured(String prompt, Class<T> type, Boolean fast) {
        return chatClient.prompt()
                .user(prompt)
                .options(options(fast))
                .call()
                .entity(type, spec -> spec.validateSchema());
    }

    /** Ask the model for free-form prose, used only for the documentation answer. */
    public String text(String prompt, Boolean fast) {
        String content = chatClient.prompt()
                .user(prompt)
                .options(options(fast))
                .call()
                .content();
        return content == null ? "" : content.strip();
    }

    /** The model that will serve a request, so the workflow trace can report it. */
    public String modelName(Boolean fast) {
        return properties.modelFor(fast);
    }

    private OllamaChatOptions.Builder options(Boolean fast) {
        OllamaChatOptions.Builder builder = OllamaChatOptions.builder();
        builder.model(properties.modelFor(fast));
        builder.temperature(0.0d);
        builder.disableThinking();
        return builder;
    }
}
