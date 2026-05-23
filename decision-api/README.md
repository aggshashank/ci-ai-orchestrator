# Decision API — Day 1

Spring Boot intake API for the AI Credit Card Decisioning POC.

## What this service does

1. Receives `POST /api/v1/applications` with applicant data
2. Validates the payload (JSR-380 bean validation)
3. Generates a traceable `correlationId`
4. Publishes an `ApplicationReceivedEvent` to Kafka topic `application.received`
5. Returns `202 Accepted` with the `correlationId` for async tracking

The actual AI decisioning is handled by the `ai-orchestrator` service (Day 3).

---

## Quick start (Docker)

```bash
docker-compose up -d
```

Services started:
| Service | URL |
|---|---|
| Decision API | http://localhost:8080 |
| Kafka UI | http://localhost:8090 |
| Kafka broker | localhost:9092 |

---

## Submit an application

```bash
curl -X POST http://localhost:8080/api/v1/applications \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Jane Doe",
    "creditScore": 710,
    "utilization": 85,
    "addressMismatch": true,
    "delinquencies": 1,
    "channel": "WEB"
  }'
```

Expected response (202 Accepted):
```json
{
  "correlationId": "APP-1716345678901-A3F9C2D1",
  "status": "RECEIVED",
  "message": "Application accepted for AI decisioning. Track status using the correlationId.",
  "receivedAt": "2025-05-22T10:45:00Z"
}
```

## Validation errors (400)

```bash
curl -X POST http://localhost:8080/api/v1/applications \
  -H "Content-Type: application/json" \
  -d '{"name": "", "creditScore": 9999, "utilization": 150}'
```

Response:
```json
{
  "status": 400,
  "error": "Validation failed",
  "fieldErrors": {
    "creditScore": "Credit score must not exceed 850",
    "utilization": "Utilization cannot exceed 100%",
    "name": "Applicant name is required"
  }
}
```

---

## Observe the Kafka event

After submitting, open **Kafka UI** at http://localhost:8090 and navigate to:
`Topics → application.received → Messages`

You should see the `ApplicationReceivedEvent` JSON with your correlationId.

---

## Actuator endpoints

| Endpoint | Purpose |
|---|---|
| `/actuator/health` | Service health |
| `/actuator/prometheus` | Prometheus metrics scrape |
| `/actuator/metrics` | All registered metrics |

Custom metrics published:
- `application.received.count` (tagged by channel)
- `kafka.publish.duration` (tagged by outcome)
- `kafka.publish.success` / `kafka.publish.failure`

---

## Run tests

```bash
mvn test
```

---

## Project structure

```
src/main/java/com/citi/creditdecision/
├── controller/
│   └── ApplicationController.java      # POST /api/v1/applications
├── service/
│   └── ApplicationService.java         # Business logic + correlationId
├── kafka/
│   └── ApplicationEventProducer.java   # Async Kafka publish + metrics
├── model/
│   ├── ApplicationRequest.java         # Inbound DTO with validation
│   ├── ApplicationResponse.java        # 202 response DTO
│   └── ApplicationReceivedEvent.java   # Kafka event envelope
├── config/
│   ├── KafkaProducerConfig.java        # Producer factory (acks=all, idempotent)
│   └── KafkaTopicConfig.java           # Topic declarations (auto-created)
└── exception/
    └── GlobalExceptionHandler.java     # Centralised error handling
```

---

## Key design decisions (for interview discussion)

**202 vs 200**: Returns 202 Accepted because the credit decision is asynchronous.
Returning 200 OK would imply the work is complete.

**correlationId as Kafka key**: Ensures all events for the same application
land on the same Kafka partition, preserving ordering.

**acks=all + idempotence**: Prevents message loss if the broker leader
crashes after acknowledging but before replicating.

**Fire-and-forget with CompletableFuture**: The API doesn't block waiting
for Kafka ack — failures are logged and metered, not surfaced to the caller.
The DLQ handles undeliverable events.

**PII masking in logs**: Names are masked (first char + asterisks) in all
log statements — never full PII in log files.
