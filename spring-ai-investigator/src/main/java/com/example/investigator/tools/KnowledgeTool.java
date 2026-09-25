package com.example.investigator.tools;

import java.util.List;
import java.util.stream.Collectors;

import com.example.investigator.rag.KnowledgeIndexer;
import org.springframework.ai.document.Document;
import org.springframework.stereotype.Component;

/** Retrieval over the workflow rules, troubleshooting guide and business conditions. */
@Component
public class KnowledgeTool {

    private static final int TOP_K = 4;

    private final KnowledgeIndexer indexer;

    public KnowledgeTool(KnowledgeIndexer indexer) {
        this.indexer = indexer;
    }

    /** Retrieved passages labelled with their source, ready to drop into a prompt. */
    public String search(String query) {
        List<Document> documents = indexer.retrieve(query, TOP_K);
        if (documents.isEmpty()) {
            return "No documentation matched '" + query + "'.";
        }
        return documents.stream().map(KnowledgeTool::format).collect(Collectors.joining("\n\n"));
    }

    private static String format(Document document) {
        Object source = document.getMetadata().getOrDefault("source", "unknown");
        Object section = document.getMetadata().get("section");
        Object title = document.getMetadata().get("docTitle");

        String label = String.valueOf(source);
        String detail = (section != null && !String.valueOf(section).isBlank())
                ? String.valueOf(section)
                : String.valueOf(title == null ? "" : title);
        if (!detail.isBlank()) {
            label = label + " - " + detail;
        }
        return "[" + label + "]\n" + document.getText().strip();
    }
}
