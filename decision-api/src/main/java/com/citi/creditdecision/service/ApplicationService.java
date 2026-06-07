package com.citi.creditdecision.service;

import com.citi.creditdecision.kafka.ApplicationEventProducer;
import com.citi.creditdecision.model.ApplicationReceivedEvent;
import com.citi.creditdecision.model.ApplicationRequest;
import com.citi.creditdecision.model.ApplicationResponse;
import io.micrometer.core.instrument.MeterRegistry;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.slf4j.MDC;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.UUID;

import static net.logstash.logback.argument.StructuredArguments.kv;

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
        String correlationId = currentCorrelationId();

        log.info("Accepting application",
                kv("channel", nullSafe(request.getChannel(), "UNKNOWN")),
                kv("credit_band", scoreBand(request.getCreditScore())),
                kv("has_delinquencies", request.getDelinquencies() != null && request.getDelinquencies() > 0),
                kv("address_mismatch", Boolean.TRUE.equals(request.getAddressMismatch())));

        ApplicationReceivedEvent event = buildEvent(correlationId, request);
        producer.publish(event);

        meterRegistry.counter("application.received.count",
                "channel", nullSafe(request.getChannel(), "UNKNOWN")).increment();

        return ApplicationResponse.accepted(correlationId);
    }

    private String generateCorrelationId() {
        String uuidSuffix = UUID.randomUUID().toString().replace("-", "").substring(0, 8).toUpperCase();
        return "APP-" + System.currentTimeMillis() + "-" + uuidSuffix;
    }

    private String currentCorrelationId() {
        String correlationId = MDC.get("correlation_id");
        if (correlationId != null && !correlationId.isBlank()) {
            return correlationId;
        }
        correlationId = generateCorrelationId();
        MDC.put("correlation_id", correlationId);
        return correlationId;
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

    private String nullSafe(String value, String fallback) {
        return (value != null && !value.isBlank()) ? value : fallback;
    }

    private String scoreBand(Integer creditScore) {
        if (creditScore == null) {
            return "UNKNOWN";
        }
        if (creditScore < 580) {
            return "POOR";
        }
        if (creditScore < 670) {
            return "FAIR";
        }
        if (creditScore < 740) {
            return "GOOD";
        }
        return "VERY_GOOD";
    }
}
