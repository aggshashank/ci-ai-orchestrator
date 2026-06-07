package com.citi.creditdecision.controller;

import com.citi.creditdecision.model.ApplicationRequest;
import com.citi.creditdecision.model.ApplicationResponse;
import com.citi.creditdecision.service.ApplicationService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

/**
 * REST controller for credit card application intake.
 *
 * Returns 202 Accepted — the decision is asynchronous.
 * Controller is intentionally thin: validation + delegation only.
 */
@Slf4j
@RestController
@RequestMapping("/api/v1")
@RequiredArgsConstructor
public class ApplicationController {

    private final ApplicationService applicationService;

    @PostMapping("/applications")
    public ResponseEntity<ApplicationResponse> submitApplication(
            @Valid @RequestBody ApplicationRequest request) {
        log.debug("Application submission received");
        ApplicationResponse response = applicationService.accept(request);
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(response);
    }

    @GetMapping("/applications/health")
    public ResponseEntity<String> health() {
        return ResponseEntity.ok("Decision API is running");
    }
}
