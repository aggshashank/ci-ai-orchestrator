package com.citi.creditdecision.kafka;

import com.citi.creditdecision.model.ApplicationReceivedEvent;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.slf4j.MDC;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;
import org.springframework.stereotype.Service;

import java.util.concurrent.CompletableFuture;

import static net.logstash.logback.argument.StructuredArguments.kv;

@Slf4j
@Service
@RequiredArgsConstructor
public class ApplicationEventProducer {

    private final KafkaTemplate<String, ApplicationReceivedEvent> kafkaTemplate;
    private final MeterRegistry meterRegistry;

    @Value("${kafka.topics.application-received:application.received}")
    private String topic;

    public CompletableFuture<SendResult<String, ApplicationReceivedEvent>> publish(
            ApplicationReceivedEvent event) {

        Timer.Sample sample = Timer.start(meterRegistry);

        log.info("Publishing application event", kv("channel", event.getChannel()));

        CompletableFuture<SendResult<String, ApplicationReceivedEvent>> future =
                kafkaTemplate.send(topic, event.getCorrelationId(), event);

        future.whenComplete((result, ex) -> {
            sample.stop(Timer.builder("kafka.publish.duration")
                    .tag("topic", topic)
                    .tag("outcome", ex == null ? "success" : "failure")
                    .register(meterRegistry));

            try (MDC.MDCCloseable ignored = MDC.putCloseable("correlation_id", event.getCorrelationId())) {
                if (ex != null) {
                    log.error("Failed to publish application event",
                            kv("error_type", ex.getClass().getSimpleName()));
                    meterRegistry.counter("kafka.publish.failure", "topic", topic).increment();
                } else {
                    log.info("Event published successfully",
                            kv("partition", result.getRecordMetadata().partition()),
                            kv("offset", result.getRecordMetadata().offset()));
                    meterRegistry.counter("kafka.publish.success", "topic", topic).increment();
                }
            }
        });

        return future;
    }
}
