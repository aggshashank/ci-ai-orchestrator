package com.citi.creditdecision.model;

import lombok.Builder;
import lombok.Data;

import java.time.Instant;

/**
 * Response returned to the caller immediately after intake.
 * The actual decision is async — tracked via correlationId.
 */
@Data
@Builder
public class ApplicationResponse {

    private String correlationId;
    private String status;           // RECEIVED | REJECTED
    private String message;
    private Instant receivedAt;

    // Convenience factory for accepted applications
    public static ApplicationResponse accepted(String correlationId) {
        return ApplicationResponse.builder()
                .correlationId(correlationId)
                .status("RECEIVED")
                .message("Application accepted for AI decisioning. Track status using the correlationId.")
                .receivedAt(Instant.now())
                .build();
    }
}
