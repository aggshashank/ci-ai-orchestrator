package com.citi.creditdecision.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import jakarta.validation.constraints.*;
import lombok.Builder;
import lombok.Data;

/**
 * Inbound credit card application payload.
 *
 * Validation rules mirror typical underwriting pre-checks:
 *  - creditScore 300–850 (FICO range)
 *  - utilization 0–100 (percentage)
 *  - annualIncome must be positive if provided
 */
@Data
@Builder
@JsonIgnoreProperties(ignoreUnknown = true)
public class ApplicationRequest {

    @NotBlank(message = "Applicant name is required")
    @Size(max = 100, message = "Name must not exceed 100 characters")
    private String name;

    @NotNull(message = "Credit score is required")
    @Min(value = 300, message = "Credit score must be at least 300")
    @Max(value = 850, message = "Credit score must not exceed 850")
    private Integer creditScore;

    @NotNull(message = "Utilization percentage is required")
    @DecimalMin(value = "0.0", message = "Utilization cannot be negative")
    @DecimalMax(value = "100.0", message = "Utilization cannot exceed 100%")
    private Double utilization;

    // Optional enrichment fields — populated by downstream agents
    private Boolean addressMismatch;

    @Min(value = 0, message = "Delinquency count cannot be negative")
    private Integer delinquencies;

    @Positive(message = "Annual income must be a positive value")
    private Double annualIncome;

    // Channel: WEB | MOBILE | BRANCH | PARTNER
    private String channel;
}
