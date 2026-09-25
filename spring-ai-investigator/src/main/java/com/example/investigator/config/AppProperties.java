package com.example.investigator.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Central configuration, overridable through application.yml or the environment.
 *
 * @param chatModel          reasoning model used by default
 * @param fastChatModel      smaller model used when a request asks for fast mode
 * @param fastMode           default for the fast flag when a request does not specify one
 * @param embeddingModel     model used to embed the knowledge base
 * @param maxInvestigationLoops cap on how many times the graph may re-plan
 * @param knowledgeDir       classpath-relative folder holding the Markdown knowledge base
 * @param logFile            classpath-relative application log file
 * @param vectorStoreFile    where the embedded index is persisted between runs
 */
@ConfigurationProperties("investigator")
public record AppProperties(
        String chatModel,
        String fastChatModel,
        boolean fastMode,
        String embeddingModel,
        int maxInvestigationLoops,
        String knowledgeDir,
        String logFile,
        String vectorStoreFile) {

    public AppProperties {
        if (chatModel == null) {
            chatModel = "qwen3:14b";
        }
        if (fastChatModel == null) {
            fastChatModel = "qwen3:8b";
        }
        if (embeddingModel == null) {
            embeddingModel = "qwen3-embedding:0.6b";
        }
        if (maxInvestigationLoops <= 0) {
            maxInvestigationLoops = 2;
        }
        if (knowledgeDir == null) {
            knowledgeDir = "classpath:data/knowledge/";
        }
        if (logFile == null) {
            logFile = "classpath:data/logs/application.log";
        }
        if (vectorStoreFile == null) {
            vectorStoreFile = "data/vector-store.json";
        }
    }

    /** The model that should serve a request, honouring a per-request fast override. */
    public String modelFor(Boolean fast) {
        boolean useFast = (fast == null) ? fastMode : fast;
        return useFast ? fastChatModel : chatModel;
    }
}
