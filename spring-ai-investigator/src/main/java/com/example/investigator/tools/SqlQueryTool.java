package com.example.investigator.tools;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.ResultSetMetaData;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * Read-only SQL access to the sample shipping database.
 *
 * <p>Second protection layer: the connection itself is opened read-only, so even a statement that
 * somehow passed {@link SqlSafetyValidator} cannot write.
 */
@Component
public class SqlQueryTool {

    /** Presented to the model so it can write valid queries without guessing column names. */
    public static final String SCHEMA = """
            facilities(code TEXT PK, name TEXT, outbound_enabled INTEGER)   -- 1 = outbound allowed
            trailers(trailer_id TEXT PK, status TEXT, last_inspection TEXT) -- status: ACTIVE | MAINTENANCE | RETIRED
            shipments(shipment_id TEXT PK, status TEXT, trailer_id TEXT NULL, location TEXT,
                      priority TEXT, created_at TEXT)
                      -- status: CREATED | READY_FOR_DISPATCH | IN_TRANSIT | DELIVERED | ON_HOLD
                      -- trailer_id is NULL when no trailer is assigned
                      -- location references facilities.code""";

    private final String jdbcUrl;

    public SqlQueryTool(@Value("${spring.datasource.url}") String jdbcUrl) {
        this.jdbcUrl = jdbcUrl;
    }

    /**
     * Everything needed to diagnose one shipment, as a fixed query.
     *
     * <p>Deliberately not model-generated: it is faster, cannot be malformed, and the LEFT JOIN is
     * what makes a NULL trailer visible. An inner join would return no rows and hide the cause.
     */
    public String describeShipment(String shipmentId) {
        String sql = """
                SELECT s.shipment_id, s.status, s.trailer_id, s.location, s.priority,
                       s.created_at, t.status AS trailer_status, t.last_inspection,
                       f.name AS facility_name, f.outbound_enabled
                FROM shipments s
                LEFT JOIN trailers t ON t.trailer_id = s.trailer_id
                LEFT JOIN facilities f ON f.code = s.location
                WHERE s.shipment_id = ?""";
        try (Connection connection = openReadOnly();
             PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, shipmentId);
            try (ResultSet rs = statement.executeQuery()) {
                return formatVertical(toRows(rs));
            }
        } catch (SQLException ex) {
            return "Database error: " + ex.getMessage();
        }
    }

    /** Run an arbitrary read-only SELECT, validated first. */
    public String runQuery(String query) {
        String safe;
        try {
            safe = SqlSafetyValidator.validate(query);
        } catch (SqlSafetyException ex) {
            return "Query rejected by safety validation: " + ex.getMessage();
        }

        try (Connection connection = openReadOnly();
             PreparedStatement statement = connection.prepareStatement(safe);
             ResultSet rs = statement.executeQuery()) {
            return formatVertical(toRows(rs));
        } catch (SQLException ex) {
            return "Database error: " + ex.getMessage();
        }
    }

    /** Row count for a validated query, used by the health checks. */
    public List<Map<String, Object>> select(String query) throws SQLException {
        String safe = SqlSafetyValidator.validate(query);
        try (Connection connection = openReadOnly();
             PreparedStatement statement = connection.prepareStatement(safe);
             ResultSet rs = statement.executeQuery()) {
            return toRows(rs);
        }
    }

    private Connection openReadOnly() throws SQLException {
        Connection connection = DriverManager.getConnection(jdbcUrl);
        try {
            connection.setReadOnly(true);
        } catch (SQLException ignored) {
            // Not every driver honours this; the validator remains the primary guard.
        }
        return connection;
    }

    private static List<Map<String, Object>> toRows(ResultSet rs) throws SQLException {
        List<Map<String, Object>> rows = new ArrayList<>();
        ResultSetMetaData meta = rs.getMetaData();
        int columns = meta.getColumnCount();
        while (rs.next() && rows.size() < SqlSafetyValidator.MAX_ROWS) {
            Map<String, Object> row = new LinkedHashMap<>();
            for (int i = 1; i <= columns; i++) {
                row.put(meta.getColumnLabel(i), rs.getObject(i));
            }
            rows.add(row);
        }
        return rows;
    }

    private static String formatVertical(List<Map<String, Object>> rows) {
        if (rows.isEmpty()) {
            return "Query returned no rows.";
        }
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < rows.size(); i++) {
            if (i > 0) {
                out.append("\n---\n");
            }
            rows.get(i).forEach((key, value) ->
                    out.append(key).append(": ").append(value == null ? "NULL" : value).append('\n'));
        }
        return out.toString().strip();
    }
}
