package com.example.investigator.tools;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import com.example.investigator.config.AppProperties;
import org.springframework.core.io.Resource;
import org.springframework.core.io.ResourceLoader;
import org.springframework.stereotype.Component;

/**
 * Keyword search over the application log.
 *
 * <p>Deliberately plain text matching rather than embeddings: log investigation is about exact
 * identifiers such as SHP-1007, where substring matching beats semantic similarity. Results are
 * ordered most severe first so the ERROR line leads.
 */
@Component
public class LogSearchTool {

    public static final int MAX_MATCHES = 25;

    private static final Map<String, Integer> LEVEL_RANK =
            Map.of("ERROR", 0, "WARN", 1, "INFO", 2, "DEBUG", 3);

    private final AppProperties properties;
    private final ResourceLoader resourceLoader;

    public LogSearchTool(AppProperties properties, ResourceLoader resourceLoader) {
        this.properties = properties;
        this.resourceLoader = resourceLoader;
    }

    /** Matching log lines, ERROR first. Empty when nothing matches. */
    public List<String> search(String term) {
        if (term == null || term.isBlank()) {
            return List.of();
        }

        List<String> needles = new ArrayList<>();
        needles.add(term.strip().toLowerCase());
        // A whole phrase rarely appears verbatim in a log line, so also try its longer words.
        if (term.contains(" ")) {
            for (String word : term.split("\\s+")) {
                if (word.length() > 3) {
                    needles.add(word.toLowerCase());
                }
            }
        }

        record Match(int rank, String line) {}
        List<Match> matches = new ArrayList<>();

        for (String line : readLines()) {
            String lowered = line.toLowerCase();
            boolean hit = needles.stream().anyMatch(lowered::contains);
            if (hit) {
                int rank = LEVEL_RANK.entrySet().stream()
                        .filter(e -> line.contains(e.getKey()))
                        .map(Map.Entry::getValue)
                        .findFirst()
                        .orElse(LEVEL_RANK.get("INFO"));
                matches.add(new Match(rank, line.strip()));
            }
        }

        matches.sort(Comparator.comparingInt(Match::rank));

        Set<String> unique = new LinkedHashSet<>();
        for (Match match : matches) {
            unique.add(match.line());
            if (unique.size() >= MAX_MATCHES) {
                break;
            }
        }
        return List.copyOf(unique);
    }

    /** Search formatted for inclusion in a prompt. */
    public String searchAsText(String term) {
        List<String> lines = search(term);
        return lines.isEmpty()
                ? "No log lines matched '" + term + "'."
                : String.join("\n", lines);
    }

    private List<String> readLines() {
        Resource resource = resourceLoader.getResource(properties.logFile());
        if (!resource.exists()) {
            return List.of();
        }
        try {
            return resource.getContentAsString(StandardCharsets.UTF_8).lines().toList();
        } catch (IOException ex) {
            throw new UncheckedIOException("Could not read the log file", ex);
        }
    }
}
