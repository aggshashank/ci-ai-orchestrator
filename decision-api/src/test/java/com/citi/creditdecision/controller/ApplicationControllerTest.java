package com.citi.creditdecision.controller;

import com.citi.creditdecision.model.ApplicationRequest;
import com.citi.creditdecision.model.ApplicationResponse;
import com.citi.creditdecision.service.ApplicationService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(ApplicationController.class)
class ApplicationControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private ApplicationService applicationService;

    @Test
    @DisplayName("POST /applications with valid payload returns 202 with correlationId")
    void submitApplication_validRequest_returns202() throws Exception {
        ApplicationRequest request = ApplicationRequest.builder()
                .name("Jane Smith")
                .creditScore(720)
                .utilization(45.0)
                .addressMismatch(false)
                .channel("WEB")
                .build();

        ApplicationResponse mockResponse = ApplicationResponse.accepted("APP-TEST-CORRELID");
        when(applicationService.accept(any())).thenReturn(mockResponse);

        mockMvc.perform(post("/api/v1/applications")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.correlationId").value("APP-TEST-CORRELID"))
                .andExpect(jsonPath("$.status").value("RECEIVED"));
    }

    @Test
    @DisplayName("POST /applications with invalid credit score returns 400")
    void submitApplication_invalidCreditScore_returns400() throws Exception {
        ApplicationRequest request = ApplicationRequest.builder()
                .name("Bad Actor")
                .creditScore(9999)  // out of FICO range
                .utilization(50.0)
                .build();

        mockMvc.perform(post("/api/v1/applications")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.fieldErrors.creditScore").exists());
    }

    @Test
    @DisplayName("POST /applications missing required name returns 400")
    void submitApplication_missingName_returns400() throws Exception {
        ApplicationRequest request = ApplicationRequest.builder()
                .creditScore(700)
                .utilization(60.0)
                .build();

        mockMvc.perform(post("/api/v1/applications")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.fieldErrors.name").exists());
    }

    @Test
    @DisplayName("POST /applications with high-risk signals still returns 202 (decision is async)")
    void submitApplication_highRiskSignals_stillReturns202() throws Exception {
        // The intake API never rejects based on risk — that's the AI's job
        ApplicationRequest request = ApplicationRequest.builder()
                .name("High Risk")
                .creditScore(310)
                .utilization(99.0)
                .addressMismatch(true)
                .delinquencies(5)
                .build();

        ApplicationResponse mockResponse = ApplicationResponse.accepted("APP-HIGHRISK-001");
        when(applicationService.accept(any())).thenReturn(mockResponse);

        mockMvc.perform(post("/api/v1/applications")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isAccepted());
    }
}
