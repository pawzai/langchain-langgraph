package com.example.investigator.tools;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatExceptionOfType;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class SqlSafetyValidatorTest {

    @ParameterizedTest
    @ValueSource(strings = {
            "DELETE FROM shipments",
            "SELECT 1; DROP TABLE shipments",
            "UPDATE shipments SET status = 'DELIVERED'",
            "PRAGMA table_info(shipments)",
            "SELECT * FROM shipments UNION SELECT 1; DELETE FROM trailers",
            "INSERT INTO trailers VALUES ('X', 'ACTIVE', '2026-01-01')",
            "",
    })
    void rejectsAnythingThatIsNotAReadOnlySelect(String query) {
        assertThatExceptionOfType(SqlSafetyException.class)
                .isThrownBy(() -> SqlSafetyValidator.validate(query));
    }

    @Test
    void neutralisesWritesSmuggledBehindAComment() {
        // The comment is stripped rather than the query rejected, so confirm the write is gone.
        String safe = SqlSafetyValidator.validate("SELECT * FROM shipments -- ; DROP TABLE trailers");

        assertThat(safe).doesNotContainIgnoringCase("drop");
        assertThat(safe).startsWithIgnoringCase("select");
    }

    @Test
    void appendsALimitWhenTheQueryHasNone() {
        assertThat(SqlSafetyValidator.validate("SELECT * FROM shipments"))
                .isEqualTo("SELECT * FROM shipments LIMIT " + SqlSafetyValidator.MAX_ROWS);
    }

    @Test
    void keepsAnExplicitLimit() {
        assertThat(SqlSafetyValidator.validate("SELECT * FROM shipments LIMIT 3"))
                .isEqualTo("SELECT * FROM shipments LIMIT 3");
    }

    @Test
    void allowsCommonTableExpressions() {
        assertThat(SqlSafetyValidator.validate("WITH x AS (SELECT 1) SELECT * FROM x"))
                .startsWithIgnoringCase("with");
    }
}
