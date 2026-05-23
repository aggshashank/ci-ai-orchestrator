# AI Credit Card Decisioning POC

A production-grade **Agentic AI** proof-of-concept that augments traditional rule-based credit card underwriting with multi-agent orchestration, retrieval-augmented generation, explainability, and human-in-loop governance — running entirely on a local machine with no cloud API keys required.

---

## What This Project Demonstrates

| Capability | Implementation |
|---|---|
| Multi-agent orchestration | LangGraph `StateGraph` with 5 specialist agents |
| Retrieval-Augmented Generation | nomic-embed-text embeddings + Qdrant vector search |
| Event-driven architecture | Apache Kafka with 4 topics + DLQ |
| Explainability | ECOA-compliant adverse action codes (AA01–AA12) |
| Human-in-loop | Review queue + underwriter decision API |
| Observability | Prometheus metrics on both services |
| Local LLM | Ollama (Llama 3) — no OpenAI key needed |
| Resilience | Fail-safe fallbacks, DLQ routing, manual commit |

---

## Architecture

```
                    ┌─────────────────────┐
                    │   Decision API      │  Spring Boot · :8080
                    │  POST /applications │
                    └──────────┬──────────┘
                               │ 202 Accepted
                               ▼
                    ┌─────────────────────┐
                    │  Apache Kafka       │
                    │  application.       │
                    │  received           │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  AI Orchestrator    │  FastAPI + LangGraph · :8001
                    └──┬──────┬───────┬──┘
                       │      │       │   (sequential, CPU-optimised)
               ┌───────▼──┐ ┌─▼────┐ ┌▼──────────┐
               │ Credit   │ │Fraud │ │Policy RAG │
               │ Agent    │ │Agent │ │Agent      │
               └───────┬──┘ └─┬────┘ └┬──────────┘
                       │      │       │
                       └──────▼───────┘
                    ┌─────────────────────┐
                    │  Risk Decision      │  Deterministic weighted rules
                    │  Agent              │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Explainability     │  ECOA codes + audit log
                    │  Agent              │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  audit_log.jsonl    │  Full decision trace
                    └─────────────────────┘
```

---

## Tech Stack

### Backend — Decision API

| Component | Technology |
|---|---|
| Language | Java 21 |
| Framework | Spring Boot 3.2.5 |
| Messaging | Spring Kafka (producer) |
| Validation | Jakarta Bean Validation (JSR-380) |
| Metrics | Micrometer + Prometheus |
| Build | Maven 3.9+ |

### AI Orchestrator

| Component | Technology |
|---|---|
| Language | Python 3.11+ |
| Web framework | FastAPI 0.111 |
| Agent orchestration | LangGraph 0.1.19+ |
| LLM | Ollama — Llama 3 (local, no API key) |
| Embeddings | Ollama — nomic-embed-text (768-dim) |
| LLM framework | LangChain + langchain-ollama |
| Vector database | Qdrant 1.9+ |
| Kafka client | kafka-python-ng |
| Config | Pydantic Settings |

### Infrastructure

| Component | Technology |
|---|---|
| Message broker | Apache Kafka 7.6 (Confluent) |
| Vector store | Qdrant (Docker) |
| Containers | Docker Desktop |
| Local LLM server | Ollama |

---

## Agents

| Agent | Role | Output |
|---|---|---|
| **Credit Risk Agent** | Analyses credit score, utilization, delinquencies | `{riskLevel, reason, score}` |
| **Fraud Agent** | Analyses address mismatch, velocity indicators | `{fraudRisk, indicators, recommendAction}` |
| **Policy RAG Agent** | Retrieves applicable policy rules from Qdrant | `{rules, action, citations}` |
| **Risk Decision Agent** | Deterministic weighted synthesis (credit 45%, fraud 30%, policy 25%) | `{recommendation, confidence, reasons}` |
| **Explainability Agent** | Generates ECOA adverse action codes + audit narrative | `{plain_language_summary, adverse_action_codes, audit_narrative}` |

**Recommendations:** `APPROVE` · `MANUAL_REVIEW` · `DECLINE`

---

## Kafka Topics

| Topic | Producer | Consumer |
|---|---|---|
| `application.received` | Decision API | AI Orchestrator |
| `application.dlq` | AI Orchestrator | Ops / manual replay |
| `recommendation.generated` | AI Orchestrator | Downstream notification |
| `manual.review.required` | AI Orchestrator | Underwriting UI |

---

## API Reference

### Decision API — `localhost:8080`

#### Submit application
```
POST /api/v1/applications
Content-Type: application/json

{
  "name": "Jane Doe",
  "creditScore": 710,        // 300–850 (FICO)
  "utilization": 85.0,       // 0–100 (%)
  "addressMismatch": true,   // optional
  "delinquencies": 1,        // optional
  "annualIncome": 65000,     // optional
  "channel": "WEB"           // WEB | MOBILE | BRANCH | PARTNER
}
```

Response `202 Accepted`:
```json
{
  "correlationId": "APP-1716345678901-A3F9C2D1",
  "status": "RECEIVED",
  "message": "Application accepted for AI decisioning.",
  "receivedAt": "2026-05-23T..."
}
```

