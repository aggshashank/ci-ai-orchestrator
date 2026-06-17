# Deployment — AWS

This guide covers deploying the AI Decisioning Platform to AWS using ECS Fargate, MSK (Kafka), RDS PostgreSQL, and Amazon Bedrock (optional LLM swap).

## Architecture on AWS

```
Internet → ALB → ECS Fargate (ai-orchestrator)
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
         Amazon MSK   RDS Aurora  OpenSearch / Qdrant
         (Kafka)      (Postgres)  (vector store)
```

## Prerequisites

- AWS CLI configured (`aws configure`)
- Docker installed
- Terraform (optional — manual steps are shown)

## 1. Push images to ECR

```bash
# Authenticate
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin 123456789.dkr.ecr.us-east-1.amazonaws.com

# Build + push ai-orchestrator
docker build -t ai-orchestrator ./ai-orchestrator
docker tag ai-orchestrator:latest 123456789.dkr.ecr.us-east-1.amazonaws.com/ai-orchestrator:latest
docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/ai-orchestrator:latest
```

Repeat for `dashboard` and `decision-api`.

## 2. RDS PostgreSQL

```bash
aws rds create-db-instance \
  --db-instance-identifier decisioning-db \
  --db-instance-class db.t3.medium \
  --engine postgres \
  --master-username postgres \
  --master-user-password <password> \
  --allocated-storage 20 \
  --vpc-security-group-ids sg-xxx \
  --db-name decisioning
```

Set `DATABASE_URL=postgresql+asyncpg://postgres:<password>@<endpoint>/decisioning` in ECS task environment variables.

## 3. Amazon MSK

Create an MSK cluster with 3 brokers (kafka 3.6). Note the bootstrap server endpoints and set `KAFKA_BOOTSTRAP_SERVERS`.

MSK uses IAM authentication by default — configure the Kafka client with SASL/IAM:

```python
# in config.py — set these via environment
kafka_security_protocol: str = "SASL_SSL"
kafka_sasl_mechanism: str = "AWS_MSK_IAM"
```

## 4. LLM — Amazon Bedrock (optional)

To replace Ollama with Bedrock (Claude Haiku for speed, Claude Sonnet for quality):

```bash
pip install langchain-aws
```

In `llm/factory.py`:
```python
from langchain_aws import ChatBedrock

def get_llm():
    return ChatBedrock(model_id="anthropic.claude-haiku-4-5-20251001-v1:0", region_name="us-east-1")
```

Remove the `OLLAMA_*` environment variables and set `AWS_REGION`.

## 5. ECS Task Definition

Key environment variables:
```
DATABASE_URL=postgresql+asyncpg://...
KAFKA_BOOTSTRAP_SERVERS=b-1.msk-cluster....amazonaws.com:9096,...
QDRANT_URL=http://qdrant.internal:6333
ACTIVE_STRATEGY_VERSION=v1.0.0
LLM_CACHE_ENABLED=true
```

CPU: 1024 (1 vCPU), Memory: 2048 MB minimum. Scale horizontally — the orchestrator is stateless.

## 6. Application Load Balancer

Create an ALB with:
- HTTP → 8001 for `ai-orchestrator`
- HTTP → 3000 for `dashboard`
- HTTP → 8080 for `decision-api`

Enable HTTPS with ACM certificates for production.

## 7. Run migrations

```bash
aws ecs run-task --cluster decisioning --task-definition ai-orchestrator-migrate \
  --overrides '{"containerOverrides":[{"name":"ai-orchestrator","command":["alembic","upgrade","head"]}]}'
```

## Cost estimate (us-east-1, light load)

| Service | ~Cost/month |
|---|---|
| RDS t3.medium | $55 |
| MSK (3 × kafka.t3.small) | $120 |
| ECS Fargate (1 vCPU × 3 tasks) | $60 |
| ALB | $20 |
| **Total** | **~$255** |
