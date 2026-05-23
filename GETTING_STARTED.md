# AI Credit Card Decisioning POC — Getting Started

> **Stack:** Java 21 · Spring Boot 3.2 · Python 3.11 · FastAPI · LangGraph · Apache Kafka · Qdrant · Ollama (Llama 3)  
> **Platform:** Windows 10/11 with Git Bash · Docker Desktop  
> **Purpose:** Production-grade Agentic AI POC for fintech credit card decisioning

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Project Structure](#2-project-structure)
3. [First-Time Setup](#3-first-time-setup)
4. [Running the POC](#4-running-the-poc)
5. [End-to-End Verification](#5-end-to-end-verification)
6. [Troubleshooting](#6-troubleshooting)
7. [Quick Reference](#7-quick-reference)

---

## 1. Prerequisites

### 1.1 Required tools

Install these once before starting.

| Tool | Minimum Version | Download |
|------|----------------|----------|
| JDK | 21 LTS | https://adoptium.net |
| Maven | 3.9+ | https://maven.apache.org/download.cgi |
| Python | 3.11+ | https://www.python.org/downloads |
| Docker Desktop | 24+ | https://www.docker.com/products/docker-desktop |
| Git | 2.x | https://git-scm.com/download/win |
| Ollama | Latest | https://ollama.com/download/windows |

### 1.2 Verify installations

Open **Git Bash** and run:

```bash
java -version          # openjdk 21
mvn -version           # Apache Maven 3.9+
python --version       # Python 3.11+
docker --version       # Docker 24+
git --version          # git 2.x
```

### 1.3 Configure JAVA_HOME

Add to `~/.bashrc`:

```bash
export JAVA_HOME="C:/Program Files/Eclipse Adoptium/jdk-21.x.x-hotspot"
export PATH="$JAVA_HOME/bin:$PATH"
```

Apply:

```bash
source ~/.bashrc
java -version    # verify
```

### 1.4 Pull Ollama models

Ollama installs as a Windows background service. After installation:

```bash
# LLM for agent reasoning — ~4.7 GB
ollama pull llama3:latest

# Embedding model for RAG — ~274 MB
ollama pull nomic-embed-text

# Verify
ollama list
# NAME                     SIZE
# llama3:latest            4.7 GB
# nomic-embed-text:latest  274 MB
```

**Low RAM alternative** — if your machine has less than 16 GB RAM:

```bash
ollama pull phi3          # 2.3 GB, runs on 8 GB RAM
# Set in .env: OLLAMA_MODEL=phi3
```

---

## 2. Project Structure

```
<project-root>/
│
├── decision-api/                      # Spring Boot intake API (Java 21)
│   ├── src/
│   │   ├── main/java/com/citi/creditdecision/
│   │   │   ├── DecisionApiApplication.java
│   │   │   ├── controller/ApplicationController.java
│   │   │   ├── service/ApplicationService.java
│   │   │   ├── kafka/ApplicationEventProducer.java
│   │   │   ├── model/
│   │   │   │   ├── ApplicationRequest.java
│   │   │   │   ├── ApplicationResponse.java
│   │   │   │   └── ApplicationReceivedEvent.java
│   │   │   ├── config/
│   │   │   │   ├── KafkaProducerConfig.java
│   │   │   │   └── KafkaTopicConfig.java
│   │   │   └── exception/GlobalExceptionHandler.java
│   │   ├── main/resources/application.yml
│   │   └── test/java/com/citi/creditdecision/
│   │       ├── controller/ApplicationControllerTest.java
│   │       └── service/ApplicationServiceTest.java
│   ├── pom.xml
│   └── Dockerfile
│
├── ai-orchestrator/                   # Python AI Orchestrator (FastAPI + LangGraph)
│   ├── agents/
│   │   ├── state.py                   # LangGraph GraphState TypedDict
│   │   ├── credit_agent.py            # Credit risk analysis
│   │   ├── fraud_agent.py             # Fraud signal analysis
│   │   ├── policy_rag_agent.py        # RAG-grounded policy retrieval
│   │   ├── risk_decision_agent.py     # Deterministic weighted synthesis
│   │   └── explainability_agent.py   # ECOA adverse action codes + audit
│   ├── graph/
│   │   └── workflow.py                # LangGraph StateGraph definition
│   ├── messaging/                     # Kafka consumer/producer
│   │   ├── consumer.py
│   │   └── dlq_producer.py
│   ├── models/
│   │   └── events.py                  # Pydantic models matching Java schemas
│   ├── rag/
│   │   ├── ingest.py                  # Policy document ingestion pipeline
│   │   └── retriever.py               # Qdrant semantic search
│   ├── config.py                      # Pydantic Settings from .env
│   ├── llm_provider.py                # Ollama LLM + embeddings factory
│   ├── main.py                        # FastAPI app + HITL endpoints
│   ├── ingest_policies.py             # Top-level ingestion runner
│   ├── start.py                       # Top-level uvicorn runner
│   ├── pyproject.toml
│   ├── requirements.txt
│   └── .env.example                   # Template — copy to .env
│
├── policy-documents/                  # Policy text files for RAG
│   ├── underwriting_policy.txt
│   ├── fraud_policy.txt
│   └── escalation_guidelines.txt
│
├── docker-compose.yml                 # Infrastructure services
├── .gitignore
└── GETTING_STARTED.md                 # This file
```

---

## 3. First-Time Setup

Run these steps once after cloning or creating the project.

### Step 3.1 — Create the .env file

```bash
cd ai-orchestrator
cp .env.example .env
```

Open `.env` and set your values:

```ini
# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_GROUP_ID=ai-orchestrator-group
KAFKA_TOPIC_APPLICATION_RECEIVED=application.received
KAFKA_TOPIC_DLQ=application.dlq
KAFKA_TOPIC_MANUAL_REVIEW=manual.review.required
KAFKA_TOPIC_DECISION_COMPLETED=decision.completed

# Ollama — local LLM, no API key needed
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3:latest
OLLAMA_EMBED_MODEL=nomic-embed-text

# Qdrant — local vector database
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=policy_docs

# Policy documents path (relative to ai-orchestrator/)
POLICY_DOCS_PATH=../policy-documents
```

> `.env` is in `.gitignore` and will never be committed. Only `.env.example` goes into version control.

```bash
cd ..
```

### Step 3.2 — Set up Python virtual environment

```bash
cd ai-orchestrator

# Create virtualenv
python -m venv venv

# Activate
source venv/Scripts/activate       # Git Bash on Windows
# .\venv\Scripts\activate          # PowerShell alternative

# Confirm activation — prompt must show (venv)
which python
# Must point to: .../ai-orchestrator/venv/Scripts/python

# Install all dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Install project as editable package (prevents ModuleNotFoundError)
pip install -e .

# Verify
python -c "import qdrant_client, structlog, langchain, langgraph, fastapi, kafka; print('All packages OK')"

cd ..
```

### Step 3.3 — Build the Spring Boot API

```bash
cd decision-api
mvn clean package -DskipTests
# Expected: BUILD SUCCESS
cd ..
```

### Step 3.4 — Create policy documents

```bash
mkdir -p policy-documents

cat > policy-documents/underwriting_policy.txt << 'EOF'
UNDERWRITING POLICY — CREDIT CARD DECISIONING v1.0

1. CREDIT SCORE THRESHOLDS
   1.1 Applications with a credit score below 580 result in automatic decline.
   1.2 Applications with a credit score between 580 and 669 require enhanced review.
   1.3 Applications with a credit score of 670 or above may proceed to standard evaluation.
   1.4 Applications with a credit score of 740 or above qualify for expedited approval.

2. REVOLVING UTILIZATION
   2.1 Applications with revolving utilization above 80% must route to manual review.
   2.2 Applications with revolving utilization above 80% AND address mismatch MUST route to manual review without exception.
   2.3 Utilization between 50% and 80% requires additional income verification.
   2.4 Utilization below 30% is considered low risk.

3. DELINQUENCY HISTORY
   3.1 Three or more delinquencies in the past 24 months result in automatic decline.
   3.2 One or two delinquencies require manual review and supervisor sign-off.
   3.3 No delinquencies in the past 24 months is considered satisfactory.

4. COMBINED RISK TRIGGERS
   4.1 Any two HIGH risk signals across credit, fraud, and address verification require mandatory manual review.
   4.2 All three HIGH risk signals result in automatic decline.
EOF

cat > policy-documents/fraud_policy.txt << 'EOF'
FRAUD PREVENTION POLICY — CREDIT CARD APPLICATIONS v1.0

1. ADDRESS VERIFICATION
   1.1 Address mismatch between application and bureau records is a fraud indicator.
   1.2 Address mismatch alone triggers MEDIUM fraud risk and requires verification.
   1.3 Address mismatch combined with any other fraud indicator triggers HIGH fraud risk.
   1.4 Applications with HIGH fraud risk must not be auto-approved under any circumstances.

2. VELOCITY CHECKS
   2.1 More than three applications from the same device within 24 hours triggers HIGH fraud risk.
   2.2 More than two applications from the same IP address within one hour triggers review.

3. CHANNEL RISK
   3.1 Applications from PARTNER channel require additional identity verification.
   3.2 Applications from MOBILE channel with address mismatch require step-up authentication.

4. ESCALATION
   4.1 Any application flagged HIGH fraud risk must be reviewed by the fraud operations team.
   4.2 Fraud operations team has 4 business hours to complete review under SLA.
EOF

cat > policy-documents/escalation_guidelines.txt << 'EOF'
ESCALATION AND MANUAL REVIEW GUIDELINES v1.0

1. MANUAL REVIEW TRIGGERS
   1.1 AI recommendation of MANUAL_REVIEW with confidence below 0.75.
   1.2 Revolving utilization above 80% with address mismatch present.
   1.3 Credit score between 580 and 620 regardless of other signals.
   1.4 One or two delinquencies in the past 24 months.

2. SLA REQUIREMENTS
   2.1 Standard manual review must be completed within 2 business days.
   2.2 Expedited review must be completed within 4 business hours.

3. ADVERSE ACTION CODES
   AA01 — Credit score below minimum threshold
   AA04 — Revolving credit utilization too high
   AA07 — Address verification failed
   AA09 — Recent delinquencies on credit report
   AA12 — Application does not meet policy criteria
EOF

echo "Policy documents created"
```

---

## 4. Running the POC

Start services in this order every session. Each service runs in its own terminal window.

### Step 4.1 — Start Docker Desktop

Open Docker Desktop from the Start menu. Wait until the whale icon in the system tray stops animating (~30 seconds).

### Step 4.2 — Start infrastructure (Terminal 1)

```bash
cd <project-root>

docker-compose up -d

# Wait 15 seconds for Kafka to elect a leader, then verify
docker-compose ps
```

All four containers must show `Up` or `running`:

```
NAME              STATUS
poc-zookeeper     Up
poc-kafka         Up
poc-kafka-ui      Up
poc-qdrant        Up
```

Verify Qdrant is ready:

```bash
curl http://localhost:6333/health
# Expected: {"title":"qdrant - vector search engine","version":"..."}
```

### Step 4.3 — Verify Ollama is running

```bash
curl http://localhost:11434/api/tags
# Expected: shows llama3:latest and nomic-embed-text:latest
```

If Ollama is not responding, open it from the Start menu.

### Step 4.4 — Ingest policy documents (Terminal 1)

> Run only on first start, after `docker-compose down` (Qdrant data cleared),
> or when policy files are updated.

```bash
cd ai-orchestrator
source venv/Scripts/activate

python ingest_policies.py
```

Expected output:

```
[info] Initialising Ollama Embeddings  model=nomic-embed-text
[info] Created Qdrant collection       name=policy_docs
[info] Chunked document  file=underwriting_policy.txt  chunks=12
[info] Chunked document  file=fraud_policy.txt         chunks=8
[info] Chunked document  file=escalation_guidelines.txt chunks=9

✓ Ingested 29 chunks from 3 files into 'policy_docs'
```

### Step 4.5 — Start Spring Boot API (Terminal 2 — new window)

```bash
cd <project-root>/decision-api
mvn spring-boot:run
```

Wait for:

```
Started DecisionApiApplication in X.XXX seconds
```

Verify:

```bash
curl http://localhost:8080/actuator/health
# Expected: {"status":"UP",...}
```

### Step 4.6 — Start AI Orchestrator (Terminal 3 — new window)

```bash
cd <project-root>/ai-orchestrator
source venv/Scripts/activate
uvicorn main:app --reload --port 8001
```

Wait for all of these lines:

```
INFO:  Uvicorn running on http://127.0.0.1:8001
[info] Ollama ready          model=llama3:latest  embed_model=nomic-embed-text
[info] Kafka consumer thread started
[info] Kafka consumer started  topic=application.received
[info] LangGraph workflow ready
```

> **`Invalid file descriptor: -1`** — harmless Windows warning from the Kafka
> client on startup. The consumer recovers automatically.

Verify:

```bash
curl http://localhost:8001/health
# Expected: {"status":"ok","ollama":{"status":"ok","llm_ready":true,"embed_ready":true}}
```

### Service URLs

| Service | URL |
|---------|-----|
| Decision API | http://localhost:8080 |
| AI Orchestrator | http://localhost:8001 |
| Kafka UI | http://localhost:8090 |
| Qdrant Dashboard | http://localhost:6333/dashboard |
| Actuator Metrics | http://localhost:8080/actuator/prometheus |
| Orchestrator Metrics | http://localhost:8001/metrics |

---

## 5. End-to-End Verification

Run after every startup to confirm the full pipeline is working.

### Test 1 — Good application (expect APPROVE)

```bash
curl -s -X POST http://localhost:8080/api/v1/applications \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Good Applicant",
    "creditScore": 780,
    "utilization": 22,
    "addressMismatch": false,
    "channel": "WEB"
  }' | python -m json.tool
```

Expected response (202 Accepted):

```json
{
  "correlationId": "APP-1234567890123-ABCD1234",
  "status": "RECEIVED",
  "message": "Application accepted for AI decisioning. Track status using the correlationId.",
  "receivedAt": "2026-..."
}
```

Watch **Terminal 3** — after ~2-5 minutes (CPU inference time):

```
[info] credit_agent complete    riskLevel=LOW
[info] fraud_agent complete     fraudRisk=LOW
[info] policy_rag_agent complete action=APPROVE
[info] risk_decision complete   recommendation=APPROVE  confidence=0.78
[info] Workflow complete
```

### Test 2 — Borderline application (expect MANUAL_REVIEW)

```bash
curl -s -X POST http://localhost:8080/api/v1/applications \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Borderline Applicant",
    "creditScore": 680,
    "utilization": 83,
    "addressMismatch": true,
    "channel": "WEB"
  }' | python -m json.tool
```

Save the `correlationId` from the response. Watch Terminal 3:

```
[info] risk_decision complete   recommendation=MANUAL_REVIEW
[info] explainability complete  adverse_codes=['AA04', 'AA07', 'AA12']
```

### Test 3 — Human-in-loop review

```bash
# Check the review queue
curl -s http://localhost:8001/api/v1/review-queue | python -m json.tool

# Submit underwriter decision (replace CORR_ID with your correlationId)
curl -s -X POST http://localhost:8001/api/v1/review/CORR_ID/decision \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "APPROVE",
    "reviewer": "underwriter-01",
    "notes": "Address verified via ID document"
  }' | python -m json.tool
```

### Test 4 — Audit trail

```bash
curl -s http://localhost:8001/api/v1/audit/CORR_ID | python -m json.tool
```

Expected: full JSON record with `credit_result`, `fraud_result`, `policy_context`,
`risk_decision`, `explanation`, `human_decision`, `reviewer`, `decided_at`.

### Test 5 — Validation rejection (expect 400)

```bash
curl -s -X POST http://localhost:8080/api/v1/applications \
  -H "Content-Type: application/json" \
  -d '{"name": "", "creditScore": 9999, "utilization": 150}' \
  | python -m json.tool
```

Expected (400 Bad Request):

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

### Test 6 — Kafka event inspection

Open http://localhost:8090 in a browser:

1. Click **Topics** → `application.received`
2. Click **Messages** tab
3. Confirm your submitted applications appear with `correlationId` as the key

### Stop all services

```bash
# Stop Spring Boot: Ctrl+C in Terminal 2
# Stop Orchestrator: Ctrl+C in Terminal 3

# Stop Docker infrastructure
docker-compose down
```

---

## 6. Troubleshooting

### T-01: `ModuleNotFoundError: No module named 'rag'`

```bash
cd ai-orchestrator
pip install -e .
# Then use the wrapper: python ingest_policies.py
```

### T-02: Any `ModuleNotFoundError` for a pip package

```bash
cd ai-orchestrator
source venv/Scripts/activate
python -m pip install -r requirements.txt
```

### T-03: `No module named 'langchain.text_splitter'`

```bash
pip install langchain-text-splitters
```

In `rag/ingest.py` update the import:

```python
# Replace:
from langchain.text_splitter import RecursiveCharacterTextSplitter
# With:
from langchain_text_splitters import RecursiveCharacterTextSplitter
```

### T-04: LangChain dependency conflict on install

```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

Ensure `requirements.txt` uses `>=` (not `==`) for the LangChain family.

### T-05: `UnsatisfiedLinkError: libsnappyjava.so`

In `decision-api/src/.../config/KafkaProducerConfig.java`:

```java
// Change:
props.put(ProducerConfig.COMPRESSION_TYPE_CONFIG, "snappy");
// To:
props.put(ProducerConfig.COMPRESSION_TYPE_CONFIG, "none");
```

### T-06: `ImportError: cannot import name 'KafkaConsumer' from 'kafka'`

The local `kafka/` folder shadows the `kafka-python-ng` library.

```bash
mv ai-orchestrator/kafka ai-orchestrator/messaging
```

Update imports in `main.py` and `messaging/consumer.py`:

```python
# Change: from kafka.consumer import ...
# To:     from messaging.consumer import ...
```

### T-07: `No module named 'kafka.vendor.six.moves'`

```bash
pip uninstall kafka-python -y
pip install kafka-python-ng
```

### T-08: `OllamaEmbeddings` deprecation warning or ImportError

```bash
pip install langchain-ollama
```

In `llm_provider.py`:

```python
# Replace:
from langchain_community.llms import Ollama
from langchain_community.embeddings import OllamaEmbeddings
# With:
from langchain_ollama import OllamaLLM, OllamaEmbeddings
```

### T-09: `ConnectError` / `Connection refused` on Qdrant

```bash
docker-compose up -d qdrant
curl http://localhost:6333/health    # wait until this returns ok
```

### T-10: `model "nomic-embed-text" not found`

```bash
ollama pull nomic-embed-text
ollama list    # verify it appears
```

### T-11: `model 'llama3.1' not found`

```bash
ollama list    # check exact name (may be llama3:latest not llama3.1)
# Update .env: OLLAMA_MODEL=llama3:latest
```

### T-12: `QdrantClient has no attribute 'search'`

`search()` was removed in qdrant-client 1.10+. In `rag/retriever.py`:

```python
# Replace:
results = self.client.search(collection_name=..., query_vector=..., limit=k)
# With:
results = self.client.query_points(collection_name=..., query=..., limit=k).points
```

### T-13: `CommitFailedError: group has already rebalanced`

In `messaging/consumer.py`, add to `KafkaConsumer` constructor:

```python
max_poll_interval_ms=1200000,   # 20 minutes — accommodates slow CPU LLM inference
max_poll_records=1,
heartbeat_interval_ms=10000,
session_timeout_ms=60000,
```

### T-14: `UnsupportedCodecError: Libraries for lz4 not found`

```bash
pip install lz4
# Or change compression in KafkaProducerConfig.java to "none"
```

### T-15: `Invalid file descriptor: -1`

Harmless Windows warning from the Kafka client on startup. No action needed.

---

## 7. Quick Reference

### Startup sequence

```bash
# Terminal 1 — infrastructure
docker-compose up -d && sleep 15

# Ingest (first run or after docker-compose down)
cd ai-orchestrator && source venv/Scripts/activate
python ingest_policies.py && cd ..

# Terminal 2 — Spring Boot
cd decision-api && mvn spring-boot:run

# Terminal 3 — AI Orchestrator
cd ai-orchestrator && source venv/Scripts/activate
uvicorn main:app --reload --port 8001
```

### Test commands

```bash
# Submit application
curl -s -X POST http://localhost:8080/api/v1/applications \
  -H "Content-Type: application/json" \
  -d '{"name":"Test","creditScore":680,"utilization":83,"addressMismatch":true}' \
  | python -m json.tool

# Review queue
curl -s http://localhost:8001/api/v1/review-queue | python -m json.tool

# Submit decision
curl -s -X POST http://localhost:8001/api/v1/review/<CORR_ID>/decision \
  -H "Content-Type: application/json" \
  -d '{"decision":"APPROVE","reviewer":"underwriter-01","notes":"Verified"}' \
  | python -m json.tool

# Audit trail
curl -s http://localhost:8001/api/v1/audit/<CORR_ID> | python -m json.tool
```

### Shutdown

```bash
# Ctrl+C in Terminals 2 and 3, then:
docker-compose down
```
