package com.citi.creditdecision.service;

import com.citi.creditdecision.kafka.ApplicationEventProducer;
import com.citi.creditdecision.model.*;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.concurrent.CompletableFuture;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class ApplicationServiceTest {

    @Mock
    private ApplicationEventProducer producer;

    private ApplicationService service;

    @BeforeEach
    void setUp() {
        service = new ApplicationService(producer, new SimpleMeterRegistry());
        when(producer.publish(any())).thenReturn(CompletableFuture.completedFuture(null));
    }

    @Test
    @DisplayName("accept() returns RECEIVED status with non-null correlationId")
    void accept_returnsAcceptedResponse() {
        ApplicationRequest request = validRequest();
        ApplicationResponse response = service.accept(request);

        assertThat(response.getStatus()).isEqualTo("RECEIVED");
        assertThat(response.getCorrelationId()).isNotBlank();
        assertThat(response.getCorrelationId()).startsWith("APP-");
    }

    @Test
    @DisplayName("accept() publishes exactly one Kafka event")
    void accept_publishesOneEvent() {
        service.accept(validRequest());
        verify(producer, times(1)).publish(any(ApplicationReceivedEvent.class));
    }

    @Test
    @DisplayName("Kafka event contains the original application payload")
    void accept_eventContainsApplicationPayload() {
        ApplicationRequest request = validRequest();
        ArgumentCaptor<ApplicationReceivedEvent> captor =
                ArgumentCaptor.forClass(ApplicationReceivedEvent.class);

        service.accept(request);
        verify(producer).publish(captor.capture());

        ApplicationReceivedEvent event = captor.getValue();
        assertThat(event.getApplication().getCreditScore()).isEqualTo(710);
        assertThat(event.getApplication().getUtilization()).isEqualTo(85.0);
        assertThat(event.getEventVersion()).isEqualTo(ApplicationReceivedEvent.CURRENT_VERSION);
    }

    @Test
    @DisplayName("Channel defaults to WEB when not provided")
    void accept_defaultsChannelToWeb() {
        ApplicationRequest request = validRequest();
        request.setChannel(null);

        ArgumentCaptor<ApplicationReceivedEvent> captor =
                ArgumentCaptor.forClass(ApplicationReceivedEvent.class);

        service.accept(request);
        verify(producer).publish(captor.capture());

        assertThat(captor.getValue().getChannel()).isEqualTo("WEB");
    }

    private ApplicationRequest validRequest() {
        return ApplicationRequest.builder()
                .name("John Doe")
                .creditScore(710)
                .utilization(85.0)
                .addressMismatch(true)
                .channel("MOBILE")
                .build();
    }
}
