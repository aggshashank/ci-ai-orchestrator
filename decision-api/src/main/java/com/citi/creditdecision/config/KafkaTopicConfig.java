package com.citi.creditdecision.config;

import org.apache.kafka.clients.admin.NewTopic;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.config.TopicBuilder;

/**
 * Declares Kafka topics programmatically.
 * Spring Kafka's KafkaAdmin auto-creates these on startup if they don't exist.
 *
 * Partition count = 3: allows 3 parallel consumers in the same group.
 * Replicas = 1: fine for local Docker; set to 3 in production.
 */
@Configuration
public class KafkaTopicConfig {

    @Bean
    public NewTopic applicationReceivedTopic() {
        return TopicBuilder.name("application.received")
                .partitions(3)
                .replicas(1)
                .build();
    }

    @Bean
    public NewTopic applicationDlqTopic() {
        return TopicBuilder.name("application.dlq")
                .partitions(1)
                .replicas(1)
                .build();
    }

    @Bean
    public NewTopic recommendationGeneratedTopic() {
        return TopicBuilder.name("recommendation.generated")
                .partitions(3)
                .replicas(1)
                .build();
    }

    @Bean
    public NewTopic manualReviewTopic() {
        return TopicBuilder.name("manual.review.required")
                .partitions(1)
                .replicas(1)
                .build();
    }
}
