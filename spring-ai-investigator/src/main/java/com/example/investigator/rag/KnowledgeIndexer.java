package com.example.investigator.rag;

import java.io.File;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import com.example.investigator.config.AppProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.document.Document;
import org.springframework.ai.embedding.EmbeddingModel;
import org.springframework.ai.vectorstore.SearchRequest;
import org.springframework.ai.vectorstore.SimpleVectorStore;
import org.springframework.core.io.Resource;
import org.springframework.core.io.support.PathMatchingResourcePatternResolver;
import org.springframework.stereotype.Component;

/**
 * Builds and queries the knowledge base.
 *
 * <p>Chunking splits on Markdown headings first and only then on size. Heading-aware splitting
 * keeps a rule and its conditions together, which matters here because the dispatch rules are
 * written as short numbered lists under a heading.
 *
 * <p>The index is persisted to a JSON file so a restart does not pay the embedding cost again.
 */
@Component
public class KnowledgeIndexer {

    private static final Logger log = LoggerFactory.getLogger(KnowledgeIndexer.class);

    private static final int MAX_CHUNK_CHARS = 900;
    private static final int OVERLAP_CHARS = 120;

    private final AppProperties properties;
    private final SimpleVectorStore vectorStore;

    public KnowledgeIndexer(AppProperties properties, EmbeddingModel embeddingModel) {
        this.properties = properties;
        this.vectorStore = SimpleVectorStore.builder(embeddingModel).build();
    }

    /** Load a previously saved index, or build one if none exists. Returns the chunk count. */
    public int loadOrBuild() {
        File file = indexFile();
        if (file.exists() && file.length() > 0) {
            vectorStore.load(file);
            log.info("Loaded knowledge index from {}", file);
            return count();
        }
        return rebuild();
    }

    /** Re-embed every document and overwrite the saved index. Returns the chunk count. */
    public int rebuild() {
        List<Document> documents = loadDocuments();
        if (documents.isEmpty()) {
            log.warn("No knowledge documents found under {}", properties.knowledgeDir());
            return 0;
        }

        log.info("Embedding {} chunks with {}", documents.size(), properties.embeddingModel());
        vectorStore.add(documents);

        File file = indexFile();
        File parent = file.getParentFile();
        if (parent != null) {
            parent.mkdirs();
        }
        vectorStore.save(file);
        return documents.size();
    }

    public boolean isEmpty() {
        return count() == 0;
    }

    public List<Document> retrieve(String query, int topK) {
        if (query == null || query.isBlank()) {
            return List.of();
        }
        List<Document> results = vectorStore.similaritySearch(
                SearchRequest.builder().query(query).topK(topK).build());
        return results == null ? List.of() : results;
    }

    private int count() {
        List<Document> probe = vectorStore.similaritySearch(
                SearchRequest.builder().query("shipment").topK(1000).build());
        return probe == null ? 0 : probe.size();
    }

    private File indexFile() {
        return Paths.get(properties.vectorStoreFile()).toFile();
    }

    // --- chunking ---

    private List<Document> loadDocuments() {
        List<Document> documents = new ArrayList<>();
        try {
            Resource[] resources = new PathMatchingResourcePatternResolver()
                    .getResources(properties.knowledgeDir() + "*.md");
            for (Resource resource : resources) {
                String name = resource.getFilename();
                String text = resource.getContentAsString(StandardCharsets.UTF_8);
                documents.addAll(splitMarkdown(text, name == null ? "unknown.md" : name));
            }
        } catch (IOException ex) {
            throw new UncheckedIOException("Could not read the knowledge base", ex);
        }
        documents.sort((a, b) -> {
            String sa = String.valueOf(a.getMetadata().get("source"));
            String sb = String.valueOf(b.getMetadata().get("source"));
            return sa.compareTo(sb);
        });
        return documents;
    }

    /** Split on headings, then split any oversized section on paragraph boundaries. */
    static List<Document> splitMarkdown(String text, String source) {
        List<Document> documents = new ArrayList<>();

        StringBuilder current = new StringBuilder();
        String docTitle = "";
        String section = "";

        for (String line : text.split("\\R", -1)) {
            boolean isHeading = line.startsWith("# ") || line.startsWith("## ") || line.startsWith("### ");
            if (isHeading && !current.isEmpty()) {
                addChunks(documents, current.toString(), source, docTitle, section);
                current.setLength(0);
            }
            if (line.startsWith("# ")) {
                docTitle = line.substring(2).trim();
                section = "";
            } else if (line.startsWith("## ")) {
                section = line.substring(3).trim();
            } else if (line.startsWith("### ")) {
                section = line.substring(4).trim();
            }
            current.append(line).append('\n');
        }
        addChunks(documents, current.toString(), source, docTitle, section);

        return documents;
    }

    private static void addChunks(List<Document> target, String body, String source,
                                  String docTitle, String section) {
        String trimmed = body.strip();
        if (trimmed.isEmpty()) {
            return;
        }
        for (String piece : splitBySize(trimmed)) {
            Map<String, Object> metadata = new LinkedHashMap<>();
            metadata.put("source", source);
            metadata.put("docTitle", docTitle);
            metadata.put("section", section);
            target.add(new Document(piece, metadata));
        }
    }

    private static List<String> splitBySize(String text) {
        if (text.length() <= MAX_CHUNK_CHARS) {
            return List.of(text);
        }
        List<String> pieces = new ArrayList<>();
        int start = 0;
        while (start < text.length()) {
            int end = Math.min(start + MAX_CHUNK_CHARS, text.length());
            if (end < text.length()) {
                int breakAt = text.lastIndexOf("\n\n", end);
                if (breakAt > start + OVERLAP_CHARS) {
                    end = breakAt;
                }
            }
            pieces.add(text.substring(start, end).strip());
            if (end >= text.length()) {
                break;
            }
            start = Math.max(end - OVERLAP_CHARS, start + 1);
        }
        return pieces;
    }

    /** Resolved path of the persisted index, for diagnostics. */
    public Path indexPath() {
        return indexFile().toPath().toAbsolutePath();
    }
}
