package com.citi.creditdecision.config;

import com.citi.creditdecision.model.ApplicationReceivedEvent;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.common.serialization.StringSerializer;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.core.DefaultKafkaProducerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.core.ProducerFactory;
import org.springframework.kafka.support.serializer.JsonSerializer;

import java.util.HashMap;
import java.util.Map;

/**
 * Kafka producer configuration.
 *
 * Key producer settings explained (PE interview depth):
 *
 *  acks=all          — broker waits for all in-sync replicas to confirm.
 *                      Prevents data loss if the leader crashes after ack.
 *
 *  retries=3         — automatic retry on transient broker errors.
 *                      Combined with idempotence, safe to retry without duplicates.
 *
 *  enable.idempotence — ensures exactly-once delivery per producer session.
 *                      Requires acks=all and retries > 0.
 *
 *  linger.ms=5       — micro-batch window: waits 5ms to accumulate records
 *                      before sending. Trades tiny latency for better throughput.
 *
 *  compression.type=snappy — reduces network bandwidth ~50-60% with low CPU cost.
 *                            Good default for JSON payloads.
 */
@Configuration
public class KafkaProducerConfig {

    @Value("${spring.kafka.bootstrap-servers:localhost:9092}")
    private String bootstrapServers;

    @Bean
    public ProducerFactory<String, ApplicationReceivedEvent> producerFactory() {
        Map<String, Object> props = new HashMap<>();

        props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
        props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, JsonSerializer.class);

        // Reliability
        props.put(ProducerConfig.ACKS_CONFIG, "all");
        props.put(ProducerConfig.RETRIES_CONFIG, 3);
        props.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true);

        // Throughput optimisation
        props.put(ProducerConfig.LINGER_MS_CONFIG, 5);
        props.put(ProducerConfig.COMPRESSION_TYPE_CONFIG, "lz4");

        // Type info so consumers can deserialise correctly
        props.put(JsonSerializer.ADD_TYPE_INFO_HEADERS, false);

        return new DefaultKafkaProducerFactory<>(props);
    }

    @Bean
    public KafkaTemplate<String, ApplicationReceivedEvent> kafkaTemplate() {
        return new KafkaTemplate<>(producerFactory());
    }
}
