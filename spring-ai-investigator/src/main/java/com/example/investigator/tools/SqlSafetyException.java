package com.example.investigator.tools;

/** Raised when a query is not a safe read-only SELECT. */
public class SqlSafetyException extends RuntimeException {

    public SqlSafetyException(String message) {
        super(message);
    }
}
