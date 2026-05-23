package com.citi.creditdecision.exception;

import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;

/**
 * Centralised exception handler.
 *
 * Intercepts bean validation failures and returns a structured 400
 * with field-level error messages — avoids leaking stack traces to callers.
 */
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    /** Bean validation failure → 400 with per-field errors */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, Object>> handleValidation(
            MethodArgumentNotValidException ex) {

        Map<String, String> fieldErrors = new HashMap<>();
        for (FieldError fe : ex.getBindingResult().getFieldErrors()) {
            fieldErrors.put(fe.getField(), fe.getDefaultMessage());
        }

        Map<String, Object> body = new HashMap<>();
        body.put("status", 400);
        body.put("error", "Validation failed");
        body.put("fieldErrors", fieldErrors);
        body.put("timestamp", Instant.now().toString());

        log.warn("Validation failure: {}", fieldErrors);
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(body);
    }

    /** Catch-all — log and return generic 500 */
    @ExceptionHandler(Exception.class)
    public ResponseEntity<Map<String, Object>> handleUnexpected(Exception ex) {
        log.error("Unexpected error", ex);
        Map<String, Object> body = new HashMap<>();
        body.put("status", 500);
        body.put("error", "Internal server error");
        body.put("timestamp", Instant.now().toString());
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(body);
    }
}
