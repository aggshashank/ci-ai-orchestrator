package com.citi.creditdecision.kafka;

import com.citi.creditdecision.model.ApplicationReceivedEvent;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;
import org.springframework.stereotype.Service;

import java.util.concurrent.CompletableFuture;

/**
 * Kafka producer responsible for publishing application intake events.
 *
 * Key decisions:
 *  - Async send with explicit CompletableFuture — caller is not blocked
 *    waiting for broker ack. Failures are logged + metered.
 *  - correlationId used as Kafka message key → ensures all events for
 *    the same application land on the same partition (ordering guarantee).
 *  - Timer metric wraps the publish call for Grafana latency tracking.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ApplicationEventProducer {

    private final KafkaTemplate<String, ApplicationReceivedEvent> kafkaTemplate;
    private final MeterRegistry meterRegistry;

    @Value("${kafka.topics.application-received:application.received}")
    private String topic;

    /**
     * Publish an ApplicationReceivedEvent.
     *
     * @param event the fully-populated intake event
     * @return CompletableFuture that resolves once the broker acknowledges
     */
    public CompletableFuture<SendResult<String, ApplicationReceivedEvent>> publish(
            ApplicationReceivedEvent event) {

        Timer.Sample sample = Timer.start(meterRegistry);

        log.info("Publishing application event | correlationId={} channel={}",
                event.getCorrelationId(), event.getChannel());

        CompletableFuture<SendResult<String, ApplicationReceivedEvent>> future =
                kafkaTemplate.send(topic, event.getCorrelationId(), event);

        future.whenComplete((result, ex) -> {
            sample.stop(Timer.builder("kafka.publish.duration")
                    .tag("topic", topic)
                    .tag("outcome", ex == null ? "success" : "failure")
                    .register(meterRegistry));

            if (ex != null) {
                log.error("Failed to publish application event | correlationId={} error={}",
                        event.getCorrelationId(), ex.getMessage(), ex);
                meterRegistry.counter("kafka.publish.failure", "topic", topic).increment();
            } else {
                log.info("Event published successfully | correlationId={} partition={} offset={}",
                        event.getCorrelationId(),
                        result.getRecordMetadata().partition(),
                        result.getRecordMetadata().offset());
                meterRegistry.counter("kafka.publish.success", "topic", topic).increment();
            }
        });

        return future;
    }
}
