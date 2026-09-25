package com.example.investigator;

import com.example.investigator.rag.KnowledgeIndexer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;

/**
 * Makes the application self-preparing: the database is seeded by Spring's SQL initializer and the
 * knowledge index is built here if it is missing. Starting the app is the only step a demo needs.
 */
@Component
public class StartupRunner implements ApplicationRunner {

    private static final Logger log = LoggerFactory.getLogger(StartupRunner.class);

    private final KnowledgeIndexer knowledgeIndexer;

    public StartupRunner(KnowledgeIndexer knowledgeIndexer) {
        this.knowledgeIndexer = knowledgeIndexer;
    }

    @Override
    public void run(ApplicationArguments args) {
        try {
            int chunks = knowledgeIndexer.loadOrBuild();
            log.info("Knowledge index ready with {} chunks at {}", chunks, knowledgeIndexer.indexPath());
        } catch (RuntimeException ex) {
            // A missing Ollama server should not stop the app from starting: the UI can then
            // render a useful diagnostic instead of failing to load at all.
            log.error("Could not prepare the knowledge index. Is Ollama running? {}", ex.getMessage());
        }
    }
}
