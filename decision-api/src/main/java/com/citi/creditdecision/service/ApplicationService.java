package com.citi.creditdecision.service;

import com.citi.creditdecision.kafka.ApplicationEventProducer;
import com.citi.creditdecision.model.*;
import io.micrometer.core.instrument.MeterRegistry;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.UUID;

/**
 * Core intake service.
 *
 * Responsibilities:
 *  1. Generate a stable, traceable correlationId
 *  2. Normalise and enrich the inbound request
 *  3. Build the Kafka event envelope
 *  4. Delegate to the Kafka producer
 *  5. Return a lightweight acknowledgment to the API layer
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ApplicationService {

    private final ApplicationEventProducer producer;
    private final MeterRegistry meterRegistry;

    public ApplicationResponse accept(ApplicationRequest request) {
        String correlationId = generateCorrelationId();

        log.info("Accepting application | correlationId={} applicant={} creditScore={} utilization={}",
                correlationId, mask(request.getName()),
                request.getCreditScore(), request.getUtilization());

        ApplicationReceivedEvent event = buildEvent(correlationId, request);
        producer.publish(event);

        meterRegistry.counter("application.received.count",
                "channel", nullSafe(request.getChannel(), "UNKNOWN")).increment();

        return ApplicationResponse.accepted(correlationId);
    }

    /**
     * Correlation ID format: APP-<timestamp-ms>-<8-char UUID fragment>
     * Human-readable for ops. Production: use ULID for sortable globally unique IDs.
     */
    private String generateCorrelationId() {
        String uuidSuffix = UUID.randomUUID().toString().replace("-", "").substring(0, 8).toUpperCase();
        return "APP-" + System.currentTimeMillis() + "-" + uuidSuffix;
    }

    private ApplicationReceivedEvent buildEvent(String correlationId, ApplicationRequest request) {
        return ApplicationReceivedEvent.builder()
                .correlationId(correlationId)
                .receivedAt(Instant.now())
                .channel(nullSafe(request.getChannel(), "WEB"))
                .application(request)
                .eventVersion(ApplicationReceivedEvent.CURRENT_VERSION)
                .build();
    }

    /** Mask all but first character — keeps logs useful without leaking PII. */
    private String mask(String name) {
        if (name == null || name.length() < 2) return "***";
        return name.charAt(0) + "*".repeat(name.length() - 1);
    }

    private String nullSafe(String value, String fallback) {
        return (value != null && !value.isBlank()) ? value : fallback;
    }
}
