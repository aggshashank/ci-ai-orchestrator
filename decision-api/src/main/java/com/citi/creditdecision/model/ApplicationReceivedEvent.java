package com.citi.creditdecision.model;

import lombok.Builder;
import lombok.Data;

import java.time.Instant;

/**
 * Kafka event envelope for the application.received topic.
 *
 * Wraps the raw ApplicationRequest with routing metadata.
 * The AI Orchestrator consumes this event and fans out to agents.
 *
 * Schema evolution note: add fields freely — downstream consumers
 * must use @JsonIgnoreProperties(ignoreUnknown = true) to stay
 * backward-compatible.
 */
@Data
@Builder
public class ApplicationReceivedEvent {

    // Trace identifier — flows through every downstream system
    private String correlationId;

    // ISO-8601 instant the API received the request
    private Instant receivedAt;

    // Originating channel for routing / risk scoring context
    private String channel;

    // The raw applicant payload
    private ApplicationRequest application;

    // Schema version — increment when breaking changes are made
    private String eventVersion;

    public static final String CURRENT_VERSION = "1.0";
}
