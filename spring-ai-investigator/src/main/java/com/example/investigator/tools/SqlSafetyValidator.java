package com.example.investigator.tools;

import java.util.regex.Pattern;

/**
 * First of two independent layers protecting the database, because a model can always be talked
 * into emitting a DELETE. The second layer is the read-only JDBC connection in
 * {@link SqlQueryTool}.
 *
 * <p>Rejects anything that is not a single bare SELECT, strips comments so a write cannot be
 * smuggled behind one, and appends a LIMIT when the query has none.
 */
public final class SqlSafetyValidator {

    public static final int MAX_ROWS = 50;

    private static final Pattern LINE_COMMENT = Pattern.compile("--[^\\n]*");
    private static final Pattern BLOCK_COMMENT = Pattern.compile("/\\*.*?\\*/", Pattern.DOTALL);
    private static final Pattern FORBIDDEN = Pattern.compile(
            "\\b(insert|update|delete|drop|alter|create|replace|truncate|attach|detach|"
                    + "pragma|vacuum|reindex|grant|revoke)\\b",
            Pattern.CASE_INSENSITIVE);
    private static final Pattern HAS_LIMIT = Pattern.compile("\\blimit\\b", Pattern.CASE_INSENSITIVE);

    private SqlSafetyValidator() {
    }

    /** Returns a normalised, safe SELECT or throws {@link SqlSafetyException}. */
    public static String validate(String query) {
        if (query == null || query.isBlank()) {
            throw new SqlSafetyException("Empty query.");
        }

        String cleaned = LINE_COMMENT.matcher(query).replaceAll(" ");
        cleaned = BLOCK_COMMENT.matcher(cleaned).replaceAll(" ");
        cleaned = cleaned.strip();
        while (cleaned.endsWith(";")) {
            cleaned = cleaned.substring(0, cleaned.length() - 1).strip();
        }

        if (cleaned.contains(";")) {
            throw new SqlSafetyException("Multiple statements are not allowed.");
        }

        String lowered = cleaned.toLowerCase();
        if (!(lowered.startsWith("select") || lowered.startsWith("with"))) {
            throw new SqlSafetyException("Only SELECT queries are allowed.");
        }

        if (FORBIDDEN.matcher(cleaned).find()) {
            throw new SqlSafetyException("Query contains a write or schema-modifying keyword.");
        }

        if (!HAS_LIMIT.matcher(lowered).find()) {
            cleaned = cleaned + " LIMIT " + MAX_ROWS;
        }

        return cleaned;
    }
}