#### Health
```
GET /actuator/health
GET /actuator/prometheus
```

---

### AI Orchestrator — `localhost:8001`

#### Health (includes Ollama model status)
```
GET /health
```

#### Pending review queue
```
GET /api/v1/review-queue
```

#### Submit underwriter decision
```
POST /api/v1/review/{correlationId}/decision
Content-Type: application/json

{
  "decision": "APPROVE",
  "reviewer": "underwriter-01",
  "notes": "Address verified via ID document"
}
```

#### Full audit trail
```
GET /api/v1/audit/{correlationId}
```

---

## Sample Flow

**Input** (borderline application):
```json
{ "creditScore": 680, "utilization": 83, "addressMismatch": true }
```

**Agent outputs:**
```
credit_agent  →  riskLevel=MEDIUM  (utilization borderline)
fraud_agent   →  fraudRisk=MEDIUM  (address mismatch detected)
policy_rag    →  action=MANUAL_REVIEW
               rules=["Utilization >80% AND address mismatch MUST route to manual review"]
```

**Decision:**
```json
{
  "recommendation": "MANUAL_REVIEW",
  "confidence": 0.50,
  "reasons": [
    "Credit: High revolving utilization at 83%",
    "Fraud: Address mismatch detected",
    "Policy: Applications with utilization >80% and address mismatch must route to manual review"
  ]
}
```

**Adverse action codes generated:** `AA04` (utilization), `AA07` (address), `AA12` (policy threshold)

---

## Project Structure

```
.
├── decision-api/               Spring Boot intake API
│   ├── src/main/java/...
│   │   ├── controller/         REST endpoints
│   │   ├── service/            Business logic + correlationId generation
│   │   ├── kafka/              Async Kafka producer
│   │   ├── model/              Request / Response / Event DTOs
│   │   ├── config/             Kafka producer + topic configuration
│   │   └── exception/          Global error handler
│   └── pom.xml
│
├── ai-orchestrator/            Python AI Orchestrator
│   ├── agents/                 5 LangGraph agent nodes
│   ├── graph/                  StateGraph workflow definition
│   ├── messaging/              Kafka consumer + DLQ producer
│   ├── models/                 Pydantic event schemas
│   ├── rag/                    Ingestion pipeline + Qdrant retriever
│   ├── llm_provider.py         Ollama LLM + embeddings factory
│   ├── config.py               Environment configuration
│   ├── main.py                 FastAPI app + HITL endpoints
│   └── requirements.txt
│
├── policy-documents/           Policy text files for RAG ingestion
│   ├── underwriting_policy.txt
│   ├── fraud_policy.txt
│   └── escalation_guidelines.txt
│
├── docker-compose.yml          Infrastructure services
├── GETTING_STARTED.md          Setup and run instructions
└── README.md                   This file
```

---

## Key Design Decisions

**`202 Accepted` not `200 OK`** — The credit decision is asynchronous. Returning 200 would imply the decision is complete. The caller tracks status via `correlationId`.

**`correlationId` as Kafka message key** — Guarantees all events for the same application land on the same partition (ordering guarantee). Format: `APP-{timestamp}-{8char}`.

**Deterministic risk synthesis** — The Risk Decision Agent uses a weighted formula (not a 5th LLM call). Regulated systems need reproducible, auditable logic — a formula satisfies regulators; an LLM output does not.

**RAG over fine-tuning** — Policy documents change frequently. Re-ingestion into Qdrant takes minutes; re-training takes days. RAG also provides inline citations — auditable evidence for every policy claim.

**Human-in-loop mandatory** — AI recommends, humans decide. Under ECOA/Reg B, adverse action notices must state specific reasons. The explainability agent generates ECOA-compliant codes (AA01–AA12).

**Fail-safe defaults** — Any agent error returns HIGH risk → MANUAL_REVIEW. The system never auto-approves on missing signal.

**`messaging/` not `kafka/`** — The package is named `messaging` to avoid shadowing the `kafka-python-ng` library in Python's module resolution.

---

## Performance Notes

Agents run sequentially on CPU with a local Llama 3 8B model. Typical latency per agent on CPU is 30–90 seconds. Total pipeline time is approximately 3–6 minutes on a 16 GB RAM machine without a GPU.

To improve inference speed:

| Option | Change | Speed gain |
|---|---|---|
| Smaller model | `OLLAMA_MODEL=phi3` in `.env` | 3–4× faster |
| NVIDIA GPU | Install CUDA drivers; Ollama auto-detects | 20–30× faster |
| Groq API | `pip install langchain-groq`, swap `llm_provider.py` | 50–100× faster |

---

## Requirements

- Docker Desktop (running)
- JDK 21
- Maven 3.9+
- Python 3.11+
- Ollama with `llama3:latest` and `nomic-embed-text` pulled
- 8 GB RAM minimum · 16 GB recommended

See [GETTING_STARTED.md](GETTING_STARTED.md) for full setup instructions.

---

## License

For educational and portfolio purposes.
